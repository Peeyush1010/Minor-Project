"""Central configuration for the Aditya-L1 flare pipeline."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Raw zips as downloaded from PRADAN (kept untouched)
RAW_ROOT = REPO_ROOT / "dataset"
SOLEXS_RAW = RAW_ROOT / "solexs"
HEL1OS_RAW = RAW_ROOT / "hel1os"

# Pipeline outputs
DATA_ROOT = REPO_ROOT / "backend" / "data"
PROCESSED = DATA_ROOT / "processed"      # unified light curves (parquet)
CATALOGS = DATA_ROOT / "catalogs"        # event lists + master catalog
GOES_DIR = DATA_ROOT / "goes"            # NOAA GOES reference data (netcdf + parquet)
EDA_DIR = DATA_ROOT / "eda"              # diagnostic plots / logs
MERGED_DIR = DATA_ROOT / "merged"        # merged single-file datasets (export_merged.py)

for _d in (PROCESSED, CATALOGS, GOES_DIR, EDA_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- detection
DETECT = {
    "smooth_s": 20.0,          # boxcar smoothing of rate (seconds)
    "bg_window_s": 2700.0,     # rolling background window (45 min)
    "start_nsigma": 5.0,       # excess (smoothed) above background to start a flare
    "start_sustain_s": 30.0,   # must stay above threshold this long
    "end_nsigma": 1.5,         # decay back to within this excess to end
    "min_duration_s": 60.0,    # candidate shorter than this is dropped
    "merge_gap_s": 300.0,      # episodes closer than this are one flare
    "peak_pad_s": 120.0,       # pad for peak search beyond the flagged rise
    "max_duration_s": 21600.0, # 6 h cap (particle-event / data-gap guard)
    "working_dt_s": None,      # resample before detection (e.g. 60 for HEL1OS)
}

# Flare classes from GOES 1-8 A peak flux (W/m^2)
CLASS_THRESHOLDS = [(-4, "X"), (-5, "M"), (-6, "C"), (-7, "B")]
# class letter = largest letter whose threshold <= log10(peak_flux)

# Instruments
SDD_BAND = (1.0, 22.0)   # SoLEXS nominal soft band (keV)
HEL1OS_WORKING_DT_S = 60  # photon-starved bands: detect on 60-s binned rates
