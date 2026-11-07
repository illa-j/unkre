import Image from "next/image";
import type { CSSProperties } from "react";

const studies = {
  intro: [
    { image: "krea-2-turbo.png", width: 832, height: 1248, alt: "Krea 2 Turbo example: a woman with glasses beside a studio microphone" },
    { image: "qwen-image-2-1/example.png", width: 2048, height: 3072, alt: "Qwen Image 2.1 example: a woman with silver and mint hair, tattoos and a denim top" },
  ],
  create: [
    { image: "krea-2-character/sfw-2.png", width: 1024, height: 1536, alt: "Krea 2 example: a woman in a black and white outfit seated on a black car at night" },
    { image: "krea-2-turbo.png", width: 832, height: 1248, alt: "Krea 2 Turbo example: a woman with glasses beside a studio microphone" },
    { image: "qwen-image-2-1/example.png", width: 2048, height: 3072, alt: "Qwen Image 2.1 example: a woman with silver and mint hair, tattoos and a denim top" },
  ],
} as const;

export function StudioStudies({ variant }: { variant: keyof typeof studies }) {
  return (
    <figure className={`floating-studies floating-studies-${variant}`}>
      {studies[variant].map(({ image, width, height, alt }) => (
        <div key={image} className="floating-study" style={{ "--study-aspect-ratio": `${width} / ${height}` } as CSSProperties}>
          <Image src={`/images/${image}`} alt={alt} fill sizes="(max-width: 760px) 46vw, (max-width: 1100px) 140px, 182px" quality={85} />
        </div>
      ))}
      <figcaption>Krea 2 &amp; Qwen Image 2.1 examples</figcaption>
    </figure>
  );
}
