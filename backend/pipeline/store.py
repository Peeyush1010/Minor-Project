"""Parquet store for unified light curves + shared time helpers.

Unified series schema (one parquet per instrument/detector/day):
    ts       : datetime64[ns]  (naive UTC)
    rate_cps : float64         (counts per second)
    err_cps  : float64         (statistical error, 1 sigma)
    is_good  : bool            (inside good-time intervals)

Layout:
    PROCESSED/solexs/{SDD1,SDD2}/{YYYYMMDD}.parquet          band = nominal 1-22 keV
    PROCESSED/hel1os/{CDTE1,CDTE2,CZT1,CZT2}/{YYYYMMDD}.parquet  (hel1os rows also
        carry band_lo_kev / band_hi_kev / band_label for the chosen hard band)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import PROCESSED

UNIX_EPOCH = pd.Timestamp("1970-01-01")


def to_ts(seconds) -> pd.Series:
    """Convert unix-epoch seconds (float array/Series) to naive-UTC datetimes."""
    return UNIX_EPOCH + pd.to_timedelta(np.asarray(seconds, dtype=float), unit="s")


def ts_to_unix(ts: pd.Series) -> np.ndarray:
    return (pd.to_datetime(ts) - UNIX_EPOCH).dt.total_seconds().to_numpy()


def series_path(instrument: str, detector: str, day: str) -> Path:
    p = PROCESSED / instrument.lower() / detector.upper()
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{day}.parquet"


def write_series(instrument: str, detector: str, day: str, df: pd.DataFrame) -> None:
    df.to_parquet(series_path(instrument, detector, day), index=False)


def read_series(instrument: str, detector: str, days: list[str] | None = None) -> pd.DataFrame:
    base = PROCESSED / instrument.lower() / detector.upper()
    files = sorted(base.glob("*.parquet"))
    if days is not None:
        want = set(days)
        files = [f for f in files if f.stem in want]
    if not files:
        return pd.DataFrame(columns=["ts", "rate_cps", "err_cps", "is_good"])
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def available_days(instrument: str, detector: str) -> list[str]:
    base = PROCESSED / instrument.lower() / detector.upper()
    return sorted(f.stem for f in base.glob("*.parquet"))
