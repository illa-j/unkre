import Link from "next/link";
import { LegalArticle } from "@/components/legal/legal-article";
import { legal, legalMetadata } from "@/lib/legal";

export const metadata = legalMetadata({
  title: "Copyright & Likeness Takedown | UNKRE",
  description: "How to report copyright infringement, a real person’s likeness, impersonation or non-consensual intimate imagery on UNKRE.",
  path: "/copyright",
  ogAlt: "UNKRE copyright and likeness takedown process",
});

export default function CopyrightPage() {
  return <LegalArticle
    title="Copyright & likeness"
    intro="UNKRE respects copyright and personal rights. This page explains how to send a usable takedown notice, what happens next and how to appeal a removal."
    current="/copyright"
  >
    <h2>1. Before you send a notice</h2>
    <p>Please identify the exact material and explain your relationship to it. We can review a report faster when it includes a URL or a generation ID, the work or person affected, and a way to contact you. Do not send explicit images by email; a link or identifier is enough.</p>
    <p>If someone is in immediate danger, contact local emergency services first. For urgent non-consensual intimate imagery, use <strong>[Urgent NCII]</strong> in the subject line.</p>

    <h2>2. Copyright takedown notice</h2>
    <p>Where the DMCA or a similar law applies, send a written notice to <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a> with the subject <strong>[Copyright]</strong>. A complete notice should include:</p>
    <ul>
      <li>your physical or electronic signature;</li>
      <li>identification of the copyrighted work you believe has been infringed;</li>
      <li>the URL or generation ID of the material you want removed, with enough detail for us to locate it;</li>
      <li>your name, address, telephone number and email address;</li>
      <li>a statement that you have a good-faith belief that the use is not authorized by the copyright owner, its agent or the law;</li>
      <li>a statement, under penalty of perjury, that the information in the notice is accurate and that you are the copyright owner or authorized to act on the owner’s behalf.</li>
    </ul>
    <p>If a notice is incomplete, we may ask for the missing information or decline to act until we receive it. Knowingly submitting a materially false notice can create legal liability.</p>

    <h2>3. Counter-notice</h2>
    <p>If your content was removed and you believe the removal was a mistake or misidentification, you can send a counter-notice to the same address with the subject <strong>[Copyright counter-notice]</strong>. Include your contact details, identification of the removed material and its previous location, a statement under penalty of perjury that you have a good-faith belief the material was removed by mistake or misidentification, and your consent to the jurisdiction and service of process required by applicable law.</p>
    <p>We may share the counter-notice with the original complainant. We may restore the material if the complainant does not take legal action within the period allowed by law.</p>

    <h2>4. Likeness, privacy and non-consensual imagery</h2>
    <p>You do not need to own a copyright to report a likeness or privacy problem. If an image depicts you or someone you are authorized to represent, and you believe it is intimate, misleading, harassing or created without consent, email <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a> with the subject <strong>[Likeness]</strong> or <strong>[Urgent NCII]</strong>.</p>
    <p>Include the URL or generation ID, the person depicted and their relationship to you, the basis of your complaint and a contact address. We may ask for reasonable verification that the request is genuine. We will not require you to send an explicit image by email.</p>
    <p>We may remove the material while we review it, especially where the report involves a minor, non-consensual intimacy, a threat or an immediate safety risk.</p>

    <h2>5. What happens after a report</h2>
    <ul>
      <li>We acknowledge the report where possible and ask for missing information.</li>
      <li>We review the material, the account history and any response from the uploader.</li>
      <li>We may remove or restrict the material, warn the account, suspend it or preserve records for legal purposes.</li>
      <li>We may notify the uploader that content was removed, without disclosing information that could put the reporter at risk.</li>
      <li>We may report serious threats or apparent child sexual abuse material to the appropriate authorities.</li>
    </ul>

    <h2>6. Repeat infringement</h2>
    <p>We maintain a policy of removing material and restricting accounts that repeatedly infringe copyright or ignore likeness and consent rules. A serious first violation can result in immediate suspension.</p>

    <h2>7. Legal requests</h2>
    <p>Valid subpoenas, court orders and law-enforcement requests should be sent to <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a> with <strong>[Legal request]</strong> in the subject line. We review the request for legal validity and may notify the affected user where the law allows.</p>

    <h2>8. Contact</h2>
    <p>Copyright and likeness: <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>. General abuse reports: use the <Link href="/acceptable-use">acceptable use page</Link>. For everything else, see <Link href="/contact">contact</Link>.</p>

    <div className="legal-note">
      <p><strong>Operator details.</strong> UNKRE is operated by the UNKRE team. Registered business details and the current copyright contact are available on request from <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>. This page describes our process; it is not legal advice to you.</p>
    </div>

    <div className="legal-contact">
      <a href={`mailto:${legal.contactEmail}`}>Email copyright</a>
      <Link href="/acceptable-use">Acceptable use</Link>
      <Link href="/terms">Terms of Service</Link>
      <Link href="/trust">Trust center</Link>
    </div>
  </LegalArticle>;
}
