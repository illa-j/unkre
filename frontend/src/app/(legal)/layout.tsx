import type { ReactNode } from "react";
import { MarketingHeader, MarketingFooter } from "@/components/marketing/shell";
import "../landing.css";
import "./legal.css";

export default function LegalLayout({ children }: { children: ReactNode }) {
  return <div className="site-shell landing-v2">
    <a className="skip-link" href="#main">Skip to content</a>
    <MarketingHeader />
    <main id="main" tabIndex={-1} className="legal-main content-width">{children}</main>
    <MarketingFooter />
  </div>;
}
