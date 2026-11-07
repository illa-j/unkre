import Link from "next/link";
import { LegalArticle } from "@/components/legal/legal-article";
import { legal, legalMetadata } from "@/lib/legal";
import { site } from "@/lib/site";

export const metadata = legalMetadata({
  title: "About UNKRE — Independent AI Image Studio",
  description: "UNKRE is an independent studio for realistic SFW and NSFW AI images, built around reference photos, recurring characters and curated LoRAs.",
  path: "/about",
  ogAlt: "About UNKRE — an independent AI image studio for adults",
});

export default function AboutPage() {
  return <LegalArticle
    title="About UNKRE"
    intro="A focused image studio for adults: realistic models, reference photos, recurring characters and LoRAs — without pretending that AI is magic or that every output is safe to publish."
    current="/about"
    schemaType="AboutPage"
  >
    <h2>What UNKRE is</h2>
    <p>UNKRE is an independent AI image studio. It brings Krea 2 Turbo and Qwen Image 2.1 into one workflow, adds reference-photo support and character consistency tools, and lets you shape the result with curated LoRAs. It is built for people who want an adult-friendly creative space without a generic “anything goes” interface.</p>
    <p>The product is deliberately narrow. It is not a social network, a marketplace for prompts, a face-swap tool or a place to publish other people’s private images. It is a studio for creating your own images, with public examples and guides that show what the models can do.</p>

    <h2>What you can create</h2>
    <ul>
      <li><strong>Text-to-image portraits and scenes</strong> with Krea 2 Turbo or Qwen Image 2.1.</li>
      <li><strong>Reference-based images</strong> with Qwen, using a photo you have the right to use.</li>
      <li><strong>Recurring characters</strong> by keeping a description and seed stable while changing the scene.</li>
      <li><strong>Style exploration</strong> with model-specific LoRA collections and adjustable strength.</li>
      <li><strong>SFW and NSFW work</strong> for adults, within the boundaries of the <Link href="/acceptable-use">acceptable use policy</Link>.</li>
    </ul>

    <h2>How it works</h2>
    <ol>
      <li>Sign in with Google or Telegram. New accounts receive the welcome credits shown on the landing page.</li>
      <li>Choose a model, write a prompt and add a reference photo if the workflow supports it.</li>
      <li>Generate an image and review the result in Studio. Completed images are cached briefly on our side and saved in your browser library.</li>
      <li>Add credits when you need more. Crypto checkout is handled by ATLOS; card payments through Telegram are handled with Telegram Stars.</li>
    </ol>
    <p>Credits are prepaid and used per generation. Prices and minimums are shown in Studio before you pay. There is no subscription and no automatic renewal.</p>

    <h2>Who it is for</h2>
    <p>UNKRE is for adults creating their own visual work: portrait and character experiments, moodboards, adult creators working with fictional adults, and anyone exploring a photographic look with AI. It is not for anyone under 18, and it is not for creating intimate content about real people without their consent.</p>

    <h2>What we stand for</h2>
    <ul>
      <li><strong>Adults only.</strong> Age is a hard boundary, not a disclaimer.</li>
      <li><strong>Consent and rights.</strong> Reference photos must be yours or used with permission. Real people are not content props.</li>
      <li><strong>Privacy.</strong> We do not run advertising trackers, and our first-party analytics deliberately excludes prompts, files and user IDs.</li>
      <li><strong>Transparency.</strong> We say when an image is an example, when a result varies and when a model or LoRA may not reproduce the original recipe.</li>
      <li><strong>Craft.</strong> The guides explain how the tools behave rather than promising a guaranteed face, body or style.</li>
    </ul>

    <h2>How the guides are written</h2>
    <p>The public guides are written by the UNKRE team from the product’s actual workflows and the public documentation of the models we use. Examples are illustrative: they show a direction, not a guaranteed output. When a model, workflow or LoRA changes, we review the relevant guide and update its “last reviewed” date. If you find something inaccurate, email <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>.</p>

    <h2>Independent, but not anonymous</h2>
    <p>UNKRE is operated by the UNKRE team. We publish a real support address, a Telegram bot and these policies because an adult AI product needs someone accountable behind it. Registered business details are available on request from <a href={`mailto:${legal.contactEmail}`}>{legal.contactEmail}</a>.</p>

    <div className="legal-contact">
      <a href={`mailto:${legal.contactEmail}`}>Email the team</a>
      <a href={site.telegramBotUrl} target="_blank" rel="noopener noreferrer">Telegram bot &amp; MiniApp</a>
      <Link href="/contact">All contact options</Link>
      <Link href="/trust">Trust center</Link>
    </div>
  </LegalArticle>;
}
