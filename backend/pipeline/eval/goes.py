"""NOAA GOES XRS reference data: download, flare list, flux calibration.

- Download GOES-R series XRS 1-min averages (netCDF4, via xarray) for our windows.
  sci_xrsf-l2-avg1m per satellite day files on
  https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/
- From the 1-8 A channel build a reference flare list (same detector logic) ->
  ground truth for TPR / FAR evaluation.
- Calibrate SoLEXS peak counts -> GOES 1-8 A peak flux via log-log linear
  regression on matched events (SoLEXS detects near-soft-X-ray band).
"""
from __future__ import annotations

import io
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from ..config import CLASS_THRESHOLDS, GOES_DIR
from ..detect.detector import detect_flares

BASE_DIR = ("https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/"
            "goes/goes16/l2/data/xrsf-l2-avg1m_science/{year}/{month:02d}/")

_listing_cache: dict[str, list[str]] = {}


def _month_listing(year: int, month: int) -> list[str]:
    key = f"{year}-{month:02d}"
    if key in _listing_cache:
        return _listing_cache[key]
    import re
    import urllib.request
    url = BASE_DIR.format(year=year, month=month)
    try:
        html = urllib.request.urlopen(url, timeout=60).read().decode()
        files = re.findall(r'href="([^"]+\.nc)"', html)
    except Exception:
        files = []
    _listing_cache[key] = files
    return files


def _url_for(day: str) -> tuple[str | None, str]:
    d = pd.Timestamp(day)
    ymd = d.strftime("%Y%m%d")
    fname = f"g16_xrs_1m_{ymd}.nc"
    matches = [f for f in _month_listing(d.year, d.month) if f"_d{ymd}_" in f]
    if not matches:
        return None, fname
    f = sorted(matches)[-1]  # newest version
    return BASE_DIR.format(year=d.year, month=d.month) + f, fname


def download_days(days: list[str], max_workers: int = 8) -> pd.DataFrame:
    """Download missing day files; return the concatenated 1-min flux dataframe."""
    GOES_DIR.mkdir(parents=True, exist_ok=True)
    todo = []
    for day in days:
        _, fname = _url_for(day)
        if not (GOES_DIR / fname).exists():
            todo.append(day)
    def fetch(day):
        url, fname = _url_for(day)
        if url is None:
            print(f"[goes] no file listed for {day}")
            return None
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                (GOES_DIR / fname).write_bytes(r.read())
            return None
        except Exception as e:
            print(f"[goes] miss {day}: {type(e).__name__}")
            return None
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(fetch, d) for d in todo]
        for f in as_completed(futs):
            f.result()

    frames = []
    for f in sorted(GOES_DIR.glob("g16_xrs_1m_*.nc")):
        try:
            ds = xr.open_dataset(f)
            fb = ds["xrsb_flux"].to_series()  # 1-8 A channel (class-defining)
            fa = ds["xrsa_flux"].to_series()  # 0.5-4 A channel
            t = pd.to_datetime(fb.index).tz_localize(None)
            frames.append(pd.DataFrame({"ts": t.values,
                                        "flux_wm2": fb.values,
                                        "flux_a_wm2": fa.values}))
            ds.close()
        except Exception as e:
            print(f"[goes] parse fail {f.name}: {e}")
    if not frames:
        return pd.DataFrame(columns=["ts", "flux_wm2"])
    df = (pd.concat(frames).dropna(subset=["flux_wm2"])
            .drop_duplicates("ts").sort_values("ts").reset_index(drop=True))
    df.to_parquet(GOES_DIR / "goes16_xrs_1m.parquet", index=False)
    return df


