"""FastAPI service exposing the flare pipeline to the React dashboard.

Endpoints:
    GET /api/coverage              -> available days per instrument/detector
    GET /api/lightcurve            -> binned time series for charting
    GET /api/flares                -> master catalog (filters: from, to, cls)
    GET /api/summary               -> headline stats for the header bar
    GET /api/forecast              -> per-timestamp forecast probabilities
    GET /api/events/{window}       -> events overlapping [from, to]
    WS  /ws/replay                 -> accelerated replay of a day through the
                                      live detector, emitting nowcast alerts
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.pipeline.catalog.master import load_master
from backend.pipeline.config import CATALOGS, DETECT, GOES_DIR, MERGED_DIR
from backend.pipeline.detect.detector import detect_flares
from backend.pipeline.detect.timeseries import resample_uniform
from backend.pipeline.store import available_days, read_series

app = FastAPI(title="Aditya-L1 Flare Watch — Solar-Flare Nowcasting (Minor Project)")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_TS0 = pd.Timestamp("1970-01-01")


def _to_unix(s: pd.Series) -> np.ndarray:
    return (pd.to_datetime(s) - _TS0).dt.total_seconds().to_numpy()


def _parse_range(from_: str | None, to: str | None) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Date-only `to` is inclusive (end of that day)."""
    f = pd.Timestamp(from_) if from_ else None
    t = None
    if to:
        t = pd.Timestamp(to)
        if t == t.normalize() and "T" not in to and ":" not in to:
            t = t + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    return f, t


@app.get("/api/coverage")
def coverage() -> dict:
    out = {}
    for inst, dets in (("solexs", ["SDD1", "SDD2"]),
                       ("hel1os", ["CDTE1", "CDTE2", "CZT1", "CZT2"])):
        out[inst] = {d: available_days(inst, d) for d in dets}
    master = load_master()
    out["master_count"] = len(master)
    return out


@app.get("/api/lightcurve")
def lightcurve(
    instrument: str = Query("solexs"),
    detector: str = Query("SDD2"),
    from_: str = Query(None, alias="from"),
    to: str = Query(None),
    bin_s: int = Query(60, ge=1, le=3600),
) -> dict:
    f, t = _parse_range(from_, to)
    days = None
    if f and t:
        d0, d1 = f.strftime("%Y%m%d"), t.strftime("%Y%m%d")
        all_days = available_days(instrument, detector)
        days = [d for d in all_days if d0 <= d <= d1]
    df = read_series(instrument, detector, days)
    if df.empty:
        return {"t": [], "rate": [], "good": []}
    df = df.sort_values("ts")
    if f:
        df = df[df.ts >= f]
    if t:
        df = df[df.ts <= t]
    if df.empty:
        return {"t": [], "rate": [], "good": []}
    t = _to_unix(df.ts)
    tb, rb = resample_uniform(t, df.rate_cps.to_numpy(), float(bin_s))
    gb = np.zeros(len(tb), dtype=int)
    if df.is_good.any():
        _, gb_f = resample_uniform(t, df.is_good.astype(float), float(bin_s))
        gb = (np.nan_to_num(gb_f) >= 0.5).astype(int)
    finite = np.isfinite(rb)
    return {
        "t": (tb[finite] * 1000).astype("int64").tolist(),  # ms for JS Date
        "rate": [None if not np.isfinite(v) else round(float(v), 3) for v in rb[finite]],
        "good": gb[finite].tolist(),
        "bin_s": bin_s,
        "instrument": instrument,
        "detector": detector,
    }


@app.get("/api/flares")
def flares(
    from_: str = Query(None, alias="from"),
    to: str = Query(None),
    cls: str = Query(None),
) -> dict:
    m = load_master()
    if m.empty:
        return {"flares": []}
    f, t = _parse_range(from_, to)
    if f:
        m = m[m.start >= f]
    if t:
        m = m[m.start <= t]
    if cls:
        m = m[m.class_proxy == cls]
    m = m.sort_values("start")
    recs = json.loads(m.to_json(orient="records", date_format="iso"))
    return {"flares": recs}


