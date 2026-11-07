const dateFormat = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric" });
const dateTimeFormat = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
const numberFormat = new Intl.NumberFormat("en-US");

export function formatNumber(value: number | null | undefined): string {
  return numberFormat.format(Number(value ?? 0));
}

export function formatMoney(value: string | number | null | undefined, currency = "USD"): string {
  const amount = Number(value ?? 0);
  const digits = Number.isFinite(amount) ? (Number.isInteger(amount) ? 0 : 2) : 0;
  return amount.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits }) + (currency === "XTR" ? " ★" : ` ${currency}`);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dateFormat.format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dateTimeFormat.format(date);
}

export function isoDay(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : `${date.getUTCDate()}/${date.getUTCMonth() + 1}`;
}

export type BadgeTone = "ok" | "bad" | "warn" | "muted";

export function statusTone(status: string): BadgeTone {
  switch (status) {
    case "completed":
    case "succeeded":
    case "active":
      return "ok";
    case "failed":
    case "cancelled":
    case "timed_out":
    case "expired":
    case "refunded":
      return "bad";
    case "processing":
    case "queued":
    case "pending":
      return "warn";
    default:
      return "muted";
  }
}

export function displayUser(firstName: string, lastName?: string | null, username?: string | null, email?: string | null): string {
  const name = [firstName, lastName].filter(Boolean).join(" ").trim();
  return name || (username ? `@${username}` : email ?? "Unknown user");
}

export function initials(value: string): string {
  return value.trim().split(/\s+/).slice(0, 2).map(part => part[0]?.toUpperCase() ?? "").join("") || "?";
}
