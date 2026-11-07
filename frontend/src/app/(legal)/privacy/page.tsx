import Link from "next/link";
import { LegalArticle } from "@/components/legal/legal-article";
import { legal, legalMetadata } from "@/lib/legal";

export const metadata = legalMetadata({
  title: "Privacy Policy | UNKRE",
  description: "How UNKRE collects, uses, shares and retains account, generation, payment and analytics data — and how to exercise your privacy rights.",
  path: "/privacy",
  ogAlt: "UNKRE Privacy Policy",
});

export default function PrivacyPage() {
  return <LegalArticle
    title="Privacy Policy"
    intro="This policy explains what UNKRE collects, why we need it, who processes it and what you can ask us to do with it. It covers the public site, Studio, the Telegram MiniApp and payments."
    current="/privacy"
  >
    <h2>1. Who we are</h2>
    <p>UNKRE is an adult AI image studio operated by the UNKRE team. The operator of UNKRE is the controller of the personal data described in this policy. You can contact us at <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>.</p>
    <p>UNKRE is for adults only. We do not knowingly collect personal data from anyone under {legal.minimumAge}.</p>

    <h2>2. Data we collect</h2>
    <h3>Account and sign-in data</h3>
    <ul>
      <li><strong>Google:</strong> the Google account identifier, verified email address, name and profile language, if you sign in with Google.</li>
      <li><strong>Telegram:</strong> your Telegram user ID, username, first and last name, language code and profile photo URL, if you sign in with Telegram or the MiniApp.</li>
      <li><strong>Account data:</strong> referral code, credit balance, account status, registration and last-activity timestamps.</li>
      <li><strong>Authentication data:</strong> one-time login challenges, hashed refresh tokens and session cookies. We do not store your Google or Telegram password.</li>
    </ul>

    <h3>Generations and content</h3>
    <ul>
      <li><strong>Prompts and settings:</strong> the prompt, negative prompt, selected model or workflow, LoRA names and strengths, seed, aspect ratio and other generation settings.</li>
      <li><strong>Reference photos:</strong> images you upload for a reference-based workflow. They are sent to the processing service to create the requested image.</li>
      <li><strong>Generation records:</strong> status, timestamps, error messages, credit cost and the provider job identifier.</li>
      <li><strong>Generated images:</strong> a temporary copy may be cached on our infrastructure so your browser can retrieve it. The cache is short-lived by design.</li>
      <li><strong>Presets and library data:</strong> presets you save, including any preset you choose to make public, favorites and images stored in your browser’s local library.</li>
    </ul>

    <h3>Payments and credits</h3>
    <ul>
      <li><strong>Payment records:</strong> provider, purchased credits, amount, currency, status, invoice and transaction identifiers, and timestamps.</li>
      <li><strong>Crypto payments:</strong> asset and blockchain codes, asset amount and fee, blockchain transaction hash and, where provided by the payment processor, the sender address.</li>
      <li><strong>Telegram Stars:</strong> the Telegram payer identifier and Telegram payment charge identifier.</li>
      <li><strong>Ledger:</strong> credit purchases, spends, refunds, adjustments and before/after balances. These records are needed to keep the balance correct and to meet accounting obligations.</li>
    </ul>
    <p>Card payments through Telegram are handled by Telegram. We do not receive or store full card numbers. Crypto checkout is handled by ATLOS.</p>

    <h3>Analytics and technical data</h3>
    <p>Our first-party analytics records aggregate product events such as page views, CTA clicks, sign-up completion, generation start/completion and Core Web Vitals. The payload is deliberately limited to an event name, placement or preset identifier, a broad page path, device class, referral channel and, for Web Vitals, a metric value. It does <strong>not</strong> include prompts, images, user IDs, cookies or query strings. We respect the browser’s Do Not Track signal for these events.</p>
    <p>Like most services, our servers and security layer may process IP address, user agent, request path, timestamps, response status and similar technical data for security, rate limiting, abuse prevention and troubleshooting.</p>

    <h2>3. Cookies and local storage</h2>
    <p>We use a small set of essential cookies. We do not use advertising cookies or third-party behavioral tracking cookies.</p>
    <ul>
      <li><strong><code>cl_access_token</code></strong> — an HttpOnly session cookie used to authenticate your account. It is short-lived.</li>
      <li><strong><code>cl_refresh_token</code></strong> — an HttpOnly cookie used to renew your session. It can last up to 30 days and is rotated when used.</li>
      <li><strong><code>csrf_token</code></strong> — a readable security cookie used to protect state-changing requests against cross-site request forgery.</li>
      <li><strong>Admin cookies</strong> — separate cookies for the local-only administration panel. They are not issued to normal visitors.</li>
    </ul>
    <p>We also use browser storage for product functionality: a referral code may be kept in <code>sessionStorage</code>; drafts, display preferences and saved workspace data may be kept in <code>localStorage</code>; and completed images may be kept in <code>IndexedDB</code> so you can view them without downloading them again. The <code>unkre.adult.v1</code> key records your 18+ confirmation, and <code>unkre.reference-consent.v1</code> records that you accepted the reference-photo consent statement. This browser data stays on your device until you clear it or the site removes it. It is not sent to us unless you use a feature that requires it.</p>

    <h2>4. Why we use data</h2>
    <ul>
      <li><strong>To provide the service:</strong> authenticate you, generate images, keep your balance, show your history and deliver the features you request.</li>
      <li><strong>To process payments:</strong> create invoices, confirm payments, credit your wallet, handle refunds and keep accounting records.</li>
      <li><strong>To keep the service safe:</strong> rate-limit abuse, detect fraud or credential attacks, investigate reports and enforce our <Link href="/acceptable-use">acceptable use policy</Link>.</li>
      <li><strong>To improve the product:</strong> understand aggregate usage and performance without profiling you for advertising.</li>
      <li><strong>To comply with law:</strong> respond to valid legal requests, tax and accounting rules, and enforce our <Link href="/terms">Terms of Service</Link>.</li>
    </ul>
    <p>Where data protection law requires a legal basis, we rely on performance of our contract with you, our legitimate interests in operating and securing the service, compliance with legal obligations and, where required, your consent. You can withdraw consent at any time, without affecting processing that already happened.</p>

    <h2>5. Who processes data</h2>
    <p>We share only what is needed for the relevant service, with providers that are bound by their own terms and, where required, data processing agreements:</p>
    <ul>
      <li><strong>Google</strong> — sign-in and account identity verification.</li>
      <li><strong>Telegram</strong> — sign-in, MiniApp launch, the bot and Telegram Stars payments.</li>
      <li><strong>ATLOS</strong> — crypto checkout and payment confirmation.</li>
      <li><strong>Runpod</strong> — GPU processing of prompts and reference images to create the requested output.</li>
      <li><strong>Our hosting, storage and security providers</strong> — running the site, the short-lived image cache, backups, email and network protection.</li>
      <li><strong>Professional advisers and authorities</strong> — where necessary for legal, tax, accounting, fraud prevention or a valid legal request.</li>
    </ul>
    <p>We do not sell personal data. We do not share it for cross-context behavioral advertising. If we are involved in a merger, acquisition or transfer of the service, data may be transferred as part of that transaction, subject to this policy and applicable law.</p>

    <h2>6. International transfers</h2>
    <p>Our providers may process data in countries other than yours. Where required, we use appropriate safeguards for those transfers, such as contractual protections or an equivalent legal mechanism. You can ask us for more information about the safeguards that apply to your data.</p>

    <h2>7. How long we keep data</h2>
    <ul>
      <li><strong>Account data:</strong> while your account is active. After a verified deletion request, we delete or anonymize it within a reasonable period, unless we must keep it for legal, accounting, fraud-prevention or dispute reasons.</li>
      <li><strong>Generation records:</strong> until you delete the generation or your account, or for as long as needed for the service and abuse prevention. Deleting a generation also removes its temporary image cache where available.</li>
      <li><strong>Temporary image cache:</strong> up to 24 hours by default. The exact period can be shorter. Your browser may keep its own copy until you clear the site’s storage.</li>
      <li><strong>Payment and ledger records:</strong> for as long as tax, accounting, anti-fraud or financial rules require. These records may outlive your account.</li>
      <li><strong>Authentication and security data:</strong> one-time challenges are short-lived; refresh tokens are rotated and stored as hashes; security logs are kept for a limited period and then deleted or aggregated.</li>
      <li><strong>Analytics:</strong> aggregate events may be retained for product reporting. They are designed not to identify you.</li>
      <li><strong>Support messages:</strong> for as long as needed to resolve your request and keep a record of the outcome.</li>
    </ul>

    <h2>8. Your rights</h2>
    <p>Depending on where you live, you may have the right to access, correct, delete, restrict or object to processing of your personal data; to receive a portable copy; to withdraw consent; and to complain to your local data protection authority. You can also ask us not to use your data for direct marketing — we do not run direct marketing.</p>
    <p>To exercise a right, email <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a> with the subject <strong>[Privacy]</strong>. We may need to verify that you control the account. We aim to respond within 30 days, and we will tell you if we need more time. Deleting your account may not remove records we must keep for tax, accounting, fraud prevention or legal reasons, or content already saved in your browser.</p>

    <h2>9. Security</h2>
    <p>We use HTTPS in production, HttpOnly and SameSite cookies, hashed authentication tokens, access controls, rate limiting and short-lived image caching. No online service is completely secure. Use a strong, unique sign-in method, protect your Telegram and Google accounts, and contact us if you suspect unauthorized access.</p>

    <h2>10. Adult content and sensitive data</h2>
    <p>UNKRE is an adult service. Do not upload government identity documents, financial credentials, medical records or images of anyone under 18. Reference photos may depict an adult only if you have the right and consent to use them. We process them to create your requested image, not to build a public profile. See the <Link href="/acceptable-use">acceptable use policy</Link> for the content rules.</p>

    <h2>11. Automated decisions</h2>
    <p>We may use automated checks for rate limiting, fraud prevention and abuse detection. These can temporarily block a request or account. We do not make solely automated decisions that produce legal or similarly significant effects without a way to contact us and ask for review.</p>

    <h2>12. Changes to this policy</h2>
    <p>We may update this policy as the product, providers or law change. The “last updated” date at the top shows the current version. If a change materially affects how we use personal data, we will take reasonable steps to make it visible before it applies.</p>

    <h2>13. Contact</h2>
    <p>Privacy questions and requests: <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>. General support and legal notices use the same address. You can also use the <Link href="/contact">contact page</Link>.</p>

    <div className="legal-note">
      <p><strong>Operator details.</strong> UNKRE is operated by the UNKRE team. Registered business details are available on request from <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>. If you need the legal entity name, registered address or a data protection contact for a formal request, ask support and we will provide the current details.</p>
    </div>

    <div className="legal-contact">
      <a href={`mailto:${legal.contactEmail}`}>Email privacy</a>
      <Link href="/terms">Terms of Service</Link>
      <Link href="/acceptable-use">Acceptable use</Link>
      <Link href="/trust">Trust center</Link>
    </div>
  </LegalArticle>;
}
