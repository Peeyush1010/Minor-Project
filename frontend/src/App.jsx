import { useMemo, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ReferenceArea, ReferenceLine,
} from "recharts";
import { CLASS_COLORS, clsOf, fmtTime, parseUtc, useApi, useReplay, useSummary } from "./api";
import GuidePage from "./GuidePage";

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

const STEPS = [
  { n: 1, title: "Pick a day", desc: "Choose instrument & date — or tap an example above" },
  { n: 2, title: "Read the light curve", desc: "Spikes are flares; colored bands mark what the detector caught" },
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
    <div className="stat" title={hint || ""}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
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
      <span className="muted">(energy increases A→B→C→M→X, ×10 each step)</span>
    </div>
  );
}

/* ------------------------------------------------------------------ header */

function Header({ summary }) {
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
          <span className="badge-future">🔮 FORECASTING = FUTURE WORK (MAJOR PROJECT)</span>
        </div>
      </div>
      <div className="stats">
        <Stat label="Flares nowcasted" value={summary ? summary.total_flares : "…"}
          hint="Flares detected automatically across all days (master catalog)" />
        <Stat label="Seen by hard X-ray too" value={summary ? summary.hard_matched : "…"}
          hint="Events confirmed independently by HEL1OS in the overlap window" />
        <Stat label="Hard X leads soft by"
          value={summary?.median_hard_lead_s ? `${Math.round(summary.median_hard_lead_s)} s` : "–"}
          hint="Median head start of hard X-rays before soft X-rays (Neupert effect)" />
        <Stat label="Detection rate vs GOES"
          value={ev.tpr ? `${(ev.tpr * 100).toFixed(1)}%` : "–"}
          hint={`X ${Math.round((pc.X?.tpr || 0) * 100)}% · M ${Math.round((pc.M?.tpr || 0) * 100)}% · C ${Math.round((pc.C?.tpr || 0) * 100)}% — validated against NOAA GOES-16`} />
        <Stat label="False alarms / day" value={ev.far_per_day ? ev.far_per_day.toFixed(1) : "–"}
          hint="Most are real small flares below GOES's detection floor — SoLEXS is more sensitive" />
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- controls */

function Controls({ state, set }) {
  return (
    <Card title="1 · Pick a day & instrument"
      subtitle="SoLEXS sees the hot flare plasma (soft X-rays); HEL1OS sees the electron beams (hard X-rays)."
      right={
        <div className="presets">
          {PRESETS.map((p) => (
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
        <label>Day
          <input type="date" value={state.from} onChange={(e) => set({ from: e.target.value, to: e.target.value })} />
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
        Good first picks: any day 2024-03-14 → 2024-05-31 (big flare season) or 2026-09-07 → 09-15
        (both instruments observing).
      </div>
    </Card>
  );
}

/* -------------------------------------------------------------- lightcurve */

function Lightcurve({ data, flares, log }) {
  const ds = useMemo(() => downsampleMax(data, 4000), [data]);
  return (
    <ResponsiveContainer width="100%" height={360}>
      <LineChart data={ds} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#1e293b" />
        <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
          tickFormatter={(v) => fmtTime(v).slice(5, 16)} stroke="#64748b" tick={{ fontSize: 11 }} />
        <YAxis stroke="#64748b" tick={{ fontSize: 11 }} scale={log ? "log" : "auto"}
          domain={log ? ["auto", "auto"] : undefined} allowDataOverflow
          label={{ value: "X-ray counts / second", angle: -90, position: "insideLeft",
                   style: { fill: "#64748b", fontSize: 11 } }} />
        <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
          labelFormatter={(v) => fmtTime(v)} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {flares.map((f, i) => (
          <ReferenceArea key={i} x1={parseUtc(f.start)} x2={parseUtc(f.end)}
            fill={CLASS_COLORS[clsOf(f)] || "#64748b"} fillOpacity={0.14} ifOverflow="extendDomain" />
        ))}
        {flares.map((f, i) => (
          <ReferenceLine key={"p" + i} x={parseUtc(f.peak)} stroke={CLASS_COLORS[clsOf(f)] || "#64748b"}
            strokeDasharray="4 2" ifOverflow="extendDomain" />
        ))}
        <Line type="monotone" dataKey="rate" stroke="#38bdf8" dot={false} strokeWidth={1.4}
          name="count rate (cps) — spikes = flares" connectNulls={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
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
      badge="NOT part of this minor project"
      subtitle="A preview of the Major-project deliverable: an ML model (LightGBM) predicting “will a C-class-or-better flare erupt within 30 minutes?”. Shown here for demonstration only — kept out of the minor-project scope."
      right={<span className="pill-future">FUTURE · MAJOR PROJECT</span>}>
      {points.length ? (
        <ResponsiveContainer width="100%" height={130}>
          <LineChart data={points} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#1e293b" />
            <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
              tickFormatter={(v) => fmtTime(v).slice(5, 16)} stroke="#64748b" tick={{ fontSize: 11 }} />
            <YAxis domain={[0, 1]} stroke="#64748b" tick={{ fontSize: 11 }}
              label={{ value: "P(flare ≤30 min)", angle: -90, position: "insideLeft",
                       style: { fill: "#64748b", fontSize: 11 } }} />
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

const DATASET_LABELS = {
  solexs_merged: "SoLEXS (soft X-ray) — all days, one file",
  hel1os_merged: "HEL1OS (hard X-ray) — all detectors, one file",
  merged_all_data: "Combined — both instruments in one file",
};

function DatasetCard() {
  const { data } = useApi("/api/dataset", []);
  if (!data) return <Card title="📦 Merged dataset"><div className="muted">loading…</div></Card>;
  if (!data.available) {
    return (
      <Card title="📦 Merged dataset">
        <div className="muted">Not built yet — run <code>python -m backend.pipeline.export_merged</code></div>
      </Card>
    );
  }
  const files = Object.entries(data.files || {});
  const zips = data.raw_zips || {};
  return (
    <Card title="📦 Merged dataset — every download, one file each"
      subtitle="All PRADAN zips ingested, cleaned and flattened into single deliverable files (parquet + CSV). Details in DATASET.md."
      right={<span className="muted">{data.solexs_days} SoLEXS days · {data.hel1os_days} HEL1OS days</span>}>
      <div className="ds-grid">
        {files.map(([k, v]) => (
          <div className="ds-item" key={k}>
            <div className="ds-name">{DATASET_LABELS[k] || k}</div>
            <div className="ds-meta">
              <b>{(v.rows / 1e6).toFixed(1)}M</b> rows · parquet <b>{v.parquet_mb} MB</b> · CSV{" "}
              <b>{v.csv_mb} MB</b>
              <div className="muted">{(v.t_start || "").slice(0, 10)} → {(v.t_end || "").slice(0, 10)} UTC</div>
            </div>
          </div>
        ))}
      </div>
      <div className="muted hint-line">
        Built { (data.generated_utc || "").slice(0, 10) } from {zips.solexs?.n_zips ?? 0} SoLEXS +{" "}
        {zips.hel1os?.n_zips ?? 0} HEL1OS raw zips · flare catalog also exported:{" "}
        <code>backend/data/catalogs/master_catalog.csv</code>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------- flare table */

function FlareTable({ flares, onSelect }) {
  const [filter, setFilter] = useState("");
  const rows = useMemo(() => {
    if (!flares) return [];
    const f = filter.toUpperCase();
    return flares.filter((x) => !f || clsOf(x) === f).slice(0, 300);
  }, [flares, filter]);
  return (
    <div>
      <div className="table-tools">
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
        <span className="muted">{flares.length} flares in window (showing {rows.length}) — click a row to jump to its day</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th title="When the flare started">Start (UT)</th>
              <th title="Moment of maximum X-ray output">Peak (UT)</th>
              <th title="GOES class from calibrated flux — bigger letter = more energy">Class</th>
              <th title="Soft X-ray count rate at peak">Peak (cps)</th>
              <th title="How long the flare lasted">Dur (min)</th>
              <th title="Also detected independently by HEL1OS (hard X-rays)">Hard X</th>
              <th title="How many seconds the hard X-ray peak led the soft X-ray peak (Neupert effect)">Lead (s)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <tr key={f.flare_id} onClick={() => onSelect && onSelect(f)} className="clickable">
                <td>{fmtTime(parseUtc(f.start))}</td>
                <td>{fmtTime(parseUtc(f.peak))}</td>
                <td><span className="pill" style={{ background: CLASS_COLORS[clsOf(f)] }}>{clsOf(f)}</span></td>
                <td>{f.solexs_peak_cps?.toFixed(1)}</td>
                <td>{(f.duration_s / 60).toFixed(0)}</td>
                <td>{f.hard_detected ? "●" : "–"}</td>
                <td>{f.hard_lead_s != null ? Math.round(f.hard_lead_s) : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------------- app */

export default function App() {
  const { data: summary } = useSummary();
  const [state, set_] = useState({
    instrument: "solexs", detector: "SDD2",
    from: "2024-05-14", to: "2024-05-14", bin_s: 60, log: true,
  });
  const set = (patch) => set_((s) => ({ ...s, ...patch }));

  const qs = new URLSearchParams({
    instrument: state.instrument, detector: state.detector,
    from: state.from, to: state.to, bin_s: String(state.bin_s),
  });
  const { data: lc } = useApi(`/api/lightcurve?${qs}`, [qs.toString()]);
  const { data: fl } = useApi(`/api/flares?${new URLSearchParams({ from: state.from, to: state.to })}`,
    [state.from, state.to]);

  const [replayOn, setReplayOn] = useState(false);
  const [speed, setSpeed] = useState(2000);
  const [toast, setToast] = useState(null);
  const [showHow, setShowHow] = useState(false);
  const [page, setPage] = useState("dashboard");
  const replay = useReplay({
    instrument: state.instrument, detector: state.detector,
    from: state.from, to: state.to, speed,
    enabled: replayOn,
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

  return (
    <div className="app">
      <nav className="topnav">
        <button className={"navbtn" + (page === "dashboard" ? " on" : "")}
          onClick={() => setPage("dashboard")}>🛰 Dashboard</button>
        <button className={"navbtn" + (page === "guide" ? " on" : "")}
          onClick={() => setPage("guide")}>📖 Guide &amp; Glossary</button>
        <span className="muted nav-hint">Presenting? Open the Guide page — every keyword explained with “where you see it” pointers.</span>
      </nav>

      {page === "dashboard" && (
      <>
      <Header summary={summary} />
      <StepBar />

      <Controls state={state} set={set} />

      <Card title="2 · Watch the Sun — light curve"
        subtitle="Each point is the Sun's X-ray output. A sudden spike = a flare; the colored band shows the flare our detector caught, dashed line = its peak."
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
              <li><b>Colored bands</b> — flares detected automatically. Band color = class (red X &gt; orange M &gt; yellow C &gt; blue B).</li>
              <li><b>Gaps in the line</b> — no data: instrument off, calibration, or Earth blocked the view.</li>
              <li><b>log scale</b> — ON, giant and tiny flares fit on one chart. Turn OFF to inspect quiet-Sun detail.</li>
              <li><b>Bin size</b> — averages seconds per point; larger = smoother, smaller = more detail.</li>
              <li><b>Replay (step 3)</b> — replays the day at high speed through the live detector: each 🚨 pop-up is a nowcast alert, exactly as a ground station would receive it.</li>
            </ul>
          </div>
        )}
        <div className="lc-meta muted">
          {state.instrument.toUpperCase()} · {state.detector} · {chartPoints.length} points
          {replayOn && <span className="live-chip">● LIVE REPLAY ×{speed}</span>}
        </div>
        {chartPoints.length
          ? <Lightcurve data={chartPoints} flares={chartFlares} log={state.log} />
          : <div className="empty">
              No data for this window.<br />
              <span className="muted">Try an example day above, or any date 2024-03-14 → 2024-05-31 (SoLEXS) /
              2026-09-07 → 09-15 (soft+hard overlap).</span>
            </div>}
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
        subtitle="Every flare detected across all observed days, with GOES class, duration and hard-X confirmation. Click a row to jump to that day."
        right={<span className="muted">{summary ? `${summary.total_flares} flares total` : ""}</span>}>
        <FlareTable flares={fl ? fl.flares : []} onSelect={(f) => {
          const d = new Date(parseUtc(f.start)).toISOString().slice(0, 10);
          set({ from: d, to: d, instrument: "solexs", detector: "SDD2" });
          window.scrollTo({ top: 0, behavior: "smooth" });
        }} />
      </Card>

      <DatasetCard />

      <ForecastStrip from={state.from} to={state.to} />
      </>
      )}

      {page === "guide" && <GuidePage />}

      <footer className="muted">
        Minor project — <b>solar-flare nowcasting</b> · Data: ISRO Aditya-L1 SoLEXS &amp; HEL1OS Level-1
        (ISSDC PRADAN) · Reference: NOAA GOES-16 XRS · 🔮 Forecasting prototype = future work (Major project)
      </footer>
    </div>
  );
}
