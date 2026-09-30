"""Run flare detection over the whole processed store.

- Per instrument: detect independently on each detector, then merge detections
  across detectors (same physical flare seen by SDD1+SDD2 / CDTE+CZT units).
- Outputs: CATALOGS/events_{instrument}.parquet (+ csv)
- Then builds the master catalog: cross_match(soft, hard) -> master_catalog.parquet
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .catalog.master import cross_match, events_to_df, save_master
from .config import CATALOGS, HEL1OS_WORKING_DT_S
from .detect.detector import detect_flares
from .store import available_days, read_series


def _merge_detector_events(dfs: list[pd.DataFrame], merge_gap_s: float = 300.0) -> pd.DataFrame:
    """Union detections from multiple detectors, collapsing coincident events."""
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True).sort_values("start_unix").reset_index(drop=True)
    merged_rows: list[dict] = []
    for row in df.to_dict("records"):
        if merged_rows and row["start_unix"] - merged_rows[-1]["end_unix"] <= merge_gap_s:
            last = merged_rows[-1]
            take_new_peak = row["peak_cps"] > last["peak_cps"]
            merged_rows[-1] = dict(
                start_unix=min(last["start_unix"], row["start_unix"]),
                peak_unix=row["peak_unix"] if take_new_peak else last["peak_unix"],
                end_unix=max(last["end_unix"], row["end_unix"]),
                peak_cps=max(last["peak_cps"], row["peak_cps"]),
                background_cps=min(last["background_cps"], row["background_cps"]),
                excess_sigma=max(last["excess_sigma"], row["excess_sigma"]),
                duration_s=max(last["end_unix"], row["end_unix"])
                - min(last["start_unix"], row["start_unix"]),
                rise_s=(row["peak_unix"] if take_new_peak else last["peak_unix"])
                - min(last["start_unix"], row["start_unix"]),
                decay_s=max(last["end_unix"], row["end_unix"])
                - (row["peak_unix"] if take_new_peak else last["peak_unix"]),
                detector=last["detector"] if not take_new_peak else row["detector"],
                instrument=last["instrument"],
            )
        else:
            merged_rows.append(dict(row))
    return pd.DataFrame(merged_rows)


def detect_instrument(instrument: str, detectors: list[str],
                      params: dict | None = None) -> pd.DataFrame:
    if instrument == "hel1os":
        params = {"working_dt_s": HEL1OS_WORKING_DT_S, **(params or {})}
    per_det_dfs = []
    for det in detectors:
        days = available_days(instrument, det)
        if not days:
            continue
        df = read_series(instrument, det, days)
        df = df.sort_values("ts").reset_index(drop=True)
        t = (df.ts - pd.Timestamp("1970-01-01")).dt.total_seconds().to_numpy()
        y = df.rate_cps.to_numpy()
        g = df.is_good.to_numpy()
        # split into contiguous segments so day boundaries don't smear the background
        gaps = np.where(np.diff(t) > max(120.0, 3 * (params or {}).get("working_dt_s", 1.0) or 120.0))[0]
        seg_bounds = np.split(np.arange(len(t)), gaps + 1)
        for seg in seg_bounds:
            if len(seg) < 600:
                continue
            ev = detect_flares(t[seg], y[seg], g[seg], params)
            per_det_dfs.append(events_to_df(ev, det, instrument))
    return _merge_detector_events(per_det_dfs)


def run_all() -> dict[str, pd.DataFrame]:
    results = {}
    soft = detect_instrument("solexs", ["SDD1", "SDD2"])
    soft.to_parquet(CATALOGS / "events_solexs.parquet", index=False)
    soft.to_csv(CATALOGS / "events_solexs.csv", index=False)
    hard = detect_instrument("hel1os", ["CDTE1", "CDTE2", "CZT1", "CZT2"])
    hard.to_parquet(CATALOGS / "events_hel1os.parquet", index=False)
    hard.to_csv(CATALOGS / "events_hel1os.csv", index=False)
    master = cross_match(soft, hard)
    save_master(master)
    results["solexs"] = soft
    results["hel1os"] = hard
    results["master"] = master
    return results


if __name__ == "__main__":  # pragma: no cover
    res = run_all()
    print("SoLEXS events:", len(res["solexs"]))
    print("HEL1OS events:", len(res["hel1os"]))
    print("Master catalog:", len(res["master"]))
    print(res["master"].head(20).to_string())
