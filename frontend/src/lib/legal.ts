import type { Metadata } from "next";
import { canonicalUrl, defaultSocialImage, isIndexable, languageAlternates, site } from "./site";

export const legal = {
  effectiveDate: "3 November 2026",
  lastUpdated: "3 November 2026",
  updatedISO: "2026-11-03",
  contactEmail: site.supportEmail ?? "support@unkre.cc",
  minimumAge: 18,
  responseTime: "two business days",
  refundWindowDays: 14,
  governingLaw: "the laws of the operator’s principal place of business",
};

export const legalPages = [
  { href: "/trust", label: "Trust center" },
  { href: "/about", label: "About UNKRE" },
  { href: "/contact", label: "Contact" },
  { href: "/privacy", label: "Privacy Policy" },
  { href: "/terms", label: "Terms of Service" },
  { href: "/refunds", label: "Refunds & cancellations" },
  { href: "/acceptable-use", label: "Acceptable use" },
  { href: "/copyright", label: "Copyright & likeness" },
  { href: "/security", label: "Security" },
  { href: "/transparency", label: "Transparency" },
  { href: "/status", label: "Service status" },
] as const;

export function privacyRequestHref(kind: "export" | "delete") {
  const subject = kind === "export" ? "[Privacy] Data export request" : "[Privacy] Account deletion request";
  const action = kind === "export" ? "export a copy of the personal data linked to" : "delete the account and personal data linked to";
  const body = `Please ${action} my UNKRE account.\n\nAccount email or Telegram username:\nAccount ID (if known):\n\nI understand that financial and accounting records may be retained where required by law.`;
  return `mailto:${legal.contactEmail}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

export function legalMetadata({ title, description, path, ogAlt }: {
  title: string;
  description: string;
  path: string;
  ogAlt?: string;
}): Metadata {
  const url = canonicalUrl(path);
  const image = defaultSocialImage;
  const alt = ogAlt ?? `${title} — UNKRE`;
  return {
    title,
    description,
    alternates: url ? { canonical: url, languages: languageAlternates(url) } : undefined,
    robots: {
      index: isIndexable,
      follow: isIndexable,
      ...(isIndexable ? { "max-image-preview": "large" as const, "max-snippet": -1, "max-video-preview": -1 } : {}),
    },
    openGraph: {
      type: "website",
      locale: "en_US",
      siteName: site.name,
      title,
      description,
      ...(url ? { url } : {}),
      images: [{ url: image, width: 1200, height: 630, alt }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [{ url: image, alt }],
    },
  };
}
