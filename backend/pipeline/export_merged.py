"""Build merged single-file datasets from ALL ingested PRADAN data.

One streaming pass over every processed per-day parquet (the direct product
of the ISRO PRADAN Level-1 zips) writes:

    backend/data/merged/solexs_merged.parquet / .csv
        All SoLEXS days (SDD2 ingested) — soft X-ray light curves.
    backend/data/merged/hel1os_merged.parquet / .csv
        All HEL1OS days x detectors — hard X-ray light curves + band.
    backend/data/merged/merged_all_data.parquet / .csv
        Every instrument/detector in one table (superset schema).
    backend/data/merged/manifest.json
        Row counts, date ranges, source-zip stats, flare-catalog counts.

Unified row schema
    instrument, detector, date (UTC day), ts (naive UTC), rate_cps,
    err_cps, is_good [, band_lo_kev, band_hi_kev for HEL1OS]

Rows are kept sorted by instrument -> detector -> time. NaN rate rows
(SoLEXS data gaps) are preserved as nulls in parquet / empty CSV fields.

Run:  python -m backend.pipeline.export_merged
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from .config import CATALOGS, PROCESSED, RAW_ROOT, REPO_ROOT
from .store import available_days

OUT_DIR = REPO_ROOT / "backend" / "data" / "merged"

COMBINED_SCHEMA = pa.schema([
    ("instrument", pa.string()),
    ("detector", pa.string()),
    ("ts", pa.timestamp("us")),
    ("rate_cps", pa.float64()),
    ("err_cps", pa.float64()),
    ("is_good", pa.bool_()),
    ("band_lo_kev", pa.float64()),
    ("band_hi_kev", pa.float64()),
    ("date", pa.string()),
])


def _day_date(day: str) -> str:
    return f"{day[0:4]}-{day[4:6]}-{day[6:8]}"


def _block(inst: str, det: str, day: str) -> pa.Table:
    """One per-day parquet as an arrow table in the combined schema."""
    df = pd.read_parquet(PROCESSED / inst / det / f"{day}.parquet")
    df["ts"] = df["ts"].astype("datetime64[us]")
    if "rate_cps" in df:
        df["rate_cps"] = np.round(df["rate_cps"], 6)
    if "err_cps" in df:
        df["err_cps"] = np.round(df["err_cps"], 6)
    n = len(df)
    tbl = pa.Table.from_pandas(df, preserve_index=False)
    cols = {
        "instrument": pa.array(np.full(n, inst), type=pa.string()),
        "detector": pa.array(np.full(n, det), type=pa.string()),
        "ts": tbl.column("ts").cast(pa.timestamp("us")),
        "rate_cps": tbl.column("rate_cps"),
        "err_cps": tbl.column("err_cps"),
        "is_good": tbl.column("is_good"),
        "band_lo_kev": tbl.column("band_lo_kev") if "band_lo_kev" in tbl.column_names
        else pa.array(np.full(n, None, dtype="float64")),
        "band_hi_kev": tbl.column("band_hi_kev") if "band_hi_kev" in tbl.column_names
        else pa.array(np.full(n, None, dtype="float64")),
        "date": pa.array(np.full(n, _day_date(day)), type=pa.string()),
    }
    return pa.table(cols, schema=COMBINED_SCHEMA)


class _Sink:
    """Paired parquet + CSV writer for one output stem."""

    def __init__(self, stem: str, schema: pa.Schema) -> None:
        self.pq_path = OUT_DIR / f"{stem}.parquet"
        self.csv_path = OUT_DIR / f"{stem}.csv"
        self.rows = 0
        self.first_ts: pd.Timestamp | None = None
        self.last_ts: pd.Timestamp | None = None
        self._pq = pq.ParquetWriter(self.pq_path, schema, compression="snappy")
        self._csv = pacsv.CSVWriter(
            self.csv_path.open("wb"), schema,
            write_options=pacsv.WriteOptions(include_header=True, batch_size=65536),
        )

    def write(self, tbl: pa.Table) -> None:
        self._pq.write_table(tbl)
        self._csv.write_table(tbl)
        self.rows += tbl.num_rows
        ts = tbl.column("ts").to_pylist()
        if ts:
            f, l = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])
            self.first_ts = f if self.first_ts is None else min(self.first_ts, f)
            self.last_ts = l if self.last_ts is None else max(self.last_ts, l)

    def close(self) -> dict:
        self._pq.close()
        self._csv.close()
        return {
            "rows": self.rows,
            "t_start": str(self.first_ts),
            "t_end": str(self.last_ts),
            "parquet": str(self.pq_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "parquet_mb": round(self.pq_path.stat().st_size / 1e6, 1),
            "csv": str(self.csv_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "csv_mb": round(self.csv_path.stat().st_size / 1e6, 1),
        }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[merged] streaming {PROCESSED} -> {OUT_DIR}")

    plan: list[tuple[str, str, list[str]]] = []
    for inst, dets in (("solexs", ["SDD1", "SDD2"]),
                       ("hel1os", ["CDTE1", "CDTE2", "CZT1", "CZT2"])):
        for det in dets:
            days = available_days(inst, det)
            if days:
                plan.append((inst, det, days))

    prov: dict = {"solexs": {"detectors": {}}, "hel1os": {"detectors": {}}}
    sink_s = _Sink("solexs_merged", COMBINED_SCHEMA)
    sink_h = _Sink("hel1os_merged", COMBINED_SCHEMA)
    sink_c = _Sink("merged_all_data", COMBINED_SCHEMA)

    for inst, det, days in plan:
        n_rows = 0
        for day in days:
            tbl = _block(inst, det, day)
            (sink_s if inst == "solexs" else sink_h).write(tbl)
            sink_c.write(tbl)
            n_rows += tbl.num_rows
        prov[inst]["detectors"][det] = {
            "n_days": len(days), "rows": n_rows,
            "first_day": days[0], "last_day": days[-1],
        }
        print(f"  {inst}/{det}: {len(days)} days, {n_rows:,} rows")

    files = {"solexs_merged": sink_s.close(), "hel1os_merged": sink_h.close(),
             "merged_all_data": sink_c.close()}
    for inst in prov:
        prov[inst]["rows"] = sum(d["rows"] for d in prov[inst]["detectors"].values())

    raw_zip_stats: dict = {}
    for name in ("solexs", "hel1os"):
        d = RAW_ROOT / name
        zips = list(d.glob("*.zip")) if d.is_dir() else []
        raw_zip_stats[name] = {
            "n_zips": len(zips),
            "total_mb": round(sum(f.stat().st_size for f in zips) / 1e6, 1),
        }

    flare_counts: dict = {}
    for stem in ("events_solexs", "events_hel1os", "master_catalog"):
        p = CATALOGS / f"{stem}.parquet"
        flare_counts[stem] = int(len(pd.read_parquet(p))) if p.exists() else 0

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "ISRO Aditya-L1 Level-1 SoLEXS + HEL1OS, downloaded from ISSDC PRADAN",
        "description": "Merged clean light-curve datasets: one row per second "
                       "(SoLEXS SDD2) or per ~1 s accumulated count (HEL1OS; "
                       "flare detection bins these to 60 s) with UTC timestamp, "
                       "count rate, error and good-time flag. Produced by "
                       "backend/pipeline/export_merged.py.",
        "row_schema": {f.name: str(f.type) for f in COMBINED_SCHEMA},
        "note_xlsx": "CSV files exceed Excel's 1,048,576-row sheet limit; "
                     "open the parquet files with pandas/pyarrow for full data.",
        "raw_zips": raw_zip_stats,
        "files": files,
        "provenance": prov,
        "flares": flare_counts,
    }
    mp = OUT_DIR / "manifest.json"
    mp.write_text(json.dumps(manifest, indent=2))

    for stem, info in files.items():
        print(f"  {stem}: {info['rows']:,} rows | parquet {info['parquet_mb']} MB | "
              f"csv {info['csv_mb']} MB")
    print(f"[merged] manifest -> {mp}")


if __name__ == "__main__":
    main()
