import Link from "next/link";
import type { ReactNode } from "react";
import { legal, legalPages } from "@/lib/legal";
import { canonicalUrl, site } from "@/lib/site";

export function LegalArticle({ title, intro, current, wide = false, schemaType = "WebPage", children }: {
  title: string;
  intro: string;
  current: string;
  wide?: boolean;
  schemaType?: "WebPage" | "AboutPage" | "ContactPage";
  children: ReactNode;
}) {
  const url = canonicalUrl(current);
  const schema = url ? {
    "@context": "https://schema.org",
    "@type": schemaType,
    "@id": `${url}#webpage`,
    url,
    name: title,
    description: intro,
    inLanguage: "en",
    dateModified: legal.updatedISO,
    publisher: { "@type": "Organization", name: site.name, url: site.url?.href },
  } : null;

  return <div className={`legal-article${wide ? " is-wide" : ""}`}>
    <nav className="guide-breadcrumb" aria-label="Breadcrumb">
      <Link href="/">UNKRE</Link>
      <span aria-hidden="true">/</span>
      {current === "/trust" ? null : <><Link href="/trust">Trust center</Link><span aria-hidden="true">/</span></>}
      <span>{title}</span>
    </nav>
    <header className="legal-hero">
      <p className="eyebrow">LEGAL &amp; TRUST</p>
      <h1>{title}</h1>
      <p className="legal-intro">{intro}</p>
      <p className="legal-meta">Effective {legal.effectiveDate} · Last updated {legal.lastUpdated}</p>
    </header>
    <div className="legal-layout">
      <aside className="legal-nav" aria-label="Legal and trust pages">
        {legalPages.map(page => <Link key={page.href} href={page.href} aria-current={page.href === current ? "page" : undefined}>{page.label}</Link>)}
      </aside>
      <article className="legal-body">{children}</article>
    </div>
    {schema && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema).replace(/</g, "\\u003c") }} />}
  </div>;
}
