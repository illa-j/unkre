"use client";

import { useReportWebVitals } from "next/web-vitals";
import { trackEvent } from "@/lib/analytics";

type Report = Parameters<typeof useReportWebVitals>[0];
const reported = new Set<string>();
const report: Report = metric => {
  if (metric.name !== "LCP" && metric.name !== "INP" && metric.name !== "CLS") return;
  const key = `${metric.id}:${metric.name}`;
  if (reported.has(key)) return;
  reported.add(key);
  if (reported.size > 200) {
    const oldest = reported.values().next().value;
    if (oldest) reported.delete(oldest);
  }
  let path = location.pathname;
  if ("navigationURL" in metric && typeof metric.navigationURL === "string") {
    try { path = new URL(metric.navigationURL, location.origin).pathname; } catch { /* Use the current path. */ }
  }
  trackEvent("web_vital", { metric:metric.name, value:Math.round(metric.value*1000)/1000, path });
};

export function WebVitalsReporter() {
  useReportWebVitals(report);
  return null;
}
