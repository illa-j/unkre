import Link from "next/link";
import { LegalArticle } from "@/components/legal/legal-article";
import { legal, legalMetadata } from "@/lib/legal";

export const metadata = legalMetadata({
  title: "Terms of Service | UNKRE",
  description: "The rules for using UNKRE: account eligibility, credits and payments, ownership of AI outputs, acceptable use, refunds and liability.",
  path: "/terms",
  ogAlt: "UNKRE Terms of Service",
});

export default function TermsPage() {
  return <LegalArticle
    title="Terms of Service"
    intro="These terms are the agreement between you and the operator of UNKRE. They cover eligibility, accounts, credits, payments, your content and the limits of an AI image service."
    current="/terms"
  >
    <h2>1. Agreement and eligibility</h2>
    <p>By using UNKRE, creating an account, buying credits or generating an image, you agree to these Terms, the <Link href="/privacy">Privacy Policy</Link>, the <Link href="/acceptable-use">Acceptable Use Policy</Link> and the <Link href="/refunds">Refund Policy</Link>. If you do not agree, do not use the service.</p>
    <p>You must be at least {legal.minimumAge} years old and legally able to enter into this agreement. If you use UNKRE on behalf of a business, you confirm that you have authority to bind that business. We may ask you to confirm your age or identity where we reasonably need to.</p>

    <h2>2. The service</h2>
    <p>UNKRE lets you create images with third-party AI models, including Krea 2 Turbo and Qwen Image 2.1, optionally using reference photos and LoRAs. Features, models, workflows, LoRA collections and prices can change, be limited or be withdrawn. We do not guarantee that a particular model, style, seed or example will remain available or reproduce the same result.</p>
    <p>The service is provided for creative use by adults. It is not a storage service, a social network, a backup service or a guarantee of a specific level of realism, likeness or quality. Generated images may be inaccurate, unexpected or similar to images created by others.</p>

    <h2>3. Accounts</h2>
    <ul>
      <li>Sign-in is available through Google and Telegram. You are responsible for the security of those accounts and for activity under your UNKRE account.</li>
      <li>Provide accurate information and do not impersonate another person or create an account to evade a suspension.</li>
      <li>Do not share access, sell accounts or use one account for coordinated abusive activity.</li>
      <li>Tell us promptly if you believe your account has been compromised.</li>
    </ul>

    <h2>4. Credits and payments</h2>
    <p>Credits are a prepaid unit used to request generations. One credit is not a fixed number of images: the credit cost is shown in Studio when a generation has a recorded price. Credits have no cash value, are not a bank deposit or e-money, and cannot be transferred, sold or exchanged outside the service.</p>
    <p>Credits do not expire unless we clearly tell you otherwise before a purchase or applicable law requires a different rule. Prices, minimum purchase amounts and available payment methods are shown in Studio before you pay. We may change prices for future purchases; a change does not reduce credits you already hold.</p>
    <p>Crypto checkout is provided by ATLOS. Card payments through Telegram are provided with Telegram Stars. Those providers may apply their own terms, currency conversion, network fees and verification requirements. Credits are added only after the provider confirms the payment. An unpaid invoice can expire; an expired invoice does not create a charge.</p>
    <p>You are responsible for taxes, duties and fees associated with your purchase or use of outputs, except where we are legally required to collect them. Promo codes, referral credits and welcome credits are governed by the rules shown when they are offered and have no cash value.</p>

    <h2>5. Refunds</h2>
    <p>Refunds are handled under the <Link href="/refunds">Refund Policy</Link>. In short: contact us before opening a chargeback or sending a payment dispute; we review duplicate, unauthorized and undelivered payments, and we honor rights that cannot be excluded by law. Credits that have already been spent are generally not refundable.</p>

    <h2>6. Your content and AI outputs</h2>
    <p>You keep ownership of the prompts, reference photos and other material you submit, and of the images you generate, subject to applicable law and the rights of others. You grant us a limited, worldwide, non-exclusive license to host, process, transmit, display and delete that content as needed to provide the service, secure it, investigate abuse and comply with law. This license ends when the content is deleted, except for backups and records we must keep.</p>
    <p>You represent and warrant that:</p>
    <ul>
      <li>you have the rights and permissions needed to upload every reference photo and to use every prompt or asset you submit;</li>
      <li>every person depicted in a reference photo is an adult and has consented to the use you are making of their image;</li>
      <li>your content does not violate the <Link href="/acceptable-use">Acceptable Use Policy</Link>, copyright, trademark, privacy, publicity, biometric or other rights;</li>
      <li>you will not present AI output as a real photograph, document or verified fact in a way that misleads or harms someone.</li>
    </ul>
    <p>AI output is generated probabilistically. It may resemble existing people, characters or works, and it may contain errors. You are responsible for reviewing an output before you publish or use it. We do not guarantee that an output is unique, copyrightable, non-infringing or suitable for a particular purpose. Your use of a model or LoRA may also be subject to the model provider’s license.</p>

    <h2>7. Acceptable use</h2>
    <p>The <Link href="/acceptable-use">Acceptable Use Policy</Link> is part of these Terms. It prohibits, among other things, content involving minors, non-consensual intimate imagery, real-person impersonation, sexual violence, hate, harassment, illegal instructions and attempts to bypass safety controls. We may remove content, restrict features or suspend an account when we reasonably believe these rules are being violated.</p>

    <h2>8. Intellectual property</h2>
    <p>The UNKRE name, logo, site design, original text, interface and curated collections are owned by the operator or its licensors. We grant you a limited, revocable, non-exclusive license to use the service for its intended purpose. You may not copy, scrape, resell or reverse-engineer the service except as allowed by law. Third-party model and LoRA names and materials remain the property of their owners.</p>
    <p>If you send us feedback or a suggestion, you allow us to use it without restriction or compensation.</p>

    <h2>9. Third-party services</h2>
    <p>UNKRE depends on Google, Telegram, ATLOS, Runpod and other infrastructure providers. Their services have their own terms and privacy policies. We are not responsible for their independent acts or outages, but we choose and review them as part of operating UNKRE. A payment provider’s decision to decline, reverse or delay a transaction is outside our control.</p>

    <h2>10. Availability and changes</h2>
    <p>We aim to keep UNKRE available, but we do not promise uninterrupted or error-free service. Maintenance, provider outages, model changes, abuse mitigation and security work can interrupt generation or payments. We may add, change or remove features, models, LoRAs, prices or limits. Where a change materially affects a paid balance, we will handle it fairly and in line with applicable law.</p>

    <h2>11. Disclaimers</h2>
    <p>To the maximum extent permitted by law, the service is provided “as is” and “as available”. We disclaim implied warranties of merchantability, fitness for a particular purpose, non-infringement, accuracy and quiet enjoyment. We do not warrant that an image will match a reference, that a character will stay consistent, that a LoRA will produce a particular style, or that an output will be lawful in your jurisdiction. Adult content laws differ; you are responsible for how and where you use an output.</p>
    <p>Nothing in these Terms excludes a warranty or right that cannot be excluded under the mandatory law of your country.</p>

    <h2>12. Limitation of liability</h2>
    <p>To the maximum extent permitted by law, the operator of UNKRE will not be liable for indirect, incidental, special, consequential, exemplary or punitive damages, loss of profits, revenue, data, goodwill or business opportunity, even if we were advised of the possibility. Our total liability for claims relating to the service will not exceed the amount you paid to UNKRE in the 12 months before the event giving rise to the claim.</p>
    <p>This section does not limit liability for fraud, willful misconduct, death or personal injury, or any other liability that applicable law does not allow us to limit.</p>

    <h2>13. Indemnity</h2>
    <p>To the extent permitted by law, you agree to indemnify and hold harmless the operator of UNKRE and its team from claims, losses, liabilities and reasonable costs arising from your content, your use of an output, your breach of these Terms or your violation of another person’s rights. This does not apply to claims caused by our own breach or negligence.</p>

    <h2>14. Suspension and termination</h2>
    <p>You may stop using UNKRE at any time. We may suspend or terminate an account, remove content or refuse a transaction if we reasonably believe you violated these Terms, created a legal or payment risk, engaged in fraud or chargeback abuse, or if the law requires it. Where appropriate, we will explain the reason and provide a way to appeal.</p>
    <p>If we terminate for a reason not caused by your violation, we will handle unused paid credits fairly, including a refund where required by law. If we terminate for a serious violation, unused credits may be forfeited only to the extent permitted by law. Financial records and content may be retained as described in the Privacy Policy.</p>

    <h2>15. Governing law and disputes</h2>
    <p>These Terms are governed by {legal.governingLaw}, without regard to conflict-of-law rules. Before starting formal proceedings, please contact us at <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a> so we can try to resolve the issue informally. Nothing here prevents you from using a mandatory consumer dispute process or the courts available to you under the law of your country of residence.</p>

    <h2>16. Changes to these Terms</h2>
    <p>We may update these Terms as the product or law changes. The “last updated” date shows the current version. If a change materially affects your rights, we will take reasonable steps to make it visible before it applies. Continuing to use UNKRE after the effective date means you accept the updated Terms.</p>

    <h2>17. Contact</h2>
    <p>Questions about these Terms: <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>. Legal notices should use the same address with <strong>[Legal]</strong> in the subject line.</p>

    <div className="legal-note">
      <p><strong>Operator details.</strong> UNKRE is operated by the UNKRE team. Registered business details are available on request from <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>. These Terms are a public product policy, not legal advice to you.</p>
    </div>

    <div className="legal-contact">
      <a href={`mailto:${legal.contactEmail}`}>Email legal</a>
      <Link href="/privacy">Privacy Policy</Link>
      <Link href="/refunds">Refund Policy</Link>
      <Link href="/acceptable-use">Acceptable use</Link>
    </div>
  </LegalArticle>;
}
