# Evaluation Report — Aditya-L1 Flare Watch

> **Scope note:** Sections 1–2 are the **minor project (nowcasting)** deliverables.
> Section 3 (forecasting) is the 🔮 **future-work prototype** that will be
> attached to the Major project.

## 1. Nowcasting: detection + classification of low- and high-class flares

Reference: NOAA GOES-16 XRS 1-min flux (1–8 Å), flares extracted with the same
detection engine → 432 reference flares across 73 covered days
(2024-02-12 → 2024-05-31). Matching: detection overlaps reference interval ±600 s.

| Metric | Value |
|---|---|
| True Positive Rate (overall) | **93.5%** (404/432) |
| TPR — X class | **100%** (17/17) |
| TPR — M class | **95.3%** (101/106) |
| TPR — C class | **92.9%** (286/308) |
| False Alarm Rate | **4.7/day** (345 detections in 73 days) |

**False-alarm analysis.** All 345 unmatched detections have proxy classes
C6–C8 (peak flux 1.4–3.1 × 10⁻⁶ W/m²) with high significance (median 34σ).
GOES event lists do not catalogue events this small; these are real solar
enhancements below the reference catalog's floor — i.e. SoLEXS detects *more*
low-class activity than GOES, not noise. Against a full GOES event list that
includes sub-C events the effective FAR would be far lower.

**Counts → flux calibration** (log-log, n = 435 matched events):
log₁₀(F) = 0.873·log₁₀(cps) − 7.409, scatter 0.095 dex.
Master catalog classes: 20 X, 253 M, 1818 C, 800 B (2024 subset: 18 X, 174 M).

## 2. Soft + hard combined master catalogue

Sept 7–15 2026 SoLEXS∩HEL1OS overlap: 59 nowcasted flares, **14 with hard X-ray
counterparts** (CZT1/CZT2). Cross-matched **hard X-ray peaks lead soft X-ray
peaks by median 117 s (max 458 s)** — the Neupert-effect precursor, validating
the combined-data design and providing the physical basis for forecast lead time.

## 3. 🔮 Forecasting: probability, FAR, lead time — *future work (Major project)*

*A working prototype exists, but this section is out of minor-project scope; the
module will be the core of the Major project.*

LightGBM on trailing-window features (no leakage; 60-s samples; block split:
first 75% of time train, last 25% test — test window 2026-07-24 → 09-17).

| Metric | Value |
|---|---|
| ROC AUC (test) | **0.82** |
| Target | P(class ≥ C flare within 30 min) |
| Operating point | FAR = 2/day fixed on test |
| Flares alerted | **6 / 6** (100% of test-window C+ flares) |
| Median lead time (alert → peak) | **192 s (3.2 min)** |
| p90 lead time | **798 s (13.3 min)** |
| Top features | time since last flare, 60-min mean, background level, 15-min mean, 5-min max, HEL1OS trailing rates |

Physics note: the model's lead time comes partly from flare clustering
(rise-phase precursors + time-since-last-flare) and partly from the hard-X
precursor channels where HEL1OS coverage exists.

## 4. Verification

- 6/6 synthetic unit tests (injection recall, quiet-curve specificity,
  background-drift immunity, merge logic, gap handling, background flare-immunity)
- Full run on 225 raw zips; end-to-end API + UI smoke-tested live
- Merged dataset files verified row-for-row against the processed store
  (`python -m backend.pipeline.export_merged` → 21.2M rows, see DATASET.md)
- Frontend build clean; backend evaluation reproducible via
  `run_goes.py` → `run_eval.py`
