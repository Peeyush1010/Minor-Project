"""Evaluation metrics: nowcast performance vs the GOES reference flare list.

Matching rule: a detected event matches a reference flare when their
[start, end] intervals overlap (extended by tol_s on both sides).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ..config import EDA_DIR


def _unix(df: pd.DataFrame, col: str) -> np.ndarray:
    if col in df.columns:
        return (pd.to_datetime(df[col]) - pd.Timestamp("1970-01-01")).dt.total_seconds().to_numpy()
    alt = f"{col}_unix"
    if alt in df.columns:
        return pd.to_numeric(df[alt], errors="coerce").to_numpy(dtype=float)
    raise KeyError(f"neither '{col}' nor '{alt}' in columns {list(df.columns)}")


def match_events(detected: pd.DataFrame, reference: pd.DataFrame,
                 tol_s: float = 600.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return copies of both frames annotated with match flags/ids."""
    detected = detected.copy()
    reference = reference.copy()
    detected["matched_ref"] = -1
    reference["matched_det"] = -1
    if detected.empty or reference.empty:
        return detected, reference
    d_start, d_end = _unix(detected, "start"), _unix(detected, "end")
    r_start, r_end = _unix(reference, "start"), _unix(reference, "end")
    for j in range(len(reference)):
        overlaps = np.where(
            (d_start <= r_end[j] + tol_s) & (d_end + tol_s >= r_start[j])
            & (detected.matched_ref.to_numpy() == -1)
        )[0]
        if len(overlaps):
            i = overlaps[0]
            detected.at[detected.index[i], "matched_ref"] = j
            reference.at[reference.index[j], "matched_det"] = int(detected.index[i])
    return detected, reference


def _overlaps_any(detected: pd.DataFrame, reference: pd.DataFrame,
                  tol_s: float = 600.0) -> np.ndarray:
    """Boolean per detection: overlaps ANY reference interval (many-to-one)."""
    d_start, d_end = _unix(detected, "start"), _unix(detected, "end")
    r_start, r_end = _unix(reference, "start"), _unix(reference, "end")
    out = np.zeros(len(detected), dtype=bool)
    for j in range(len(reference)):
        out |= (d_start <= r_end[j] + tol_s) & (d_end + tol_s >= r_start[j])
    return out


def evaluate(detected: pd.DataFrame, reference: pd.DataFrame,
             coverage_days: float, tol_s: float = 600.0) -> dict:
    n_ref = len(reference)
    n_det = len(detected)
    if n_det and n_ref:
        any_overlap = _overlaps_any(detected, reference, tol_s)
        detected = detected.copy()
        detected["is_tp"] = any_overlap
    elif n_det:
        detected = detected.copy()
        detected["is_tp"] = False
    # TPR: fraction of reference flares matched by >= 1 detection
    if n_ref and n_det:
        detected_a, reference_a = match_events(detected, reference, tol_s)
        matched_ref = int((reference_a.matched_det >= 0).sum())
    else:
        matched_ref = 0
    false_alarms = int((~detected.is_tp).sum()) if n_det else 0
    out = {
        "n_reference_flares": n_ref,
        "n_detected_events": n_det,
        "true_positives": matched_ref,
        "tpr": matched_ref / n_ref if n_ref else None,
        "false_alarms": false_alarms,
        "far_per_day": false_alarms / coverage_days if coverage_days else None,
        "coverage_days": coverage_days,
        "per_class": {},
    }
    if n_ref and "cls" in reference.columns:
        _, reference_a = match_events(detected, reference, tol_s) if n_det else (detected, reference)
        for cls, grp in reference_a.groupby("cls"):
            hit = int((grp.matched_det >= 0).sum())
            out["per_class"][str(cls)] = {
                "reference": len(grp),
                "detected": hit,
                "tpr": hit / len(grp) if len(grp) else None,
            }
    if n_det and "class_proxy" in detected.columns:
        dist = detected.class_proxy.value_counts().to_dict()
        out["detected_class_distribution"] = {str(k): int(v) for k, v in dist.items()}
    return out


def save_report(report: dict, name: str = "eval_report.json") -> None:
    (EDA_DIR / name).write_text(json.dumps(report, indent=2, default=str))
