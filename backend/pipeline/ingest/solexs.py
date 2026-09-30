"""SoLEXS Level-1 daily zip reader.

Zip layout (verified on AL1_SLX_L1_20240508_v1.0.zip):
    AL1_SLX_L1_<date>_vX.X/
        SDD1/ AL1_SOLEXS_<date>_SDD1_L1.{gti,lc,pi}.gz   (lc/pi sometimes absent)
        SDD2/ AL1_SOLEXS_<date>_SDD2_L1.{gti,lc,pi}.gz

.lc.gz  -> FITS BinTable 'RATE', columns TIME (unix s), COUNTS (counts/s, 1 s bins)
.gti.gz -> FITS BinTable 'GTI',  columns START, STOP (unix s)
"""
from __future__ import annotations

import gzip
import io
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from astropy.io import fits

from ..config import SOLEXS_RAW
from ..store import to_ts, write_series

_ZIP_RE = re.compile(r"AL1_SLX_L1_(\d{8})_v[\d.]+\.zip")


def _open_gz_fits(zf: zipfile.ZipFile, member: str):
    with gzip.open(io.BytesIO(zf.read(member))) as g:
        return fits.open(io.BytesIO(g.read()), memmap=False)


def _gtis(hdul) -> list[tuple[float, float]]:
    tab = hdul[1].data
    return [(float(a), float(b)) for a, b in zip(tab["START"], tab["STOP"])]


def read_solexs_zip(zip_path: Path) -> dict[str, pd.DataFrame]:
    """Return {detector: unified_df} for one daily SoLEXS zip."""
    out: dict[str, pd.DataFrame] = {}
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.namelist()
        for det in ("SDD1", "SDD2"):
            lc_members = [m for m in members if f"/{det}/" in m and m.endswith(".lc.gz")]
            if not lc_members:
                continue
            hdul = _open_gz_fits(zf, lc_members[0])
            tab = hdul[1].data
            t = np.asarray(tab["TIME"], dtype=float)
            rate = np.asarray(tab["COUNTS"], dtype=float)
            # COUNTS may be raw counts per bin; TIMEDEL tells bin width.
            td = float(hdul[1].header.get("TIMEDEL", 1.0))
            if td != 1.0:
                rate = rate / td
            err = np.sqrt(np.clip(rate, 0, None))
            gtis = []
            gti_members = [m for m in members if f"/{det}/" in m and m.endswith(".gti.gz")]
            if gti_members:
                hg = _open_gz_fits(zf, gti_members[0])
                gtis = _gtis(hg)
                hg.close()
            good = np.zeros(len(t), dtype=bool)
            for s, e in gtis:
                good |= (t >= s) & (t < e)
            if not gtis:  # be permissive if GTI file missing
                good[:] = True
            out[det] = pd.DataFrame(
                {"ts": to_ts(pd.Series(t)), "rate_cps": rate, "err_cps": err, "is_good": good}
            )
            hdul.close()
    return out


def ingest_all(limit: int | None = None) -> pd.DataFrame:
    """Ingest every SoLEXS zip into the parquet store; return a summary."""
    rows = []
    zips = sorted(SOLEXS_RAW.glob("*.zip"))
    for i, zp in enumerate(zips):
        m = _ZIP_RE.match(zp.name)
        if not m:
            continue
        day = m.group(1)
        try:
            dets = read_solexs_zip(zp)
        except Exception as e:  # pragma: no cover
            print(f"[solexs] FAILED {zp.name}: {e}")
            continue
        for det, df in dets.items():
            write_series("solexs", det, day, df)
            rows.append(
                dict(day=day, detector=det, n=len(df),
                     good_frac=float(df.is_good.mean()),
                     median_cps=float(df.rate_cps.median()),
                     max_cps=float(df.rate_cps.max()))
            )
        if limit and i + 1 >= limit:
            break
    return pd.DataFrame(rows)


if __name__ == "__main__":  # pragma: no cover
    print(ingest_all().to_string())
