import Image from "next/image";
import Link from "next/link";
import { ArrowIcon } from "@/components/icons";
import { StatueScene } from "@/components/statue-scene";
import { AdultDetails } from "@/components/age-consent";
import { LoraCollections } from "@/components/lora-collections";
import { KreaCharacterExamples } from "@/components/krea-character-examples";
import { HeroShowcase } from "@/components/marketing/hero-showcase";
import { CreateLink } from "@/components/marketing/create-link";
import { LandingBehavior } from "@/components/marketing/landing-behavior";
import { MarketingHeader, MarketingFooter } from "@/components/marketing/shell";
import { landingPresets, referenceHref, characterHref } from "@/lib/landing";
import { landingFaq } from "@/lib/landing-faq";
import { creationHref } from "@/lib/creation-intent";
import { site, welcomeOffer } from "@/lib/site";
import "./landing.css";

function SectionLink({ href, children }: { href: string; children: React.ReactNode }) {
  return <Link href={href} className="marketing-text-link">{children}<ArrowIcon diagonal /></Link>;
}

export default function Home() {
  const structuredData = site.url ? {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "@id": `${site.url.href}#organization`,
        name: site.name,
        url: site.url.href,
        logo: { "@type": "ImageObject", url: new URL("/brand/unkre-mark-512.png", site.url).href, width: 407, height: 512 },
        ...(site.supportEmail ? { email: site.supportEmail } : {}),
        ...(/^https:\/\/(t\.me|telegram\.me)\//.test(site.telegramBotUrl) ? { sameAs: [site.telegramBotUrl] } : {}),
      },
      {
        "@type": "WebSite",
        "@id": `${site.url.href}#website`,
        name: site.name,
        url: site.url.href,
        description: site.description,
        inLanguage: "en",
        publisher: { "@id": `${site.url.href}#organization` },
      },
      {
        "@type": "WebApplication",
        "@id": `${site.url.href}#app`,
        name: site.name,
        url: site.url.href,
        applicationCategory: "MultimediaApplication",
        operatingSystem: "Web",
        browserRequirements: "Requires JavaScript",
        description: site.description,
        inLanguage: "en",
        isPartOf: { "@id": `${site.url.href}#website` },
        publisher: { "@id": `${site.url.href}#organization` },
      },
      {
        "@type": "FAQPage",
        "@id": `${site.url.href}#faq`,
        mainEntity: landingFaq.map((item) => ({
          "@type": "Question",
          name: item.question,
          acceptedAnswer: { "@type": "Answer", text: item.answer },
        })),
      },
    ],
  } : null;
  return <div className="site-shell landing-v2" data-scene-shell>
    <a className="skip-link" href="#main">Skip to content</a>
    <StatueScene />
    <MarketingHeader home />
    <main id="main" tabIndex={-1}>
      <section id="intro" className="landing-hero content-width" aria-labelledby="hero-title">
        <div className="landing-hero-copy"><p className="eyebrow"><span className="status-dot" />UNCENSORED AI IMAGE GENERATOR</p>
          <h1 id="hero-title">Ultra-realistic{" "}<br />AI images.{" "}<br /><em>Uncensored.</em></h1>
          <p className="hero-description">Generate <strong>SFW and NSFW images</strong> from your reference photos, or create your own AI character. Your ideas, brought to life with Krea 2 and Qwen Image 2.1.</p>
          <div id="hero-action" className="hero-actions"><CreateLink placement="hero">Create my first image <ArrowIcon diagonal /></CreateLink><a className="marketing-text-link" href="#references">See what’s possible <span aria-hidden="true">↓</span></a></div>
          <p className="offer-note"><span aria-hidden="true">✳</span>{welcomeOffer}<small>Google or Telegram sign-in · <a href={site.telegramBotUrl} target="_blank" rel="noopener noreferrer">Telegram bot &amp; MiniApp</a></small></p>
          <div className="hero-capability-row"><span>Text to image</span><span>Reference photos</span><span>Character creation</span></div>
        </div>
        <HeroShowcase />
        <div className="hero-scroll-note"><span>MADE FOR YOUR IMAGINATION</span><a href="#references">SCROLL TO EXPLORE <span aria-hidden="true">↓</span></a></div>
      </section>

      <section id="references" className="landing-section content-width" aria-labelledby="references-title">
        <div className="section-heading"><div><p className="eyebrow">START WITH SOMEONE. GO SOMEWHERE NEW.</p><h2 id="references-title">Your reference.{" "}<br /><em>A new possibility.</em></h2></div><p>Use your reference photos to generate SFW and NSFW images with Qwen Image 2.1. Describe a different scene, mood or outfit, and explore a new direction.</p></div>
        <div className="reference-feature"><figure className="reference-input"><div className="feature-image"><Image src="/images/qwen-image-2-1/reference.png" alt="Reference photo of an adult woman with long black hair beneath a conservatory roof" width={450} height={600} sizes="(max-width:760px) 40vw, 330px" quality={85} /></div><figcaption><span>01</span>Your reference photo</figcaption></figure><div className="reference-connector" aria-hidden="true"><ArrowIcon /></div><figure className="reference-output"><div className="feature-image"><Image src="/images/qwen-image-2-1/sfw.png" alt="Qwen Image 2.1 generated example of the referenced woman in a new scene at a warm, dimly lit bar" width={896} height={1184} sizes="(max-width:760px) 47vw, 450px" quality={85} /><span className="image-label">QWEN IMAGE 2.1 · SFW</span></div><figcaption><span>02</span>A different scene. The same starting point.</figcaption></figure><div className="reference-feature-copy"><span className="feature-number">01 — REIMAGINE</span><h3>A photo is{" "}<br />just the beginning.</h3><p>Start with a person you want to create with. Add your reference in Studio and tell Qwen what comes next.</p><CreateLink href={referenceHref} placement="reference">Create from a reference <ArrowIcon diagonal /></CreateLink><SectionLink href="/learn/reference-images">How reference images work</SectionLink></div></div>
        <AdultDetails className="adult-feature lora-adult-previews" summary={<><span className="lora-badge lora-badge-adult">NSFW · 18+</span><span>Explore the same reference in an adult example</span><span className="lora-disclosure-icon" aria-hidden="true">+</span></>}><div className="adult-feature-content"><Image src="/images/qwen-image-2-1/nsfw.png" alt="Adult NSFW Qwen image generated using the same reference photo" width={896} height={1184} sizes="(max-width:760px) 80vw, 360px" quality={85} /><div><h3>Another creative direction.</h3><p>Use the same reference as a starting point, then explore a new scene with your prompt and compatible LoRAs.</p><CreateLink href={referenceHref} placement="reference_adult">Use my reference <ArrowIcon diagonal /></CreateLink></div></div></AdultDetails>
      </section>

      <section id="characters" className="landing-section character-section content-width" aria-labelledby="characters-title"><div className="character-copy"><p className="eyebrow">CREATE SOMEONE OF YOUR OWN</p><h2 id="characters-title">Your character.{" "}<br /><em>More to their story.</em></h2><p>Build a recurring AI character and explore different scenes. For Krea 2, keep the same seed and character description, then change the moment around them.</p><p className="small-copy">Explore consistent character generation for SFW and NSFW images. Results can vary, including facial details and other features.</p><CreateLink href={characterHref} placement="characters">Create my character <ArrowIcon diagonal /></CreateLink><SectionLink href="/learn/consistent-characters">A guide to character consistency</SectionLink></div><KreaCharacterExamples /></section>

      <section id="how-it-works" className="landing-section steps-section content-width" aria-labelledby="steps-title"><div className="section-heading"><div><p className="eyebrow">FROM AN IDEA TO AN IMAGE</p><h2 id="steps-title">Make it happen.{" "}<br /><em>In three steps.</em></h2></div><CreateLink placement="steps" className="button button-outline">Start creating <ArrowIcon diagonal /></CreateLink></div><ol className="creation-steps"><li><span>01</span><h3>Choose your model.</h3><p>Explore Krea 2 Turbo or Qwen Image 2.1. Each offers a different starting point.</p></li><li><span>02</span><h3>Give it your direction.</h3><p>Write a prompt, add a reference with Qwen, or try a compatible LoRA for a new look.</p></li><li><span>03</span><h3>Make it yours.</h3><p>Generate your image, explore another idea and download your results from Studio.</p></li></ol></section>

      <section id="models" className="landing-section content-width" aria-labelledby="models-title"><div className="section-heading"><div><p className="eyebrow">THE TOOLS BEHIND YOUR IDEAS</p><h2 id="models-title">Two starting points.{" "}<br /><em>One creative studio.</em></h2></div><p>Generate ultra-realistic AI images with Krea 2 Turbo, or use Qwen Image 2.1 for text prompts and reference photos.</p></div><div className="landing-model-grid">{landingPresets.map((model,index)=><article key={model.id} className="landing-model-card"><div className="model-card-art"><Image src={model.image} alt={model.alt} width={model.width} height={model.height} sizes="(max-width:650px) 90vw, (max-width:1000px) 45vw, 390px" quality={85} /><span>0{index+1}</span></div><div className="model-card-body"><h3>{model.model}</h3><p>{model.model.startsWith("Qwen") ? "Turn text prompts and reference photos into a new scene. Explore compatible Qwen LoRAs." : "Explore photographic images, build a character from a description and shape the look with compatible LoRAs."}</p><CreateLink href={creationHref({model:model.model,prompt:model.prompt})} placement="model_card" preset={model.id} className="marketing-text-link">Try {model.model} <ArrowIcon diagonal /></CreateLink><Link className="model-learn-link" href={model.model.startsWith("Qwen") ? "/learn/qwen-image-2-1" : "/learn/krea-2"}>Model guide</Link></div></article>)}</div><p className="model-swipe-note">Swipe to explore both models <span aria-hidden="true">→</span></p></section>

      <section id="loras" className="landing-section content-width" aria-labelledby="loras-title"><div className="section-heading"><div><p className="eyebrow">FIND YOUR LOOK</p><h2 id="loras-title">A different LoRA.{" "}<br /><em>A different feeling.</em></h2></div><p>Choose a LoRA to shape the look of your images. Explore SFW and NSFW examples from compatible Krea 2 and Qwen collections. These are only a few examples — explore all LoRAs and try them in Studio.</p></div><LoraCollections compact /><div className="section-bottom-action"><p>A selection of what’s possible. Explore available model and LoRA combinations in Studio.</p><CreateLink href="/studio/loras" placement="lora_collection" className="button button-outline">Explore LoRAs <ArrowIcon diagonal /></CreateLink></div></section>

      <section id="credits" className="landing-section content-width" aria-labelledby="credits-title"><div className="credits-offer"><div><p className="eyebrow">ROOM FOR YOUR FIRST IDEA</p><h2 id="credits-title">{site.welcomeCredits > 0 ? <>{site.welcomeCredits} free credits.{" "}<br /><em>A new beginning.</em></> : <>Your next image.{" "}<br /><em>Starts here.</em></>}</h2><p>{site.welcomeCredits > 0 ? "New accounts receive welcome credits after their first Google or Telegram sign-in. No card is needed to register." : "Sign in with Google or Telegram to create your account and explore Studio."}</p><CreateLink placement="credits_offer">Create my first image <ArrowIcon diagonal /></CreateLink><SectionLink href="/learn/credits">How credits work</SectionLink></div><div className="credit-facts"><div><span>01</span><p><strong>Your account, your collection.</strong>Find your generations and balance in Studio.</p></div><div><span>02</span><p><strong>Clear next steps.</strong>Review available top-ups and their prices before payment.</p></div><div><span>03</span><p><strong>A welcome offer.</strong>Starter credits are for new accounts, rather than a daily allowance or a fixed image count.</p></div></div></div></section>

      <section id="faq" className="landing-section faq-section content-width" aria-labelledby="faq-title"><div><p className="eyebrow">A FEW THINGS TO KNOW</p><h2 id="faq-title">Before you{" "}<br /><em>begin.</em></h2><p>Models, reference photos, character consistency and your first credits.</p><SectionLink href="/learn/credits">Getting started & credits</SectionLink></div><div className="landing-faq">{landingFaq.map(item=><details key={item.question}><summary>{item.question}<span aria-hidden="true">+</span></summary><p>{item.answer}</p></details>)}</div></section>

      <section id="create" className="landing-section final-create content-width" aria-labelledby="final-title"><p className="eyebrow">YOUR IMAGINATION HAS SOMEWHERE TO GO</p><h2 id="final-title">Make it{" "}<br /><em>yours.</em></h2><p>Ultra-realistic images. Original characters. SFW or NSFW.{" "}<br />Start with your imagination, or bring a reference photo.</p><CreateLink placement="final">Create my first image <ArrowIcon diagonal /></CreateLink><span className="offer-note">{welcomeOffer}</span></section>
    </main>
    <MarketingFooter /><LandingBehavior />
    <noscript><p className="noscript-notice content-width">Explore the examples and guides without JavaScript. Enable JavaScript to sign in and create images in Studio.</p></noscript>
    {structuredData && <script type="application/ld+json" dangerouslySetInnerHTML={{__html:JSON.stringify(structuredData).replace(/</g,"\\u003c")}} />}
  </div>;
}