@app.get("/api/dataset")
def dataset() -> dict:
    """Merged-dataset deliverable info (built by export_merged.py)."""
    mp = MERGED_DIR / "manifest.json"
    if not mp.exists():
        return {"available": False,
                "note": "run: python -m backend.pipeline.export_merged"}
    man = json.loads(mp.read_text())
    files = man.get("files", {})
    prov = man.get("provenance", {})
    out = {
        "available": True,
        "generated_utc": man.get("generated_utc"),
        "files": {
            k: {
                "rows": v.get("rows"),
                "parquet_mb": v.get("parquet_mb"),
                "csv_mb": v.get("csv_mb"),
                "t_start": v.get("t_start"),
                "t_end": v.get("t_end"),
            } for k, v in files.items()
        },
        "solexs_days": sum(d.get("n_days", 0)
                           for d in prov.get("solexs", {}).get("detectors", {}).values()),
        "hel1os_days": sum(d.get("n_days", 0)
                           for d in prov.get("hel1os", {}).get("detectors", {}).values()),
        "raw_zips": man.get("raw_zips", {}),
    }
    mc = CATALOGS / "master_catalog.csv"
    out["master_catalog_csv"] = str(mc.relative_to(CATALOGS.parents[2])).replace("\\", "/") \
        if mc.exists() else None
    return out


@app.get("/api/dataset/download/{stem}")
def dataset_download(stem: str, fmt: str = Query("parquet")) -> FileResponse:
    """Download a merged-dataset deliverable (parquet or csv) or the manifest."""
    if stem == "manifest":
        p = MERGED_DIR / "manifest.json"
        if not p.exists():
            return JSONResponse({"error": "manifest not built"}, status_code=404)
        return FileResponse(p, filename="merged_dataset_manifest.json", media_type="application/json")
    if stem not in {"solexs_merged", "hel1os_merged", "merged_all_data"}:
        return JSONResponse({"error": f"unknown dataset '{stem}'"}, status_code=404)
    ext = "parquet" if fmt == "parquet" else "csv"
    p = MERGED_DIR / f"{stem}.{ext}"
    if not p.exists():
        return JSONResponse({"error": f"{p.name} not built"}, status_code=404)
    media = "application/octet-stream" if ext == "parquet" else "text/csv"
    return FileResponse(p, filename=p.name, media_type=media)


@app.get("/api/report/day")
def report_day(from_: str = Query(None, alias="from"), to: str = Query(None)) -> dict:
    """Exportable detection report for a day/range: events, metrics, provenance.

    Re-runs the detector over the requested window (capped at 31 days) and
    merges in calibrated classes from the master catalog.
    """
    import time as _time
    t_start = _time.time()
    f, t = _parse_range(from_, to)
    if not f or not t:
        return JSONResponse({"error": "provide from and to (YYYY-MM-DD)"}, status_code=400)
    if (t - f).days > 31:
        return JSONResponse({"error": "range capped at 31 days"}, status_code=400)
    d0, d1 = f.strftime("%Y%m%d"), t.strftime("%Y%m%d")
    days = [d for d in available_days("solexs", "SDD2") if d0 <= d <= d1]
    df = read_series("solexs", "SDD2", days)
    if df.empty:
        return JSONResponse({"error": "no data for window"}, status_code=404)
    tb, rb = resample_uniform(_to_unix(df.ts), df.rate_cps.to_numpy(), 10.0)
    good = np.isfinite(rb)
    events = detect_flares(tb[good], rb[good], None, DETECT)
    m = load_master()
    m_win = m[(m.start >= f) & (m.start <= t)] if len(m) else m
    cal = json.loads((GOES_DIR / "solexs_calibration.json").read_text()) if \
        (GOES_DIR / "solexs_calibration.json").exists() else {}
    classes = {}
    if len(m_win):
        classes = m_win.class_proxy.value_counts().to_dict()
    return JSONResponse(
        {
            "report": {
                "generated_utc": pd.Timestamp.utcnow().isoformat(),
                "pipeline": "Aditya-L1 Flare Watch nowcast v1.0 (SoLEXS SDD2, 10-s grid)",
                "window": {"from": str(f), "to": str(t), "days": len(days)},
                "events_detected": len(events),
                "events": [
                    {
                        "start": pd.Timestamp(e.start_unix, unit="s").isoformat(),
                        "peak": pd.Timestamp(e.peak_unix, unit="s").isoformat(),
                        "end": pd.Timestamp(e.end_unix, unit="s").isoformat(),
                        "peak_cps": round(float(e.peak_cps), 1),
                        "excess_sigma": round(float(e.excess_sigma), 1),
                        "duration_s": round(float(e.duration_s), 1),
                    }
                    for e in events
                ],
                "class_counts": classes,
                "catalog_events_in_window": len(m_win),
                "calibration": cal,
                "runtime_s": round(_time.time() - t_start, 2),
            }
        },
        headers={"Content-Disposition": 'attachment; filename="flare_detection_report.json"'},
    )


