"use client";

import Image from "next/image";
import Link from "next/link";
import { useRef, useState } from "react";
import type { Lora, Workflow } from "@/lib/api-types";
import { loraTitle, workflowTitle } from "@/lib/catalog";
import { useWorkspace } from "@/lib/workspace";
import { useCatalog } from "./catalog-provider";
import { LoraPreviewViewer, Chevron, type LoraPreviewRequest } from "./lora-preview-viewer";
import { SessionNotice } from "./session-notice";
import { StudioIcon } from "./studio-icon";
import { Select } from "@/components/ui/select";

type CatalogLora = Lora & { workflow: Workflow };

export function LoraCatalog() {
  const catalog = useCatalog();
  const workspace = useWorkspace();
  const [search, setSearch] = useState("");
  const [workflow, setWorkflow] = useState("");
  const [preview, setPreview] = useState<{ request: LoraPreviewRequest; session: number } | null>(null);
  const previewSession = useRef(0);
  const openPreview = (request: LoraPreviewRequest) => {
    previewSession.current += 1;
    setPreview({ request, session: previewSession.current });
  };
  const collections = catalog.workflows
    .filter(item => !workflow || item.id === workflow)
    .flatMap(item => item.loras.map(lora => ({ ...lora, workflow: item })))
    .filter(item => `${loraTitle(item)} ${workflowTitle(item.workflow)} ${item.name} ${item.description ?? ""} ${item.is_nsfw ? "nsfw 18+" : "sfw"}`.toLowerCase().includes(search.toLowerCase()));
  return <>
    <div className="studio-page-heading"><div><h1>Explore LoRAs</h1><p>Find a LoRA compatible with your model.</p></div></div>
    <SessionNotice />
    <div className="studio-filterbar"><label className="studio-search"><StudioIcon name="search" size={18} /><input aria-label="Search LoRAs" value={search} placeholder="Find a LoRA…" onChange={event => setSearch(event.target.value)} /></label><div className="studio-filter-select"><span className="studio-sr-only">Filter by model</span><Select ariaLabel="Filter by model" value={workflow} options={[{ value: "", label: "All models" }, ...catalog.workflows.map(item => ({ value: item.id, label: workflowTitle(item) }))]} onChange={setWorkflow} /></div></div>
    {catalog.loading && <p className="studio-live-note" role="status">Loading your LoRAs…</p>}
    {catalog.error && <div className="studio-api-notice" role="alert"><p>{catalog.error}</p><button type="button" className="studio-button" onClick={catalog.reload}>Try again</button></div>}
    <p className="studio-results-note">{collections.length} available styles<span>Each LoRA is shown with its compatible model.</span></p>
    <div className="studio-lora-grid">{collections.map(item => <LoraCard key={`${item.workflow.id}:${item.id}`} item={item} showAdult={workspace.settings.showAdult} onOpenPreview={openPreview} />)}</div>
    {!catalog.loading && !catalog.error && !collections.length && <div className="studio-empty"><StudioIcon name="lora" size={30} /><h2>No styles here yet.</h2><p>Try another model or check back for new LoRAs.</p></div>}
    <LoraPreviewViewer key={preview?.session ?? 0} preview={preview?.request ?? null} onClose={() => setPreview(null)} />
  </>;
}

function LoraCard({ item, showAdult, onOpenPreview }: { item: CatalogLora; showAdult: boolean; onOpenPreview: (preview: LoraPreviewRequest) => void }) {
  const [revealed, setRevealed] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const title = loraTitle(item);
  const previews = item.preview_urls;
  const total = previews.length;
  const hasMultiple = total > 1;
  const active = previews[activeIndex] ?? previews[0];
  const isRevealed = revealed || showAdult;
  const canBrowse = hasMultiple && (!item.is_nsfw || isRevealed);
  const step = (delta: number) => setActiveIndex(current => (current + delta + total) % total);
  const previewLabel = `${hasMultiple ? `Open all ${total} previews` : "View preview"} for ${title}`;
  const openViewer = () => onOpenPreview({ title, urls: previews, index: activeIndex, isNsfw: item.is_nsfw });
  return <article className="studio-lora-card">
    <div className="studio-lora-art studio-live-lora-art">
      {item.is_nsfw && !isRevealed
        ? active
          ? <div className="studio-adult-cover">
            <Image className="studio-adult-cover-img" src={active} alt="" aria-hidden width={600} height={700} unoptimized />
            <div className="studio-adult-cover-body"><span className="studio-adult-age">18+</span><p>NSFW preview</p><button type="button" className="studio-button studio-button-small" onClick={() => setRevealed(true)}>Reveal preview</button></div>
          </div>
          : <div className="studio-adult-cover"><div className="studio-adult-cover-body"><span className="studio-adult-age">18+</span><p>{title}</p><p>No preview available</p></div></div>
        : active
          ? <button type="button" className="studio-lora-preview-trigger" aria-label={previewLabel} onClick={openViewer}>
            <Image className="studio-lora-preview" src={active} alt={`${title} preview ${activeIndex + 1} of ${total}`} width={600} height={700} unoptimized />
            {hasMultiple && <span className="studio-lora-preview-count">{activeIndex + 1} / {total}</span>}
          </button>
          : <div className="studio-lora-placeholder"><StudioIcon name="lora" size={30} /><span>{title}</span></div>}
      <div className="studio-lora-badges">
        <span className="studio-lora-model">{workflowTitle(item.workflow)}</span>
        {item.is_nsfw && <span className="studio-lora-age-badge">18+</span>}
      </div>
      {canBrowse && <>
        <button type="button" className="studio-lora-card-nav is-previous" aria-label={`Previous preview for ${title}`} onClick={() => step(-1)}><Chevron direction="left" /></button>
        <button type="button" className="studio-lora-card-nav is-next" aria-label={`Next preview for ${title}`} onClick={() => step(1)}><Chevron direction="right" /></button>
      </>}
    </div>
    <div className="studio-lora-info">
      <h2 title={title}>{title}</h2>
      <p>{workflowTitle(item.workflow)}{item.workflow.recommended_strengths?.[item.id] != null ? ` · recommended strength ${item.workflow.recommended_strengths[item.id].toFixed(2)}` : ""}</p>
      <div className="studio-lora-actions">
        <Link className="studio-button studio-button-small studio-lora-use" href={`/studio?model=${encodeURIComponent(item.workflow.id)}&lora=${encodeURIComponent(item.id)}`}>Use this LoRA <StudioIcon name="plus" size={15} /></Link>
        {hasMultiple && (!item.is_nsfw || isRevealed) && <button type="button" className="studio-button studio-button-small studio-lora-preview-more" onClick={openViewer}>View all <span>{previews.length}</span></button>}
      </div>
    </div>
  </article>;
}
