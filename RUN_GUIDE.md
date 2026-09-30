# 🚀 Running the Project in VS Code

> **Minor project = nowcasting.** The forecast step below is marked 🔮 — it is
> future work for the Major project and optional for the minor demo.

## Prerequisites

| Tool | Check | Install |
|---|---|---|
| Python 3.11+ | `python --version` | python.org (tick "Add to PATH") |
| Node.js 18+ | `node --version` | nodejs.org (LTS) |
| VS Code | — | code.visualstudio.com |

## 1. Open the project

`File → Open Folder…` → select your project folder.

Install these extensions (search in Extensions panel):
- **Python** (ms-python.python)
- **Pylance** (ms-python.vscode-pylance)

## 2. Create a virtual environment

Open the VS Code terminal (**Ctrl + `** or `Terminal → New Terminal`):

```powershell
python -m venv .venv
.\.venv\Scripts\activate        # Windows
# source .venv/bin/activate     # macOS/Linux
```

VS Code will ask *"Select the Python environment?"* → choose **`.venv`**.
Or press **Ctrl+Shift+P** → "Python: Select Interpreter" → pick `.venv`.

## 3. Install Python dependencies

```powershell
pip install -r requirements.txt
```

## 4. Install frontend dependencies

```powershell
cd frontend
npm install
cd ..
```

## 5. Run the app (two terminals)

Open **two terminals** (click the `+` icon in the terminal panel):

**Terminal 1 — Backend API:**
```powershell
python -m uvicorn backend.app.main:app --port 8000 --reload
```
Wait for `Application startup complete.`

**Terminal 2 — Frontend:**
```powershell
cd frontend
npm run dev
```
Wait for `Local: http://localhost:5173/` → **Ctrl+Click** it (or open in browser).

### F5 Debug Option

With the .vscode configs installed:
- Press **F5** to launch the backend in debug mode
- Open `Run and Debug` panel (Ctrl+Shift+D) → pick "Start Frontend" task

## 6. Rebuild from scratch (if data is missing)

If the dashboard shows "no data", run these commands **in order** from the project root:

```powershell
# 1. Ingest raw zips → parquet (~5 minutes)
python -m backend.pipeline.ingest.solexs
python -m backend.pipeline.ingest.hel1os

# 2. Detect flares → master catalog
python -m backend.pipeline.run_detection

# 3. Download GOES + calibrate + classify
python -m backend.pipeline.run_goes

# 4. Evaluation report (TPR/FAR)
python -m backend.pipeline.run_eval

# 5. Merged dataset files (parquet + CSV, ~1 minute)
python -m backend.pipeline.export_merged

# 6. (🔮 FUTURE / Major project) Train forecast model
python -m backend.pipeline.forecast.model
```

## 7. Tests

```powershell
python -m pytest -q               # 6 detector tests (~1 s)
cd frontend && npm run build      # verify UI compiles
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No module named backend` | Run from the **project root**, not inside `backend/` |
| Dashboard shows "no data" | Run the rebuild commands (step 6) |
| Port 8000 in use | `netstat -ano | findstr :8000` → `taskkill /PID <pid> /F`, or use `--port 8001` |
| `pip install` fails | Use Python 3.11 or 3.12 (not 3.13) |
| Charts empty for a date | That date may not have data in `dataset/solexs/` |
| Frontend can't reach API | Backend must be running; check `frontend/src/api.js` port |
| WebSocket replay not connecting | Ensure backend is on port 8000 (same as api.js) |

## What You Should See

The **Aditya-L1 Flare Watch** dashboard (minor project = nowcast):
- Header stat cards (2891 flares, hard-X lead, TPR, FAR)
- Guided 3-step flow: **1 Choose** a date → **2 Watch** the light curve → **3 Replay** live alerts
- Light curve with flare bands + peak markers and plain-language hints
- Live replay with alert toasts (the nowcast in action)
- Master flare catalog (filterable by X/M/C/B class)
- Merged-dataset card (what was merged, sizes, dates covered)
- One clearly-marked 🔮 **FUTURE WORK** panel: the forecast prototype (Major project)
- **📖 Guide & Glossary page** (nav bar) — every project keyword explained in plain
  words with "where you see it" pointers; ideal while presenting to mentors
