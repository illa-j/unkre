import Image from "next/image";
import { landingPresets } from "@/lib/landing";
import { creationHref } from "@/lib/creation-intent";
import { CreateLink } from "./create-link";
import { ArrowIcon } from "../icons";

export function HeroShowcase() {
  const preset = landingPresets[1];
  return <div className="hero-showcase">
    <div className="showcase-top"><span><i /><i /><i /></span><p>YOUR UNKRE STUDIO</p><span className="showcase-example">Model example</span></div>
    <div className="showcase-art" style={{ aspectRatio: `${preset.width} / ${preset.height}` }}><Image src={preset.image} alt={preset.alt} width={preset.width} height={preset.height} sizes="(max-width: 760px) 90vw, (max-width:1100px) 46vw, 600px" quality={85} preload fetchPriority="high" /><span className="showcase-model">{preset.model}</span><div className="showcase-detail"><span>THE DETAILS MAKE IT REAL</span><p>Every detail.<br /><em>Brought to life.</em></p></div></div>
    <div className="showcase-controls"><CreateLink href={creationHref({model:preset.model,prompt:preset.prompt})} placement="hero_example" preset={preset.id} className="showcase-try">Try this look <ArrowIcon diagonal /></CreateLink></div>
  </div>;
}
