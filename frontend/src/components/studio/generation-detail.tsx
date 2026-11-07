"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { deleteLocalImage } from "@/lib/local-images";
import { workflowTitle } from "@/lib/catalog";
import { loraLabel } from "@/lib/lora";
import { useApiData } from "@/lib/use-api-data";
import { useSession } from "../session-provider";
import { useCatalog } from "./catalog-provider";
import { activeGeneration, GenerationArt } from "./generation-art";
import { SessionNotice } from "./session-notice";

export function GenerationDetail({ id }: { id: string }) {
  const session = useSession();
  const catalog = useCatalog();
  const router = useRouter();
  const load = useCallback(() => api.generation(id), [id]);
  const data = useApiData(session.user ? `${session.user.id}:${id}` : null, load, 5000, activeGeneration);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const generation = data.data;
  const workflow = catalog.workflows.find(item => item.id === generation?.workflow_id);
  const loras = generation
    ? Object.entries(generation.loras_strength).map(([loraId, strength]) => ({
      id: loraId,
      lora: workflow?.loras.find(item => item.id === loraId),
      strength,
    }))
    : [];
  const loraParam = loras.map(item => item.id).join(",");

  async function remove() {
    setBusy(true); setNote("");
    try { await api.deleteGeneration(id); if (session.user) await deleteLocalImage(session.user.id, id); router.replace("/studio/gallery"); }
    catch (error) { setNote(errorMessage(error)); }
    finally { setBusy(false); dialog.current?.close(); }
  }

  return <>
    <div className="studio-detail-top"><Link className="studio-text-link" href="/studio/gallery">← Back to my images</Link><span className="studio-outline-tag">YOUR GENERATION</span></div>
    <SessionNotice />
    {data.loading && <p role="status" className="studio-live-note">Opening your generation…</p>}
    {data.error && <div className="studio-api-notice" role="alert"><p>{data.error}</p><button type="button" className="studio-button" onClick={data.reload}>Try again</button></div>}
    {generation && <div className="studio-detail-layout">
      <div className="studio-detail-art"><GenerationArt generation={generation} userId={session.user?.id} download /></div>
      <section className="studio-detail-info">
        <p className="studio-eyebrow">{workflow ? workflowTitle(workflow) : "YOUR IMAGE"}</p>
        <span className="studio-tag">{generation.status.replaceAll("_", " ")}</span>
        <div className="studio-detail-prompt"><h2>Your prompt</h2><p>{generation.prompt || "None"}</p></div>
        <div className="studio-detail-prompt"><h2>Negative prompt</h2><p>{generation.negative_prompt || "None"}</p></div>
        <h2 className="studio-detail-settings-title">All settings</h2>
        <dl className="studio-image-properties">
          <div><dt>Model</dt><dd>{workflow ? workflowTitle(workflow) : "Image generation"}</dd></div>
          <div><dt>Status</dt><dd>{generation.status.replaceAll("_", " ")}</dd></div>
          <div><dt>Seed</dt><dd>{generation.seed ?? "Random"}</dd></div>
          <div><dt>Reference images</dt><dd>{generation.uploaded_images || "None"}</dd></div>
          <div><dt>LoRAs</dt><dd>{loras.length || "None"}</dd></div>
          <div><dt>Created</dt><dd>{new Date(generation.created_at).toLocaleString()}</dd></div>
          <div><dt>Credits spent</dt><dd>{generation.credits_spent ?? "—"}</dd></div>
          {loras.map(item => <div key={item.id}><dt>{item.lora ? loraLabel(item.lora) : "LoRA"}</dt><dd>{item.strength.toFixed(2)}</dd></div>)}
        </dl>
        {generation.error && <p className="studio-live-note" role="alert">{generation.error}</p>}
        <div className="studio-detail-actions">
          <Link className="studio-button studio-button-primary" href={`/studio?model=${generation.workflow_id}&prompt=${encodeURIComponent(generation.prompt)}&seed=${generation.seed ?? ""}${loraParam ? `&lora=${encodeURIComponent(loraParam)}` : ""}`}>Use this idea</Link>
          <button type="button" className="studio-button studio-button-danger" disabled={busy} onClick={() => dialog.current?.showModal()}>Delete generation</button>
        </div>
      </section>
    </div>}
    <p className="studio-live-note" role="status">{note}</p>
    <dialog ref={dialog} className="studio-confirm-dialog" aria-labelledby="delete-generation-title"><h2 id="delete-generation-title">Delete this generation?</h2><p>An image still being generated will be cancelled first. The copy saved in this browser is removed too, so download it first if you want to keep it.</p><div><button type="button" className="studio-button" disabled={busy} onClick={() => dialog.current?.close()}>Keep it</button><button type="button" className="studio-button studio-button-danger" disabled={busy} onClick={() => void remove()}>{busy ? "Deleting…" : "Delete generation"}</button></div></dialog>
  </>;
}
