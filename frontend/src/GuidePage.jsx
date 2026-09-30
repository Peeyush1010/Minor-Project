import { useMemo, useState } from "react";

/* ------------------------------------------------------------------ data */

const SECTIONS = [
  {
    id: "instruments",
    icon: "🛰️",
    title: "The mission & instruments",
    intro: "Aditya-L1 is ISRO's solar observatory, parked 1.5 million km away at the L1 point where it enjoys a continuous, uninterrupted view of the Sun.",
    terms: [
      { k: "Aditya-L1", d: "India's first space-based solar observatory, orbiting the Sun–Earth L1 point (1.5 million km from Earth). From there it watches the Sun 24×7 — no day/night, no eclipses.", see: "Dashboard header — every number here comes from this spacecraft." },
      { k: "L1 point", d: "A gravity-balanced spot between Earth and Sun where a spacecraft can 'hover' with minimal fuel, keeping the Sun always in view. (Not to be confused with Lagrange in general — L1 is the first of five such points.)", see: "Mentioned in the footer and README." },
      { k: "SoLEXS", d: "SoLar Low Energy X-ray Spectrometer — measures SOFT X-rays (1–22 keV). It sees the hot flare plasma 'glow' — the big slow burst of energy. Think of it as the wide-angle camera.", see: "Instrument selector in '1 · Pick a day' — the default view (SDD2 detector)." },
      { k: "HEL1OS", d: "High Energy L1 Orbiting X-ray Spectrometer — measures HARD X-rays (5–160 keV). It sees the electron beams fired at the very start of a flare. The 'night-vision camera' that catches the flare's first shot.", see: "Second option in the Instrument selector." },
      { k: "SDD / CdTe / CZT", d: "The detector materials: Silicon Drift detectors (SoLEXS, soft X-rays) and Cadmium-Telluride / Cadmium-Zinc-Telluride crystals (HEL1OS, hard X-rays). Each material is sensitive to a different energy range.", see: "The Detector dropdown (SDD1/SDD2, CDTE1/2, CZT1/2)." },
      { k: "Soft vs hard X-ray", d: "Soft = lower energy (like a hospital X-ray), produced by hot plasma after the explosion. Hard = higher energy (like airport scanners), produced the instant electrons are accelerated. Hard arrives FIRST — that's the Neupert effect.", see: "The 'Hard X leads soft by 117 s' stat in the header." },
    ],
  },
  {
    id: "data",
    icon: "📁",
    title: "Data & files",
    intro: "Everything starts as raw satellite packets on the ISRO PRADAN portal and ends as the clean tables the dashboard shows.",
    terms: [
      { k: "PRADAN", d: "ISRO's public data portal (PRADAN = PRocessing and Analysis for Data from Aditya-L1... officially 'Archive'). This is where all SoLEXS/HEL1OS Level-1 files were downloaded from — 203 SoLEXS + 22 HEL1OS zips in this project.", see: "Footer: 'Data: ISSDC PRADAN'." },
      { k: "Level-1 data", d: "Raw instrument counts, minimally calibrated (time-tagged, flagged for instrument state). Not yet flux-calibrated — which is why we calibrate counts → classes ourselves against GOES.", see: "README → Data sources." },
      { k: "FITS", d: "Flexible Image Transport System — the standard astronomy file format (a zip of tables + metadata). Both instruments deliver Level-1 data as (gzipped) FITS inside the zips.", see: "backend/pipeline/ingest/ reads these." },
      { k: "Parquet", d: "A columnar table format — like CSV but compressed, typed and 10–50× faster to read in analysis tools. The pipeline's working format and the merged dataset files.", see: "'📦 Merged dataset' card: parquet + CSV sizes shown." },
      { k: "Merged dataset", d: "Every downloaded day flattened into single files per instrument: 17.5M SoLEXS rows + 3.7M HEL1OS rows = 21.2M combined, each row = one second of X-ray counts with UTC time, error and quality flag.", see: "The whole '📦 Merged dataset' card (built by export_merged.py)." },
      { k: "GTI (Good Time Interval)", d: "The periods when the instrument was actually working properly (not calibrating, not occulted). Rows outside GTIs are flagged is_good = False so we never mistake instrument state for solar physics.", see: "Gaps in the light curve — those moments are excluded." },
      { k: "cps (counts per second)", d: "The raw unit of the charts: how many X-ray photons the detector caught per second. Not a physical flux — but we convert it to one (see Calibration).", see: "Y-axis of the light curve: 'X-ray counts / second'." },
    ],
  },
  {
    id: "flares",
    icon: "☀️",
    title: "Flares & classification",
    intro: "Flares are explosions on the Sun that release as much energy as billions of hydrogen bombs — classified by how bright they are in soft X-rays.",
    terms: [
      { k: "Solar flare", d: "A sudden release of magnetic energy on the Sun, accelerating particles and heating plasma to tens of millions of degrees. Disturbs satellites, GPS and power grids on Earth.", see: "Every spike in the light curve is one." },
      { k: "Flare classes A B C M X", d: "The official GOES scale of peak soft X-ray flux. Each letter is 10× the previous: A=10⁻⁸, B=10⁻⁷, C=10⁻⁶, M=10⁻⁵, X=10⁻⁴ W/m². A number after the letter subdivides (M5 = 5×10⁻⁵).", see: "Colored bands on the chart + filter badges on the catalog." },
      { k: "GOES", d: "NOAA's Geostationary Operational Environmental Satellite — has measured soft X-ray flux since the 1970s. The world's reference for flare classes, and our 'ground truth' for validation.", see: "Header stat: 'Detection rate vs GOES'." },
      { k: "Calibration", d: "Our counts are dimensionless, GOES flux is physical. We matched 435 simultaneous events and fitted log₁₀(flux) = 0.873·log₁₀(cps) − 7.409 (scatter 0.095 dex) — so every detection gets a real class without needing GOES online.", see: "The 'Class' column in the flare catalog." },
      { k: "Light curve", d: "Brightness vs time — the core chart. For X-ray astronomers it's the equivalent of a heartbeat monitor for the Sun.", see: "Card '2 · Watch the Sun'." },
      { k: "Neupert effect", d: "The observed law: hard X-ray emission (electron beams) peaks BEFORE the soft X-ray glow (heated plasma). In our data the hard peak leads by a median 117 s (up to 458 s). The physical reason forecasting is possible at all.", see: "Header stat 'Hard X leads soft by' + the Lead column in the catalog." },
    ],
  },
  {
    id: "detection",
    icon: "🔍",
    title: "How detection works (the nowcast engine)",
    intro: "The detector is a pipeline of five plain-English steps — each keyword below maps to one knob of that machinery.",
    terms: [
      { k: "Nowcasting", d: "'What is happening RIGHT NOW' — detecting and characterizing a flare as it erupts, with zero prediction. This is the minor project's entire scope.", see: "The MINOR PROJECT · NOWCASTING badge in the header." },
      { k: "Forecasting", d: "'What will happen in the next 30 min?' — predicting a flare before its peak. Built as a prototype, deliberately kept for the Major project.", see: "The purple '🔮 Future work' panel at the bottom." },
      { k: "Background", d: "The Sun's quiet baseline X-ray level, anywhere between ~10 and 300 cps. We track it with a rolling MINIMUM over 45 min: flares only push counts UP, so the minimum is immune to them — the trick that keeps detection honest during flare storms.", see: "Nothing on screen — but it's why the detector doesn't saturate on X-class days." },
      { k: "Smoothing", d: "A moving average (boxcar) over ~20 s that kills single-photon noise so real rises stand out. Wider = smoother but later; we tuned 20 s as the balance.", see: "The 'Bin size' control changes a related averaging." },
      { k: "5σ threshold", d: "A flare starts when the smoothed signal exceeds the local background by 5 standard deviations (σ, computed fresh every moment from Poisson statistics) AND stays there for 30 s. 5σ ≈ a 1-in-3.5-million random chance — this is the same 'sigma' language used to claim Higgs-boson discoveries.", see: "The σ value in the 🚨 alert toast." },
      { k: "Sustain & merge", d: "Anti-flicker rules: the excess must persist 30 s to count (kills noise spikes), and episodes within 300 s are merged into ONE flare (a big flare often sputters). A 6-h cap guards against particle-event contamination.", see: "Why the catalog shows 11 flares on May 14, not 40 fragments." },
      { k: "Cross-match", d: "SoLEXS and HEL1OS detect independently; cross-matching links the two views of the same physical flare (±300 s tolerance) into a single master-catalog entry with both soft and hard parameters.", see: "The 'Hard X ●' and 'Lead (s)' columns in the catalog." },
      { k: "Master catalog", d: "The project's main output: 2,891 automatically nowcasted flares with start/peak/end, class, duration, hard-X confirmation and lead time. Built fully without human labeling.", see: "Card 'Flare catalog — the automated nowcast database'." },
    ],
  },
  {
    id: "validation",
    icon: "📊",
    title: "Validation & metrics (why you can trust the numbers)",
    intro: "We validated the detector against NOAA's official GOES flare lists — these are the metrics scientists quote.",
    terms: [
      { k: "TPR (True Positive Rate)", d: "Of all real flares in the GOES reference, what fraction did we detect? Ours: 93.5% overall — X 100%, M 95.3%, C 92.9%. 'Recall' means the same thing.", see: "Header stat 'Detection rate vs GOES'." },
      { k: "FAR (False Alarm Rate)", d: "How many alerts per day turn out not to match the GOES list: ours 4.7/day. The twist: almost all are real C6–C8 flares BELOW GOES's detection floor — SoLEXS simply sees smaller flares than GOES does.", see: "Header stat 'False alarms / day'." },
      { k: "Precision / Recall", d: "Precision = when we alert, how often are we right? Recall = of all real events, how many did we catch? The detector is tuned to maximize recall at a tolerable false-alarm rate — missing an X-flare is worse than a few extra alerts.", see: "EVALUATION.md holds the full tables." },
      { k: "Reference flares", d: "432 GOES-16 flares across 73 observed days (308 C, 106 M, 17 X, 1 B) extracted from NOAA's 1-min data with the same detection engine — an apples-to-apples benchmark.", see: "EVALUATION.md section 1." },
      { k: "Sub-GOES sensitivity", d: "SoLEXS detects flares smaller than anything in GOES's official event lists. Our 'false alarms' are mostly this — a strength: we're more sensitive than the reference standard.", see: "The fine print under the FAR stat." },
      { k: "Unit tests", d: "Six synthetic light-curve tests verify the detector catches injected flares, ignores quiet Sun, survives data gaps and background drift, and merges episodes correctly. They run in under a second.", see: "python -m pytest -q → '6 passed'." },
    ],
  },
  {
    id: "forecast",
    icon: "🔮",
    title: "Forecast keywords (future / Major project)",
    intro: "The prototype that becomes the Major project — shown in the dashboard only as a clearly-marked preview.",
    terms: [
      { k: "LightGBM", d: "A gradient-boosted decision-tree library — the ML model behind the forecast prototype. Fast, robust on tabular features, standard for this kind of time-series classification.", see: "Subtitle of the 'Future work' panel." },
      { k: "P(flare ≤ 30 min)", d: "The model's output: probability that a C-class-or-better flare erupts within the next 30 minutes, computed fresh every 60 s from trailing features.", see: "Y-axis of the purple panel's chart." },
      { k: "Trailing features", d: "Inputs summarizing the recent past: rate stats over 5/15/60 min, current excess over background in σ, slope, time since last flare, and HEL1OS hard-X channels where available. No future information is used (no leakage).", see: "backend/pipeline/forecast/model.py" },
      { k: "AUC", d: "Area Under the ROC Curve — how well the model separates 'flare coming' from 'quiet'. 0.5 = coin flip, 1.0 = perfect. Ours: 0.82 on time-blocked test data.", see: "Future-work panel subtitle." },
      { k: "Lead time", d: "How long before the flare peak the alert fires: prototype median 192 s (3.2 min), best cases 13 min. In the nowcast table the same word refers to the hard-X lead (117 s) — the physical precursor.", see: "Header 'Hard X leads soft by' (nowcast) vs the Future panel (forecast)." },
      { k: "Time-blocked split", d: "Train on the first 75% of days, test on the last 25% — never shuffled. Prevents 'memorizing' specific days, the classic way flare-prediction papers overstate accuracy.", see: "EVALUATION.md section 3." },
      { k: "FAR = 2/day operating point", d: "The alert threshold is chosen so the model cries wolf at most twice a day on test data — then lead time is measured at that threshold. A fixed, honest operating point.", see: "EVALUATION.md section 3." },
    ],
  },
];

