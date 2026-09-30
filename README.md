# ⚡ Aditya-L1 Flare Watch — Solar-Flare Nowcasting (Minor Project)

**Minor project scope: NOWCASTING** — detecting solar flares the moment they
happen, from combined **soft (SoLEXS)** and **hard (HEL1OS)** X-ray light curves
of ISRO's Aditya-L1 mission (hackathon Problem Statement 15).

> 🔮 **Forecasting is future work (Major project).** A working forecast prototype
> (LightGBM, AUC 0.82, ~3–13 min lead) already exists in this repo, but it is
> **intentionally kept out of the minor-project scope** and will be attached to
> the Major project. It is shown in the dashboard only as a clearly-marked
> *FUTURE WORK* preview.

---

## Scope at a glance

| | Minor project (this repo, now) | Major project (future) |
|---|---|---|
| Flare **nowcasting** from SoLEXS + HEL1OS | ✅ core deliverable | — |
| Automated flare database (soft+hard cross-matched) | ✅ 2,891 flares | extended as data grows |
| Counts → GOES class calibration | ✅ validated vs NOAA GOES-16 | — |
| Merged single-file datasets (all PRADAN data) | ✅ `backend/data/merged/` | — |
| Interactive dashboard with live-alert replay | ✅ | — |
| **Forecast** P(flare ≤ 30 min) + lead times | 🔮 prototype only | ✅ main deliverable |

## What the minor project delivers

| Outcome | Where |
|---|---|
| Automated database of nowcasted flares (soft+hard combined) | `backend/data/catalogs/master_catalog.parquet` — 2,891 flares; 14 with hard-X matches in the overlap window |
| Validated detection accuracy vs NOAA GOES-16 | TPR **93.5%** (X 100%, M 95.3%, C 92.9%), FAR 4.7/day — residual "false alarms" are real C6–C8 events *below GOES's detection floor* (SoLEXS is more sensitive than the reference) |
| Physical precursor (Neupert effect) | HEL1OS hard-X peaks lead SoLEXS soft-X peaks by **median 117 s** (max 458 s) in cross-matched events |
| **Merged dataset — all downloaded PRADAN data in single files** | `backend/data/merged/` (parquet + CSV + manifest; see below) |
| Interface visualizing light curves with visual alerts | React dashboard: guided 3-step flow, live charts, replay with real-time alert toasts |

## Merged dataset (all PRADAN downloads → one file per instrument)

Built by [`backend/pipeline/export_merged.py`](backend/pipeline/export_merged.py)
in one streaming pass over the processed store; documented in [DATASET.md](DATASET.md).

| File (parquet + CSV) | Rows | Content |
|---|---|---|
| `backend/data/merged/solexs_merged.*` | 17,539,200 | All 203 SoLEXS days (SDD2), 1-s soft X-ray rates |
| `backend/data/merged/hel1os_merged.*` | 3,665,558 | All 12 days × 4 HEL1OS detectors, ~1-s hard X-ray rates + band |
| `backend/data/merged/merged_all_data.*` | 21,204,758 | Both instruments in one table |
| `backend/data/merged/manifest.json` | — | Row counts, date ranges, source-zip stats, schema |

Rebuild anytime: `python -m backend.pipeline.export_merged`

## Architecture

```
dataset/                     raw PRADAN zips (SoLEXS daily, HEL1OS 12-h segments)
backend/
  pipeline/
    ingest/solexs.py         FITS reader: 1-s TIME/COUNTS + GTIs → parquet
    ingest/hel1os.py         FITS reader: MJD/CTR per band + GTIs → parquet
    store.py                 unified parquet store (ts, rate_cps, err_cps, is_good)
    detect/timeseries.py     gap-aware smoothing, rolling-min background, resampling
    detect/detector.py       nowcast engine (σ-threshold + sustain + merge; 6 unit tests)
    catalog/master.py        cross-match soft+hard → master catalog
    export_merged.py         merged single-file datasets + manifest  ← NEW
    forecast/model.py        🔮 FUTURE (Major project): LightGBM P(flare ≤ 30 min)
    eval/goes.py             GOES download, reference flares, counts→flux calibration
    eval/metrics.py          TPR / FAR / per-class evaluation
    run_detection.py         detection over the whole store
    run_goes.py              calibration driver
    run_eval.py              evaluation driver
  app/main.py                FastAPI: lightcurve, flares, dataset, summary, WS replay
  data/                      processed parquet, catalogs, merged/, GOES (generated)
frontend/                    React 19 + Vite + Recharts dark-ops dashboard
```

## Running

```bash
pip install -r requirements.txt

# 1) ingest raw zips → unified parquet
python -m backend.pipeline.ingest.solexs
python -m backend.pipeline.ingest.hel1os

# 2) detect flares + build master catalog
python -m backend.pipeline.run_detection

# 3) GOES calibration + classes + reference list
python -m backend.pipeline.run_goes

# 4) evaluation report (TPR/FAR vs GOES)
python -m backend.pipeline.run_eval

# 5) merged single-file datasets (parquet + CSV + manifest)
python -m backend.pipeline.export_merged

# 6) serve API + UI
python -m uvicorn backend.app.main:app --port 8000
cd frontend && npm install && npm run dev    # http://localhost:5173
```

Tests: `python -m pytest -q` (synthetic light curves → detector precision/recall,
background immunity, gap handling, merge logic).

## Methods (nowcast)

Per detector: boxcar-smoothed rate → flare-immune rolling-min background
(recentered) → local Poisson σ(t) = √(B/n_eff) → start when the smoothed rate
exceeds 5σ for 30 s; end on decay below 1.5σ or a 6-h cap (particle-event
guard); merge episodes within 300 s; independent detection per instrument then
cross-match (±300 s) into the master catalog. HEL1OS is detected on 60-s binned
rates (photon-starved 1-s samples are mostly zero).

Classification: SoLEXS peak counts → GOES 1–8 Å flux via log-log regression
(slope 0.87, intercept −7.41, scatter 0.095 dex, n = 435 matched events), then
standard B/C/M/X thresholds on the proxy flux.

### 🔮 Future work — forecasting (Major project)

60-s trailing features (rate stats over 5/15/60 min, excess over background in
σ, slope, time-since-last-flare, HEL1OS trailing rates) → LightGBM predicting
P(C+ flare within 30 min); time-blocked 75/25 split; threshold at FAR = 2/day;
lead = first alert → peak. Prototype results: AUC 0.82, 6/6 test flares
alerted, median lead 192 s, p90 798 s. This module will be the core of the
Major project and is deliberately out of minor-project scope.

## Data sources

- Aditya-L1 SoLEXS & HEL1OS Level-1 (ISSDC PRADAN portal) — SoLEXS: 2024-02-12,
  2024-03-14→05-31, 2026-05-06→09-17; HEL1OS: 2026-09-07→09-18
- NOAA GOES-16 XRS 1-min (1–8 Å / 0.5–4 Å) for calibration + ground truth
  (auto-downloaded from data.ngdc.noaa.gov)
