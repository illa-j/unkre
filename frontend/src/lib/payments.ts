export function multiplyPrice(value: string, credits: number) {
  const match = /^(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/.exec(value);
  if (!match || !Number.isSafeInteger(credits) || credits < 1) return null;
  const exponent = Number(match[3] ?? 0);
  if (Math.abs(exponent) > 100) return null;
  const fraction = match[2] ?? "";
  const scale = Math.max(0, fraction.length - exponent);
  const units = BigInt(match[1] + fraction + "0".repeat(Math.max(0, exponent - fraction.length)));
  const scaled = (units * BigInt(credits)).toString().padStart(scale + 1, "0");
  return scale ? `${scaled.slice(0, -scale)}.${scaled.slice(-scale)}`.replace(/\.?0+$/, "") : scaled;
}

export function safeCheckoutUrl(value: string): string | null {
  try { const url = new URL(value); return url.protocol === "https:" && !url.username && !url.password ? url.href : null; } catch { return null; }
}

function parseDecimal(value: string): { units: bigint; scale: number } | null {
  const match = /^(\d+)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/.exec(value.trim());
  if (!match) return null;
  const exponent = Number(match[3] ?? 0);
  if (!Number.isInteger(exponent) || Math.abs(exponent) > 100) return null;
  const fraction = match[2] ?? "";
  let units = BigInt(match[1] + fraction);
  let scale = fraction.length - exponent;
  if (scale < 0) {
    units *= BigInt(10) ** BigInt(-scale);
    scale = 0;
  }
  return { units, scale };
}

/** How many whole credits a given price buys at the configured per-credit rate. */
export function creditsForPrice(value: string, unit: string): number | null {
  const price = parseDecimal(value);
  const rate = parseDecimal(unit);
  if (!price || !rate || rate.units <= BigInt(0)) return null;
  const numerator = price.units * BigInt(10) ** BigInt(rate.scale);
  const denominator = rate.units * BigInt(10) ** BigInt(price.scale);
  const credits = numerator / denominator;
  if (credits < BigInt(1) || credits > BigInt(Number.MAX_SAFE_INTEGER)) return null;
  return Number(credits);
}