const PIPELINE = [
  { icon: "📥", t: "Ingest", d: "FITS zips from PRADAN → clean 1-second tables" },
  { icon: "🔍", t: "Detect", d: "background → smoothing → 5σ threshold → merge" },
  { icon: "🤝", t: "Cross-match", d: "soft + hard views of the same flare linked" },
  { icon: "🏷️", t: "Classify", d: "counts → GOES flux → A/B/C/M/X class" },
  { icon: "📦", t: "Deliver", d: "master catalog + merged single-file datasets" },
];

const CLASS_SCALE = [
  { cls: "A", flux: "10⁻⁸", color: "#64748b", ex: "barely a ripple — Sun is quiet" },
  { cls: "B", flux: "10⁻⁷", color: "#3b82f6", ex: "small background wobble" },
  { cls: "C", flux: "10⁻⁶", color: "#eab308", ex: "common, minor radio blackouts" },
  { cls: "M", flux: "10⁻⁵", color: "#f97316", ex: "strong — radio/RDS events" },
  { cls: "X", flux: "10⁻⁴", color: "#ef4444", ex: "extreme — satellite & grid threats" },
];

/* ------------------------------------------------------------------ ui */

function Term({ k, d, see }) {
  return (
    <div className="term">
      <div className="term-head">
        <span className="term-k">{k}</span>
        {see && <span className="term-see">👉 {see}</span>}
      </div>
      <div className="term-d">{d}</div>
    </div>
  );
}

