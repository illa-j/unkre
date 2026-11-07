import Link from "next/link";
import { LegalArticle } from "@/components/legal/legal-article";
import { StatusProbe } from "@/components/status-probe";
import { legal, legalMetadata } from "@/lib/legal";

export const metadata = legalMetadata({
  title: "Service Status | UNKRE",
  description: "Check the current availability of the UNKRE website and Studio API, and learn how to report a generation or payment problem.",
  path: "/status",
  ogAlt: "UNKRE service status",
});

export default function StatusPage() {
  return <LegalArticle
    title="Service status"
    intro="A quick look at the parts of UNKRE we can check from your browser. These are liveness checks, not a guarantee that every generation or payment will succeed."
    current="/status"
    schemaType="WebPage"
  >
    <StatusProbe />

    <h2>What these checks mean</h2>
    <p>The website check confirms that the public frontend is responding. The Studio API check confirms that the application server is reachable. They do not run a real generation, sign in for you or test a payment.</p>
    <p>Payments depend on ATLOS and Telegram. Generation depends on GPU capacity, the selected model and the queue. A healthy website can still have a slow queue or a provider-side payment delay.</p>

    <h2>If something is not working</h2>
    <ul>
      <li>Refresh the page and try once more. Do not submit the same payment twice.</li>
      <li>Check <Link href="/studio/credits">Credits &amp; plans</Link> for the payment status before opening a new checkout.</li>
      <li>Check <Link href="/studio/gallery">My images</Link> for a failed or stuck generation and its error message.</li>
      <li>If the problem continues, contact <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a> with the generation ID or payment ID and the time it happened.</li>
    </ul>

    <h2>Incident communication</h2>
    <p>We do not currently publish a separate incident feed. For payment or generation problems, support is the fastest route. If an incident affects many accounts, we will add a notice to this page or the Trust center.</p>

    <h2>Provider status</h2>
    <p>Cloudflare, Telegram and ATLOS operate their own infrastructure. Their status pages and terms apply to their part of the service. UNKRE cannot guarantee a provider’s uptime or reverse a provider-side delay.</p>

    <div className="legal-contact">
      <a href={`mailto:${legal.contactEmail}`}>Contact support</a>
      <Link href="/contact">All contact options</Link>
      <Link href="/trust">Trust center</Link>
      <Link href="/refunds">Refund policy</Link>
    </div>
  </LegalArticle>;
}
