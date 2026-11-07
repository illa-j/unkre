export const referralStorageKey = "unkre.referral.v1";
const referralPattern = /^[0-9a-f]{24}$/;

export function normalizeReferralCode(value: string | null | undefined) {
  const code = value?.trim().toLowerCase() ?? "";
  return referralPattern.test(code) ? code : "";
}

export function rememberReferralCode(search: string) {
  const code = normalizeReferralCode(new URLSearchParams(search).get("ref"));
  if (!code) return "";
  try { sessionStorage.setItem(referralStorageKey, code); } catch { /* The code still works for this page view. */ }
  return code;
}

export function readReferralCode() {
  try { return normalizeReferralCode(sessionStorage.getItem(referralStorageKey)); } catch { return ""; }
}

export function forgetReferralCode() {
  try { sessionStorage.removeItem(referralStorageKey); } catch { /* Nothing to clear. */ }
}

export function inviteUrl(origin: string, code: string) {
  const url = new URL("/", origin);
  url.searchParams.set("ref", normalizeReferralCode(code));
  return url.href;
}
