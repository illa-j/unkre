"use client";

import { useEffect, useState } from "react";

type ProbeState = "checking" | "ok" | "down";
type Probe = { id: string; label: string; detail: string; url: string };

const probes: Probe[] = [
  { id: "site", label: "Website", detail: "Public pages and the Studio shell", url: "/healthz" },
  { id: "api", label: "Studio API", detail: "Sign-in, generations, credits and account data", url: "/api/healthz" },
];

export function StatusProbe() {
  const [states, setStates] = useState<Record<string, ProbeState>>({ site: "checking", api: "checking" });
  const [checkedAt, setCheckedAt] = useState("");

  useEffect(() => {
    let active = true;
    async function run() {
      const results = await Promise.all(probes.map(async probe => {
        const controller = new AbortController();
        const timeout = window.setTimeout(() => controller.abort(), 5000);
        try {
          const response = await fetch(probe.url, { cache: "no-store", signal: controller.signal });
          return [probe.id, response.ok ? "ok" : "down"] as const;
        } catch {
          return [probe.id, "down"] as const;
        } finally {
          window.clearTimeout(timeout);
        }
      }));
      if (!active) return;
      setStates(Object.fromEntries(results));
      setCheckedAt(new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
    }
    void run();
    const timer = window.setInterval(() => void run(), 60000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  return <section aria-labelledby="status-checks-title">
    <h2 id="status-checks-title">Live checks</h2>
    <div className="status-grid">
      {probes.map(probe => {
        const state = states[probe.id];
        const label = state === "ok" ? "Operational" : state === "down" ? "Unavailable" : "Checking";
        return <article className="status-card" key={probe.id}>
          <div className="status-card-head"><span className={`service-status-dot is-${state}`} aria-hidden="true" /><span>{label}</span></div>
          <h3>{probe.label}</h3>
          <p>{probe.detail}</p>
        </article>;
      })}
      <article className="status-card">
        <div className="status-card-head"><span className="service-status-dot is-external" aria-hidden="true" /><span>External</span></div>
        <h3>Payments</h3>
        <p>ATLOS and Telegram Stars process payments. A provider outage can delay confirmation even when this site is up.</p>
      </article>
      <article className="status-card">
        <div className="status-card-head"><span className="service-status-dot is-external" aria-hidden="true" /><span>Limited visibility</span></div>
        <h3>Generation queue</h3>
        <p>Generation workers are internal. A failed or stuck request is shown in Studio or My images; contact support if it does not resolve.</p>
      </article>
    </div>
    <p className="status-checked" role="status">Last checked {checkedAt || "…"} · checks run again every 60 seconds.</p>
  </section>;
}
