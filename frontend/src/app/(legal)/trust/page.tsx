import Link from "next/link";
import { LegalArticle } from "@/components/legal/legal-article";
import { legal, legalMetadata } from "@/lib/legal";

export const metadata = legalMetadata({
  title: "Trust Center — Safety, Privacy & Payments | UNKRE",
  description: "How UNKRE handles adult content, privacy, payments, copyright and abuse reports. Read our policies and contact the team.",
  path: "/trust",
  ogAlt: "UNKRE trust center — safety, privacy and payment policies",
});

const cards = [
  { href: "/privacy", title: "Privacy Policy", body: "What we collect, why we collect it, how long we keep it and the rights you can exercise.", cta: "Read the policy" },
  { href: "/terms", title: "Terms of Service", body: "The rules for using UNKRE, owning your images, credits, payments and account responsibilities.", cta: "Read the terms" },
  { href: "/refunds", title: "Refunds & cancellations", body: "When a credit purchase can be refunded, how to request it and what happens with crypto and Stars.", cta: "Read the policy" },
  { href: "/acceptable-use", title: "Acceptable use", body: "Adults only. No minors, non-consensual imagery, impersonation or illegal content.", cta: "Read the rules" },
  { href: "/copyright", title: "Copyright & likeness", body: "How to report copyright infringement, a real person’s likeness or non-consensual intimate content.", cta: "Read the process" },
  { href: "/contact", title: "Contact", body: "Support, billing, privacy requests, abuse reports and security contacts in one place.", cta: "Contact us" },
  { href: "/security", title: "Security", body: "How we protect accounts, payments and images, and how to report a vulnerability.", cta: "Read the security page" },
  { href: "/transparency", title: "Transparency", body: "How abuse reports are triaged, what actions we can take and what we publish.", cta: "Read the process" },
  { href: "/status", title: "Service status", body: "Live checks for the public site and Studio API, plus guidance for payment and generation problems.", cta: "Check status" },
] as const;

export default function TrustPage() {
  return <LegalArticle
    title="Trust center"
    intro="UNKRE is an adult AI image studio. That means trust has to be concrete: clear rules, honest data practices, working payment support and a real way to report harm."
    current="/trust"
    wide
  >
    <p>This page brings the important policies together. The short version is below; each card links to the full document. These policies apply to the public site, Studio, the Telegram MiniApp and every image, prompt, preset or payment connected to your account.</p>

    <h2>The short version</h2>
    <div className="trust-principles">
      <div><strong>Adults only</strong><p>You must be at least 18. Minors are never permitted in prompts, reference photos or generated images.</p></div>
      <div><strong>Consent matters</strong><p>Do not use a real person’s photo or likeness to create intimate, humiliating or misleading content without their consent.</p></div>
      <div><strong>Privacy by default</strong><p>We collect what the service needs, keep generated images in a short-lived cache and store the rest in your browser.</p></div>
      <div><strong>Clear money rules</strong><p>Credits, prices and refund conditions are shown before payment. No subscriptions and no surprise renewals.</p></div>
      <div><strong>AI is not a guarantee</strong><p>Outputs may be inaccurate, unexpected or similar to other users’ results. You decide what to create and how to use it.</p></div>
      <div><strong>Reports get reviewed</strong><p>Abuse, copyright and privacy reports can be sent to our support address and are reviewed by a person.</p></div>
    </div>

    <h2>Policies</h2>
    <div className="trust-grid">
      {cards.map(card => <Link key={card.href} href={card.href} className="trust-card">
        <span>Policy</span>
        <h2>{card.title}</h2>
        <p>{card.body}</p>
        <span className="trust-card-link">{card.cta} →</span>
      </Link>)}
    </div>

    <h2>Payments &amp; billing</h2>
    <p>Credits are prepaid and there is no subscription or automatic renewal. Prices and minimums are shown in Studio before checkout. Crypto payments are processed by ATLOS; card payments through Telegram use Telegram Stars. We do not store full card numbers. Approved refunds are handled under the <a href="/refunds">Refund Policy</a>, and we ask you to contact support before opening a chargeback.</p>
    <p>The credit ledger records purchases, spends, refunds and adjustments with before/after balances. Financial records may be retained after account closure where tax, accounting or fraud-prevention rules require it. If you need an invoice, a payment identifier or the current operator details for a dispute, email <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>.</p>

    <h2>How reports are handled</h2>
    <p>Send reports to <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>. Include the URL or generation ID, what you believe is wrong and the best way to reach you. For urgent non-consensual intimate imagery, put “Urgent NCII” in the subject line.</p>
    <p>We may remove content, restrict an account, preserve relevant records or report serious threats to the appropriate authorities. We aim to acknowledge reports within {legal.responseTime}. We cannot promise a particular outcome, but every report is reviewed.</p>

    <div className="legal-note">
      <p><strong>Operator details.</strong> UNKRE is operated by the UNKRE team. Registered business details are available on request from <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>. If you need our legal entity name, registered address or a VAT/tax identifier for a payment dispute, ask support and we will provide the current details.</p>
      <p>These pages describe our public policies in plain language. They are not legal advice to you, and they do not replace the mandatory rights you have under the law of your country.</p>
    </div>

    <div className="legal-contact">
      <a href={`mailto:${legal.contactEmail}`}>Email support</a>
      <Link href="/contact">Contact options</Link>
      <Link href="/acceptable-use">Report prohibited content</Link>
    </div>
  </LegalArticle>;
}
