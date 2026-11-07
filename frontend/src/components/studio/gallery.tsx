"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { workflowTitle } from "@/lib/catalog";
import { listLocalImageIds, subscribeLibrary, syncGenerationImages } from "@/lib/local-images";
import { useApiData } from "@/lib/use-api-data";
import { studioImages } from "@/lib/studio";
import { useSession } from "../session-provider";
import { useCatalog } from "./catalog-provider";
import { activeGeneration, GenerationArt } from "./generation-art";
import type { Generation } from "@/lib/api-types";
import { ImageCard } from "./image-card";
import { SessionNotice } from "./session-notice";
import { StudioIcon } from "./studio-icon";

const hasActiveGenerations = (items: Generation[]) => items.some(activeGeneration);
const EMPTY_IDS: Set<string> = new Set();

export function Gallery() {
  const session = useSession();
  const catalog = useCatalog();
  const [tab, setTab] = useState("images");
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [storedIds, setStoredIds] = useState<Set<string>>(new Set());
  const [libraryRevision, setLibraryRevision] = useState(0);
  const load = useCallback(() => api.generations(offset), [offset]);
  const data = useApiData(session.user ? `${session.user.id}:${offset}` : null, load, 5000, hasActiveGenerations);
  const userId = session.user?.id;
  const stored = userId ? storedIds : EMPTY_IDS;
  const images = studioImages.filter(item => `${item.title} ${item.promptIdea}`.toLowerCase().includes(search.toLowerCase()));
  const generations = (data.data ?? []).filter(item => item.prompt.toLowerCase().includes(search.toLowerCase()));
  const lost = generations.filter(item => !activeGeneration(item) && !stored.has(item.id));
  const visible = tab === "lost" ? lost : generations.filter(item => activeGeneration(item) || stored.has(item.id));

  useEffect(() => subscribeLibrary(() => setLibraryRevision(value => value + 1)), []);

  useEffect(() => {
    if (!userId) return;
    let mounted = true;
    void listLocalImageIds(userId).then(ids => { if (mounted) setStoredIds(ids); });
    return () => { mounted = false; };
  }, [userId, libraryRevision]);

  useEffect(() => {
    if (!userId || !data.data || tab === "examples") return;
    void syncGenerationImages(userId, data.data);
  }, [userId, data.data, tab]);

  const tabs = [
    { id: "images", label: "My images" },
    { id: "lost", label: "Lost images" },
    { id: "examples", label: "Studio examples" },
  ];

  return <>
    <div className="studio-page-heading"><div><h1>My images</h1><p>Saved in this browser. New images stay reachable from any device for 24 hours.</p></div><Link href="/studio" className="studio-button studio-button-primary"><StudioIcon name="plus" size={18} /> Create an image</Link></div>
    <div className="studio-tabs" aria-label="Image collections">{tabs.map(item => <button key={item.id} type="button" aria-pressed={tab === item.id} onClick={() => { setTab(item.id); setSearch(""); }}>{item.label}</button>)}</div>
    <div className="studio-filterbar"><label className="studio-search"><StudioIcon name="search" size={18} /><input aria-label="Search images on this page" placeholder="Find an image on this page…" value={search} onChange={event => setSearch(event.target.value)} /></label></div>
    {tab !== "examples" ? <>
      <SessionNotice />
      {data.error && <div className="studio-api-notice" role="alert"><p>{data.error}</p><button type="button" className="studio-button" onClick={data.reload}>Try again</button></div>}
      {data.loading && <p className="studio-live-note" role="status">Loading your generations…</p>}
      {userId && data.data && <><p className="studio-results-note">{tab === "lost" ? `${lost.length} lost` : `${visible.length} generations`}<span>{!visible.length && data.loading ? "Opening your library…" : tab === "lost" ? "The 24-hour window passed and the file never reached this browser." : "Stored on this device."}</span></p>
        <div className="studio-generation-grid">{visible.map(item => <article className="studio-generation-card studio-panel" key={item.id}>{activeGeneration(item) || stored.has(item.id) ? <Link href={`/studio/images/${item.id}`} aria-label={`View generation: ${item.prompt}`}><GenerationArt generation={item} userId={userId} /></Link> : <GenerationArt generation={item} userId={userId} />}<Link href={`/studio/images/${item.id}`}><div className="studio-generation-summary"><span className="studio-tag">{item.status.replaceAll("_", " ")}</span><h2>{item.prompt}</h2><p>{workflowTitle(catalog.workflows.find(workflow => workflow.id === item.workflow_id) ?? { name: "Image generation" })} · {item.seed ? `Seed ${item.seed}` : "Random seed"} · {Object.keys(item.loras_strength).length} LoRA{item.uploaded_images ? ` · ${item.uploaded_images} reference` : ""}{item.credits_spent != null ? ` · ${item.credits_spent} credits` : ""}</p></div></Link></article>)}</div>
        {!visible.length && <div className="studio-empty"><StudioIcon name="gallery" size={30} /><h2>{tab === "lost" ? (search ? "No lost images match your search." : "Nothing is lost.") : (search ? "No images match your search." : "Your collection starts with an idea.")}</h2><p>{tab === "lost" ? "Images are kept in the browser that created them. This tab collects generations whose file did not reach this device within the 24-hour window." : "Every generation you open here is copied to this browser."}</p><Link className="studio-button studio-button-primary" href={tab === "lost" ? "/studio/gallery" : "/studio"}>{tab === "lost" ? "Back to my images" : "Create an image"}</Link></div>}
        <div className="studio-pagination"><button type="button" className="studio-button" disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 24))}>Previous</button><button type="button" className="studio-button" disabled={data.data.length < 24} onClick={() => setOffset(value => value + 24)}>Next</button><button type="button" className="studio-text-button" onClick={data.reload}>Refresh</button></div>
      </>}
    </> : <><p className="studio-results-note">{images.length} images<span>Model examples for inspiration.</span></p><div className="studio-image-grid">{images.map((image, index) => <ImageCard key={image.id} image={image} eager={index < 8} />)}</div>{!images.length && <div className="studio-empty"><h2>Nothing here just yet.</h2><button type="button" className="studio-button" onClick={() => { setTab("examples"); setSearch(""); }}>Browse examples</button></div>}</>}
  </>;
}
