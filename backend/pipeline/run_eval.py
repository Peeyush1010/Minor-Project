"""Run nowcast evaluation against the GOES reference flare list (2024 window)."""
from __future__ import annotations

import pandas as pd

from .config import GOES_DIR
from .eval.goes import calibrate_solexs_to_flux
from .eval.metrics import evaluate, save_report
from .store import available_days


def run() -> dict:
    ref = pd.read_parquet(GOES_DIR / "goes_reference_flares.parquet")
    soft = pd.read_parquet("backend/data/catalogs/events_solexs.parquet")
    # restrict to dates where GOES coverage exists (2024 window)
    days = [d for d in available_days("solexs", "SDD2") if d.startswith("2024")]
    ref = ref[(ref.start >= pd.Timestamp(days[0])) &
              (ref.start < pd.Timestamp(days[-1]) + pd.Timedelta(days=1))]
    soft24 = soft[soft.start_unix < (pd.Timestamp(days[-1]) + pd.Timedelta(days=1)).timestamp()]
    # approximate coverage: count of days with >12 h good data
    from .store import read_series
    df = read_series("solexs", "SDD2", days)
    good_hours = df.groupby(df.ts.dt.date).is_good.sum() / 3600
    coverage_days = float((good_hours > 12).sum())

    report = evaluate(soft24, ref, coverage_days=coverage_days)
    save_report(report)
    return report


if __name__ == "__main__":  # pragma: no cover
    import json
    r = run()
    print(json.dumps(r, indent=2, default=str))
