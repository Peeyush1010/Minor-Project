# ⚡ Aditya-L1 Flare Watch — Project Explainer

## The Problem (1 paragraph)

Solar flares are violent bursts of X-ray radiation from the Sun that can damage satellites, disrupt GPS, and knock out power grids. ISRO's Aditya-L1 spacecraft sits at a special point 1.5 million km from Earth, watching the Sun with two X-ray instruments: **SoLEXS** (soft X-rays) and **HEL1OS** (hard X-rays). **This minor project solves the *nowcasting* half of Problem Statement 15: detect flares the moment they happen, from both instruments combined, and show them live.** The *forecasting* half (predicting a flare before it peaks) is built as a prototype but deliberately kept as **future work for the Major project**.

---

## What We Built (minor project)

| Piece | What it does |
|---|---|
| **Ingestion** | Reads FITS files (astronomy format) from SoLEXS and HEL1OS, converts them to clean tables |
| **Detection (the core)** | Automatically finds flares in X-ray light curves using a physics-informed algorithm |
| **Cross-match** | Combines soft and hard X-ray detections into one master catalog |
| **Calibration** | Converts raw instrument counts into standard GOES flare classes (A/B/C/M/X) using NOAA data |
| **Merged datasets** | Every downloaded observation flattened into single files per instrument (`backend/data/merged/`) |
| **Dashboard** | React web interface showing live light curves, flare bands, and real-time alert replay |

> 🔮 **Not in this project's scope (future / Major project):** the LightGBM
> forecast model (P(flare ≤ 30 min), AUC 0.82 prototype). The dashboard shows it
> in one clearly-marked *FUTURE WORK* panel — it will be attached to the Major
> project.

---

## Pipeline Walkthrough (plain language)

### Stage 1: Ingestion — "FITS → spreadsheets"

The satellite sends data as FITS files (the astronomy standard — like a zip of tables and images). Our reader extracts the time-stamped X-ray count rates and good-time-interval flags, then saves them as Parquet tables (a fast columnar format). We handle two detectors per instrument (SDD1/SDD2 for SoLEXS, CDTE/CZT for HEL1OS).

### Stage 2: Detection — "Hearing a shout above room noise" *(the heart of the minor project)*

We need to find flares in a noisy signal. The algorithm works like this:

1. **Estimate background**: the Sun's quiet-state X-ray level (rolling minimum over 45 minutes — immune to flares because flares only push counts *up*)
2. **Smooth**: boxcar average to kill random photon noise
3. **Set threshold**: if the smoothed signal stays above the background by 5 standard deviations for 30 seconds, that's a flare start
4. **Find the peak and end**: track when the signal decays back to background
5. **Merge nearby events**: if two bursts happen close together, count as one flare

For HEL1OS (which is photon-starved — sometimes zero counts per second), we first combine data into 60-second bins to get meaningful statistics.

### Stage 3: Cross-match — "Two cameras, one event"

When the same flare is seen by both SoLEXS (soft) and HEL1OS (hard), we link them into one entry in the master catalog. This is where the **Neupert effect** shows up: hard X-ray peaks arrive *before* soft X-ray peaks, giving us a natural precursor signal.

### Stage 4: Classification — "Converting numbers into A/B/C/M/X"

The standard flare classification (A, B, C, M, X) is based on GOES satellite flux in the 1–8 Å band. We download GOES reference data, match our detections against it, then fit a log-log linear model: `GOES flux = 0.87 × log(counts) − 7.41`. This lets us assign classes to any detection, even without GOES data.

### Stage 5: Merged datasets — "Everything in one file"

All 225 downloaded PRADAN zips end up as **three single files** (parquet + CSV each): one for all SoLEXS data, one for all HEL1OS data, and one combined — 21.2 million timestamped rows with UTC time, count rate, error and good-time flag. See [DATASET.md](DATASET.md).

### 🔮 Future: Forecast — "Knowing a sneeze is coming by watching the buildup" *(Major project)*

A LightGBM classifier was prototyped on trailing-window features (rate stats, excess over background, time since last flare, HEL1OS hard-X channels). It predicts "will a C-class-or-better flare peak within 30 minutes?" with AUC 0.82 and 3–13 min lead time on held-out data. This module will be the core of the Major project.

---

## Key Results (nowcast — minor project)

