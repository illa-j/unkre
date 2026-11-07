"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import type { StudioImage } from "@/lib/studio";
import { useWorkspace } from "@/lib/workspace";

export function ImageCard({ image, saved = false, eager = false }: { image: StudioImage; saved?: boolean; eager?: boolean }) {
  const workspace = useWorkspace();
  const [revealed, setRevealed] = useState(false);
  const gated = image.category === "NSFW" && !workspace.settings.showAdult && !revealed;
  const badge = saved ? "SAVED PREVIEW" : image.category === "NSFW" ? "NSFW · 18+" : "STUDIO EXAMPLE";
  return <article className="studio-image-card"><div className={`studio-image-card-art${gated ? " is-gated" : ""}`}>
    {gated
      ? <button type="button" className="studio-image-gate" onClick={() => setRevealed(true)} aria-label={`Reveal ${image.title}, adults only 18+`}>
        <Image src={image.src} alt="" width={image.width} height={image.height} loading="lazy" sizes="(max-width: 540px) 43vw, (max-width: 1100px) 30vw, 300px" quality={85} />
        <span className="studio-image-gate-label"><strong>18+</strong>Tap to reveal<small>{image.title}</small></span>
      </button>
      : <Link href={`/studio/images/${image.id}`} aria-label={`View ${image.title}`}><Image src={image.src} alt={image.title} width={image.width} height={image.height} loading={eager ? "eager" : "lazy"} sizes="(max-width: 540px) 43vw, (max-width: 1100px) 30vw, 300px" quality={85} /></Link>}
    <span className="studio-image-card-badge">{badge}</span>
  </div>{image.lora && <p className="studio-image-card-lora"><span>LoRA</span>{image.lora}</p>}</article>;
}
