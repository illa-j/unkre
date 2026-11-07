import Link from "next/link";
import { LegalArticle } from "@/components/legal/legal-article";
import { legal, legalMetadata } from "@/lib/legal";
import { site } from "@/lib/site";

export const metadata = legalMetadata({
  title: "Contact UNKRE — Support, Billing & Abuse Reports",
  description: "Contact UNKRE for account help, payment issues, privacy requests, copyright complaints, abuse reports or security concerns.",
  path: "/contact",
  ogAlt: "Contact UNKRE support, billing, privacy and abuse teams",
});

const routes = [
  { subject: "Account support", body: "Sign-in problems, missing generations, Studio questions or account settings." },
  { subject: "Payments & credits", body: "A payment that did not arrive, a duplicate charge, a refund request or a credit balance issue." },
  { subject: "Privacy request", body: "Access, correction, deletion, portability or another data protection request." },
  { subject: "Abuse report", body: "Content involving minors, non-consensual imagery, impersonation, threats or other prohibited use." },
  { subject: "Copyright or likeness", body: "A copyright notice, a real-person likeness complaint or a request to remove private information." },
  { subject: "Security", body: "A vulnerability, credential leak or suspicious activity. Please do not include exploit details in a public message." },
] as const;

export default function ContactPage() {
  return <LegalArticle
    title="Contact UNKRE"
    intro="A real person reads support, billing, privacy and abuse messages. Choose the category that fits so your request reaches the right queue."
    current="/contact"
    schemaType="ContactPage"
  >
    <h2>Email</h2>
    <p>Write to <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>. We aim to acknowledge most messages within {legal.responseTime}. Complex payment or privacy requests can take longer, especially when we need to verify account ownership.</p>
    <p>For faster handling, put one of these subjects at the start of your message:</p>
    <ul>
      <li><strong>[Billing]</strong> — payments, credits, refunds or invoices.</li>
      <li><strong>[Privacy]</strong> — access, deletion or another data request.</li>
      <li><strong>[Abuse]</strong> — prohibited content or account behavior.</li>
      <li><strong>[Copyright]</strong> — copyright or likeness complaints.</li>
      <li><strong>[Security]</strong> — security reports.</li>
    </ul>

    <h2>What to include</h2>
    <ul>
      <li>The email address or Telegram username connected to your UNKRE account, if you have one.</li>
      <li>The payment provider, payment ID and date for billing questions. Do not send full card numbers.</li>
      <li>The generation ID or page URL for content questions.</li>
      <li>A short description of what happened and what outcome you want.</li>
    </ul>
    <div className="legal-note">
      <p><strong>Please do not send</strong> government ID documents, passwords, full card numbers, private keys or explicit images by email. If we need to verify something, we will tell you what is necessary and how to send it safely.</p>
    </div>

    <h2>Common requests</h2>
    <div className="trust-grid">
      {routes.map(route => <a key={route.subject} className="trust-card" href={`mailto:${legal.contactEmail}?subject=${encodeURIComponent(`[${route.subject}]`)}`}>
        <span>Contact route</span>
        <h2>{route.subject}</h2>
        <p>{route.body}</p>
        <span className="trust-card-link">Write to support →</span>
      </a>)}
    </div>

    <h2>Telegram</h2>
    <p>You can also reach the product through the Telegram bot and MiniApp. Telegram is useful for quick product questions, but email is better for billing, privacy and legal requests because it gives us a durable record.</p>
    <p><a href={site.telegramBotUrl} target="_blank" rel="noopener noreferrer">Open the UNKRE Telegram bot &amp; MiniApp</a></p>

    <h2>Urgent safety reports</h2>
    <p>If someone is in immediate danger, contact your local emergency services first. For urgent non-consensual intimate imagery or content involving a minor, email <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a> with <strong>[Urgent NCII]</strong> or <strong>[Urgent minor safety]</strong> in the subject line and include the URL or generation ID. Do not download, forward or redistribute the material.</p>

    <h2>Operator details</h2>
    <p>UNKRE is operated by the UNKRE team. Registered business details, including the legal entity name and address, are available on request from <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>. Use the same address for legal notices and payment disputes.</p>

    <div className="legal-contact">
      <a href={`mailto:${legal.contactEmail}`}>Email {legal.contactEmail}</a>
      <Link href="/privacy">Privacy Policy</Link>
      <Link href="/terms">Terms of Service</Link>
      <Link href="/trust">Trust center</Link>
    </div>
  </LegalArticle>;
}