def goes_reference_flares(gdf: pd.DataFrame) -> pd.DataFrame:
    """Detect flares on the GOES 1-8 A 1-min series with the same engine."""
    t = (gdf.ts - pd.Timestamp("1970-01-01")).dt.total_seconds().to_numpy()
    y = gdf.flux_wm2.to_numpy()
    y = pd.Series(y).interpolate(limit=10).to_numpy()
    params = {
        "working_dt_s": 60, "smooth_s": 180.0, "bg_window_s": 4 * 3600.0,
        "start_nsigma": 4.0, "start_sustain_s": 180.0, "min_duration_s": 120.0,
        "merge_gap_s": 600.0, "max_duration_s": 4 * 3600.0, "peak_pad_s": 300.0,
    }
    ev = detect_flares(t, flux_to_cps(y), good=None, params=params)
    if not ev:
        return pd.DataFrame(columns=["start", "peak", "end", "peak_flux", "class"])
    rows = []
    for e in ev:
        rows.append(dict(
            start=pd.to_datetime(e.start_unix, unit="s"),
            peak=pd.to_datetime(e.peak_unix, unit="s"),
            end=pd.to_datetime(e.end_unix, unit="s"),
            peak_flux=flux_from_cps(e.peak_cps),
            cls=class_for_flux(flux_from_cps(e.peak_cps)),
        ))
    return pd.DataFrame(rows)


def flux_to_cps(flux: np.ndarray) -> np.ndarray:
    """Scale flux so the shared detector can run on it (unit-safe transform)."""
    return np.asarray(flux, dtype=float) * 1e8


def flux_from_cps(v: float) -> float:
    return float(v) / 1e8


def class_for_flux(peak_flux_wm2: float) -> str:
    lg = np.log10(max(peak_flux_wm2, 1e-12))
    for thr, name in CLASS_THRESHOLDS:
        if lg >= thr:
            return name
    return "A"


def calibrate_solexs_to_flux(solexs_events: pd.DataFrame,
                             gdf: pd.DataFrame) -> dict:
    """Log-log regression SoLEXS peak counts -> GOES 1-8 A peak flux.

    For each SoLEXS event take the max GOES 1-8 A flux within [start-10m, end+10m];
    keep events with finite flux and peak_cps > 3x local background; regress.
    """
    if solexs_events.empty:
        return {}
    s = solexs_events.copy()
    s["match_flux"] = np.nan
    gt = (pd.to_datetime(gdf.ts) - pd.Timestamp("1970-01-01")).dt.total_seconds().to_numpy()
    gf = gdf.flux_wm2.to_numpy()
    for i, r in s.iterrows():
        m = (gt >= (r.start_unix - 600)) & (gt <= (r.end_unix + 600))
        if m.any():
            s.at[i, "match_flux"] = float(np.nanmax(gf[m]))
    ok = s[(s.match_flux > 0) & (s.peak_cps > 3 * s.background_cps)]
    if len(ok) < 10:
        return {"slope": np.nan, "intercept": np.nan, "n": len(ok)}
    x = np.log10(ok.peak_cps.to_numpy())
    yv = np.log10(ok.match_flux.to_numpy())
    slope, intercept = np.polyfit(x, yv, 1)
    resid = yv - (slope * x + intercept)
    return {
        "slope": float(slope), "intercept": float(intercept), "n": int(len(ok)),
        "scatter_dex": float(np.std(resid)), "fit": "log10(flux) = slope*log10(cps)+intercept",
    }


def apply_class_proxy(master: pd.DataFrame, cal: dict) -> pd.DataFrame:
    """Fill class_proxy in the master catalog from calibrated counts->flux."""
    if master.empty or not cal or not np.isfinite(cal.get("slope", np.nan)):
        return master
    lg_cps = np.log10(master.solexs_peak_cps.clip(lower=1e-3))
    lg_flux = cal["slope"] * lg_cps + cal["intercept"]
    master = master.copy()
    master["goes_flux_proxy"] = 10 ** lg_flux
    master["class_proxy"] = [class_for_flux(f) for f in master.goes_flux_proxy]
    return master


def save_reference(list_df: pd.DataFrame, cal: dict) -> None:
    list_df.to_parquet(GOES_DIR / "goes_reference_flares.parquet", index=False)
    list_df.to_csv(GOES_DIR / "goes_reference_flares.csv", index=False)
    (GOES_DIR / "solexs_calibration.json").write_text(json.dumps(cal, indent=2))