| Metric | Number | What it means |
|---|---|---|
| Flares detected | 2,891 | Automated nowcast database, soft+hard combined |
| Hard X-ray matches | 14 | Combined soft+hard detection confirmed in the overlap window |
| Hard-X lead time | 117 s median | Neupert-effect precursor validated |
| Detection TPR | 93.5% overall | X: 100%, M: 95%, C: 93% (vs NOAA GOES-16) |
| False alarm rate | 4.7/day | Most are real small flares below GOES threshold |
| Merged dataset | 21.2M rows | All PRADAN downloads in single files |

🔮 *Future/Major:* forecast AUC 0.82, lead 3–13 min (prototype, out of minor scope).

---

## The Science Story

**The Neupert Effect**: When a solar flare happens, high-energy electrons crash into the solar surface first (hard X-rays detected by HEL1OS), and then the heated plasma glows afterward (soft X-rays detected by SoLEXS). So HEL1OS sees the flare *before* SoLEXS does.

In our data, hard X-ray peaks precede soft X-ray peaks by a **median of 117 seconds** (up to 458 s). This physical precursor is exactly why the mission flies both instruments — and it will be the basis for forecasting in the Major project.

**Sub-GOES sensitivity**: Our "false alarms" aren't false — they're real C6–C8 class events that GOES's own catalog doesn't include. SoLEXS is actually more sensitive than our reference standard, which is a strength, not a weakness.

---

## Demo Script (2 minutes, for mentors/judges)

1. **Open the dashboard** — point at header: "2,891 flares nowcasted, 93.5% detection rate validated against GOES"
2. **Set date to May 14, 2024** — "This was an X8.7 storm, the biggest flare Aditya-L1 observed"
3. **Show the light curve** — dramatic spike on log scale, colored bands marking detected flares
4. **Switch to September 12, 2026** — the soft+hard overlap window
5. **Point to the Hard X / Lead columns** in the catalog — "hard X-rays arrive ~2 minutes *before* soft — the Neupert effect"
6. **Click "▶ Start replay"** — light curve streams, red toast pops when the flare fires — "this is the nowcast working live"
7. **Open "Dataset" in the nav** — "every downloaded PRADAN file merged into single deliverable files"
8. **Point at the purple FUTURE WORK panel** — "forecasting prototype exists; it becomes the Major project"
9. **Open "📖 Guide & Glossary"** in the nav — "every keyword on this page is explained
   in plain words with a pointer to where it appears on the dashboard — ask me about any term"

---

## Glossary

| Term | Meaning |
|---|---|
| **SoLEXS** | Soft X-ray Spectrometer (1–22 keV) — sees the hot plasma glow |
| **HEL1OS** | Hard X-ray Spectrometer (5–160 keV) — sees the electron impacts |
| **FITS** | Flexible Image Transport System — standard astronomy file format |
| **GTI** | Good Time Intervals — periods when the instrument was working |
| **Flare class** | A = tiny, B = small, C = common, M = medium, X = massive |
| **GOES** | US weather satellite measuring solar flares since the 1970s — our reference |
| **TPR** | True Positive Rate — what fraction of real flares did we detect? |
| **FAR** | False Alarm Rate — how many wrong alerts per day? |
| **Neupert Effect** | Hard X-ray emission precedes soft X-ray emission in flares |
| **Nowcasting** | Detecting a flare that is happening right now *(this project)* |
| **Forecasting** | Predicting a flare before it happens *(future / Major project)* |

---

## Files You Should Know About

| File | What it is |
|---|---|
| `README.md` | Project overview, architecture, run steps |
| `DATASET.md` | The merged dataset deliverable (files, columns, coverage) |
| `EVALUATION.md` | Full metrics tables |
| `RUN_GUIDE.md` | Step-by-step VS Code setup and run |
| `EXPLAINER.md` | This document |
| `backend/pipeline/ingest/` | FITS readers for SoLEXS and HEL1OS |
| `backend/pipeline/detect/` | Flare detection engine + tests |
| `backend/pipeline/catalog/` | Cross-match + master catalog |
| `backend/pipeline/export_merged.py` | Builds the merged dataset files |
| `backend/pipeline/forecast/` | 🔮 FUTURE (Major project): ML forecasting model |
| `backend/pipeline/eval/` | GOES calibration + TPR/FAR evaluation |
| `backend/app/main.py` | FastAPI server |
| `frontend/src/App.jsx` | React dashboard |
| `frontend/src/GuidePage.jsx` | In-app Guide & Glossary page (keyword explanations) |
| `dataset/solexs/`, `dataset/hel1os/` | Raw PRADAN zips |
| `backend/data/merged/` | ✅ Merged dataset files + manifest |
