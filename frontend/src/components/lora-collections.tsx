import Image from "next/image";
import { CreateLink } from "./marketing/create-link";
import { creationHref } from "@/lib/creation-intent";
import { ArrowIcon } from "@/components/icons";
import { AdultDetails } from "@/components/age-consent";
import { loraCollections, type LoraCollection, type LoraExample } from "@/lib/lora-collections";

function PreviewGrid({ examples, name, category, mixedLayout = false }: {
  examples: LoraExample[];
  name: string;
  category: "SFW" | "NSFW";
  mixedLayout?: boolean;
}) {
  return (
    <div className={`lora-gallery${mixedLayout ? " lora-gallery-mixed" : ""}`}>
      {examples.map(({ file, width, height }, index) => (
        <div key={file} className="lora-preview">
          <Image
            src={`/images/loras/${file}.png`}
            alt={`${name} — ${category} example ${index + 1}`}
            width={width}
            height={height}
            sizes="(max-width: 760px) 44vw, 300px"
            quality={85}
          />
        </div>
      ))}
    </div>
  );
}

function CollectionCard({ collection, compact = false }: { collection: LoraCollection; compact?: boolean }) {
  return (
    <article id={`lora-${collection.id}`} className="lora-collection" aria-labelledby={`${collection.id}-title`}>
      <header className="lora-collection-heading">
        <h4 id={`${collection.id}-title`}>{collection.name}</h4>
        {collection.source && (
          <a className="lora-source" href={collection.source} target="_blank" rel="noopener noreferrer" aria-label={`View ${collection.name} on Civitai (opens in a new tab)`}>
            Civitai <ArrowIcon diagonal />
          </a>
        )}
      </header>

      {collection.sfw.length > 0 && (
        <div className="lora-preview-group">
          <p className="lora-gallery-label"><span className="lora-badge">SFW</span><span>{collection.sfw.length} {collection.sfw.length === 1 ? "example" : "examples"}</span></p>
          <PreviewGrid examples={collection.sfw} name={`${collection.model} · ${collection.name}`} category="SFW" />
        </div>
      )}

      {collection.nsfw.length > 0 && (
        <AdultDetails
          className="lora-adult-previews"
          summary={<>
            <span className="lora-badge lora-badge-adult">NSFW · 18+</span>
            <span>{collection.nsfw.length} examples</span>
            <span className="lora-disclosure-icon" aria-hidden="true">+</span>
          </>}
        >
          <PreviewGrid examples={collection.nsfw} name={`${collection.model} · ${collection.name}`} category="NSFW" mixedLayout={collection.mixedLayout} />
        </AdultDetails>
      )}
      {compact && <CreateLink href={creationHref({ model: collection.model, lora: collection.name })} placement="lora_card" preset={collection.id} className="marketing-text-link">Explore this look <ArrowIcon diagonal /></CreateLink>}
    </article>
  );
}

export function LoraCollections({ compact = false }: { compact?: boolean }) {
  const models = [...new Set(loraCollections.map((collection) => collection.model))];

  return (
    <div className={`lora-collections${compact ? " is-compact" : ""}`}>
      {models.map((model) => {
        const modelId = `lora-model-${model.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
        return (
          <div key={model} className="lora-model-group" role="group" aria-labelledby={modelId}>
            <h3 id={modelId} className="lora-model-title">{model}</h3>
            {loraCollections.filter((collection) => collection.model === model).map((collection) => (
              <CollectionCard key={collection.id} collection={collection} compact={compact} />
            ))}
          </div>
        );
      })}
    </div>
  );
}
