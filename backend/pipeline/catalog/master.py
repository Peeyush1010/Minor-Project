"""Event catalogs: per-instrument lists + soft/hard cross-match -> master catalog.

The master catalog is the "automated database of nowcasted solar flares" outcome:
one row per flare with soft (SoLEXS) properties, hard (HEL1OS) properties when
observed, and combined classification.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config import CATALOGS

MASTER_COLUMNS = [
    "flare_id", "start", "peak", "end",
    "solexs_peak_cps", "solexs_bg_cps", "solexs_excess_sigma",
    "hard_detected", "hard_peak_cps", "hard_lead_s",
    "hardness_ratio", "class_proxy", "duration_s", "rise_s", "decay_s",
    "detectors",
]


def events_to_df(events: list, detector: str, instrument: str) -> pd.DataFrame:
    if not events:
        return pd.DataFrame()
    rows = []
    for e in events:
        r = e.as_dict()
        r["detector"] = detector
        r["instrument"] = instrument
        rows.append(r)
    return pd.DataFrame(rows)


def cross_match(soft_df: pd.DataFrame, hard_df: pd.DataFrame,
                tol_s: float = 300.0) -> pd.DataFrame:
    """Match SoLEXS flares with HEL1OS hard X-ray detections.

    For each soft flare, find the hard event whose [start, end] window overlaps
    or lies within tol_s of the soft start. hard_lead_s = soft_peak - hard_peak
    (positive = hard peaked before the soft peak: the Neupert-effect precursor).
    """
    if soft_df.empty:
        return pd.DataFrame(columns=MASTER_COLUMNS)
    out = []
    hard = hard_df.sort_values("start_unix").reset_index(drop=True) if not hard_df.empty else None
    for i, s in soft_df.iterrows():
        s_start, s_end, s_peak = s.start_unix, s.end_unix, s.peak_unix
        hard_row = None
        if hard is not None and len(hard):
            cand = hard[
                (hard.end_unix >= s_start - tol_s) & (hard.start_unix <= s_end + tol_s)
            ]
            if len(cand):
                hard_row = cand.loc[cand.peak_cps.idxmax()]
        duration = s_end - s_start
        row = dict(
            flare_id=f"F{int(s_start)}",
            start=pd.to_datetime(s_start, unit="s"),
            peak=pd.to_datetime(s_peak, unit="s"),
            end=pd.to_datetime(s_end, unit="s"),
            solexs_peak_cps=s.peak_cps,
            solexs_bg_cps=s.background_cps,
            solexs_excess_sigma=s.excess_sigma,
            duration_s=duration,
            rise_s=s_peak - s_start,
            decay_s=s_end - s_peak,
        )
        if hard_row is not None:
            hard_lead = s_peak - hard_row.peak_unix
            hard_peak_bg = max(hard_row.background_cps, 1e-9)
            row.update(
                hard_detected=True,
                hard_peak_cps=hard_row.peak_cps,
                hard_lead_s=hard_lead,
                hardness_ratio=float(hard_row.peak_cps / hard_peak_bg),
                detectors=f"solexs+{hard_row.detector.lower()}",
            )
        else:
            row.update(
                hard_detected=False, hard_peak_cps=0.0, hard_lead_s=None,
                hardness_ratio=None, detectors="solexs",
            )
        out.append(row)
    df = pd.DataFrame(out, columns=MASTER_COLUMNS)
    return df.sort_values("start").reset_index(drop=True)


def save_master(df: pd.DataFrame, name: str = "master_catalog") -> Path:
    p = CATALOGS / f"{name}.parquet"
    df.to_parquet(p, index=False)
    df.to_csv(CATALOGS / f"{name}.csv", index=False)
    return p


def load_master(name: str = "master_catalog") -> pd.DataFrame:
    p = CATALOGS / f"{name}.parquet"
    if not p.exists():
        return pd.DataFrame(columns=MASTER_COLUMNS)
    return pd.read_parquet(p)
