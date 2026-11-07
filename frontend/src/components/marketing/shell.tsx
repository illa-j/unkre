import Image from "next/image";
import Link from "next/link";
import { AuthLink } from "../auth-link";
import { ArrowIcon } from "../icons";
import { CreateLink } from "./create-link";
import { site } from "@/lib/site";

export function MarketingHeader({ home = false }: { home?: boolean }) {
  const anchor = (id: string) => home ? `#${id}` : `/#${id}`;
  return <header className="marketing-header content-width"><Link href="/" className="wordmark" aria-label="UNKRE home"><Image className="wordmark-mark" src="/brand/unkre-mark-ui.webp" alt="" width={204} height={256} priority />unkre<span>.</span></Link><nav className="marketing-nav" aria-label="Explore UNKRE"><a href={anchor("references")}>What’s possible</a><a href={anchor("models")}>Models</a><a href={anchor("credits")}>Credits</a><a href={anchor("faq")}>FAQ</a><a href={site.telegramBotUrl} target="_blank" rel="noopener noreferrer">Telegram <span aria-hidden="true">↗</span></a></nav><nav className="auth-nav" aria-label="Account"><AuthLink mode="login" className="login-link">Log in</AuthLink><CreateLink placement="header" className="button button-primary button-small">Start creating <ArrowIcon diagonal /></CreateLink></nav></header>;
}

export function MarketingFooter() {
  return <footer className="marketing-footer content-width">
    <div className="footer-brand">
      <Link className="wordmark" href="/" aria-label="UNKRE home"><Image className="wordmark-mark" src="/brand/unkre-mark-ui.webp" alt="" width={204} height={256} />unkre<span>.</span></Link>
      <p>Your imagination. Your studio.</p>
    </div>
    <nav aria-label="Resources">
      <Link href="/learn/qwen-image-2-1">Qwen Image 2.1</Link>
      <Link href="/learn/krea-2">Krea 2</Link>
      <Link href="/learn/reference-images">Reference photos</Link>
      <Link href="/learn/consistent-characters">Consistent characters</Link>
      <Link href="/learn/loras">LoRA guide</Link>
      <Link href="/learn/credits">Credits &amp; help</Link>
    </nav>
    <nav aria-label="Company and legal">
      <Link href="/about">About</Link>
      <Link href="/trust">Trust center</Link>
      <Link href="/contact">Contact</Link>
      <Link href="/privacy">Privacy</Link>
      <Link href="/terms">Terms</Link>
      <Link href="/refunds">Refunds</Link>
      <Link href="/acceptable-use">Acceptable use</Link>
      <Link href="/copyright">Copyright</Link>
      <Link href="/security">Security</Link>
      <Link href="/transparency">Transparency</Link>
      <Link href="/status">Service status</Link>
    </nav>
    <div className="footer-contact">
      <a href={site.telegramBotUrl} target="_blank" rel="noopener noreferrer">Telegram bot &amp; MiniApp</a>
      {site.supportEmail && <a href={`mailto:${site.supportEmail}`}>Contact support</a>}
      <span>© {new Date().getFullYear()} UNKRE</span>
    </div>
  </footer>;
}
