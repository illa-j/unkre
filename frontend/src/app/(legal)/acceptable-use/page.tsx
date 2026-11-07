import Link from "next/link";
import { LegalArticle } from "@/components/legal/legal-article";
import { legal, legalMetadata } from "@/lib/legal";

export const metadata = legalMetadata({
  title: "Acceptable Use & Content Policy | UNKRE",
  description: "UNKRE is for adults only. Read the rules on minors, consent, real people, sexual content, copyright, LoRAs and platform abuse.",
  path: "/acceptable-use",
  ogAlt: "UNKRE acceptable use and content policy",
});

export default function AcceptableUsePage() {
  return <LegalArticle
    title="Acceptable use & content policy"
    intro="UNKRE is an adult creative studio, not a place for content that harms people. These rules apply to prompts, reference photos, generated images, presets, messages and any attempt to use the service."
    current="/acceptable-use"
  >
    <h2>1. Adults only</h2>
    <p>You must be at least {legal.minimumAge}. Do not create, request, upload or share any content that depicts, describes or sexualizes a person under 18. Do not use age-ambiguous language or imagery to work around this rule. A fictional setting does not make a minor eligible.</p>
    <p>If we reasonably believe an account belongs to a minor or is being used to create content involving minors, we will suspend it, remove the content and report it where required by law.</p>

    <h2>2. Consent and real people</h2>
    <p>Do not use a real person’s photo, name or likeness to create sexual, intimate, humiliating, threatening or misleading content without their verifiable consent. This includes public figures, celebrities, private individuals, coworkers, ex-partners and images taken from social media.</p>
    <p>Reference photos must be of an adult, must be yours or used with permission, and must not be identity documents, medical images, private images obtained without consent or images of someone who has asked you not to use them. We may remove a reference and restrict the account even when the prompt itself looks acceptable.</p>

    <h2>3. Prohibited content</h2>
    <p>Do not create, upload, request or distribute:</p>
    <ul>
      <li>child sexual abuse material, sexualized minors or any content involving a minor;</li>
      <li>non-consensual intimate imagery, “revenge porn” or sexual deepfakes of real people;</li>
      <li>sexual violence, rape, torture, mutilation or extreme gore;</li>
      <li>bestiality, incest or content that sexualizes a family relationship;</li>
      <li>hate speech, dehumanizing propaganda, harassment, threats or targeted abuse;</li>
      <li>content that promotes self-harm, suicide, eating disorders or dangerous challenges;</li>
      <li>instructions for weapons, explosives, chemical or biological agents, drug synthesis or other serious crime;</li>
      <li>fraud, phishing, scams, fake documents, false identity verification or financial deception;</li>
      <li>malware, credential theft, bypassing security controls or attacking a service or person;</li>
      <li>content that infringes copyright, trademark, publicity, privacy or another person’s rights;</li>
      <li>content that violates a model or LoRA license, or that uses a LoRA to reproduce a protected character or real person unlawfully.</li>
    </ul>
    <p>This list is illustrative, not exhaustive. We may remove content that creates a serious legal, safety or payment risk even if it is not listed here.</p>

    <h2>4. Reference photos and privacy</h2>
    <p>Upload only what you have the right to use. Do not upload a photo of a person who has not consented to the specific use, and do not upload private images from a phone, cloud account or message without permission. Do not upload government IDs, passports, financial records, medical records or biometric templates.</p>
    <p>If you are a person depicted in an image and you did not consent, use the <Link href="/copyright">copyright and likeness process</Link> or email <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a> with <strong>[Urgent NCII]</strong> in the subject line. Do not redistribute the image while we review it.</p>

    <h2>5. Copyright, LoRAs and models</h2>
    <p>You are responsible for the prompts, reference images and LoRAs you use. A LoRA’s availability in UNKRE does not give you ownership of the style, character, trademark or source material it may evoke. Do not use the service to reproduce a copyrighted work, a protected character or a living person’s likeness for commercial or deceptive use without the necessary rights.</p>
    <p>Model and LoRA providers may impose additional restrictions. If a provider’s license conflicts with these rules, the stricter restriction applies to your use of that model or LoRA.</p>

    <h2>6. Platform abuse</h2>
    <p>Do not:</p>
    <ul>
      <li>scrape, crawl or automate the service in a way that bypasses rate limits or exposes other users’ data;</li>
      <li>resell access, share accounts or use the service as a backend for a competing product without written permission;</li>
      <li>attempt to bypass safety controls, age checks, payment controls or content filters;</li>
      <li>upload malware or interfere with the site, API, workers or other users;</li>
      <li>use stolen payment credentials, fraudulent chargebacks or crypto transactions designed to obscure the payer;</li>
      <li>misuse referral, promo or welcome-credit systems through duplicate accounts or coordinated abuse.</li>
    </ul>

    <h2>7. Reporting</h2>
    <p>Report prohibited content or behavior to <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>. Include the page URL or generation ID, a short description and, for urgent safety issues, <strong>[Urgent]</strong> in the subject line. For copyright and likeness complaints, use the <Link href="/copyright">copyright page</Link> so the notice includes the information we need.</p>
    <p>Do not send explicit material by email unless we specifically ask for a copy for review. A link or identifier is usually enough.</p>

    <h2>8. Enforcement</h2>
    <p>We may remove content, limit features, suspend or terminate an account, cancel unpaid orders, preserve evidence and report serious threats to the relevant authorities. We consider the severity, repetition, risk to others and whether the conduct appears accidental. A first serious violation can still result in immediate suspension.</p>
    <p>Where appropriate, we will explain the reason and provide an appeal route. Do not create a new account to evade enforcement.</p>

    <h2>9. Appeals</h2>
    <p>If you believe a moderation decision was wrong, email <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a> with <strong>[Appeal]</strong> in the subject line, the account identifier and the content or decision you are appealing. We will review the available record. We may not be able to restore content that is illegal or creates a serious risk.</p>

    <h2>10. Law enforcement</h2>
    <p>We may preserve and disclose information when we receive a valid legal request or when we believe disclosure is necessary to prevent serious harm. We aim to be transparent about legal requests where the law allows it.</p>

    <h2>11. Contact</h2>
    <p>Questions about these rules: <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>. Read the <Link href="/terms">Terms of Service</Link>, <Link href="/privacy">Privacy Policy</Link> and <Link href="/copyright">copyright and likeness process</Link> for the related rules.</p>

    <div className="legal-contact">
      <a href={`mailto:${legal.contactEmail}`}>Report a violation</a>
      <Link href="/copyright">Copyright &amp; likeness</Link>
      <Link href="/terms">Terms of Service</Link>
      <Link href="/trust">Trust center</Link>
    </div>
  </LegalArticle>;
}
