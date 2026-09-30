"""Flare detector: nowcasting engine.

Algorithm (per light curve, gap-aware, streaming-friendly):
  1. Optionally resample to a working cadence (`working_dt_s`) — essential for
     photon-starved hard X-ray bands where 1-s samples are mostly zero.
  2. Smooth with a short boxcar; estimate background B(t) via rolling-min +
     recentering (flare-immune).
  3. Local Poisson noise sigma(t) = sqrt(max(B(t),eps)/n_eff), floored by the
     robust scatter of the residual series -> threshold k*sigma(t).
  4. Flare start: smoothed rate above threshold for `start_sustain_s`
     (>= 2 samples). End: decays to within `end_nsigma`*sigma, or `max_duration_s`
     is hit (particle-event guard). Episodes within `merge_gap_s` merge.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

from ..config import DETECT
from .timeseries import resample_uniform, rolling_background, smooth


@dataclass
class Event:
    start_unix: float
    peak_unix: float
    end_unix: float
    peak_cps: float
    background_cps: float
    excess_sigma: float
    duration_s: float
    rise_s: float
    decay_s: float

    def as_dict(self) -> dict:
        return asdict(self)


def _robust_sigma(y: np.ndarray) -> float:
    """Robust noise estimate from the MAD of the first difference."""
    d = np.diff(y)
    d = d[np.isfinite(d)]
    if len(d) == 0:
        return 0.0
    mad = np.median(np.abs(d - np.median(d)))
    return 1.4826 * mad * np.sqrt(0.5)


def _prep(t, y, good, working_dt_s: float | None):
    if working_dt_s and working_dt_s > 1.0:
        t2, y2 = resample_uniform(np.asarray(t, float), np.asarray(y, float),
                                  dt_out=float(working_dt_s), agg="mean")
        g2 = np.zeros(len(t2), dtype=bool)
        if good is not None:
            _, gf = resample_uniform(np.asarray(t, float), np.asarray(good, float),
                                     dt_out=float(working_dt_s), agg="mean")
            g2 = np.nan_to_num(gf, nan=0.0) >= 0.5
        else:
            g2 = np.isfinite(y2)
        keep = np.isfinite(y2)
        return t2[keep], y2[keep], g2[keep]
    return np.asarray(t, float), np.asarray(y, float), (
        np.ones(len(t), dtype=bool) if good is None else np.asarray(good, bool))


def detect_flares(t, y, good=None, params: dict | None = None) -> list[Event]:
    p = {**DETECT, **(params or {})}
    t, y, good = _prep(t, y, good, p.get("working_dt_s"))
    n = len(t)
    if n < 50:
        return []
    dt = float(np.median(np.diff(t))) if n > 1 else 1.0
    if not np.isfinite(dt) or dt <= 0:
        dt = 1.0

    ysm = smooth(y, p["smooth_s"], dt)
    bg = rolling_background(t, ysm, p["bg_window_s"], dt)

    # sigma(t): local Poisson noise of the smoothed rate + robust global floor
    n_eff = max(p["smooth_s"] / dt, 1.0)
    sig_local = np.sqrt(np.clip(bg, 1e-9, None) / n_eff)
    resid = ysm - bg
    sig_floor = max(_robust_sigma(resid), 1e-6)
    sig = np.maximum(sig_local, sig_floor)

    excess = ysm - bg
    above = (excess > p["start_nsigma"] * sig) & good & np.isfinite(ysm)

    events: list[Event] = []
    sustain = max(2, int(round(p["start_sustain_s"] / dt)))
    end_sustain = max(2, int(round(10 * p["smooth_s"] / dt)))
    end_factor = p["end_nsigma"]

    i = 0
    while i < n:
        if above[i]:
            j = i
            while j < n and above[j]:
                j += 1
            if j - i >= sustain:
                k = j
                below = 0
                while k < n and below < end_sustain:
                    if above[k]:
                        below = 0
                    else:
                        below += 1
                    k += 1
                end_idx = min(n - 1, k)
                while end_idx > j and not above[end_idx]:
                    end_idx -= 1
                # decay below end threshold or hard cap at max_duration
                max_len = int(round(p["max_duration_s"] / dt))
                if t[end_idx] - t[i] > p["max_duration_s"]:
                    end_idx = min(n - 1, i + max_len)
                _emit(events, t, y, bg, sig, i, end_idx, p, dt)
                i = end_idx + 1
            else:
                i = j
        else:
            i += 1

    return _merge_close(events, p["merge_gap_s"])


def _emit(events: list[Event], t, y, bg, sig, i0, i1, p, dt) -> None:
    duration = float(t[i1] - t[i0])
    if duration < p["min_duration_s"]:
        return
    pad = int(round(p["peak_pad_s"] / max(dt, 1e-9)))
    lo, hi = max(0, i0 - pad), min(len(t) - 1, i1 + pad)
    seg = y[lo:hi + 1]
    finite = np.isfinite(seg)
    if not finite.any():
        return
    pk = int(np.argmax(np.where(finite, seg, -np.inf))) + lo
    bg_level = float(np.nanmedian(bg[i0:i1 + 1]))
    if not np.isfinite(bg_level):
        bg_level = float(np.nanmedian(bg))
    sig_at_peak = float(sig[pk]) if np.isfinite(sig[pk]) else sig_floor_global(sig)
    events.append(Event(
        start_unix=float(t[i0]),
        peak_unix=float(t[pk]),
        end_unix=float(t[i1]),
        peak_cps=float(y[pk]),
        background_cps=bg_level,
        excess_sigma=float((y[pk] - bg_level) / max(sig_at_peak, 1e-9)),
        duration_s=duration,
        rise_s=float(t[pk] - t[i0]),
        decay_s=float(t[i1] - t[pk]),
    ))


def sig_floor_global(sig: np.ndarray) -> float:
    s = sig[np.isfinite(sig)]
    return float(np.median(s)) if len(s) else 1.0


def _merge_close(events: list[Event], gap_s: float) -> list[Event]:
    if not events:
        return events
    events = sorted(events, key=lambda e: e.start_unix)
    merged = [events[0]]
    for e in events[1:]:
        last = merged[-1]
        if e.start_unix - last.end_unix <= gap_s:
            peak = e if e.peak_cps > last.peak_cps else last
            merged[-1] = Event(
                start_unix=last.start_unix,
                peak_unix=peak.peak_unix,
                end_unix=max(last.end_unix, e.end_unix),
                peak_cps=max(last.peak_cps, e.peak_cps),
                background_cps=min(last.background_cps, e.background_cps),
                excess_sigma=max(last.excess_sigma, e.excess_sigma),
                duration_s=max(last.end_unix, e.end_unix) - last.start_unix,
                rise_s=peak.peak_unix - last.start_unix,
                decay_s=max(last.end_unix, e.end_unix) - peak.peak_unix,
            )
        else:
            merged.append(e)
    return merged
