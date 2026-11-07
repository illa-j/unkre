export const analyticsEvents = ["landing_view", "cta_click", "signup_completed", "signin_completed", "generation_started", "generation_completed", "generation_failed", "web_vital"] as const;
export type AnalyticsEvent = typeof analyticsEvents[number];
export type AnalyticsPayload = { event: AnalyticsEvent; metric?: "LCP" | "INP" | "CLS"; value?: number; placement?: string; preset?: string; path?: string; device?: "mobile" | "desktop"; channel?: "search" | "social" | "direct" | "referral" };

export function validAnalyticsPayload(value: unknown): AnalyticsPayload | null {
  if (!value || typeof value !== "object") return null;
  const input = value as Record<string, unknown>;
  if (!analyticsEvents.includes(input.event as AnalyticsEvent)) return null;
  const result: AnalyticsPayload = { event: input.event as AnalyticsEvent };
  if (input.event === "web_vital") {
    if (!["LCP", "INP", "CLS"].includes(String(input.metric)) || typeof input.value !== "number" || !Number.isFinite(input.value) || input.value < 0 || input.value > 86400000) return null;
    result.metric = input.metric as AnalyticsPayload["metric"];
    result.value = input.value;
  }
  for (const key of ["placement", "preset"] as const) {
    if (input[key] !== undefined) {
      if (typeof input[key] !== "string" || !/^[a-z0-9_-]{1,48}$/.test(input[key])) return null;
      result[key] = input[key];
    }
  }
  if (input.path !== undefined) {
    if (typeof input.path !== "string" || !/^\/(?:studio(?:\/[a-z-]+)?|learn\/[a-z0-9-]+)?$/.test(input.path)) return null;
    result.path = input.path;
  }
  if (input.device === "mobile" || input.device === "desktop") result.device = input.device;
  if (["search", "social", "direct", "referral"].includes(String(input.channel))) result.channel = input.channel as AnalyticsPayload["channel"];
  return result;
}

/** First-party, aggregate events: no prompts, files, user IDs, cookies or query strings. */
export function trackEvent(event: AnalyticsEvent, properties: Pick<AnalyticsPayload, "placement" | "preset" | "metric" | "value" | "path"> = {}) {
  if (typeof window === "undefined" || navigator.doNotTrack === "1") return;
  let channel: AnalyticsPayload["channel"] = "direct";
  try {
    const host = document.referrer ? new URL(document.referrer).hostname : "";
    if (host && host !== location.hostname) channel = /(?:google|bing|duckduckgo|yahoo)\./.test(host) ? "search" : /(?:instagram|facebook|tiktok|t\.co|reddit|telegram)\./.test(host) ? "social" : "referral";
  } catch { /* A malformed referrer is treated as direct. */ }
  const rawPath = properties.path ?? location.pathname;
  const path = rawPath.startsWith("/studio") ? "/studio" : rawPath;
  const payload = validAnalyticsPayload({ event, ...properties, path, device: matchMedia("(max-width: 760px)").matches ? "mobile" : "desktop", channel });
  if (!payload) return;
  window.dispatchEvent(new CustomEvent("unkre:analytics", { detail: payload }));
  const body = JSON.stringify(payload);
  try {
    void fetch("/api/analytics", { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: true, credentials: "omit" }).catch(() => {});
  } catch { /* Analytics must never prevent creation or navigation. */ }
}
