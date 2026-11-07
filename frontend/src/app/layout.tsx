import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { site, isIndexable, defaultSocialImage, languageAlternates } from "@/lib/site";
import { SessionProvider } from "@/components/session-provider";
import { AgeConsentProvider } from "@/components/age-consent";
import { WebVitalsReporter } from "@/components/marketing/web-vitals-reporter";
import { AuthDialog } from "@/components/auth-dialog";
import { TelegramMiniAppProvider } from "@/components/telegram-miniapp";
import "./globals.css";

const sans = localFont({
  src: "../../node_modules/@fontsource-variable/dm-sans/files/dm-sans-latin-wght-normal.woff2",
  display: "swap",
  variable: "--font-sans",
});
const serif = localFont({
  src: [
    { path: "../../node_modules/@fontsource/instrument-serif/files/instrument-serif-latin-400-normal.woff2", weight: "400", style: "normal" },
    { path: "../../node_modules/@fontsource/instrument-serif/files/instrument-serif-latin-400-italic.woff2", weight: "400", style: "italic" },
  ],
  display: "swap",
  variable: "--font-serif",
});

export const metadata: Metadata = {
  metadataBase: site.url ?? new URL("http://localhost:3000"),
  title: site.title,
  description: site.description,
  applicationName: site.name,
  alternates: site.url ? { canonical: site.url.href, languages: languageAlternates(site.url.href) } : undefined,
  robots: {
    index: isIndexable,
    follow: isIndexable,
    ...(isIndexable ? { "max-image-preview": "large" as const, "max-snippet": -1, "max-video-preview": -1 } : {}),
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: site.name,
    title: site.title,
    description: site.description,
    ...(site.url ? { url: site.url.href } : {}),
    images: [{ url: defaultSocialImage, width: 1200, height: 630, alt: "UNKRE — Ultra-realistic, uncensored SFW and NSFW AI images." }],
  },
  twitter: {
    card: "summary_large_image",
    title: site.title,
    description: site.description,
    images: [{ url: defaultSocialImage, alt: "UNKRE — Ultra-realistic, uncensored SFW and NSFW AI images." }],
  },
};

export const viewport: Viewport = { themeColor: "#090e12", colorScheme: "dark" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth" className={`${sans.variable} ${serif.variable}`}>
      <body>
        <AgeConsentProvider><TelegramMiniAppProvider><SessionProvider><WebVitalsReporter />{children}<AuthDialog /></SessionProvider></TelegramMiniAppProvider></AgeConsentProvider>
      </body>
    </html>
  );
}
