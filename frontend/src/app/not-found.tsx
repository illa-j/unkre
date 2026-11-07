import type { Metadata } from "next";
import Link from "next/link";
import { MarketingHeader, MarketingFooter } from "@/components/marketing/shell";
import { ArrowIcon } from "@/components/icons";
import "./landing.css";

export const metadata: Metadata = {
  title: "Page not found — UNKRE",
  robots: { index: false, follow: false },
  alternates: { canonical: null, languages: {} },
};

export default function NotFound() {
  return <div className="site-shell landing-v2">
    <a className="skip-link" href="#main">Skip to content</a>
    <MarketingHeader />
    <main id="main" tabIndex={-1} className="not-found content-width">
      <div className="not-found-copy">
        <p className="eyebrow">404</p>
        <h1>This page<br /><em>isn’t here.</em></h1>
        <p className="not-found-intro">The link may be old, misspelled, or the page has moved. The studio is still open.</p>
        <div className="not-found-actions">
          <Link className="button button-primary" href="/">Back to UNKRE <ArrowIcon diagonal /></Link>
          <Link className="button button-outline" href="/#models">Explore models <ArrowIcon diagonal /></Link>
        </div>
        <nav className="not-found-links" aria-label="Useful links">
          <Link href="/learn/qwen-image-2-1">Qwen Image 2.1 guide</Link>
          <Link href="/learn/krea-2">Krea 2 guide</Link>
          <Link href="/studio/credits">Credits &amp; plans</Link>
          <Link href="/contact">Contact support</Link>
        </nav>
      </div>
      <div className="not-found-code" aria-hidden="true"><span>404</span></div>
    </main>
    <MarketingFooter />
  </div>;
}
