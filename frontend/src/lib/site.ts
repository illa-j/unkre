function validSiteUrl(value: string | undefined): URL | undefined {
  if (!value) return;
  try {
    const url = new URL(value);
    if (!["https:", "http:"].includes(url.protocol) || url.username || url.password) return;
    return new URL("/", url);
  } catch { return; }
}

function publicLink(value: string | undefined) {
  if (!value) return;
  try { const url = new URL(value); return url.protocol === "https:" && !url.username && !url.password ? url.href : undefined; } catch { return; }
}

const configuredCredits = Number(process.env.NEXT_PUBLIC_WELCOME_CREDITS ?? "15");
const supportEmail = process.env.NEXT_PUBLIC_SUPPORT_EMAIL;
const defaultTelegramBotUrl = "https://t.me/unkre_bot";
export const site = {
  name: "UNKRE",
  title: "UNKRE — Uncensored & NSFW AI Image Generator",
  description: "Create ultra-realistic SFW and NSFW AI images with Krea 2 and Qwen Image 2.1. Use reference photos, build recurring characters and explore LoRAs.",
  url: validSiteUrl(process.env.NEXT_PUBLIC_SITE_URL),
  welcomeCredits: Number.isSafeInteger(configuredCredits) && configuredCredits >= 0 ? configuredCredits : 15,
  supportEmail: supportEmail && /^[^\s@\r\n]+@[^\s@\r\n]+\.[^\s@\r\n]+$/.test(supportEmail) ? supportEmail : undefined,
  privacyUrl: publicLink(process.env.NEXT_PUBLIC_PRIVACY_URL),
  termsUrl: publicLink(process.env.NEXT_PUBLIC_TERMS_URL),
  telegramBotUrl: publicLink(process.env.NEXT_PUBLIC_TELEGRAM_BOT_URL) ?? defaultTelegramBotUrl,
};
export const defaultSocialImage = "/og/home.jpg";
export const isIndexable = process.env.SITE_INDEXABLE !== "false";
export function canonicalUrl(path = "/") { return site.url ? new URL(path, site.url).href : undefined; }
export function languageAlternates(url: string | undefined) {
  const normalized = url?.replace(/\/+$/, "");
  return normalized ? { en: normalized, "x-default": normalized } : undefined;
}
export const welcomeOffer = site.welcomeCredits > 0 ? `${site.welcomeCredits} free credits for new accounts` : "Create your account with Google or Telegram";
