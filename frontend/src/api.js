import { useEffect, useMemo, useRef, useState } from "react";

const API = "http://localhost:8000";

export function useApi(path, deps) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    let alive = true;
    setData(null);
    fetch(`${API}${path}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(`${r.status} ${r.statusText}`)))
      .then((j) => alive && setData(j))
      .catch((e) => alive && setErr(String(e)));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, err };
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

/** Parse backend timestamps (naive ISO = UTC) safely regardless of browser TZ. */
export function parseUtc(s) {
  if (!s) return NaN;
  if (s.length > 10 && !s.endsWith("Z") && !/[+Z]/.test(s.slice(10))) return Date.parse(s + "Z");
  return Date.parse(s);
}

/** Chunked binary-free websocket replay consumer. */
export function useReplay({ instrument, detector, from, to, speed, enabled, onAlert, onDone }) {
  const wsRef = useRef(null);
  const [points, setPoints] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [status, setStatus] = useState("idle");

  useEffect(() => {
    if (!enabled) return;
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

export function useSummary() {
  return useApi("/api/summary", []);
}

export function useMemoStats(points, alerts) {
  return useMemo(() => {
    if (!points.length) return { n: 0 };
    return {
      n: points.length,
      alerts: alerts.length,
    };
  }, [points, alerts]);
}
