import Link from "next/link";
import { LegalArticle } from "@/components/legal/legal-article";
import { legal, legalMetadata } from "@/lib/legal";

export const metadata = legalMetadata({
  title: "Refunds & Cancellations | UNKRE",
  description: "How UNKRE handles refunds for credit purchases, duplicate charges, undelivered credits, crypto payments and Telegram Stars.",
  path: "/refunds",
  ogAlt: "UNKRE refunds and cancellations policy",
});

export default function RefundsPage() {
  return <LegalArticle
    title="Refunds & cancellations"
    intro="UNKRE sells prepaid credits, not a subscription. This page explains when we can refund a purchase, when we cannot, and how to ask without opening a payment dispute first."
    current="/refunds"
  >
    <h2>1. What you are buying</h2>
    <p>Credits are a prepaid balance used to request AI generations. They are added to your UNKRE account after the payment provider confirms the payment. A generation may consume credits even when the result is not what you imagined; the model, prompt and settings affect the output, and AI results are not guaranteed.</p>
    <p>UNKRE does not charge recurring subscriptions. A payment happens only when you create a checkout and complete it. Unpaid invoices expire automatically and do not create a charge.</p>

    <h2>2. Our refund window</h2>
    <p>Contact us within <strong>{legal.refundWindowDays} days</strong> of the transaction if you believe a payment should be refunded. We review each request individually. Where the law gives you a longer or stronger right, that right applies instead of this window.</p>

    <h2>3. When we can refund</h2>
    <ul>
      <li>A duplicate or accidental charge for the same order.</li>
      <li>A payment that was confirmed by the provider but the credits were not added to your account.</li>
      <li>An incorrect amount or an unauthorized transaction, after verification.</li>
      <li>A technical failure that prevented the paid service from being delivered and cannot be resolved by adding the missing credits.</li>
      <li>Unused credits, at our discretion, if you ask before spending them. Welcome, referral and promo credits are not refundable.</li>
      <li>Any other case where a refund is required by applicable consumer law.</li>
    </ul>

    <h2>4. When we generally cannot refund</h2>
    <ul>
      <li>Credits that have already been spent on generations.</li>
      <li>A result that differs from an example, a prompt or your expectation, where the generation was delivered as requested.</li>
      <li>Change of mind after credits were used, or after the digital service was supplied with your consent.</li>
      <li>Account termination for a serious violation of the <Link href="/acceptable-use">Acceptable Use Policy</Link> or <Link href="/terms">Terms of Service</Link>.</li>
      <li>Blockchain network fees, currency conversion differences or fees charged by your bank, card issuer, Telegram or a crypto provider.</li>
      <li>Requests made after the {legal.refundWindowDays}-day window where no mandatory statutory right applies.</li>
    </ul>

    <h2>5. How to request a refund</h2>
    <p>Email <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a> with the subject <strong>[Billing] Refund request</strong>. Include:</p>
    <ul>
      <li>the email address or Telegram username connected to your UNKRE account;</li>
      <li>the payment provider (ATLOS crypto or Telegram Stars);</li>
      <li>the payment ID, date, amount and currency shown in Studio;</li>
      <li>a short explanation of what went wrong and what you want us to do.</li>
    </ul>
    <p>Do not send full card numbers, private keys or government ID documents by email. If we need to verify ownership of a crypto payment, we may ask for the transaction hash or a signature from the sending wallet. Never send a seed phrase.</p>

    <h2>6. How refunds are paid</h2>
    <p>We aim to acknowledge a refund request within {legal.responseTime} and to make a decision as soon as we have the necessary information. Approved refunds are sent back to the original payment method where the provider supports it.</p>
    <ul>
      <li><strong>Telegram Stars:</strong> refunded through Telegram’s refund mechanism to the original payer and charge where available. Telegram’s own rules and processing times apply.</li>
      <li><strong>Crypto:</strong> refunded in the original asset and blockchain where practical, to an address you confirm in writing. Network fees and price movement may affect the amount; we will explain the calculation before sending. Crypto transactions are irreversible once broadcast.</li>
      <li><strong>Credits:</strong> if a refund is approved, the corresponding credits are removed from your balance. If you have already spent them, we may refuse the refund or require the balance to be settled first.</li>
    </ul>

    <h2>7. Chargebacks and payment disputes</h2>
    <p>Please contact us before asking your bank, card issuer or payment provider to reverse a charge. A chargeback can freeze the account and take longer to resolve than a support request. If a chargeback is opened while we are investigating, we may pause the account and provide the provider with the order and delivery records. Fraudulent or abusive chargebacks may lead to suspension.</p>

    <h2>8. Cancellations</h2>
    <p>There is nothing to cancel: UNKRE does not renew credits automatically. If you have an open invoice, simply do not complete it; it will expire. If you want to stop using the service, stop generating and close your account by contacting support. Closing an account does not automatically refund unused credits — ask for a refund first if you believe you are eligible.</p>

    <h2>9. Statutory rights</h2>
    <p>Some countries give consumers a right to withdraw from certain digital purchases or to receive a remedy when digital content is faulty. Those rights cannot be excluded by this policy. If you live in the EU or UK, for example, the 14-day withdrawal right may not apply once digital content has been supplied with your consent and you have acknowledged losing that right; this does not affect your other mandatory rights. If you are unsure, ask us and we will explain how the law applies to your request.</p>

    <h2>10. Contact</h2>
    <p>Billing and refund questions: <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>. Include <strong>[Billing]</strong> in the subject line so the request is routed correctly. You can also read the <Link href="/terms">Terms of Service</Link> and the <Link href="/contact">contact page</Link>.</p>

    <div className="legal-note">
      <p><strong>Operator details.</strong> UNKRE is operated by the UNKRE team. Registered business details are available on request from <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>. This policy is a public product policy, not legal advice to you.</p>
    </div>

    <div className="legal-contact">
      <a href={`mailto:${legal.contactEmail}`}>Email billing</a>
      <Link href="/terms">Terms of Service</Link>
      <Link href="/privacy">Privacy Policy</Link>
      <Link href="/trust">Trust center</Link>
    </div>
  </LegalArticle>;
}
