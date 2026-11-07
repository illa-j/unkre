"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { defaultDraft, modelName, studioImages } from "@/lib/studio";
import { updateWorkspace, useWorkspace, useWorkspaceReady } from "@/lib/workspace";
import { StudioIcon } from "./studio-icon";

export function ImageDetail({ id }: { id: string }) {
  const workspace = useWorkspace();
  const ready = useWorkspaceReady();
  const router = useRouter();
  const saved = workspace.saved.find(image => image.id === id);
  const image = studioImages.find(image => image.id === (saved?.sourceId ?? id));
  if (!ready && !image) return <p className="studio-loading" role="status">Opening your image…</p>;
  if (!image) return <div className="studio-empty"><StudioIcon name="image" size={32} /><h1>This image isn’t in your workspace.</h1><p>Saved previews are available in the browser where you saved them.</p><Link className="studio-button studio-button-primary" href="/studio/gallery">Back to my images</Link></div>;
  if (image.category === "NSFW" && !workspace.settings.showAdult) return <div className="studio-empty"><StudioIcon name="image" size={32} /><p className="studio-eyebrow">ADULT CONTENT · 18+</p><h1>An adult image preview.</h1><p>You can reveal adult examples in this workspace.</p><button type="button" className="studio-button studio-button-primary" onClick={() => updateWorkspace(current => ({ ...current, settings: { ...current.settings, showAdult: true } }))}>Show adult example</button><Link className="studio-text-link" href="/studio/gallery">Back to my images</Link></div>;
  const draft = saved?.draft;
  const prompt = draft?.prompt ?? image.promptIdea;
  function useSettings() {
    updateWorkspace(current => ({ ...current, draft: draft ? { ...defaultDraft, ...draft } : { ...defaultDraft, model: image!.model, prompt } }));
    router.push("/studio");
  }
  return <>
    <h1 className="studio-sr-only">Image preview</h1>
    <div className="studio-detail-top">
      <Link className="studio-text-link" href="/studio/gallery">← Back to my images</Link>
      <span className="studio-outline-tag">{saved ? "SAVED PREVIEW" : "STUDIO EXAMPLE"}</span>
    </div>
    <div className="studio-detail-layout">
      <div className="studio-detail-art">
        <Image src={image.src} alt={image.title} width={image.width} height={image.height} quality={85} sizes="(max-width: 760px) 90vw, 60vw" preload />
      </div>
      <section className="studio-detail-info" aria-label="Image details">
        <p className="studio-eyebrow">{(image.modelLabel ?? modelName(image.model))} · {image.category}</p>
        <div className="studio-detail-actions">
          <a className="studio-button studio-button-primary" href={image.src} download={`${image.id}.png`}><StudioIcon name="download" size={18} /> Download image</a>
        </div>
        <dl className="studio-image-properties">
          <div><dt>Model</dt><dd>{draft ? modelName(draft.model) : (image.modelLabel ?? modelName(image.model))}</dd></div>
          {draft && <div><dt>Requested aspect ratio</dt><dd>{draft.ratio}</dd></div>}
          {saved && <div><dt>Saved</dt><dd>{new Date(saved.createdAt).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</dd></div>}
        </dl>
        <button type="button" className="studio-button studio-button-full" onClick={useSettings}>Use in the studio <StudioIcon name="arrow" size={17} /></button>
        {saved && <button className="studio-text-button studio-delete-link" type="button" onClick={() => { updateWorkspace(current => ({ ...current, saved: current.saved.filter(item => item.id !== id), favorites: current.favorites.filter(item => item !== id) })); router.push("/studio/gallery"); }}><StudioIcon name="trash" size={15} /> Remove saved preview</button>}
      </section>
    </div>
    <section className="studio-related">
      <div><p className="studio-eyebrow">KEEP EXPLORING</p><h2>There’s always another <em>angle.</em></h2></div>
      <div className="studio-related-grid">
        {studioImages.filter(item => item.id !== image.id && item.category === "SFW").slice(0, 3).map(item => <Link key={item.id} href={`/studio/images/${item.id}`}><Image src={item.src} alt={item.title} width={item.width} height={item.height} sizes="(max-width: 760px) 28vw, 240px" quality={85} /><span>{item.title} ↗</span></Link>)}
      </div>
    </section>
  </>;
}
