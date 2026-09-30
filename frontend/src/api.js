import { useEffect, useMemo, useRef, useState } from "react";

const API = "http://localhost:8000";

/* ------------------------------------------------------------- api status */

let _apiUp = null; // null = unknown, true = up, false = down
const _statusSubs = new Set();
let _coverageCache = null;
const _covSubs = new Set();

function fetchCoverage() {
  if (_coverageCache) {
    _covSubs.forEach((s) => s(_coverageCache));
    return;
  }
  fetch(`${API}/api/coverage`)
    .then((r) => {
      if (!r.ok) throw new Error(String(r.status));
      return r.json();
    })
    .then((j) => {
      _coverageCache = j;
      _apiUp = true;
      _covSubs.forEach((s) => s(j));
      _statusSubs.forEach((s) => s(true));
    })
    .catch(() => {
      _apiUp = false;
      _statusSubs.forEach((s) => s(false));
    });
}

/** True when the backend answers, false when offline, null while probing. */
export function useApiStatus() {
  const [up, setUp] = useState(_apiUp);
  useEffect(() => {
    _statusSubs.add(setUp);
    fetchCoverage();
    const t = setInterval(fetchCoverage, 30000);
    return () => {
      _statusSubs.delete(setUp);
      clearInterval(t);
    };
  }, []);
  return up;
}

/** Shared /api/coverage payload (fetched once, shared across components). */
export function useCoverage() {
  const [cov, setCov] = useState(_coverageCache);
  useEffect(() => {
    _covSubs.add(setCov);
    fetchCoverage();
    return () => _covSubs.delete(setCov);
  }, []);
  return cov;
}

/** Loaded day counts for the status pill: { solexs, hel1os } or null. */
export function useDayCounts() {
  const cov = useCoverage();
  return useMemo(() => {
    if (!cov) return null;
    return {
      solexs: (cov.solexs?.SDD2 || []).length,
      hel1os: (cov.hel1os?.CDTE1 || []).length,
    };
  }, [cov]);
}

/* ----------------------------------------------------------------- hooks */

export function useSummary() {
  return useApi("/api/summary", []);
}

export function useApi(path, deps) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    setData(null);
    setErr(null);
    setLoading(true);
    fetch(`${API}${path}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${r.status} ${r.statusText}`))))
      .then((j) => {
        if (alive) {
          setData(j);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (alive) {
          setErr(String(e.message || e));
          setLoading(false);
        }
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, err, loading };
}

/* ------------------------------------------------------------- downloads */

function triggerDownload(href, filename) {
  const a = document.createElement("a");
  a.href = href;
  if (filename) a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/** Client-side CSV export of table rows. */
export function downloadCsv(filename, rows, columns) {
  const esc = (v) => {
    if (v === null || v === undefined) return "";
    const s = String(v);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const head = columns.map((c) => esc(c.label)).join(",");
  const body = rows.map((r) => columns.map((c) => esc(r[c.key])).join(",")).join("\n");
  const blob = new Blob([head + "\n" + body], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  triggerDownload(url, filename);
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

/** Server-side file download (merged datasets, reports). */
export function downloadFile(url) {
  triggerDownload(`${API}${url}`);
}

/* ----------------------------------------------------------- replay */

/** Chunked websocket replay consumer: streams a day through the live detector. */
export function useReplay({ instrument, detector, from, to, speed, enabled, onAlert, onDone }) {
  const wsRef = useRef(null);
  const [points, setPoints] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [status, setStatus] = useState("idle");

  useEffect(() => {
    if (!enabled) return undefined;
    setPoints([]);
    setAlerts([]);
    setStatus("connecting");
    const qs = new URLSearchParams({ instrument, detector, from, to, speed: String(speed) });
    const ws = new WebSocket(`ws://localhost:8000/ws/replay?${qs}`);
    wsRef.current = ws;
    let done = false;
    ws.onopen = () => setStatus("streaming");
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "points") {
        setPoints((prev) => {
          const next = prev.concat(msg.t.map((tt, i) => ({ t: tt, rate: msg.rate[i] })));
          return next.length > 200000 ? next.slice(next.length - 200000) : next;
        });
      } else if (msg.type === "alerts") {
        setAlerts((prev) => prev.concat(msg.events));
        if (msg.events.length && onAlert) onAlert(msg.events[msg.events.length - 1]);
      } else if (msg.type === "done") {
        done = true;
        setStatus("done");
        if (onDone) onDone();
      } else if (msg.type === "error") {
        setStatus(`error: ${msg.message}`);
      }
    };
    ws.onclose = () => setStatus(done ? "done" : "closed");
    ws.onerror = () => setStatus("error");
    return () => ws.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, instrument, detector, from, to, speed]);

  return { points, alerts, status };
}

/* ----------------------------------------------------------- time & misc */

/** Parse backend timestamps (naive ISO = UTC) safely regardless of browser TZ. */
export function parseUtc(s) {
  if (!s) return NaN;
  if (s.length > 10 && !/[+Z]/.test(s.slice(10))) return Date.parse(s + "Z");
  return Date.parse(s);
}

/** Flare class color scheme shared by charts and tables. */
export const CLASS_COLORS = {
  X: "#ef4444",
  M: "#f97316",
  C: "#eab308",
  B: "#3b82f6",
  A: "#64748b",
};

export function clsOf(f) {
  return f.class_proxy || "C";
}

export function fmtTime(ms) {
  if (!ms) return "–";
  return new Date(ms).toISOString().replace("T", " ").slice(0, 16) + " UT";
}

/** Dashboard-standard date label: DD-MM-YYYY (UTC). */
export function fmtDateLabel(dmy) {
  if (!dmy) return "";
  const [y, m, d] = dmy.split("-");
  return `${d}-${m}-${y}`;
}


