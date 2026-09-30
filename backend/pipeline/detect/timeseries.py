"""Gap-aware time-series helpers shared by detection and forecasting.

All functions take (t, y) where t is float seconds (unix) sorted ascending and
y is the count rate; gaps are handled via masks rather than reindexing so the
same code works on native 1 s data and on resampled grids.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.ndimage import uniform_filter1d


def smooth(y: np.ndarray, window_s: float, dt: float) -> np.ndarray:
    """Centered boxcar smoothing that tolerates NaNs (they are ignored via nan-fill)."""
    if window_s <= dt:
        return y.copy()
    k = max(1, int(round(window_s / dt)))
    if k % 2 == 0:
        k += 1
    mask = np.isfinite(y)
    filled = np.where(mask, y, 0.0)
    sm = uniform_filter1d(filled, size=k, mode="nearest")
    cnt = uniform_filter1d(mask.astype(float), size=k, mode="nearest")
    out = np.where(cnt > 0, sm / np.maximum(cnt, 1e-9), np.nan)
    return out


def rolling_background(t: np.ndarray, y: np.ndarray, window_s: float, dt: float,
                       n_sigma_clip: float = 3.0, n_iter: int = 2) -> np.ndarray:
    """Flare-immune rolling background via rolling minimum + median recentering.

    The rolling minimum over `window_s` cannot see a flare peak (flares only push
    counts up), so it tracks the quiet-sun floor through even the largest events.
    The min-filter is biased low by the noise floor, so we recenter by adding the
    global median of the residual (y - bg): quiet-time median then sits on bg.
    O(N) via scipy minimum_filter1d.
    """
    y = np.asarray(y, dtype=float)
    s = pd.Series(y)
    k = max(3, int(round(window_s / dt)))
    if k % 2 == 0:
        k += 1
    ks = max(3, int(round(window_s / 6 / dt)))
    if ks % 2 == 0:
        ks += 1
    # rolling min tracks the quiet floor (O(N) monotonic-wedge in pandas);
    # NaNs (gaps) are skipped, min_periods keeps output NaN inside big gaps
    base = s.rolling(k, center=True, min_periods=max(3, k // 10)).min()
    bg = base.rolling(ks, center=True, min_periods=max(3, ks // 10)).mean().to_numpy()
    resid = y - bg
    resid = resid[np.isfinite(resid)]
    if len(resid):
        bg = bg + np.median(resid)  # recenter quiet-time level
    return bg


def resample_uniform(t: np.ndarray, y: np.ndarray, dt_out: float,
                     agg: str = "mean") -> tuple[np.ndarray, np.ndarray]:
    """Resample (t, y) onto a uniform grid of step dt_out (seconds).

    Returns (t_out, y_out) with NaN where no data fell in a bin (gap mask).
    """
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    t0 = np.floor(t[0] / dt_out) * dt_out
    t1 = np.ceil(t[-1] / dt_out) * dt_out
    edges = np.arange(t0, t1 + dt_out / 2, dt_out)
    idx = np.digitize(t, edges) - 1
    n = len(edges) - 1
    out = np.full(n, np.nan)
    # vectorized binning via np.add.at on clipped indices
    valid = (idx >= 0) & (idx < n) & np.isfinite(y)
    sums = np.zeros(n)
    cnts = np.zeros(n)
    np.add.at(sums, idx[valid], y[valid])
    np.add.at(cnts, idx[valid], 1)
    if agg == "mean":
        out = np.where(cnts > 0, sums / np.maximum(cnts, 1e-9), np.nan)
    elif agg == "sum":
        out = np.where(cnts > 0, sums, np.nan)
    t_out = edges[:-1] + dt_out / 2
    return t_out, out
