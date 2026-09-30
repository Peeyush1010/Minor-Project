"""Synthetic light-curve tests for the flare detector."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.pipeline.detect.detector import detect_flares
from backend.pipeline.detect.timeseries import resample_uniform, rolling_background, smooth


def _synthetic(n=86400, seed=7, flares=((20000, 400, 900, 50.0), (50000, 300, 700, 20.0))):
    """Light curve: bg=10 cps + Poisson noise + exponential flares.

    Each flare: (start_idx, rise_len, decay_len, peak_amplitude_cps).
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=float)
    y = rng.poisson(10.0, n).astype(float)
    for s, rise, decay, amp in flares:
        prof = np.zeros(n)
        prof[s:s + rise] = np.linspace(0, amp, rise)
        fall = np.exp(-np.arange(decay) / (decay / 5))
        prof[s + rise:s + rise + decay] = amp * fall
        y = y + prof
    return t, y


def test_detects_two_isolated_flares():
    t, y = _synthetic()
    ev = detect_flares(t, y)
    assert len(ev) == 2, f"expected 2 flares, got {len(ev)}"
    e0, e1 = ev
    assert abs(e0.peak_unix - 20399) < 300
    assert abs(e1.peak_unix - 50299) < 300
    assert e0.peak_cps > 50
    assert e0.duration_s > 60


def test_no_false_positive_on_quiet_curve():
    rng = np.random.default_rng(3)
    t = np.arange(86400, dtype=float)
    y = rng.poisson(10.0, 86400).astype(float)
    ev = detect_flares(t, y)
    assert len(ev) == 0, f"quiet curve flagged {len(ev)} flares"


def test_background_step_is_not_flagged():
    """A slow background drift (orbital/solar cycle) must not trigger detections."""
    rng = np.random.default_rng(11)
    t = np.arange(86400, dtype=float)
    y = rng.poisson(10 + 8 * t / 86400 * 3, 86400).astype(float)  # smooth ramp x4
    ev = detect_flares(t, y, params={"start_nsigma": 6.0})
    assert len(ev) == 0, f"slow ramp flagged {len(ev)} flares"


def test_merged_close_flares():
    t, y = _synthetic(n=86400, seed=9,
                      flares=((20000, 300, 500, 40.0), (22300, 300, 500, 60.0)))
    # episodes are ~2.3 ks apart: default gap keeps them separate...
    assert len(detect_flares(t, y)) == 2
    # ...but a wider merge gap joins them into one flare
    ev = detect_flares(t, y, params={"merge_gap_s": 3000})
    assert len(ev) == 1, f"close flares should merge, got {len(ev)}"
    assert ev[0].peak_cps > 50


def test_resample_uniform_handles_gaps():
    t = np.arange(0, 1000, 1.0)
    y = np.ones(len(t))
    t2, y2 = resample_uniform(t, y, dt_out=10.0)
    assert len(t2) == 100
    assert np.isfinite(y2).all()
    # gap: drop samples 300-399
    keep = (t < 300) | (t >= 400)
    t3, y3 = resample_uniform(t[keep], y[keep], dt_out=10.0)
    assert np.isnan(y3).sum() >= 5  # several empty bins in the gap


def test_rolling_background_ignores_flares():
    t, y = _synthetic(flares=((40000, 500, 2000, 200.0),))
    bg = rolling_background(t, smooth(y, 20, 1.0), 2700.0, 1.0)
    # background far from the flare should stay near 10
    far = bg[10000:20000]
    assert abs(np.nanmedian(far) - 10) < 2
    # during the flare the clipped background should stay well below the peak
    mid = bg[40500:41500]
    assert np.nanmedian(mid) < 40
