import Image from "next/image";
import { AdultDetails } from "@/components/age-consent";

const sfwExamples = [
  {
    file: "sfw-1.png",
    alt: "Krea 2 SFW example: a woman in a black and white outfit holding a crepe at a night market",
    caption: "At the night market",
  },
  {
    file: "sfw-2.png",
    alt: "Krea 2 SFW example: the same character in a black and white outfit seated on a black car at night",
    caption: "A different scene",
  },
];

export function KreaCharacterExamples() {
  return (
    <div className="reference-examples character-examples" role="group" aria-label="Krea 2 character consistency examples">
      <p className="method-label">KREA 2 · CHARACTER CONSISTENCY EXAMPLES</p>
      <p className="lora-gallery-label"><span className="lora-badge">SFW</span><span>2 examples</span></p>
      <div className="lora-gallery">
        {sfwExamples.map(({ file, alt, caption }) => (
          <figure key={file}>
            <div className="lora-preview">
              <Image src={`/images/krea-2-character/${file}`} alt={alt} width={1024} height={1536} sizes="(max-width: 760px) 44vw, 280px" quality={85} />
            </div>
            <figcaption>{caption}</figcaption>
          </figure>
        ))}
      </div>
      <AdultDetails
        className="lora-adult-previews"
        summary={<>
          <span className="lora-badge lora-badge-adult">NSFW · 18+</span>
          <span>1 example</span>
          <span className="lora-disclosure-icon" aria-hidden="true">+</span>
        </>}
      >
        <div className="lora-gallery">
          <figure>
            <div className="lora-preview">
              <Image src="/images/krea-2-character/nsfw-1.png" alt="Krea 2 NSFW example: the same adult character posing nude on a bed" width={1024} height={1536} sizes="(max-width: 760px) 44vw, 280px" quality={85} />
            </div>
            <figcaption>NSFW generated image</figcaption>
          </figure>
        </div>
      </AdultDetails>
      <p className="art-note">Krea 2 · One character, different scenes</p>
    </div>
  );
}
