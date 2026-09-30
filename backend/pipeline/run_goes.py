"""Download GOES reference data for all 2024 SoLEXS days, build the reference
flare list, calibrate SoLEXS counts -> GOES flux, and stamp classes on the
master catalog."""
from __future__ import annotations

import pandas as pd

from .catalog.master import save_master
from .config import CATALOGS, GOES_DIR
from .eval.goes import (apply_class_proxy, calibrate_solexs_to_flux,
                        download_days, goes_reference_flares, save_reference)
from .store import available_days


def run() -> None:
    days = [d for d in available_days("solexs", "SDD2") if d.startswith("2024")]
    print(f"GOES days to fetch: {len(days)}")
    gdf = download_days(days)
    print(f"GOES 1-min rows: {len(gdf)}")
    if gdf.empty:
        print("No GOES data available - skipping calibration.")
        return

    ref = goes_reference_flares(gdf)
    print(f"GOES reference flares: {len(ref)}")
    if len(ref):
        print(ref.cls.value_counts().to_string())

    soft = pd.read_parquet(CATALOGS / "events_solexs.parquet")
    cal = calibrate_solexs_to_flux(soft, gdf)
    print("Calibration:", cal)

    master = pd.read_parquet(CATALOGS / "master_catalog.parquet")
    master = apply_class_proxy(master, cal)
    save_master(master)
    if len(master):
        print("Master class distribution (all dates, proxy):")
        print(master.class_proxy.value_counts().to_string())
        m24 = master[master.start < "2025-01-01"]
        if len(m24):
            print("2024-only class distribution:")
            print(m24.class_proxy.value_counts().to_string())
    save_reference(ref, cal)
    print("Saved: goes_reference_flares, solexs_calibration.json, master w/ classes")


if __name__ == "__main__":  # pragma: no cover
    run()
