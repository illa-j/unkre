import type { MetadataRoute } from "next";
import { isIndexable, canonicalUrl, site, languageAlternates } from "@/lib/site";
import { publicGuides, guidesUpdatedAt } from "@/lib/public-guides";
import { legalPages, legal } from "@/lib/legal";

function sitemapEntry(url: string, lastModified: Date, changeFrequency: "monthly" | "yearly", priority: number): MetadataRoute.Sitemap[number] {
  const normalized = url.replace(/\/+$/, "");
  return { url: normalized, lastModified, changeFrequency, priority, alternates: { languages: languageAlternates(normalized) } };
}

export default function sitemap(): MetadataRoute.Sitemap {
  if (!isIndexable || !site.url) return [];
  const lastModified = new Date(guidesUpdatedAt);
  const legalUpdated = new Date(legal.updatedISO);
  return [
    sitemapEntry(canonicalUrl()!, lastModified, "monthly", 1),
    ...publicGuides.map((guide) => sitemapEntry(canonicalUrl(`/learn/${guide.slug}`)!, lastModified, "monthly", 0.7)),
    ...legalPages.map((page) => sitemapEntry(canonicalUrl(page.href)!, legalUpdated, "yearly", page.href === "/about" || page.href === "/trust" ? 0.6 : 0.4)),
  ];
}
