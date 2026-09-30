import { useEffect, useMemo, useRef, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ReferenceArea, ReferenceLine, Brush,
} from "recharts";
import {
  CLASS_COLORS, clsOf, fmtTime, parseUtc, useApi, useReplay, useSummary,
  useApiStatus, useDayCounts, downloadCsv, downloadFile, fmtDateLabel,
} from "./api";
import Info from "./Info";
import GuidePage from "./GuidePage";
import SciencePanel from "./SciencePanel";

const INSTRUMENTS = {
  solexs: ["SDD1", "SDD2"],
  hel1os: ["CDTE1", "CDTE2", "CZT1", "CZT2"],
};

const PRESETS = [
  { label: "🔥 X8.7 giant flare", day: "2024-05-14", instrument: "solexs", detector: "SDD2",
    hint: "biggest flare Aditya-L1 caught" },
  { label: "🔬 Soft+hard overlap", day: "2026-09-12", instrument: "solexs", detector: "SDD2",
    hint: "both instruments watching" },
];

// Featured demo: X8.7 storm day, zoomed to the giant event (11:00–12:30 UT)
const DEMO = {
  day: "2024-05-14", instrument: "solexs", detector: "SDD2", bin_s: 30,
  zoom: [Date.UTC(2024, 4, 14, 11, 0), Date.UTC(2024, 4, 14, 12, 30)],
  title: "🎯 Featured demonstration — X8.7 storm, 14-05-2024",
  body: "The chart is zoomed to the largest event in the whole dataset: a giant X-class flare " +
        "that peaked at 11:19 UT at ~29,600 counts/s (GOES X8.7 storm). The colored band is the " +
        "automatic detection. Press ▶ Start replay below to watch the alert fire in real time, " +
        "or reset the zoom to explore the full day.",
};

const STEPS = [
  { n: 1, title: "Pick a day", desc: "Choose instrument & date — or tap an example above" },
  { n: 2, title: "Read the light curve", desc: "Spikes are flares; bands mark detections; drag the slider or click a flare to zoom" },
  { n: 3, title: "Replay it live", desc: "Stream the day at high speed — alerts pop as they would in real time" },
];

/* ------------------------------------------------------------------ shells */

function Card({ title, subtitle, right, children, tone }) {
  return (
    <div className={"card" + (tone ? ` ${tone}` : "")}>
      <div className="card-head">
        <div>
          <h3>{title}</h3>
          {subtitle && <div className="card-sub">{subtitle}</div>}
        </div>
        {right}
      </div>
      {children}
    </div>
  );
}

function Stat({ label, value, hint }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">
        {label} {hint && <Info text={hint} />}
      </div>
    </div>
  );
}

