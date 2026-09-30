"""HEL1OS Level-1 zip reader.

Zip layout (verified on HLS_20260908_000009_43175sec_lev1_V111.zip):
    <YYYY>/<MM>/<DD>/HLS_<date>_<hhmmss>_<dur>sec_lev1_VXXX/
        cdte/lightcurve_cdte{1,2}.fits   (bands: 5-20, 20-30, 30-40, 40-60, 1.8-90 keV)
        czt/lightcurve_czt{1,2}.fits     (bands: 20-40, 40-60, 60-80, 80-150, 18-160 keV)
        aux/gticdte{1,2}.fits, gticzt{1,2}.fits  (single GTI row, MJD days)

Each light-curve HDU: columns MJD (days), ISOT (string), CTR (counts/s), STAT_ERR.
One zip = one ~12 h segment. Detectors may be partially disabled (e.g. CZT2 off).
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from astropy.io import fits

from ..config import HEL1OS_RAW
from ..store import series_path, write_series

_ZIP_RE = re.compile(r"HLS_(\d{8})_\d{6}_\d+sec_lev1_V\d+\.zip")

# Detector -> analysis band used for flare detection (keV). We use a mid band with
# good flare contrast: CdTe 5-20 keV (low band is dominated by background), CZT 20-40 keV.
BAND_CHOICE = {
    "CDTE1": ("5.00KEV_TO_20.00KEV", 5.0, 20.0),
    "CDTE2": ("5.00KEV_TO_20.00KEV", 5.0, 20.0),
    "CZT1": ("20.00KEV_TO_40.00KEV", 20.0, 40.0),
    "CZT2": ("20.00KEV_TO_40.00KEV", 20.0, 40.0),
}


def _mjd_to_unix(mjd: np.ndarray) -> np.ndarray:
    return (mjd - 40587.0) * 86400.0


def _det_name(hdu_name: str) -> str | None:
    m = re.match(r"(CDTE\d|CZT\d)", hdu_name)
    return m.group(1) if m else None


def read_hel1os_zip(zip_path: Path) -> dict[str, pd.DataFrame]:
    """Return {detector: unified_df} (rows concatenated across band HDUs is NOT done;
    one row per 1 s sample for the chosen analysis band per detector)."""
    out: dict[str, pd.DataFrame] = {}
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.namelist()
        lc_files = [m for m in members if m.endswith("lightcurve_cdte1.fits")
                    or m.endswith("lightcurve_cdte2.fits")
                    or m.endswith("lightcurve_czt1.fits")
                    or m.endswith("lightcurve_czt2.fits")]
        for lc_member in lc_files:
            det_from_file = re.search(r"lightcurve_(cdte|czt)(\d)\.fits$", lc_member)
            if not det_from_file:
                continue
            det = (det_from_file.group(1) + det_from_file.group(2)).upper()
            band_key, lo, hi = BAND_CHOICE[det]
            hdul = fits.open(io.BytesIO(zf.read(lc_member)), memmap=False)
            hdu = None
            for h in hdul[1:]:
                if h.name.endswith(band_key):
                    hdu = h
                    break
            if hdu is None or hdu.data is None or len(hdu.data) == 0:
                hdul.close()
                continue
            tab = hdu.data
            mjd = np.asarray(tab["MJD"], dtype=float)
            ctr = np.asarray(tab["CTR"], dtype=float)
            err = np.asarray(tab["STAT_ERR"], dtype=float)
            unix = _mjd_to_unix(mjd)
            # GTI: aux/gticdte{N}.fits with columns tstart/tstop in MJD (usually 1 row)
            good = np.ones(len(mjd), dtype=bool)
            gti_member = next(
                (m for m in members if m.endswith(f"gti{det.lower()}.fits")), None)
            if gti_member:
                hg = fits.open(io.BytesIO(zf.read(gti_member)), memmap=False)
                if hg[1].data is not None and len(hg[1].data) > 0:
                    g_s = _mjd_to_unix(np.asarray(hg[1].data["tstart"], dtype=float))
                    g_e = _mjd_to_unix(np.asarray(hg[1].data["tstop"], dtype=float))
                    good = np.zeros(len(mjd), dtype=bool)
                    for s, e in zip(g_s, g_e):
                        good |= (unix >= s) & (unix < e)
                hg.close()
            df = pd.DataFrame({
                "ts": pd.to_datetime(unix, unit="s"),
                "rate_cps": ctr,
                "err_cps": err,
                "is_good": good,
                "band_lo_kev": lo,
                "band_hi_kev": hi,
            })
            out.setdefault(det, []).append(df)
            hdul.close()
    return {d: pd.concat(v, ignore_index=True).sort_values("ts").reset_index(drop=True)
            for d, v in out.items()}


def ingest_all(limit: int | None = None) -> pd.DataFrame:
    """Ingest every HEL1OS zip into the parquet store; return a summary."""
    rows = []
    zips = sorted(HEL1OS_RAW.glob("*.zip"))
    for i, zp in enumerate(zips):
        m = _ZIP_RE.match(zp.name)
        if not m:
            continue
        day = m.group(1)
        try:
            dets = read_hel1os_zip(zp)
        except Exception as e:  # pragma: no cover
            print(f"[hel1os] FAILED {zp.name}: {e}")
            continue
        for det, df in dets.items():
            # A detector may span two 12 h zips for the same calendar day.
            path = series_path("hel1os", det, day)
            existing = pd.read_parquet(path) if path.exists() else None
            if path.exists():
                existing = pd.read_parquet(path)
            merged = pd.concat([x for x in (existing, df) if x is not None],
                               ignore_index=True)
            merged = (merged.drop_duplicates(subset="ts")
                            .sort_values("ts").reset_index(drop=True))
            write_series("hel1os", det, day, merged)
            rows.append(dict(day=day, detector=det, n=len(merged),
                             good_frac=float(merged.is_good.mean()),
                             median_cps=float(merged.rate_cps.median()),
                             max_cps=float(merged.rate_cps.max())))
        if limit and i + 1 >= limit:
            break
    return pd.DataFrame(rows)


if __name__ == "__main__":  # pragma: no cover
    print(ingest_all().to_string())