@app.get("/api/summary")
def summary() -> dict:
    m = load_master()
    rep_p = Path(CATALOGS.parent / "eda" / "eval_report.json")
    report = json.loads(rep_p.read_text()) if rep_p.exists() else {}
    cal_p = GOES_DIR / "solexs_calibration.json"
    cal = json.loads(cal_p.read_text()) if cal_p.exists() else {}
    hard_matched = int(m.hard_detected.sum()) if len(m) else 0
    leads = m.hard_lead_s.dropna() if len(m) else pd.Series(dtype=float)
    pos_leads = leads[leads > 0]
    return {
        "total_flares": len(m),
        "hard_matched": hard_matched,
        "median_hard_lead_s": float(pos_leads.median()) if len(pos_leads) else None,
        "class_counts": m.class_proxy.value_counts().to_dict() if len(m) else {},
        "eval": report,
        "calibration": cal,
    }


@app.get("/api/forecast")
def forecast(from_: str = Query(None, alias="from"), to: str = Query(None)) -> dict:
    p = CATALOGS / "forecast_series.parquet"
    if not p.exists():
        return {"t": [], "p": [], "note": "forecast model not trained yet"}
    f = pd.read_parquet(p)
    f_, t_ = _parse_range(from_, to)
    if f_:
        f = f[f.ts >= f_]
    if t_:
        f = f[f.ts <= t_]
    t_ms = ((f.ts - pd.Timestamp("1970-01-01")).dt.total_seconds() * 1000.0)
    return {"t": t_ms.astype("int64").tolist(), "p": f.p_flare.round(4).tolist()}


@app.websocket("/ws/replay")
async def replay(ws: WebSocket) -> None:
    """Stream a time window at accelerated speed through the live detector.

    Query: instrument, detector, from, to, speed (x real-time), bin_s
    Emits JSON: {type: 'points'|'alert', ...}
    """
    await ws.accept()
    try:
        params = dict(ws.query_params)
        instrument = params.get("instrument", "solexs")
        detector = params.get("detector", "SDD2")
        from_ = params.get("from")
        to = params.get("to")
        speed = float(params.get("speed", "600"))
        bin_s = int(params.get("bin_s", "10"))
        days = None
        if from_ and to:
            d0, d1 = pd.Timestamp(from_).strftime("%Y%m%d"), pd.Timestamp(to).strftime("%Y%m%d")
            days = [d for d in available_days(instrument, detector) if d0 <= d <= d1]
        df = read_series(instrument, detector, days).sort_values("ts")
        f, t = _parse_range(from_, to)
        if f:
            df = df[df.ts >= f]
        if t:
            df = df[df.ts <= t]
        if df.empty:
            await ws.send_json({"type": "error", "message": "no data for window"})
            await ws.close()
            return
        t = _to_unix(df.ts)
        tb, rb = resample_uniform(t, df.rate_cps.to_numpy(), float(bin_s))
        finite = np.isfinite(rb)
        tb, rb = tb[finite], rb[finite]
        if len(tb) == 0:
            await ws.send_json({"type": "error", "message": "no valid data in window"})
            await ws.close()
            return
        if len(tb) > 4_000_000:  # cap a replay at reasonable size
            tb, rb = tb[::2], rb[::2]
        await ws.send_json({"type": "meta", "n": len(tb), "bin_s": bin_s,
                            "t0": tb[0] * 1000, "t1": tb[-1] * 1000})
        # stream points in chunks; run the detector over the accumulated stream
        # every chunk_end so alerts fire live (as they would in real time)
        chunk = max(1, int(speed * 10))  # ~10 msgs/s of wall clock
        buf_t, buf_y = [], []
        i = 0
        last_flush = 0.0
        while i < len(tb):
            j = min(len(tb), i + chunk)
            buf_t.extend(tb[i:j].tolist())
            buf_y.extend(rb[i:j].tolist())
            await ws.send_json({"type": "points",
                                "t": (tb[i:j] * 1000).astype("int64").tolist(),
                                "rate": [round(float(v), 3) for v in rb[i:j]]})
            if tb[j - 1] - last_flush >= 900:  # re-detect each ~15 min of stream
                ev = detect_flares(np.array(buf_t), np.array(buf_y), None, DETECT)
                await ws.send_json({"type": "alerts", "events": [
                    {"start": e.start_unix * 1000, "peak": e.peak_unix * 1000,
                     "end": e.end_unix * 1000, "peak_cps": e.peak_cps,
                     "excess_sigma": round(e.excess_sigma, 1),
                     "duration_s": e.duration_s} for e in ev]})
                last_flush = tb[j - 1]
            i = j
            await asyncio.sleep(max(0.0, (chunk * bin_s) / speed / 20))
        await ws.send_json({"type": "done"})
    except WebSocketDisconnect:
        return
    except Exception as e:  # pragma: no cover
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