function StepBar() {
  return (
    <div className="steps">
      {STEPS.map((s) => (
        <div className="step" key={s.n}>
          <span className="step-n">{s.n}</span>
          <div>
            <div className="step-title">{s.title}</div>
            <div className="step-desc">{s.desc}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function ClassLegend() {
  return (
    <div className="legend">
      <span className="legend-title">Flare class:</span>
      <span className="lg"><i style={{ background: CLASS_COLORS.X }} /> X — extreme</span>
      <span className="lg"><i style={{ background: CLASS_COLORS.M }} /> M — major</span>
      <span className="lg"><i style={{ background: CLASS_COLORS.C }} /> C — common</span>
      <span className="lg"><i style={{ background: CLASS_COLORS.B }} /> B — small</span>
    </div>
  );
}

function LoadingScreen() {
  return (
    <div className="app">
      <div className="screen">
        <div className="spinner" />
        <h2>⚡ Aditya-L1 Flare Watch</h2>
        <div className="muted">Connecting to the analysis backend…</div>
      </div>
    </div>
  );
}

function OfflineScreen() {
  return (
    <div className="app">
      <div className="screen">
        <div className="offline-dot">●</div>
        <h2>Backend offline</h2>
        <div className="muted">
          The dashboard can't reach the analysis API on <code>localhost:8000</code>.<br /><br />
          Start it with: <code>python -m uvicorn backend.app.main:app --port 8000</code><br />
          then reload this page.
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ header */

function Header({ summary, dayCounts }) {
  const ev = summary?.eval || {};
  const pc = ev.per_class || {};
  return (
    <div className="header">
      <div>
        <h1>⚡ Aditya-L1 Flare Watch</h1>
        <div className="sub">
          Live solar-flare <b>nowcasting</b> from SoLEXS (soft) + HEL1OS (hard) X-rays · ISRO PRADAN data
        </div>
        <div className="scope-badges">
          <span className="badge-scope">MINOR PROJECT · NOWCASTING</span>
          <span className="badge-future">Forecasting module — planned extension (Major project)</span>
        </div>
      </div>
      <div className="stats">
        <Stat label="Flares nowcasted" value={summary ? summary.total_flares : "…"}
          hint="Flares detected automatically across all 203 observed days (master catalog). Found by the 5σ threshold rule — see the Science page." />
        <Stat label="Seen by hard X-ray too" value={summary ? summary.hard_matched : "…"}
          hint="Of 59 flares in the Sep-2026 window where BOTH instruments observed, 14 were independently confirmed by HEL1OS." />
        <Stat label="Hard X leads soft by"
          value={summary?.median_hard_lead_s ? `${Math.round(summary.median_hard_lead_s)} s` : "–"}
          hint="117 s = median head start of the hard-X peak BEFORE the soft-X peak across the 14 cross-matched events (Neupert effect). Range: 0–458 s." />
        <Stat label="Detection rate vs GOES"
          value={ev.tpr ? `${(ev.tpr * 100).toFixed(1)}%` : "–"}
          hint={`93.5% = 404 of 432 NOAA GOES-16 reference flares (73 days, Feb–May 2024) that we also detected. Per class: X ${Math.round((pc.X?.tpr || 0) * 100)}%, M ${Math.round((pc.M?.tpr || 0) * 100)}%, C ${Math.round((pc.C?.tpr || 0) * 100)}%.`} />
        <Stat label="False alarms / day"
          value={ev.far_per_day ? ev.far_per_day.toFixed(1) : "–"}
          hint="4.7 unmatched detections per day vs the GOES list — but they are real C6–C8 flares below GOES's detection floor, so this is an upper bound on genuinely wrong alerts." />
        <Stat label="Dataset period"
          value="2024-02 → 2026-09"
          hint={`${dayCounts ? dayCounts.solexs : 203} SoLEXS days (2024-02-12, 2024-03-14→05-31, 2026-05-06→09-17) + ${dayCounts ? dayCounts.hel1os : 12} HEL1OS days (2026-09-07→09-18).`} />
      </div>
      <div className={"api-pill " + (dayCounts ? "on" : "")}>
        ● API online · {dayCounts ? `${dayCounts.solexs} SoLEXS days loaded` : "loading coverage…"}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- controls */

function Controls({ state, set, onDemo, demo }) {
  return (
    <Card title="1 · Pick a day & instrument"
      subtitle="SoLEXS sees the hot flare plasma (soft X-rays); HEL1OS sees the electron beams (hard X-rays)."
      right={
        <div className="presets">
          <button className="btn demo" onClick={onDemo} title="Auto-select the day, zoom to the giant flare and explain it">
            ▶ Demo: X8.7 flare — 14-05-2024
          </button>
          {PRESETS.slice(1).map((p) => (
            <button key={p.label} className="btn ghost" title={p.hint}
              onClick={() => set({ from: p.day, to: p.day, instrument: p.instrument, detector: p.detector })}>
              {p.label}
            </button>
          ))}
        </div>
      }>
      <div className="controls">
        <label>Instrument
          <select value={state.instrument}
            onChange={(e) => set({ instrument: e.target.value, detector: INSTRUMENTS[e.target.value][0] })}>
            <option value="solexs">SoLEXS (soft X-ray)</option>
            <option value="hel1os">HEL1OS (hard X-ray)</option>
          </select>
        </label>
        <label>Detector
          <select value={state.detector} onChange={(e) => set({ detector: e.target.value })}>
            {INSTRUMENTS[state.instrument].map((d) => <option key={d}>{d}</option>)}
          </select>
        </label>
        <label>Day (UTC · DD-MM-YYYY shown on charts)
          <input type="date" value={state.from}
            onChange={(e) => set({ from: e.target.value, to: e.target.value })} />
        </label>
        <label>Bin size
          <select value={state.bin_s} onChange={(e) => set({ bin_s: Number(e.target.value) })}
            title="Average the signal over this many seconds per point">
            {[10, 30, 60, 300, 600].map((b) => <option key={b} value={b}>{b} s</option>)}
          </select>
        </label>
        <label className="chk" title="Log scale makes giant flares and small ones visible together">
          <input type="checkbox" checked={state.log} onChange={(e) => set({ log: e.target.checked })} />
          log scale
        </label>
      </div>
      <div className="muted hint-line">
        All times are <b>UTC</b> and shown as <b>DD-MM-YYYY</b> · Good first picks: any day 14-03-2024 → 31-05-2024
        (big flare season) or 07-09-2026 → 15-09-2026 (both instruments observing).
      </div>
      {demo && null}
    </Card>
  );
}

/* ---------------------------------------------------------------- lightcurve */

function FlareTooltip({ active, payload, flares }) {
  const ref = useRef(null);
  if (!active || !payload || !payload.length) return null;
  const t = payload[0].payload.t;
  const rate = payload[0].payload.rate;
  ref.current = t;
  const f = (flares || []).find((x) => t >= parseUtc(x.start) && t <= parseUtc(x.end));
  const dt = new Date(t).toISOString();
  return (
    <div className="chart-tip">
      <div className="ct-time">{dt.replace("T", " ").slice(0, 19)} UTC</div>
      <div className="ct-rate">{rate == null ? "no data (gap)" : `${rate.toFixed(1)} counts/s`}</div>
      {f ? (
        <div className="ct-flare">
          <span className="pill" style={{ background: CLASS_COLORS[clsOf(f)] }}>{clsOf(f)}</span>
          <b> flare in progress</b>
          <div>peak {fmtTime(parseUtc(f.peak))}</div>
          <div>{(f.duration_s / 60).toFixed(0)} min · {f.solexs_excess_sigma?.toFixed(0)}σ above background</div>
          <div>{f.hard_detected ? `● hard-X confirmed · ${Math.round(f.hard_lead_s)} s early` : "soft-X only"}</div>
        </div>
      ) : (
        <div className="ct-flare muted">quiet Sun — no flare flagged here</div>
      )}
    </div>
  );
}

function Lightcurve({ data, flares, log, zoom, onZoom, onReset }) {
  const ds = useMemo(() => downsampleMax(data, 4000), [data]);
  const domain = zoom ? [zoom[0], zoom[1]] : ["dataMin", "dataMax"];
  const shown = zoom ? ds.filter((p) => p.t >= zoom[0] && p.t <= zoom[1]) : ds;
  return (
    <div>
      <div className="zoom-bar">
        {zoom
          ? <button className="btn ghost" onClick={onReset}>⤢ Reset zoom — full day</button>
          : <span className="muted">Drag the slider below the chart to zoom into a flare · hover for details</span>}
        {zoom && (
          <span className="muted">
            zoomed: {new Date(zoom[0]).toISOString().slice(11, 16)}–{new Date(zoom[1]).toISOString().slice(11, 16)} UTC
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={340}>
        <LineChart data={shown} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#1e293b" />
          <XAxis dataKey="t" type="number" scale="time" domain={domain}
            tickFormatter={(v) => fmtTime(v).slice(5, 16)} stroke="#64748b" tick={{ fontSize: 11 }} />
          <YAxis stroke="#64748b" tick={{ fontSize: 11 }} scale={log ? "log" : "auto"}
            domain={log ? ["auto", "auto"] : undefined} allowDataOverflow
            label={{ value: "X-ray counts / second", angle: -90, position: "insideLeft",
                     style: { fill: "#64748b", fontSize: 11 } }} />
          <Tooltip content={<FlareTooltip flares={flares} />} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {flares.map((f, i) => (
            <ReferenceArea key={i} x1={parseUtc(f.start)} x2={parseUtc(f.end)}
              fill={CLASS_COLORS[clsOf(f)] || "#64748b"} fillOpacity={dimOf(f)} ifOverflow="extendDomain"
              onClick={() => onZoomFlare(f, onZoom)} />
          ))}
          {flares.filter((f) => ["X", "M"].includes(clsOf(f))).map((f, i) => (
            <ReferenceLine key={"p" + i} x={parseUtc(f.peak)} stroke={CLASS_COLORS[clsOf(f)] || "#64748b"}
              strokeDasharray="4 2" ifOverflow="extendDomain" />
          ))}
          <Line type="monotone" dataKey="rate" stroke="#38bdf8" dot={false} strokeWidth={1.4}
            name="count rate (cps) — spikes = flares" connectNulls={false} isAnimationActive={false} />
          {!zoom && (
            <Brush dataKey="t" height={26} travellerWidth={8} stroke="#38bdf8" fill="transparent"
              tickFormatter={() => ""} onChange={(r) => {
                if (r && shown[r.startIndex] && shown[r.endIndex]) {
                  onZoom([shown[r.startIndex].t, shown[r.endIndex].t]);
                }
              }} />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function dimOf(f) {
  const c = clsOf(f);
  if (c === "X") return 0.22;
  if (c === "M") return 0.16;
  if (c === "C") return 0.055;
  return 0.04;
}

function onZoomFlare(f, onZoom) {
  const s = parseUtc(f.start), e = parseUtc(f.end);
  onZoom([s - 600000, Math.max(e + 600000, s + 1800000)]);
}

function downsampleMax(points, target) {
  if (points.length <= target) return points;
  const bucket = Math.ceil(points.length / target);
  const out = [];
  for (let i = 0; i < points.length; i += bucket) {
    let best = points[i];
    for (let j = i + 1; j < Math.min(points.length, i + bucket); j++) {
      const b = best.rate ?? -Infinity, r = points[j].rate ?? -Infinity;
      if (r > b) best = points[j];
    }
    out.push(best);
  }
  return out;
}

/* ---------------------------------------------------------------- forecast */

function ForecastStrip({ from, to }) {
  const { data } = useApi(`/api/forecast?from=${from || ""}&to=${to || ""}`, [from, to]);
  const points = (data?.t || []).map((t, i) => ({ t, p: data.p[i] }));
  return (
    <Card tone="future" title="🔮 Future work — flare forecast"
      subtitle="A preview of the Major-project deliverable: an ML model (LightGBM) predicting “will a C-class-or-better flare erupt within 30 minutes?”. Shown here for demonstration only — kept out of the minor-project scope."
      right={<span className="pill-future">FUTURE · MAJOR PROJECT</span>}>
      {points.length ? (
        <ResponsiveContainer width="100%" height={130}>
          <LineChart data={points} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#1e293b" />
            <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
              tickFormatter={(v) => fmtTime(v).slice(5, 16)} stroke="#64748b" tick={{ fontSize: 11 }} />
            <YAxis domain={[0, 1]} stroke="#64748b" tick={{ fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
              labelFormatter={(v) => fmtTime(v)} />
            <ReferenceLine y={0.5} stroke="#f59e0b" strokeDasharray="4 2" />
            <Line type="monotone" dataKey="p" stroke="#a78bfa" dot={false} strokeWidth={1.6}
              name="P(flare within 30 min)" isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="muted">
          Prototype trained on 2024 data — no forecast series for this window
          (try a 2024 day). This panel exists only to preview the Major project.
        </div>
      )}
    </Card>
  );
}

/* ----------------------------------------------------------------- dataset */

const DATASET_META = {
  solexs_merged: { label: "SoLEXS (soft X-ray) — all days, one file", d: "17.5M rows · 1-s soft X-ray rates, 203 days" },
  hel1os_merged: { label: "HEL1OS (hard X-ray) — all detectors, one file", d: "3.7M rows · 4 detectors, 12 days" },
  merged_all_data: { label: "Combined — both instruments in one file", d: "21.2M rows · superset schema" },
};

function DatasetCard() {
  const { data, loading } = useApi("/api/dataset", []);
  if (loading) return <Card title="📦 Merged dataset"><div className="empty-sm">loading…</div></Card>;
  if (!data?.available) {
    return (
      <Card title="📦 Merged dataset">
        <div className="muted">Not built yet — run <code>python -m backend.pipeline.export_merged</code></div>
      </Card>
    );
  }
  return (
    <Card title="📦 Merged dataset — every download, one file each"
      subtitle="All PRADAN zips ingested, cleaned and flattened into single deliverable files. Download below (parquet = full data, CSV = opens in Excel*). Details in DATASET.md."
      right={<span className="muted">{data.solexs_days} SoLEXS days · {data.hel1os_days} HEL1OS days</span>}>
      <div className="ds-grid">
        {Object.entries(data.files || {}).map(([k, v]) => (
          <div className="ds-item" key={k}>
            <div className="ds-name">{DATASET_META[k]?.label || k}</div>
            <div className="ds-meta">
              <b>{(v.rows / 1e6).toFixed(1)}M</b> rows · {(v.t_start || "").slice(0, 10)} → {(v.t_end || "").slice(0, 10)} UTC
              <div className="ds-btns">
                <button className="btn mini" onClick={() => downloadFile(`/api/dataset/download/${k}?fmt=parquet`)}>
                  ⬇ parquet · {v.parquet_mb} MB
                </button>
                <button className="btn mini" onClick={() => downloadFile(`/api/dataset/download/${k}?fmt=csv`)}>
                  ⬇ CSV · {v.csv_mb} MB
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="muted hint-line">
        <b>Version:</b> generated {(data.generated_utc || "").slice(0, 10)} UTC from {data.raw_zips?.solexs?.n_zips ?? 0} SoLEXS +{" "}
        {data.raw_zips?.hel1os?.n_zips ?? 0} HEL1OS PRADAN zips · pipeline v1.0 ·{" "}
        <button className="btn mini" onClick={() => downloadFile("/api/dataset/download/manifest")}>⬇ manifest.json</button>
        <br />
        <b>Cite as:</b> “Aditya-L1 SoLEXS/HEL1OS Level-1 merged light curves (2026), processed with the
        Flare Watch pipeline — ISSDC PRADAN + NOAA GOES-16 reference.” &nbsp;*CSVs exceed Excel's row limit;
        use parquet + pandas for the full data.
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------- flare table */

const COLS = [
  { key: "start", label: "Start (UT)", sortable: true },
  { key: "peak", label: "Peak (UT)", sortable: true },
  { key: "cls", label: "Class", sortable: true },
  { key: "cps", label: "Peak (cps)", sortable: true },
  { key: "dur", label: "Dur (min)", sortable: true },
  { key: "hard", label: "Hard X", sortable: false },
  { key: "lead", label: "Lead (s)", sortable: true },
];

const OVERLAP = { from: "2026-09-07", to: "2026-09-15" };

function hardLabel(f) {
  if (f.hard_detected) return { txt: "● confirmed", cls: "ok" };
  const d = f.start.slice(0, 10);
  if (d >= OVERLAP.from && d <= OVERLAP.to) return { txt: "not matched", cls: "warn" };
  return { txt: "no overlap data", cls: "na" };
}

function fmtDT(ms) {
  if (!ms) return "–";
  const iso = new Date(ms).toISOString();
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}-${m}-${y} ${iso.slice(11, 16)} UT`;
}

function FlareTable({ flares, windowFrom, windowTo, onSelect }) {
  const [filter, setFilter] = useState("");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState({ key: "start", dir: 1 });
  const [page, setPage] = useState(0);
  const [copied, setCopied] = useState(false);
  const PER = 25;

  useEffect(() => { setPage(0); }, [filter, q, sort, windowFrom, windowTo]);

  const rowsAll = useMemo(() => {
    if (!flares) return [];
    const f = filter.toUpperCase();
    const query = q.trim().toLowerCase();
    return flares.filter((x) => {
      if (f && clsOf(x) !== f) return false;
      if (query) {
        const hay = `${x.start.slice(0, 10)} ${clsOf(x)} ${x.start} ${x.peak} ${x.hard_detected ? "hard-x" : "soft-only"}`;
        if (!hay.toLowerCase().includes(query)) return false;
      }
      return true;
    });
  }, [flares, filter, q]);

  const rows = useMemo(() => {
    const val = (x) => {
      switch (sort.key) {
        case "start": return parseUtc(x.start);
        case "peak": return parseUtc(x.peak);
        case "cls": return clsOf(x);
        case "cps": return x.solexs_peak_cps || 0;
        case "dur": return x.duration_s || 0;
        case "lead": return x.hard_lead_s ?? -1;
        default: return 0;
      }
    };
    return [...rowsAll].sort((a, b) => {
      const va = val(a), vb = val(b);
      if (typeof va === "string") return sort.dir * va.localeCompare(vb);
      return sort.dir * (va - vb);
    });
  }, [rowsAll, sort]);

  const pageRows = rows.slice(page * PER, page * PER + PER);
  const pages = Math.max(1, Math.ceil(rows.length / PER));

  const doExport = () => {
    downloadCsv(`flare_catalog_${windowFrom}_${windowTo}.csv`, rows.map((f) => ({
      start: fmtDT(parseUtc(f.start)), peak: fmtDT(parseUtc(f.peak)), class: clsOf(f),
      peak_cps: f.solexs_peak_cps?.toFixed(1) ?? "", duration_min: (f.duration_s / 60).toFixed(0),
      hard_x: hardLabel(f).txt, lead_s: f.hard_lead_s != null ? Math.round(f.hard_lead_s) : "",
      excess_sigma: f.solexs_excess_sigma?.toFixed(1) ?? "",
    })), [
      { key: "start", label: "Start (UT, DD-MM-YYYY)" }, { key: "peak", label: "Peak (UT)" },
      { key: "class", label: "Class" }, { key: "peak_cps", label: "Peak (cps)" },
      { key: "duration_min", label: "Duration (min)" }, { key: "hard_x", label: "Hard X-ray" },
      { key: "lead_s", label: "Hard-X lead (s)" }, { key: "excess_sigma", label: "Significance (sigma)" },
    ]);
  };

  const shareLink = () => {
    navigator.clipboard?.writeText(window.location.href).then(
      () => { setCopied(true); setTimeout(() => setCopied(false), 1800); },
      () => 0,
    );
  };

  return (
    <div>
      <div className="table-tools">
        <div className="row">
          <div className="class-badges">
            {["X", "M", "C", "B"].map((c) => (
              <button key={c} className={"badge " + (filter === c ? "on" : "")}
                style={{ borderColor: CLASS_COLORS[c], color: filter === c ? "#0b1220" : CLASS_COLORS[c] }}
                onClick={() => setFilter(filter === c ? "" : c)}
                title={`Show only ${c}-class flares`}>
                {c}
              </button>
            ))}
          </div>
          <input className="search" type="search" placeholder="🔍 search date / class…"
            value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="row">
          <span className="muted">{rows.length} flares</span>
          <button className="btn mini" onClick={doExport} title="Download the filtered table as CSV">⬇ CSV</button>
          <button className="btn mini" onClick={shareLink} title="Copy a shareable link to this exact view">
            {copied ? "✓ copied!" : "🔗 link"}
          </button>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {COLS.map((c) => (
                <th key={c.key} className={c.sortable ? "sortable" : ""}
                  title={TH_TIPS[c.key]}
                  onClick={() => c.sortable && setSort((s) => ({ key: c.key, dir: s.key === c.key ? -s.dir : 1 }))}>
                  {c.label}{sort.key === c.key ? (sort.dir > 0 ? " ▲" : " ▼") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((f) => {
              const hl = hardLabel(f);
              return (
                <tr key={f.flare_id} className="clickable"
                  title="Click to zoom the chart to this flare (also updates the URL)"
                  onClick={() => onSelect(f)}>
                  <td>{fmtDT(parseUtc(f.start))}</td>
                  <td>{fmtDT(parseUtc(f.peak))}</td>
                  <td><span className="pill" style={{ background: CLASS_COLORS[clsOf(f)] }}>{clsOf(f)}</span></td>
                  <td>{f.solexs_peak_cps?.toFixed(1)}</td>
                  <td>{(f.duration_s / 60).toFixed(0)}</td>
                  <td className={"hardx " + hl.cls}>{hl.txt}</td>
                  <td className={hl.cls}>{f.hard_lead_s != null ? `${Math.round(f.hard_lead_s)} s early` : "–"}</td>
                </tr>
              );
            })}
            {!pageRows.length && (
              <tr><td colSpan={7} className="empty-sm">no flares match this filter</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="table-foot muted">
        <span>page {page + 1} / {pages} · times UTC · DD-MM-YYYY</span>
        <span className="row">
          <button className="btn mini" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>← prev</button>
          <button className="btn mini" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>next →</button>
        </span>
      </div>
    </div>
  );
}

const TH_TIPS = {
  start: "When the flare started (UTC)",
  peak: "Moment of maximum X-ray output (UTC)",
  cls: "GOES class from calibrated flux — bigger letter = more energy",
  cps: "Soft X-ray count rate at peak",
  dur: "How long the flare lasted",
  hard: "Hard-X confirmation: ● confirmed / not matched (both instruments on, no hard counterpart) / no overlap data (HEL1OS off that day)",
  lead: "How many seconds the hard-X peak led the soft-X peak (Neupert effect)",
};

/* --------------------------------------------------------------------- app */

export default function App() {
  const apiUp = useApiStatus();
  const dayCounts = useDayCounts();

  const init = useMemo(() => new URLSearchParams(window.location.search), []);
  const [page, setPage] = useState(init.get("page") || "dashboard");
  const [state, set_] = useState({
    instrument: init.get("i") || "solexs",
    detector: init.get("det") || "SDD2",
    from: init.get("d") || "2024-05-14",
    to: init.get("d") || "2024-05-14",
    bin_s: Number(init.get("bin")) || 60,
    log: true,
  });
  const [zoom, setZoom] = useState(
    init.get("z") ? init.get("z").split("_").map(Number) : null,
  );
  const [demo, setDemo] = useState(init.get("demo") === "1");

  const set = (patch) => {
    set_((s) => ({ ...s, ...patch }));
    if ("from" in patch || "instrument" in patch) { setZoom(null); setDemo(false); }
  };

  // keep the URL shareable
  useEffect(() => {
    const p = new URLSearchParams();
    if (page !== "dashboard") p.set("page", page);
    if (state.from) p.set("d", state.from);
    if (state.instrument !== "solexs") p.set("i", state.instrument);
    if (state.detector !== "SDD2") p.set("det", state.detector);
    if (state.bin_s !== 60) p.set("bin", String(state.bin_s));
    if (zoom) p.set("z", `${zoom[0]}_${zoom[1]}`);
    if (demo) p.set("demo", "1");
    const qs = p.toString();
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
  }, [page, state, zoom, demo]);

  const { data: summary } = useSummary();
  const qs = new URLSearchParams({
    instrument: state.instrument, detector: state.detector,
    from: state.from, to: state.to, bin_s: String(state.bin_s),
  });
  const { data: lc, loading: lcLoading } = useApi(`/api/lightcurve?${qs}`, [qs.toString()]);
  const { data: fl, loading: flLoading } = useApi(
    `/api/flares?${new URLSearchParams({ from: state.from, to: state.to })}`,
    [state.from, state.to]);

  const [replayOn, setReplayOn] = useState(false);
  const [speed, setSpeed] = useState(2000);
  const [toast, setToast] = useState(null);
  const [showHow, setShowHow] = useState(false);
  const replay = useReplay({
    instrument: state.instrument, detector: state.detector,
    from: state.from, to: state.to, speed,
    enabled: replayOn && page === "dashboard",
    onAlert: (e) => {
      setToast({
        t: fmtTime(e.peak), sigma: e.excess_sigma, cps: e.peak_cps,
        cls: e.excess_sigma > 1000 ? "M/X" : "C",
      });
      setTimeout(() => setToast(null), 6000);
    },
  });

  const chartPoints = replayOn ? replay.points
    : (lc ? lc.t.map((t, i) => ({ t, rate: lc.good[i] ? lc.rate[i] : null })) : []);
  const chartFlares = replayOn
    ? replay.alerts.map((e) => ({ start: new Date(e.start).toISOString(), peak: new Date(e.peak).toISOString(), end: new Date(e.end).toISOString(), class_proxy: "C" }))
    : (fl ? fl.flares.filter((f) => ["X", "M", "C"].includes(clsOf(f))) : []);

  const runDemo = () => {
    set_((s) => ({ ...s, instrument: DEMO.instrument, detector: DEMO.detector,
                   bin_s: DEMO.bin_s, from: DEMO.day, to: DEMO.day }));
    setZoom(DEMO.zoom);
    setDemo(true);
    document.querySelector(".card")?.scrollIntoView({ behavior: "smooth" });
  };

  if (apiUp === null) return <LoadingScreen />;
  if (apiUp === false) return <OfflineScreen />;

  return (
    <div className="app">
      <nav className="topnav">
        <button className={"navbtn" + (page === "dashboard" ? " on" : "")}
          onClick={() => setPage("dashboard")}>🛰 Dashboard</button>
        <button className={"navbtn" + (page === "guide" ? " on" : "")}
          onClick={() => setPage("guide")}>📖 Guide &amp; Glossary</button>
        <button className={"navbtn" + (page === "science" ? " on" : "")}
          onClick={() => setPage("science")}>🧪 Science &amp; Results</button>
        <span className="muted nav-hint">Presenting? Use the ▶ Demo button — it zooms to the X8.7 flare and explains it.</span>
      </nav>

      {page === "dashboard" && (
      <>
      <Header summary={summary} dayCounts={dayCounts} />
      <StepBar />

      {demo && (
        <div className="demo-banner">
          <div>
            <b>{DEMO.title}</b>
            <div>{DEMO.body}</div>
          </div>
          <div className="row">
            <button className="btn ghost" onClick={() => { setZoom(null); setDemo(false); }}>✕ reset zoom</button>
          </div>
        </div>
      )}

      <Controls state={state} set={set} onDemo={runDemo} demo={demo} />

      <Card title="2 · Watch the Sun — light curve"
        subtitle="Each point is the Sun's X-ray output. A sudden spike = a flare. Hover for details; drag the slider below the chart to zoom; click a flare row in the catalog to zoom to it."
        right={
          <div className="row">
            <ClassLegend />
            <button className="btn ghost" onClick={() => setShowHow((v) => !v)}>
              {showHow ? "✕ close" : "? how to read"}
            </button>
          </div>
        }>
        {showHow && (
          <div className="howto">
            <ul>
              <li><b>Blue line</b> — X-ray counts per second coming from the Sun. Quiet Sun = flat; flare = spike.</li>
              <li><b>Colored bands</b> — flares detected automatically. X/M are highlighted strongly; common C-class bands are kept faint so the big events stand out.</li>
              <li><b>Hover anywhere</b> — exact UTC time, count rate, and if a flare is under the cursor: its class, peak time, duration, significance and hard-X status.</li>
              <li><b>Zoom</b> — drag the slider under the chart, click a catalog row, or use the ▶ Demo button. Reset zoom returns to the full day.</li>
              <li><b>Gaps in the line</b> — no data: instrument off, calibration, or Earth blocked the view.</li>
              <li><b>Replay (step 3)</b> — replays the day at high speed through the live detector: each 🚨 pop-up is a nowcast alert.</li>
            </ul>
          </div>
        )}
        <div className="lc-meta muted">
          {state.instrument.toUpperCase()} · {state.detector} · {chartPoints.length} points
          · {fmtDateLabel(state.from)} (UTC)
          {replayOn && <span className="live-chip">● LIVE REPLAY ×{speed}</span>}
          <button className="btn mini" title="Download the detection report for the selected day (JSON): events, classes, calibration, provenance"
            onClick={() => downloadFile(`/api/report/day?from=${state.from}&to=${state.to}`)}>
            ⬇ day report
          </button>
        </div>
        {lcLoading && !replayOn ? (
          <div className="empty"><div className="spinner sm" /> loading light curve…</div>
        ) : chartPoints.length ? (
          <Lightcurve data={chartPoints} flares={chartFlares} log={state.log}
            zoom={zoom} onZoom={setZoom} onReset={() => { setZoom(null); setDemo(false); }} />
        ) : (
          <div className="empty">
            No data for this window.<br />
            <span className="muted">Try the ▶ Demo button, or any date 14-03-2024 → 31-05-2024 (SoLEXS) /
            07-09-2026 → 15-09-2026 (soft+hard overlap).</span>
          </div>
        )}
      </Card>

      <Card title="3 · Replay it live — the nowcast in action"
        subtitle="Streams the selected day at high speed through the live detector. Every pop-up is a real-time flare alert."
        right={
          <div className="row">
            <label className="chk">speed
              <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} disabled={replayOn}>
                {[200, 600, 2000, 6000].map((s) => <option key={s} value={s}>{s}×</option>)}
              </select>
            </label>
            <button className={"btn " + (replayOn ? "danger" : "primary")}
              onClick={() => setReplayOn((v) => !v)} disabled={!state.from || !state.to}>
              {replayOn ? "■ Stop" : "▶ Start replay"}
            </button>
            <span className={"status " + replay.status}>{replay.status}</span>
          </div>
        }>
        <div className="muted">
          Think of it as watching the Sun's day compressed into seconds — the alert fires the
          moment the flare crosses the detection threshold, just like operations in real time.
        </div>
        {toast && (
          <div className="toast">
            🚨 FLARE NOWCAST — peak {toast.t} · {toast.cps} cps · {toast.sigma}σ · class ~{toast.cls}
          </div>
        )}
      </Card>

      <Card title="Flare catalog — the automated nowcast database"
        subtitle="Search, sort, filter, download. Click a row to zoom the chart to that flare — the URL updates so you can share the exact view."
        right={<span className="muted">{summary ? `${summary.total_flares} flares total` : ""}</span>}>
        {flLoading ? (
          <div className="empty-sm"><div className="spinner sm" /> loading catalog…</div>
        ) : (
          <FlareTable flares={fl ? fl.flares : []} windowFrom={state.from} windowTo={state.to}
            onSelect={(f) => {
              const s = parseUtc(f.start), e = parseUtc(f.end);
              setZoom([s - 600000, Math.max(e + 600000, s + 1800000)]);
              setDemo(false);
              window.scrollTo({ top: 0, behavior: "smooth" });
            }} />
        )}
      </Card>

      <DatasetCard />

      <ForecastStrip from={state.from} to={state.to} />
      </>
      )}

      {page === "guide" && <GuidePage />}
      {page === "science" && <SciencePanel />}

      <footer className="muted">
        Minor project — <b>solar-flare nowcasting</b> · Data: ISRO Aditya-L1 SoLEXS &amp; HEL1OS Level-1
        (ISSDC PRADAN) · Reference: NOAA GOES-16 XRS · Forecasting module = planned extension (Major project)
      </footer>
    </div>
  );
}
