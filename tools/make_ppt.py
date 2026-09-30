"""Generate the 10-slide mentor presentation: Aditya-L1 Flare Watch (minor project).

Run:  python tools/make_ppt.py          ->  slides/Aditya-L1_Flare_Watch.pptx
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "slides"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- palette
BG = RGBColor(0x0B, 0x12, 0x20)      # deep navy
CARD = RGBColor(0x10, 0x1A, 0x2E)
ACCENT = RGBColor(0x38, 0xBD, 0xF8)  # cyan
GOLD = RGBColor(0xF5, 0x9E, 0x0B)
PURPLE = RGBColor(0xA7, 0x8B, 0xFA)
RED = RGBColor(0xEF, 0x44, 0x44)
GREEN = RGBColor(0x34, 0xD3, 0x99)
TXT = RGBColor(0xE2, 0xE8, 0xF0)
MUT = RGBColor(0x94, 0xA3, 0xB8)

SW, SH = Inches(13.333), Inches(7.5)

prs = Presentation()
prs.slide_width = SW
prs.slide_height = SH


def blank_slide():
    s = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = BG
    return s


def box(slide, x, y, w, h, fill=CARD, line=None):
    from pptx.enum.shapes import MSO_SHAPE
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    if line:
        sh.line.color.rgb = line
        sh.line.width = Pt(1.25)
    else:
        sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def _norm_line(line):
    """Flatten any nesting so every element is a (text, size, color, bold) 4-tuple."""
    if isinstance(line, (list, tuple)) and len(line) == 4 and isinstance(line[0], str):
        return [line]
    parts = []
    stack = line if isinstance(line, list) else [line]
    for el in stack:
        if isinstance(el, list):
            parts.extend(_norm_line(el))
        elif isinstance(el, tuple) and len(el) == 4 and isinstance(el[0], str):
            parts.append(el)
        else:
            parts.append((str(el), None, None, None))
    return parts


def text(slide, x, y, w, h, runs, size=18, color=TXT, bold=False,
         align=PP_ALIGN.LEFT, font="Calibri", line_spacing=1.0):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    lines = runs if isinstance(runs, list) else [runs]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        for part, psize, pcolor, pbold in _norm_line(line):
            r = p.add_run()
            r.text = part
            r.font.size = Pt(psize if psize else size)
            r.font.color.rgb = pcolor if pcolor else color
            r.font.bold = pbold if pbold is not None else bold
            r.font.name = font
    return tb


def kicker(slide, label, color=ACCENT):
    text(slide, Inches(0.6), Inches(0.35), Inches(9), Inches(0.4),
         label.upper(), size=13, color=color, bold=True)


def title(slide, main, sub=None, color=TXT):
    text(slide, Inches(0.6), Inches(0.7), Inches(12.1), Inches(0.9),
         main, size=32, color=color, bold=True)
    if sub:
        text(slide, Inches(0.6), Inches(1.45), Inches(12.1), Inches(0.5),
             sub, size=15, color=MUT)


def footer(slide, n):
    text(slide, Inches(0.6), Inches(7.05), Inches(8), Inches(0.35),
         "Aditya-L1 Flare Watch · Minor Project · Solar-Flare Nowcasting", size=11, color=MUT)
    text(slide, Inches(12.2), Inches(7.05), Inches(0.7), Inches(0.35),
         str(n), size=11, color=MUT, align=PP_ALIGN.RIGHT)


def stat_card(slide, x, y, w, h, value, label, note=None, vcolor=ACCENT):
    box(slide, x, y, w, h)
    text(slide, x + Inches(0.18), y + Inches(0.14), w - Inches(0.36), Inches(0.6),
         value, size=30, color=vcolor, bold=True)
    text(slide, x + Inches(0.18), y + Inches(0.78), w - Inches(0.36), Inches(0.4),
         label, size=13.5, color=TXT, bold=True)
    if note:
        text(slide, x + Inches(0.18), y + Inches(1.14), w - Inches(0.36), Inches(0.55),
             note, size=11, color=MUT)


# ================================================================ slide 1
s = blank_slide()
box(s, Inches(0.6), Inches(2.5), Inches(0.14), Inches(2.2), fill=ACCENT)
text(s, Inches(1.0), Inches(2.35), Inches(11.6), Inches(1.1),
     "⚡ Aditya-L1 Flare Watch", size=54, color=TXT, bold=True)
text(s, Inches(1.0), Inches(3.5), Inches(11.6), Inches(0.7),
     "Real-time solar-flare NOWCASTING from soft + hard X-rays", size=26, color=ACCENT, bold=True)
text(s, Inches(1.0), Inches(4.35), Inches(11.6), Inches(0.5),
     "ISRO Hackathon · Problem Statement 15  ·  Minor Project — presented by Peeyush Raj",
     size=16, color=MUT)
for i, (val, lab, col) in enumerate([("2,891", "FLARES NOWCASTED", ACCENT),
                            ("93.5%", "DETECTION RATE", GREEN),
                            ("117 s", "HARD-X PRECURSOR", GOLD),
                            ("21.2M", "ROWS MERGED", PURPLE)]):
    stat_card(s, Inches(1.0 + i * 2.95), Inches(5.1), Inches(2.7), Inches(1.55), val, lab, None, col)
footer(s, 1)

# ================================================================ slide 2
s = blank_slide()
kicker(s, "The problem & why it matters")
title(s, "Solar flares break technology. We need to see them live.")
box(s, Inches(0.6), Inches(2.0), Inches(5.9), Inches(4.6))
text(s, Inches(0.9), Inches(2.25), Inches(5.3), Inches(4.1), [
    [[("The threat", 17, ACCENT, True)],
     [("Flares are sudden X-ray explosions on the Sun that can:", 14, TXT, False)],
     [("•  fry satellite electronics", 14, TXT, False)],
     [("•  black out GPS & radio for hours", 14, TXT, False)],
     [("•  collapse power grids (1989 Quebec)", 14, TXT, False)],
     [("", 8, TXT, False)],
     [("The opportunity", 17, ACCENT, True)],
     [("Aditya-L1, ISRO's solar observatory at the L1 point, watches the Sun "
       "24×7 with two X-ray eyes — SoLEXS (soft) and HEL1OS (hard).", 14, TXT, False)],
     [("", 8, TXT, False)],
     [("PS-15 asks us to detect flares from BOTH instruments combined — in real time.", 14, GOLD, True)],
]], line_spacing=1.05)
box(s, Inches(6.8), Inches(2.0), Inches(5.9), Inches(4.6))
text(s, Inches(7.1), Inches(2.25), Inches(5.3), Inches(4.1), [
    [[("Nowcast vs Forecast", 17, PURPLE, True)],
     [("NOWCAST — “a flare is happening RIGHT NOW”", 15, GREEN, True)],
     [("Detect + classify + alert within seconds of onset. THIS PROJECT (minor).", 13, MUT, False)],
     [("", 8, TXT, False)],
     [("FORECAST — “one is coming in the next 30 min”", 15, PURPLE, True)],
     [("Predict before the peak. Prototype exists — deliberately reserved for the "
       "MAJOR project (next slide explains the split).", 13, MUT, False)],
     [("", 8, TXT, False)],
     [("PS-15 covers both; we deliver one half completely instead of two halves halfway.", 14, TXT, False)],
]], line_spacing=1.05)
footer(s, 2)

# ================================================================ slide 3
s = blank_slide()
kicker(s, "Scope")
title(s, "Minor = nowcast. Major = forecast. One clean line.")
rows = [
    ("", "MINOR — THIS PROJECT", "MAJOR — FUTURE"),
    ("Detect flares as they happen", "✅ core", "—"),
    ("Soft+hard cross-matched catalog", "✅ 2,891 flares", "extends automatically"),
    ("Counts → GOES class calibration", "✅ validated", "—"),
    ("Merged single-file datasets", "✅ 21.2M rows", "—"),
    ("Dashboard + live-alert replay", "✅", "—"),
    ("Predict flares before peak", "🔮 prototype only", "✅ main deliverable"),
]
y = Inches(2.05)
for i, (a, b, c) in enumerate(rows):
    h = Inches(0.52 if i else 0.5)
    if i == 0:
        box(s, Inches(0.6), y, Inches(5.3), h, fill=RGBColor(0x14, 0x26, 0x3F))
        box(s, Inches(6.0), y, Inches(3.2), h, fill=RGBColor(0x0E, 0x2A, 0x3D))
        box(s, Inches(9.3), y, Inches(3.4), h, fill=RGBColor(0x1A, 0x14, 0x30))
        text(s, Inches(0.85), y + Inches(0.09), Inches(5), h, a, size=14, color=MUT, bold=True)
        text(s, Inches(6.2), y + Inches(0.09), Inches(2.9), h, b, size=14, color=ACCENT, bold=True)
        text(s, Inches(9.5), y + Inches(0.09), Inches(3.1), h, c, size=14, color=PURPLE, bold=True)
    else:
        box(s, Inches(0.6), y, Inches(12.1), h, fill=CARD)
        text(s, Inches(0.85), y + Inches(0.1), Inches(5), h, a, size=14, color=TXT)
        text(s, Inches(6.2), y + Inches(0.1), Inches(2.9), h, b, size=13.5, color=ACCENT if "✅" in b else MUT)
        text(s, Inches(9.5), y + Inches(0.1), Inches(3.1), h, c, size=13.5, color=PURPLE if "✅" in c else MUT)
    y += h + Inches(0.12)
text(s, Inches(0.6), Inches(6.45), Inches(12.1), Inches(0.5),
     "The forecast prototype is shown in the dashboard only as a clearly-marked FUTURE WORK panel.",
     size=14, color=MUT)
footer(s, 3)

# ================================================================ slide 4
s = blank_slide()
kicker(s, "Data")
title(s, "From PRADAN zips to one clean table per second")
box(s, Inches(0.6), Inches(1.95), Inches(6.2), Inches(2.4))
text(s, Inches(0.9), Inches(2.15), Inches(5.7), Inches(2.1), [
    [[("What we downloaded (ISRO PRADAN)", 16, ACCENT, True)],
     [("• SoLEXS: 203 daily zips — 2024-02-12, 2024-03-14→05-31, 2026-05-06→09-17", 13.5, TXT, False)],
     [("• HEL1OS: 22 zips — 2026-09-07→09-18, 12-h segments, 4 detectors", 13.5, TXT, False)],
     [("• Level-1 FITS: 1-second X-ray count rates + good-time intervals", 13.5, TXT, False)],
]], line_spacing=1.1)
box(s, Inches(0.6), Inches(4.55), Inches(6.2), Inches(2.1))
text(s, Inches(0.9), Inches(4.75), Inches(5.7), Inches(1.8), [
    [[("Ground truth for validation", 16, GOLD, True)],
     [("NOAA GOES-16 XRS 1-min flux — the world's flare-class reference. "
       "432 reference flares across 73 days; also used to calibrate our counts "
       "into physical flux.", 13.5, TXT, False)],
]], line_spacing=1.1)
box(s, Inches(7.0), Inches(1.95), Inches(5.7), Inches(4.7))
text(s, Inches(7.3), Inches(2.2), Inches(5.1), Inches(0.5),
     "📦 Merged dataset — the deliverable", size=17, color=GREEN, bold=True)
ds_rows = [
    ("solexs_merged", "17.54M rows", "179 MB pq / 1.39 GB csv"),
    ("hel1os_merged", "3.67M rows", "32 MB pq / 263 MB csv"),
    ("merged_all_data", "21.2M rows", "211 MB pq / 1.65 GB csv"),
    ("master_catalog.csv", "2,891 flares", "classes, peaks, lead times"),
]
yy = Inches(2.85)
for name, r1, r2 in ds_rows:
    box(s, Inches(7.3), yy, Inches(5.1), Inches(0.78), fill=RGBColor(0x0B, 0x12, 0x20), line=RGBColor(0x1E, 0x29, 0x3B))
    text(s, Inches(7.5), yy + Inches(0.08), Inches(2.6), Inches(0.35), name, size=13.5, color=TXT, bold=True)
    text(s, Inches(7.5), yy + Inches(0.42), Inches(2.6), Inches(0.3), r1, size=12, color=GREEN)
    text(s, Inches(10.1), yy + Inches(0.2), Inches(2.2), Inches(0.4), r2, size=11.5, color=MUT, align=PP_ALIGN.RIGHT)
    yy += Inches(0.9)
text(s, Inches(7.3), Inches(6.2), Inches(5.1), Inches(0.4),
     "One row = one second: UTC time · rate · error · quality flag", size=12, color=MUT)
footer(s, 4)

# ================================================================ slide 5
s = blank_slide()
kicker(s, "Method — the nowcast engine")
title(s, "Hearing a shout above room noise — 5 steps")
steps = [
    ("1", "INGEST", "FITS → 1-second tables; keep only good-time intervals", ACCENT),
    ("2", "BACKGROUND", "rolling 45-min MINIMUM — flares only push counts up, so the floor is immune", GOLD),
    ("3", "SMOOTH + 5σ", "20-s average; flare when signal beats background by 5 standard deviations for 30 s", ACCENT),
    ("4", "END & MERGE", "decay below 1.5σ ends it; bursts within 300 s merge into one flare", ACCENT),
    ("5", "CROSS-MATCH & CLASSIFY", "link soft+hard views; counts → GOES flux → A/B/C/M/X", GREEN),
]
y = Inches(2.0)
for num, t, d, c in steps:
    box(s, Inches(0.6), y, Inches(12.1), Inches(0.86))
    box(s, Inches(0.6), y, Inches(0.9), Inches(0.86), fill=RGBColor(0x0B, 0x12, 0x20), line=c)
    text(s, Inches(0.6), y + Inches(0.16), Inches(0.9), Inches(0.5), num, size=24, color=c, bold=True, align=PP_ALIGN.CENTER)
    text(s, Inches(1.75), y + Inches(0.1), Inches(2.9), Inches(0.6), t, size=16, color=c, bold=True)
    text(s, Inches(4.7), y + Inches(0.14), Inches(7.8), Inches(0.6), d, size=13.5, color=TXT)
    y += Inches(0.98)
text(s, Inches(0.6), Inches(6.85), Inches(12.1), Inches(0.4),
     "HEL1OS photon-starved 1-s samples are first re-binned to 60 s. Detector = backend/pipeline/detect/detector.py · 6/6 unit tests.",
     size=12, color=MUT)
footer(s, 5)

# ================================================================ slide 6
s = blank_slide()
kicker(s, "Validation")
title(s, "93.5% of every real flare caught — validated against NOAA")
stat_card(s, Inches(0.6), Inches(2.0), Inches(3.8), Inches(2.3), "93.5%", "TRUE POSITIVE RATE",
          "404/432 GOES reference flares detected", GREEN)
stat_card(s, Inches(4.75), Inches(2.0), Inches(3.8), Inches(2.3), "100%", "X-CLASS CAUGHT",
          "all 17 X-flares · M: 95.3% · C: 92.9%", ACCENT)
stat_card(s, Inches(8.9), Inches(2.0), Inches(3.8), Inches(2.3), "4.7/day", "FALSE ALARMS",
          "…and they aren't even false — see below", GOLD)
box(s, Inches(0.6), Inches(4.6), Inches(12.1), Inches(2.1))
text(s, Inches(0.9), Inches(4.8), Inches(11.5), Inches(1.8), [
    [[("The honest twist: our “false alarms” are real flares GOES never listed", 17, GOLD, True)],
     [("All 345 unmatched detections are genuine C6–C8 solar events below GOES's detection floor "
       "(median significance 34σ). SoLEXS is MORE sensitive than the reference standard — "
       "the dashboard, docs and EVALUATION.md state this openly.", 14, TXT, False)],
]], line_spacing=1.1)
footer(s, 6)

# ================================================================ slide 7
s = blank_slide()
kicker(s, "The physics highlight")
title(s, "Hard X-rays arrive first — the Neupert effect, measured")
box(s, Inches(0.6), Inches(2.0), Inches(6.4), Inches(4.5))
text(s, Inches(0.9), Inches(2.25), Inches(5.9), Inches(4.0), [
    [[("Why two instruments?", 17, ACCENT, True)],
     [("When a flare ignites:", 14, TXT, False)],
     [("1.  Electrons are slammed into the solar surface → HARD X-rays (HEL1OS) — first", 14, TXT, False)],
     [("2.  The blast-heated plasma then glows → SOFT X-rays (SoLEXS) — after", 14, TXT, False)],
     [("", 8, TXT, False)],
     [("So the hard-X peak is a built-in early warning of the soft-X peak — the "
       "Neupert effect, and the physical basis of forecasting.", 14, GOLD, True)],
]], line_spacing=1.08)
box(s, Inches(7.3), Inches(2.0), Inches(5.4), Inches(4.5))
text(s, Inches(7.6), Inches(2.3), Inches(4.8), Inches(0.5), "Measured in our data:", size=16, color=ACCENT, bold=True)
text(s, Inches(7.6), Inches(2.9), Inches(4.8), Inches(1.2), "117 s", size=64, color=GREEN, bold=True)
text(s, Inches(7.6), Inches(4.1), Inches(4.8), Inches(0.4),
     "median hard-before-soft lead (14 cross-matched events)", size=13, color=TXT)
text(s, Inches(7.6), Inches(4.75), Inches(4.8), Inches(0.4),
     "458 s  longest observed lead", size=14, color=MUT)
text(s, Inches(7.6), Inches(5.3), Inches(4.8), Inches(0.4),
     "2026-09-07→09-15 overlap window, 59 flares", size=12, color=MUT)
footer(s, 7)

# ================================================================ slide 8
s = blank_slide()
kicker(s, "Software & architecture")
title(s, "A reproducible pipeline, not a notebook")
box(s, Inches(0.6), Inches(2.0), Inches(6.2), Inches(4.5))
text(s, Inches(0.9), Inches(2.2), Inches(5.7), Inches(4.1), [
    [[("Stack", 16, ACCENT, True)],
     [("• Python 3.11 · astropy · pandas · pyarrow", 13.5, TXT, False)],
     [("• LightGBM (forecast prototype — future)", 13.5, TXT, False)],
     [("• FastAPI + WebSocket live replay", 13.5, TXT, False)],
     [("• React 19 + Vite + Recharts dashboard", 13.5, TXT, False)],
     [("", 8, TXT, False)],
     [("Engineering hygiene", 16, ACCENT, True)],
     [("• 6/6 unit tests on synthetic light curves", 13.5, TXT, False)],
     [("• deterministic CLI pipeline: ingest → detect → eval → export", 13.5, TXT, False)],
     [("• 3.7 GB data kept out of git; rebuildable via export_merged.py", 13.5, TXT, False)],
     [("• documented: README · DATASET · EXPLAINER · EVALUATION · RUN_GUIDE", 13.5, TXT, False)],
]], line_spacing=1.08)
box(s, Inches(7.0), Inches(2.0), Inches(5.7), Inches(4.5))
text(s, Inches(7.3), Inches(2.2), Inches(5.1), Inches(0.5), "What runs where", size=16, color=ACCENT, bold=True)
mods = [
    ("backend/pipeline/", "ingest · detect · catalog · eval · export_merged"),
    ("backend/app/", "FastAPI: 6 REST endpoints + WS replay"),
    ("frontend/", "dashboard + guide/glossary page"),
    ("backend/data/merged/", "the merged dataset deliverable"),
    ("docs (5 .md)", "methods, metrics, demo script, glossary"),
]
yy = Inches(2.8)
for m, d in mods:
    box(s, Inches(7.3), yy, Inches(5.1), Inches(0.64), fill=RGBColor(0x0B, 0x12, 0x20), line=RGBColor(0x1E, 0x29, 0x3B))
    text(s, Inches(7.5), yy + Inches(0.06), Inches(4.7), Inches(0.3), m, size=12.5, color=TXT, bold=True)
    text(s, Inches(7.5), yy + Inches(0.34), Inches(4.7), Inches(0.28), d, size=11, color=MUT)
    yy += Inches(0.74)
footer(s, 8)

# ================================================================ slide 9
s = blank_slide()
kicker(s, "Live demo", color=GOLD)
title(s, "The dashboard — guided, self-explanatory, live")
box(s, Inches(0.6), Inches(2.0), Inches(6.2), Inches(4.5))
text(s, Inches(0.9), Inches(2.25), Inches(5.7), Inches(4.0), [
    [[("The 3-step flow on screen", 17, ACCENT, True)],
     [("1 · Pick a day — one-click examples (X8.7 storm day)", 14, TXT, False)],
     [("2 · Watch the Sun — spikes = flares, colored bands = detections", 14, TXT, False)],
     [("3 · Replay it live — the day streams at ×6000; every 🚨 toast is a real nowcast alert", 14, TXT, False)],
     [("", 8, TXT, False)],
     [("Also on screen: merged-dataset card, filterable 2,891-flare catalog, "
       "“? how to read” panel, and a 📖 Guide & Glossary page explaining every keyword.", 14, TXT, False)],
]], line_spacing=1.1)
box(s, Inches(7.0), Inches(2.0), Inches(5.7), Inches(4.5), fill=RGBColor(0x14, 0x10, 0x24), line=PURPLE)
text(s, Inches(7.3), Inches(2.3), Inches(5.1), Inches(0.5),
     "🔮 FUTURE WORK — MAJOR PROJECT", size=15, color=PURPLE, bold=True)
text(s, Inches(7.3), Inches(2.9), Inches(5.1), Inches(3.3), [
    [[("Forecast prototype (kept out of minor scope)", 14, TXT, True)],
     [("• LightGBM P(flare ≤ 30 min), features from trailing windows", 13, MUT, False)],
     [("• AUC 0.82 · 6/6 test flares alerted", 13, MUT, False)],
     [("• median lead 192 s · p90 798 s at FAR = 2/day", 13, MUT, False)],
     [("", 8, TXT, False)],
     [("Same panel in the dashboard is explicitly labeled “future work” — "
       "scope discipline is part of the delivery.", 13, GOLD, True)],
]], line_spacing=1.1)
footer(s, 9)

# ================================================================ slide 10
s = blank_slide()
kicker(s, "Summary")
title(s, "What stands delivered — and what comes next")
box(s, Inches(0.6), Inches(2.0), Inches(6.2), Inches(4.5))
text(s, Inches(0.9), Inches(2.2), Inches(5.7), Inches(4.1), [
    [[("Delivered (minor project)", 17, GREEN, True)],
     [("✅ 2,891-flare automated nowcast database (soft+hard)", 13.5, TXT, False)],
     [("✅ 93.5% detection rate, validated vs NOAA GOES-16", 13.5, TXT, False)],
     [("✅ Neupert-effect precursor measured: 117 s median", 13.5, TXT, False)],
     [("✅ Merged dataset: 21.2M rows, single files per instrument", 13.5, TXT, False)],
     [("✅ Dashboard + replay + in-app glossary — demo-ready", 13.5, TXT, False)],
     [("✅ Reproducible: one-command rebuild, 6/6 tests", 13.5, TXT, False)],
]], line_spacing=1.12)
box(s, Inches(7.0), Inches(2.0), Inches(5.7), Inches(4.5), fill=RGBColor(0x14, 0x10, 0x24), line=PURPLE)
text(s, Inches(7.3), Inches(2.2), Inches(5.1), Inches(0.6),
     "🔮 Next: Major project = forecasting", size=17, color=PURPLE, bold=True)
text(s, Inches(7.3), Inches(2.9), Inches(5.1), Inches(3.4), [
    [[("The prototype becomes the product:", 14, TXT, True)],
     [("• attach LightGBM forecast + lead-time evaluation", 13.5, MUT, False)],
     [("• exploit the 117 s hard-X precursor as a live feature", 13.5, MUT, False)],
     [("• scale merged datasets as PRADAN releases more days", 13.5, MUT, False)],
     [("", 8, TXT, False)],
     [("“Nowcast today. Forecast tomorrow — on the same pipeline.”", 14, GOLD, True)],
]], line_spacing=1.12)
text(s, Inches(0.6), Inches(6.55), Inches(12.1), Inches(0.4),
     "Data: ISSDC PRADAN (SoLEXS + HEL1OS Level-1) · Reference: NOAA GOES-16 · Code: github.com/Peeyush1010/Minor-Project",
     size=12, color=MUT)
footer(s, 10)

# ---------------------------------------------------------------- save
path = OUT / "Aditya-L1_Flare_Watch.pptx"
prs.save(path)
print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KB, {len(prs.slides.__iter__.__self__._sldIdLst)} slides)")
