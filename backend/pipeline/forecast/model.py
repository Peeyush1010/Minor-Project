"""Forecasting: P(flare with class >= C within next HORIZON_S minutes).

Features at time t (trailing windows only -> truly predictive, no leakage):
  - SoLEXS rate stats over 5/15/60 min: mean, std, slope, max/mean
  - background level, current excess over background (sigma units)
  - time since last C+ flare, fraction of last hour above 3 sigma
  - hardness: HEL1OS CZT1 rate over trailing 5/15 min (when available)
Target: 1 if a master-catalog flare with class_proxy in {C,M,X} peaks within
[ t, t+HORIZON_S ), else 0. Sampled every 60 s in good-time intervals.

Evaluation: rolling split by day blocks; metrics = TPR at fixed FAR + lead time
(alert time - peak time for matched flares).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import CATALOGS

HORIZON_S = 1800
STEP_S = 60
POS_CLASSES = {"C", "M", "X"}


def _unix(ts: pd.Series) -> np.ndarray:
    return (pd.to_datetime(ts) - pd.Timestamp("1970-01-01")).dt.total_seconds().to_numpy()


def _build(days=None):
    from ..store import read_series
    master = pd.read_parquet(CATALOGS / "master_catalog.parquet")
    soft = read_series("solexs", "SDD2", days)
    soft = soft[soft.is_good].sort_values("ts").reset_index(drop=True)
    t = _unix(soft.ts)
    y = soft.rate_cps.to_numpy()

    # trailing rolling stats on a uniform 60 s grid for feature stability
    tg, yg = t, y
    r60 = pd.Series(yg).rolling(60, min_periods=20)
    r300 = pd.Series(yg).rolling(300, min_periods=60)
    r900 = pd.Series(yg).rolling(900, min_periods=180)
    r3600 = pd.Series(yg).rolling(3600, min_periods=600)

    bg = pd.Series(yg).rolling(3600, min_periods=600).median()
    feats = pd.DataFrame({
        "mean60": r60.mean().to_numpy(),
        "std60": r60.std().to_numpy(),
        "mean300": r300.mean().to_numpy(),
        "max300": r300.max().to_numpy(),
        "slope300": (pd.Series(yg).shift(300) - pd.Series(yg)) / 300.0,
        "mean900": r900.mean().to_numpy(),
        "mean3600": r3600.mean().to_numpy(),
        "bg": bg.to_numpy(),
    })
    feats["excess_sigma"] = (feats.mean60 - feats.bg) / np.sqrt(
        np.clip(feats.bg, 1e-3, None) / 60.0)
    feats["max_over_mean300"] = feats.max300 / np.clip(feats.mean300, 1e-6, None)

    # hardness features: HEL1OS CZT1 trailing rates, aligned by timestamp
    try:
        hard = read_series("hel1os", "CZT1")
        if not hard.empty:
            hard = hard.sort_values("ts")
            ht = _unix(hard.ts)
            hy = pd.Series(hard.rate_cps.to_numpy()).interpolate(limit=5)
            h60 = pd.Series(hy).rolling(60, min_periods=5).mean()
            h900 = pd.Series(hy).rolling(900, min_periods=60).mean()
            feats["hard_mean60"] = np.interp(tg, ht, h60.to_numpy())
            feats["hard_mean900"] = np.interp(tg, ht, h900.to_numpy())
        else:
            feats["hard_mean60"] = 0.0
            feats["hard_mean900"] = 0.0
    except Exception:
        feats["hard_mean60"] = 0.0
        feats["hard_mean900"] = 0.0

    # time since last C+ flare
    pos = master[master.class_proxy.isin(POS_CLASSES)]
    pos_t = np.sort(_unix(pos.start))
    idx = np.searchsorted(pos_t, tg, side="right") - 1
    feats["since_last_flare_s"] = np.where(idx >= 0, tg - pos_t[idx], 1e9)

    # label: C+ flare peaks within horizon
    peaks = np.sort(_unix(pos.peak))
    labels = np.zeros(len(tg), dtype=bool)
    for pk in peaks:
        lo = np.searchsorted(tg, pk - HORIZON_S)
        hi = np.searchsorted(tg, pk)
        labels[lo:hi] = True
    feats = feats.replace([np.inf, -np.inf], np.nan).bfill().ffill()
    return tg, feats, labels


def train_and_evaluate(days=None, seed: int = 42) -> dict:
    import lightgbm as lgb
    from sklearn.metrics import precision_recall_curve, roc_auc_score

    tg, X, y = _build(days)
    # block split: last 25% of time as test
    t_split = np.quantile(tg, 0.75)
    tr, te = tg <= t_split, tg > t_split
    model = lgb.LGBMClassifier(
        n_estimators=400, learning_rate=0.05, num_leaves=63,
        subsample=0.8, colsample_bytree=0.8, random_state=seed,
        class_weight="balanced", verbose=-1,
    )
    model.fit(X[tr], y[tr])
    p = model.predict_proba(X[te])[:, 1]
    auc = roc_auc_score(y[te], p) if y[te].sum() else float("nan")

    # operating point: threshold for FAR = 2/day on test
    order = np.argsort(-p)
    n_test_hours = (tg[te].max() - tg[te].min()) / 3600.0
    p_sorted = p[order]
    far = []
    for k in range(1, len(p_sorted) + 1):
        far.append(k / max(n_test_hours / 24.0, 1e-9))
    k_star = int(np.searchsorted(np.array(far), 2.0)) + 1
    thr = float(p_sorted[min(k_star, len(p_sorted) - 1)])
    alert_test = p >= thr
    # align alerts back onto the full time axis
    alert_full = np.zeros(len(tg), dtype=bool)
    alert_full[te] = alert_test
    alert = alert_full

    # lead time: for each test-window C+ flare, earliest alert before its peak
    master = pd.read_parquet(CATALOGS / "master_catalog.parquet")
    pos = master[master.class_proxy.isin(POS_CLASSES)]
    leads = []
    hits = 0
    for pk in _unix(pos.peak):
        if pk <= t_split:
            continue
        window = (tg >= pk - HORIZON_S) & (tg < pk) & alert
        if window.any():
            hits += 1
            leads.append(pk - tg[window].min())
    report = {
        "model": "lightgbm",
        "horizon_s": HORIZON_S,
        "train_samples": int(tr.sum()), "test_samples": int(te.sum()),
        "test_pos_rate": float(y[te].mean()) if te.any() else None,
        "auc": float(auc),
        "threshold_far2day": thr,
        "flares_in_test": len(leads),
        "alerted_flares": hits,
        "median_lead_s": float(np.median(leads)) if leads else None,
        "p90_lead_s": float(np.percentile(leads, 90)) if leads else None,
        "feature_importance": dict(sorted(
            zip(model.feature_name_, model.feature_importances_.tolist()),
            key=lambda kv: -kv[1])[:10]),
    }
    # persist series + model for the API (60-s grid for a light dashboard strip)
    tte = tg[te]
    grid = np.arange(tte.min() // 60 * 60, tte.max() + 60, 60)
    idx = ((tte - grid[0]) // 60).astype(int)
    ok = (idx >= 0) & (idx < len(grid))
    # keep max probability per minute (alert peaks matter, not averages)
    pmax = np.zeros(len(grid))
    np.maximum.at(pmax, idx[ok], p[ok])
    out = pd.DataFrame({
        "ts": pd.to_datetime(grid, unit="s"),
        "p_flare": pmax,
    }).drop_duplicates("ts")
    out.to_parquet(CATALOGS / "forecast_series.parquet", index=False)
    model.booster_.save_model(str(CATALOGS / "forecast_model.txt"))
    import json
    (CATALOGS / "forecast_report.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    import json as _json
    rep = train_and_evaluate()
    print(_json.dumps(rep, indent=2, default=str))
