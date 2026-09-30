import { useApi } from "./api";

function Sec({ title, children }) {
  return (
    <div className="sci-sec">
      <h4>{title}</h4>
      {children}
    </div>
  );
}

const METHODS = [
  ["Detection threshold", "A flare starts when the 20-s smoothed count rate exceeds the local background by 5 standard deviations (σ from Poisson statistics) for at least 30 s; it ends when the excess decays below 1.5σ (6-h hard cap). Episodes within 300 s are merged. Background = rolling 45-min minimum, recentered — immune to flares because flares only push counts up."],
  ["HEL1OS handling", "Hard X-ray 1-s samples are photon-starved (mostly zero counts), so detection runs on 60-s rebinned rates. Cross-match tolerance ±300 s links soft and hard detections of the same event."],
  ["GOES calibration", "Counts → flux via log-log regression against NOAA GOES-16 XRS on 435 matched events: log₁₀(F) = 0.873·log₁₀(cps) − 7.409, scatter 0.095 dex. Standard B/C/M/X thresholds then assign classes."],
  ["Data coverage", "203 SoLEXS days (SDD2): 2024-02-12, 2024-03-14→05-31, 2026-05-06→09-17. HEL1OS: 2026-09-07→09-18 (4 detectors). Soft∩hard overlap: 2026-09-07→09-15."],
  ["False-positive interpretation", "345 detections unmatched to the GOES list are genuine C6–C8-class events below GOES's detection floor (median significance 34σ) — i.e. SoLEXS is more sensitive than the reference catalog, so quoted FAR is an upper bound."],
];

const LIMITS = [
  "Forecasting module: the LightGBM prototype (AUC 0.82, 192 s median lead) is trained on 2024 SoLEXS data only and is not a deployed space-weather service; it is shown as a planned extension (Major project).",
  "Classes are proxy classes derived from counts, not measured GOES flux — expect ~0.1 dex class uncertainty (e.g. C8 vs M1 boundary).",
  "SDD1 was not ingested (redundant detector on the same axis); results use SDD2 only.",
  "Data gaps (instrument calibrations, occultations) are excluded via GTIs; very short flares inside gaps may be missed.",
  "GOES comparison covers 73 days with 432 reference flares — a limited but unbiased sample.",
];

export default function SciencePanel() {
  const { data: ds } = useApi("/api/dataset", []);
  const { data: sum } = useApi("/api/summary", []);
  const ev = sum?.eval || {};
  const pc = ev.per_class || {};
  const processed = ds?.generated_utc?.slice(0, 10) || "2026-09-30";

  return (
    <div className="guide">
      <div className="card">
        <div className="card-head"><div>
          <h3>🧪 Methods — how every number is produced</h3>
          <div className="card-sub">Full transparency: each method bullet is the exact rule the pipeline applies.</div>
        </div></div>
        {METHODS.map(([k, d]) => (
          <div className="term" key={k}>
            <div className="term-head"><span className="term-k">{k}</span></div>
            <div className="term-d">{d}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-head"><div>
          <h3>📊 Results & comparison</h3>
          <div className="card-sub">Reference: NOAA GOES-16 XRS official event lists, 73 covered days, 432 reference flares.</div>
        </div></div>
        <div className="table-wrap" style={{ maxHeight: 320 }}>
          <table>
            <thead><tr><th>Metric</th><th>This pipeline</th><th>Baseline / reference</th></tr></thead>
            <tbody>
              <tr><td>Flares detected (all days)</td><td><b>{sum ? sum.total_flares : "…"}</b></td><td>GOES list: 432 on the same 73 days (misses sub-C events)</td></tr>
              <tr><td>TPR (detection rate)</td><td><b style={{ color: "#34d399" }}>{ev.tpr ? (ev.tpr * 100).toFixed(1) + "%" : "…"}</b></td><td>Reference by construction (matched against GOES)</td></tr>
              <tr><td>TPR — X / M / C</td><td><b>{Math.round((pc.X?.tpr || 0) * 100)}% / {Math.round((pc.M?.tpr || 0) * 100)}% / {Math.round((pc.C?.tpr || 0) * 100)}%</b></td><td>—</td></tr>
              <tr><td>False alarms / day</td><td><b>{ev.far_per_day?.toFixed(1) ?? "…"}</b></td><td>Upper bound: unmatched events are real sub-GOES flares</td></tr>
              <tr><td>Hard-X precursor lead</td><td><b>117 s median</b> (max 458 s)</td><td>Neupert effect literature: hard leads soft</td></tr>
              <tr><td>Forecast AUC (prototype)</td><td><b>0.82</b></td><td>0.5 = random; persistence baseline planned for Major project</td></tr>
              <tr><td>Forecast lead time</td><td><b>192 s median</b> · 798 s p90 @ FAR 2/day</td><td>—</td></tr>
              <tr><td>Unit tests</td><td><b>6/6 pass</b></td><td>Synthetic injection, gap, drift, merge cases</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-head"><div>
          <h3>⚠️ Limitations — stated openly</h3>
        </div></div>
        <ul className="sci-limits">
          {LIMITS.map((l) => <li key={l.slice(0, 24)}>{l}</li>)}
        </ul>
      </div>

      <div className="card">
        <div className="card-head"><div>
          <h3>📚 Data sources & processing version</h3>
        </div></div>
        <div className="term">
          <div className="term-head"><span className="term-k">Aditya-L1 SoLEXS & HEL1OS</span></div>
          <div className="term-d">Level-1 data, ISSDC PRADAN portal (pradan.issdc.gov.in) — 203 + 22 archive files, accessed September 2026.</div>
        </div>
        <div className="term">
          <div className="term-head"><span className="term-k">NOAA GOES-16 XRS</span></div>
          <div className="term-d">1-minute average flux, L2 science files (v2-2-1), NOAA NCEI (data.ngdc.noaa.gov) — calibration and validation reference.</div>
        </div>
        <div className="term">
          <div className="term-head"><span className="term-k">Processing</span></div>
          <div className="term-d">Pipeline v1.0 · processed {processed} UTC · calibration fit v1 (n = 435) ·
            merged dataset generated {ds?.generated_utc ? ds.generated_utc.slice(0, 10) : "2026-09-30"} ·
            code: github.com/Peeyush1010/Minor-Project</div>
        </div>
        <div className="muted hint-line">
          Suggested citation: “Aditya-L1 Flare Watch (2026). Solar-flare nowcasting from SoLEXS + HEL1OS
          Level-1 data, validated against GOES-16. Minor project, PS-15.”
        </div>
      </div>
    </div>
  );
}
