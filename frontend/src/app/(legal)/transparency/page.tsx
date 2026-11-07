import Link from "next/link";
import { LegalArticle } from "@/components/legal/legal-article";
import { legal, legalMetadata } from "@/lib/legal";

export const metadata = legalMetadata({
  title: "Transparency & Moderation | UNKRE",
  description: "How UNKRE reviews abuse reports, what enforcement actions we can take and what we publish about moderation.",
  path: "/transparency",
  ogAlt: "UNKRE transparency and moderation overview",
});

export default function TransparencyPage() {
  return <LegalArticle
    title="Transparency & moderation"
    intro="An adult platform should be able to explain how it handles reports. This page describes our process and what we publish — without inventing numbers we do not have."
    current="/transparency"
  >
    <h2>What we review</h2>
    <p>Reports are grouped by risk and type:</p>
    <ul>
      <li><strong>Immediate safety:</strong> content involving a minor, non-consensual intimate imagery, a credible threat or an imminent risk of harm.</li>
      <li><strong>Consent and likeness:</strong> a real person depicted without permission, impersonation or a request to remove private information.</li>
      <li><strong>Copyright and trademark:</strong> a copyright notice, a counter-notice or a claim about a protected character or work.</li>
      <li><strong>Platform abuse:</strong> fraud, stolen payment credentials, scraping, malware, ban evasion or coordinated credit abuse.</li>
      <li><strong>Quality and billing:</strong> a failed generation, a missing payment, a duplicate charge or a refund request.</li>
    </ul>

    <h2>How a report moves</h2>
    <ol>
      <li>We receive the report by email or through the contact route and create a record.</li>
      <li>We check whether the report identifies the material and the basis of the complaint. If not, we ask for the missing information.</li>
      <li>A person reviews the content, the account history and any response from the uploader.</li>
      <li>We take the least restrictive action that addresses the risk, or a stronger action where the risk requires it.</li>
      <li>We record the outcome and tell the reporter what we can, without exposing private information.</li>
    </ol>

    <h2>Possible actions</h2>
    <ul>
      <li>No action, if the content does not violate our rules.</li>
      <li>Remove the content or make it private.</li>
      <li>Warn the account and require a change in behavior.</li>
      <li>Limit a feature, generation access or payment access.</li>
      <li>Suspend or terminate the account.</li>
      <li>Preserve records and report serious threats or apparent child sexual abuse material to the appropriate authorities.</li>
    </ul>

    <h2>What we record</h2>
    <p>For moderation purposes we may keep a report identifier, the category, the content or account identifier, the action taken and the date. We do not publish reporter identities. We retain records only as long as needed for safety, legal obligations, dispute resolution or fraud prevention.</p>

    <h2>Public reporting</h2>
    <p><strong>No aggregate transparency report has been published yet.</strong> UNKRE is an early-stage product and we do not want to publish invented or misleading numbers. As reporting volume becomes meaningful, we will publish aggregate figures for completed periods, including reports received, actions taken and the number of appeals.</p>
    <p>We will not publish information that could identify a reporter, a victim or a private account, or that would undermine an active investigation.</p>

    <h2>Appeals and corrections</h2>
    <p>If you believe an enforcement decision was wrong, email <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a> with <strong>[Appeal]</strong> in the subject line. Include the account identifier and the decision you are appealing. If we made a mistake, we will correct it and say so.</p>

    <h2>Report a problem</h2>
    <p>Use the <Link href="/contact">contact page</Link> for support, the <Link href="/acceptable-use">acceptable use page</Link> for content reports and the <Link href="/copyright">copyright page</Link> for copyright or likeness notices. Urgent reports should include <strong>[Urgent]</strong> in the subject line.</p>

    <div className="legal-contact">
      <a href={`mailto:${legal.contactEmail}`}>Email the team</a>
      <Link href="/acceptable-use">Acceptable use</Link>
      <Link href="/copyright">Copyright &amp; likeness</Link>
      <Link href="/trust">Trust center</Link>
    </div>
  </LegalArticle>;
}
