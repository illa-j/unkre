import Link from "next/link";
import { LegalArticle } from "@/components/legal/legal-article";
import { legal, legalMetadata } from "@/lib/legal";

export const metadata = legalMetadata({
  title: "Security at UNKRE | UNKRE",
  description: "How UNKRE protects accounts, payments and images: HTTPS, HttpOnly cookies, hashed tokens, rate limiting and short-lived image storage.",
  path: "/security",
  ogAlt: "UNKRE security overview",
});

export default function SecurityPage() {
  return <LegalArticle
    title="Security at UNKRE"
    intro="Security is part of the product, not a footer badge. This page explains the controls we use, what we do not store and how to report a problem."
    current="/security"
  >
    <h2>Account protection</h2>
    <ul>
      <li>Sign-in uses Google or Telegram. We never receive your Google or Telegram password.</li>
      <li>Session cookies are <strong>HttpOnly</strong>, <strong>SameSite</strong> and, in production, <strong>Secure</strong>. JavaScript cannot read the access or refresh token.</li>
      <li>Refresh tokens are rotated, stored as hashes and limited to the session lifetime. A used refresh token cannot be replayed.</li>
      <li>State-changing requests use a signed CSRF token in addition to the session cookie.</li>
      <li>Rate limiting, temporary IP bans and request validation reduce credential stuffing and automated abuse.</li>
    </ul>

    <h2>Payments</h2>
    <ul>
      <li>Card payments through Telegram are handled by Telegram. We do not receive or store full card numbers.</li>
      <li>Crypto checkout is handled by ATLOS. We store the order and transaction metadata needed to credit your balance and support a refund.</li>
      <li>The credit ledger is append-only at the application level: purchases, spends, refunds and adjustments are recorded with before/after balances.</li>
      <li>Payment confirmation is verified by provider signature or secret, not by a browser redirect.</li>
    </ul>

    <h2>Images and prompts</h2>
    <ul>
      <li>Reference photos are sent to the generation provider to create the requested image. They are not used to build a public profile.</li>
      <li>Generated images are cached on our infrastructure for a short period, usually no more than 24 hours, so your browser can save a copy.</li>
      <li>Your browser library uses IndexedDB on your device. Clearing site data removes that copy.</li>
      <li>Deleted generations are removed from the service and from the temporary cache where available.</li>
    </ul>

    <h2>Infrastructure</h2>
    <ul>
      <li>Production traffic uses HTTPS. The public origin is behind Cloudflare and an nginx reverse proxy.</li>
      <li>Databases and internal services are not exposed to the public internet. The admin panel is bound to the local machine only.</li>
      <li>Access to production systems is limited to the operators who need it. Credentials and tunnel tokens are kept out of source control.</li>
      <li>Dependencies and container images are reviewed and updated as part of maintenance.</li>
    </ul>

    <h2>What we do not do</h2>
    <ul>
      <li>We do not use advertising cookies or third-party behavioral tracking.</li>
      <li>We do not sell personal data.</li>
      <li>We do not store full card numbers or your Google/Telegram password.</li>
      <li>We do not claim that any online service is perfectly secure.</li>
    </ul>

    <h2>Report a vulnerability</h2>
    <p>Email <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a> with <strong>[Security]</strong> in the subject line. Describe the issue, the affected URL or component and a safe way to reproduce it. Do not access other users’ data, degrade the service, use social engineering or test third-party providers without their permission.</p>
    <p>We review good-faith reports and will explain the outcome where we can. Please give us reasonable time to fix the issue before publishing details.</p>

    <h2>Incident response</h2>
    <p>If we confirm a security incident affecting personal data, we will contain it, assess the impact and notify affected users and authorities where required by law. We may reset sessions or require re-authentication as a precaution.</p>

    <h2>Contact</h2>
    <p>Security questions: <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>. For privacy requests, use the <Link href="/privacy">Privacy Policy</Link>; for abuse reports, use the <Link href="/acceptable-use">Acceptable Use Policy</Link>.</p>

    <div className="legal-note">
      <p><strong>Operator details.</strong> UNKRE is operated by the UNKRE team. Registered business details are available on request from <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>. This page describes our current controls; it is not a warranty that a particular incident will not occur.</p>
    </div>

    <div className="legal-contact">
      <a href={`mailto:${legal.contactEmail}`}>Report security issue</a>
      <Link href="/privacy">Privacy Policy</Link>
      <Link href="/trust">Trust center</Link>
      <Link href="/status">Service status</Link>
    </div>
  </LegalArticle>;
}
