import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { MarketingHeader, MarketingFooter } from "@/components/marketing/shell";
import { CreateLink } from "@/components/marketing/create-link";
import { ArrowIcon } from "@/components/icons";
import { publicGuides, guidesUpdatedAt } from "@/lib/public-guides";
import { canonicalUrl, isIndexable, site, defaultSocialImage, languageAlternates } from "@/lib/site";
import "../../landing.css";

export const dynamicParams = false;
export function generateStaticParams() { return publicGuides.map(guide=>({slug:guide.slug})); }

function socialImage(slug: string) {
  return slug === "credits" ? defaultSocialImage : `/og/${slug}.jpg`;
}

export async function generateMetadata({params}: {params:Promise<{slug:string}>}):Promise<Metadata> {
  const {slug}=await params;
  const guide=publicGuides.find(item=>item.slug===slug);
  if (!guide) return {};
  const url=canonicalUrl(`/learn/${slug}`);
  const image=socialImage(slug);
  return {
    title:guide.title,
    description:guide.description,
    alternates:url?{canonical:url,languages:languageAlternates(url)}:undefined,
    robots:{index:isIndexable,follow:isIndexable,...(isIndexable?{"max-image-preview":"large" as const,"max-snippet":-1,"max-video-preview":-1}:{})},
    openGraph:{
      type:"article",
      locale:"en_US",
      siteName:site.name,
      title:guide.title,
      description:guide.description,
      ...(url?{url}:{}),
      images:[{url:image,width:1200,height:630,alt:guide.imageAlt??`${guide.title} — UNKRE`}],
    },
    twitter:{
      card:"summary_large_image",
      title:guide.title,
      description:guide.description,
      images:[{url:image,alt:guide.imageAlt??`${guide.title} — UNKRE`}],
    },
  };
}

export default async function GuidePage({params}:{params:Promise<{slug:string}>}) {
  const {slug}=await params;
  const guide=publicGuides.find(item=>item.slug===slug);
  if(!guide) notFound();
  const url=canonicalUrl(`/learn/${slug}`);
  const image=canonicalUrl(socialImage(slug));
  const reviewed=new Date(guidesUpdatedAt).toLocaleDateString("en-US",{year:"numeric",month:"long",day:"numeric",timeZone:"UTC"});
  const structuredData=url&&site.url&&image?{
    "@context":"https://schema.org",
    "@graph":[
      {
        "@type":"BreadcrumbList",
        "@id":`${url}#breadcrumb`,
        itemListElement:[
          {"@type":"ListItem",position:1,name:"UNKRE",item:site.url.href},
          {"@type":"ListItem",position:2,name:guide.label,item:url},
        ],
      },
      {
        "@type":"Article",
        "@id":`${url}#article`,
        mainEntityOfPage:{"@type":"WebPage","@id":url},
        headline:guide.heading,
        description:guide.description,
        image:[image],
        articleSection:guide.label,
        inLanguage:"en",
        datePublished:guidesUpdatedAt,
        dateModified:guidesUpdatedAt,
        breadcrumb:{"@id":`${url}#breadcrumb`},
        author:{"@type":"Organization",name:site.name,url:site.url.href},
        publisher:{
          "@type":"Organization",
          name:site.name,
          url:site.url.href,
          logo:{"@type":"ImageObject",url:canonicalUrl("/brand/unkre-mark-512.png")},
        },
      },
    ],
  }:null;
  return <div className="site-shell landing-v2"><a className="skip-link" href="#main">Skip to content</a><MarketingHeader /><main id="main" tabIndex={-1} className="public-guide content-width"><nav className="guide-breadcrumb" aria-label="Breadcrumb"><Link href="/">UNKRE</Link><span aria-hidden="true">/</span><span>{guide.label}</span></nav><article><header><p className="eyebrow">{guide.label}</p><h1>{guide.heading}</h1><p className="guide-intro">{guide.description}</p><p className="guide-byline">By the UNKRE team · Last reviewed {reviewed}</p><div className="guide-create"><CreateLink href={guide.href} placement="guide_top" preset={guide.slug}>{guide.cta}<ArrowIcon diagonal /></CreateLink><Link className="marketing-text-link" href="/#references">See real examples <ArrowIcon diagonal /></Link></div></header>{guide.image&&<Image className="guide-hero-image" src={guide.image} alt={guide.imageAlt??"UNKRE model example"} width={guide.imageWidth??1024} height={guide.imageHeight??1400} sizes="(max-width:760px) 90vw, 900px" quality={85} preload fetchPriority="high" />}<div className="guide-content">{guide.sections.map(section=><section key={section.title}><h2>{section.title}</h2>{section.paragraphs.map(paragraph=><p key={paragraph}>{paragraph}</p>)}</section>)}<div className="guide-create"><CreateLink href={guide.href} placement="guide_bottom" preset={guide.slug}>{guide.cta}<ArrowIcon diagonal /></CreateLink></div><nav className="guide-links" aria-label="Related guides">{guide.related.map(related=>{const item=publicGuides.find(value=>value.slug===related)!;return <Link className="marketing-text-link" key={related} href={`/learn/${related}`}>{item.label === "MODEL GUIDE" ? related === "krea-2" ? "Krea 2 guide" : "Qwen Image 2.1 guide" : item.label.toLowerCase()}<ArrowIcon diagonal /></Link>;})}</nav></div></article></main><MarketingFooter />{structuredData&&<script type="application/ld+json" dangerouslySetInnerHTML={{__html:JSON.stringify(structuredData).replace(/</g,"\\u003c")}}/>}</div>;
}