export default function GuidePage() {
  const [q, setQ] = useState("");
  const query = q.trim().toLowerCase();

  const sections = useMemo(() => {
    if (!query) return SECTIONS;
    return SECTIONS.map((s) => ({
      ...s,
      terms: s.terms.filter((t) =>
        t.k.toLowerCase().includes(query) || t.d.toLowerCase().includes(query)),
    })).filter((s) => s.terms.length > 0);
  }, [query]);

  const nTerms = sections.reduce((a, s) => a + s.terms.length, 0);

  return (
    <div className="guide">
      <div className="card">
        <div className="card-head">
          <div>
            <h3>📖 Guide & Glossary — every keyword in this project, in plain words</h3>
            <div className="card-sub">
              Use this page while presenting: each term has a one-line meaning and a
              “where you see it” pointer to the dashboard. Type to filter.
            </div>
          </div>
          <input className="guide-search" type="search" placeholder="🔍 search a keyword… e.g. sigma, GOES, parquet"
            value={q} onChange={(e) => setQ(e.target.value)} />
        </div>

        <div className="pipe-flow">
          {PIPELINE.map((p, i) => (
            <div className="pipe-step" key={p.t}>
              <div className="pipe-ico">{p.icon}</div>
              <div className="pipe-txt"><b>{p.t}</b><span>{p.d}</span></div>
              {i < PIPELINE.length - 1 && <div className="pipe-arrow">→</div>}
            </div>
          ))}
        </div>

        <div className="class-scale">
          <div className="cs-title">The flare-class scale (each step = 10× more energy):</div>
          <div className="cs-row">
            {CLASS_SCALE.map((c) => (
              <div className="cs-item" key={c.cls} style={{ borderColor: c.color }}>
                <div className="cs-letter" style={{ background: c.color }}>{c.cls}</div>
                <div className="cs-flux">{c.flux} W/m²</div>
                <div className="cs-ex">{c.ex}</div>
              </div>
            ))}
          </div>
        </div>

        {query && (
          <div className="muted" style={{ margin: "6px 2px" }}>
            {nTerms} match{nTerms === 1 ? "" : "es"} for “{q}”
          </div>
        )}
      </div>

      {sections.map((s) => (
        <div className="card" key={s.id}>
          <div className="card-head">
            <div>
              <h3>{s.icon} {s.title}</h3>
              <div className="card-sub">{s.intro}</div>
            </div>
          </div>
          <div className="terms">
            {s.terms.map((t) => <Term key={t.k} {...t} />)}
          </div>
        </div>
      ))}

      {query && nTerms === 0 && (
        <div className="card"><div className="empty">No keyword matches “{q}”. Try: sigma, class, GOES, cps, Neupert…</div></div>
      )}
    </div>
  );
}
