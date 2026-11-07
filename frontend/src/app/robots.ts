import type { MetadataRoute } from "next";
import { isIndexable, site } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: isIndexable
      ? { userAgent: "*", allow: "/", disallow: ["/admin", "/api/", "/studio"] }
      : { userAgent: "*", disallow: "/" },
    ...(isIndexable && site.url ? { sitemap: new URL("/sitemap.xml", site.url).href } : {}),
  };
}
