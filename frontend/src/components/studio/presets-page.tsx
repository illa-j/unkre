"use client";

import Image from "next/image";
import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import { api, errorMessage } from "@/lib/api";
import type { GenerationPreset } from "@/lib/api-types";
import { workflowTitle } from "@/lib/catalog";
import { Select } from "@/components/ui/select";
import { useApiData } from "@/lib/use-api-data";
import { useSession } from "../session-provider";
import { useCatalog } from "./catalog-provider";
import { SessionNotice } from "./session-notice";
import { StudioIcon } from "./studio-icon";
import { PresetPreviewUploader } from "./preset-preview-uploader";
import { LoraPreviewViewer, type LoraPreviewRequest } from "./lora-preview-viewer";

const formatDate = (value: string | null) => {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString();
};

export function PresetsPage() {
  const session = useSession();
  const catalog = useCatalog();
  const [tab, setTab] = useState<"mine" | "public" | "saved">("mine");
  const [sort, setSort] = useState<"newest" | "popular">("newest");
  const data = useApiData(session.user ? `${session.user.id}:preset-library` : null, api.presets);
  const [editTarget, setEditTarget] = useState<{ id: string; name: string; description: string; isPublic: boolean; previews: string[] } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<GenerationPreset | null>(null);
  const [note, setNote] = useState("");
  const [editNote, setEditNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<{ request: LoraPreviewRequest; session: number } | null>(null);
  const editDialog = useRef<HTMLDialogElement>(null);
  const deleteDialog = useRef<HTMLDialogElement>(null);
  const previewSession = useRef(0);
  const openPreview = (preset: GenerationPreset) => {
    previewSession.current += 1;
    setPreview({ request: { title: preset.name, urls: preset.preview_urls, kind: "preset" }, session: previewSession.current });
  };

  const modelLabel = (preset: GenerationPreset) => {
    const model = catalog.workflows.find(item => item.id === preset.workflow_id);
    return model ? workflowTitle(model) : "Model unavailable";
  };
  const owned = (preset: GenerationPreset) => preset.type === "user" && preset.user_id === session.user?.id;

  function openEdit(preset: GenerationPreset) {
    setEditTarget({ id: preset.id, name: preset.name, description: preset.description, isPublic: preset.is_public, previews: preset.preview_urls });
    setEditNote("");
    editDialog.current?.showModal();
  }

  async function saveEdit(event: FormEvent) {
    event.preventDefault();
    const name = editTarget?.name.trim();
    if (!editTarget || !name || busy) return;
    if (editTarget.previews.length > 20) { setEditNote("At most 20 preview images are allowed."); return; }
    setBusy(true); setEditNote("");
    try {
      const updated = await api.updatePreset(editTarget.id, {
        name,
        description: editTarget.description.trim(),
        is_public: editTarget.isPublic,
        preview_urls: editTarget.previews,
      });
      setNote(`Updated “${updated.name}”.`);
      editDialog.current?.close();
      data.reload();
    } catch (error) { setEditNote(errorMessage(error)); }
    finally { setBusy(false); }
  }

  async function toggleLike(preset: GenerationPreset) {
    if (busy) return;
    setBusy(true); setNote("");
    try {
      const liked = preset.is_liked ?? preset.is_favorite;
      const result = liked ? await api.unlikePreset(preset.id) : await api.likePreset(preset.id);
      setNote(result.is_liked ? `Liked “${preset.name}”.` : `Removed your like from “${preset.name}”.`);
      data.reload();
    } catch (error) { setNote(errorMessage(error)); }
    finally { setBusy(false); }
  }

  async function toggleSave(preset: GenerationPreset) {
    if (busy) return;
    setBusy(true); setNote("");
    try {
      const result = preset.is_saved ? await api.unsavePreset(preset.id) : await api.savePreset(preset.id);
      setNote(result.is_saved ? `Saved “${preset.name}”.` : `Removed “${preset.name}” from saved presets.`);
      data.reload();
    } catch (error) { setNote(errorMessage(error)); }
    finally { setBusy(false); }
  }

  async function togglePublic(preset: GenerationPreset) {
    if (busy) return;
    setBusy(true); setNote("");
    try {
      const updated = await api.updatePreset(preset.id, { is_public: !preset.is_public });
      setNote(updated.is_public ? `“${updated.name}” is now public.` : `“${updated.name}” is private again.`);
      data.reload();
    } catch (error) { setNote(errorMessage(error)); }
    finally { setBusy(false); }
  }

  async function duplicate(preset: GenerationPreset) {
    if (busy) return;
    setBusy(true); setNote("");
    try {
      const copy = await api.createPreset({
        name: `${preset.name} copy`.slice(0, 100),
        workflow_id: preset.workflow_id,
        prompt: preset.prompt,
        negative_prompt: preset.negative_prompt,
        loras_strength: Object.fromEntries(Object.entries(preset.loras_strength).map(([id, strength]) => [id, strength])),
        preview_urls: preset.preview_urls,
        is_public: false,
        ...(preset.seed == null ? {} : { seed: String(preset.seed) }),
      });
      setNote(`Duplicated as “${copy.name}”.`);
      data.reload();
    } catch (error) { setNote(errorMessage(error)); }
    finally { setBusy(false); }
  }

  function openDelete(preset: GenerationPreset) {
    setDeleteTarget(preset);
    setNote("");
    deleteDialog.current?.showModal();
  }

  async function remove() {
    if (!deleteTarget || busy) return;
    setBusy(true); setNote("");
    try {
      await api.deletePreset(deleteTarget.id);
      setNote(`“${deleteTarget.name}” deleted.`);
      deleteDialog.current?.close();
      data.reload();
    } catch (error) { setNote(errorMessage(error)); }
    finally { setBusy(false); }
  }

  const presets = data.data ?? [];
  const created = (preset: GenerationPreset) => preset.created_at ? Date.parse(preset.created_at) || 0 : 0;
  const sortPresets = (items: GenerationPreset[]) => [...items].sort((a, b) => sort === "popular" ? b.favorites_count - a.favorites_count || created(b) - created(a) : created(b) - created(a));
  const ownPresets = sortPresets(presets.filter(preset => owned(preset)));
  const publicPresets = sortPresets(presets.filter(preset => preset.is_public && !owned(preset)));
  const savedPresets = sortPresets(presets.filter(preset => preset.is_saved));
  const visiblePresets = tab === "mine" ? ownPresets : tab === "saved" ? savedPresets : publicPresets;

  function card(preset: GenerationPreset) {
    const isOwned = owned(preset);
    const hasPreviews = preset.preview_urls.length > 0;
    const prompt = preset.prompt.trim();
    const badges = <>
      <span className="studio-preset-model">{modelLabel(preset)}</span>
      {preset.type === "admin" && <span className="studio-preset-badge is-official">Official</span>}
      {preset.is_public && <span className="studio-preset-badge">Public</span>}
    </>;
    return <article className="studio-panel studio-preset-card" key={preset.id}>
      {hasPreviews && <button type="button" className="studio-preset-media" aria-label={`View all ${preset.preview_urls.length} previews for ${preset.name}`} onClick={() => openPreview(preset)}>
        <PresetPreviews urls={preset.preview_urls} name={preset.name} />
        <span className="studio-preset-badges">{badges}</span>
      </button>}
      <div className="studio-preset-body">
        {!hasPreviews && <span className="studio-preset-badges is-static">{badges}</span>}
        <h2 title={preset.name}>{preset.name}</h2>
        {preset.description && <p className="studio-preset-description" title={preset.description}>{preset.description}</p>}
        {prompt && <details className="studio-preset-prompt"><summary>Prompt</summary><p title={prompt}>{prompt}</p></details>}
        <dl className="studio-preset-meta">
          <div><dt>Seed</dt><dd>{preset.seed ?? "Random"}</dd></div>
          <div><dt>LoRAs</dt><dd>{Object.keys(preset.loras_strength).length}</dd></div>
          <div><dt>Likes</dt><dd>{preset.likes_count ?? preset.favorites_count}</dd></div>
          <div><dt>Created</dt><dd>{formatDate(preset.created_at)}</dd></div>
        </dl>
        <div className="studio-preset-card-actions">
          <div className="studio-preset-actions-primary">
            <Link className="studio-button studio-button-small studio-preset-use" href={`/studio?preset=${encodeURIComponent(preset.id)}`}>Use preset</Link>
            {isOwned ? <button type="button" className="studio-button studio-button-small" onClick={() => openEdit(preset)}>Edit</button> : <button type="button" className="studio-button studio-button-small" disabled={busy} onClick={() => void duplicate(preset)}>Duplicate</button>}
          </div>
          <div className="studio-preset-card-tools">
            {isOwned && <button type="button" className="studio-text-button studio-preset-visibility" disabled={busy} onClick={() => void togglePublic(preset)}>{preset.is_public ? "Make private" : "Make public"}</button>}
            {!isOwned && <button type="button" className="studio-button studio-button-small studio-favorite-button" aria-pressed={preset.is_liked ?? preset.is_favorite} aria-label={(preset.is_liked ?? preset.is_favorite) ? `Remove your like from ${preset.name}` : `Like ${preset.name}`} disabled={busy} onClick={() => void toggleLike(preset)}><StudioIcon name="heart" size={15} />{preset.likes_count ?? preset.favorites_count}</button>}
            {!isOwned && <button type="button" className={`studio-button studio-button-small studio-save-button${preset.is_saved ? " is-saved" : ""}`} aria-pressed={preset.is_saved} aria-label={preset.is_saved ? `Remove ${preset.name} from saved presets` : `Save ${preset.name}`} disabled={busy} onClick={() => void toggleSave(preset)}><StudioIcon name="bookmark" size={15} />{preset.is_saved ? "Saved" : "Save"}</button>}
            {isOwned && <button type="button" className="studio-icon-button" aria-label={`Delete ${preset.name}`} onClick={() => openDelete(preset)}><StudioIcon name="trash" size={16} /></button>}
          </div>
        </div>
      </div>
    </article>;
  }

  return <>
    <div className="studio-page-heading"><div><h1>Presets</h1><p>Save a model, prompts, seed and LoRAs — then start from it in one click.</p></div><Link className="studio-button studio-button-primary" href="/studio">Create an image <StudioIcon name="arrow" size={17} /></Link></div>
    <SessionNotice />
    {note && <p className="studio-live-note" role="status">{note}</p>}
    {data.loading && <p className="studio-live-note" role="status">Loading presets…</p>}
    {data.error && <div className="studio-api-notice" role="alert"><p>{data.error}</p><button type="button" className="studio-button" onClick={data.reload}>Try again</button></div>}
    {session.user && <div className="studio-tabs" aria-label="Preset collections"><button type="button" aria-pressed={tab === "mine"} onClick={() => setTab("mine")}>Your presets<span>{ownPresets.length}</span></button><button type="button" aria-pressed={tab === "public"} onClick={() => setTab("public")}>Public presets<span>{publicPresets.length}</span></button><button type="button" aria-pressed={tab === "saved"} onClick={() => setTab("saved")}>Saved<span>{savedPresets.length}</span></button></div>}
    {session.user && data.data && <div className="studio-preset-toolbar"><span>{visiblePresets.length} {visiblePresets.length === 1 ? "preset" : "presets"}</span><label className="studio-preset-sort"><span>Sort by</span><Select ariaLabel="Sort presets" value={sort} options={[{ value: "newest", label: "Date created" }, { value: "popular", label: "Most liked" }]} onChange={value => setSort(value as "newest" | "popular")} /></label></div>}
    {session.user && data.data && (tab === "saved"
      ? (savedPresets.length > 0
        ? <div className="studio-preset-grid">{savedPresets.map(card)}</div>
        : <div className="studio-empty"><StudioIcon name="bookmark" size={30} /><h2>No saved presets yet.</h2><p>Use the bookmark button on a public preset to keep it here.</p><button type="button" className="studio-button" onClick={() => setTab("public")}>Browse public presets</button></div>)
      : tab === "mine"
      ? (ownPresets.length > 0
        ? <div className="studio-preset-grid">{ownPresets.map(card)}</div>
        : <div className="studio-empty"><StudioIcon name="preset" size={30} /><h2>No presets yet.</h2><p>Configure a model, prompt and LoRAs in Studio, then save them as a preset.</p><Link className="studio-button studio-button-primary" href="/studio">Open Studio</Link></div>)
      : (publicPresets.length > 0
        ? <div className="studio-preset-grid">{publicPresets.map(card)}</div>
        : <div className="studio-empty"><StudioIcon name="preset" size={30} /><h2>No public presets yet.</h2><p>When other creators or the UNKRE team publish presets, they will appear here.</p></div>))}
    {!session.user && !session.loading && <div className="studio-empty"><StudioIcon name="preset" size={30} /><h2>Your presets live here.</h2><p>Sign in to save and reuse model, prompt, seed and LoRA combinations.</p></div>}

    <dialog ref={editDialog} className="studio-confirm-dialog" aria-labelledby="preset-edit-title" onClose={() => setEditTarget(null)}>
      <h2 id="preset-edit-title">Edit preset</h2>
      <p>Rename it, attach preview images and choose whether other creators can use it.</p>
      <form onSubmit={saveEdit}>
        <label className="studio-field"><span>Preset name</span><input autoFocus required maxLength={100} value={editTarget?.name ?? ""} onChange={event => setEditTarget(current => current ? { ...current, name: event.target.value } : current)} /></label>
        <label className="studio-field"><span>Description <small>Optional · 1,000 characters</small></span><textarea rows={3} maxLength={1000} value={editTarget?.description ?? ""} onChange={event => setEditTarget(current => current ? { ...current, description: event.target.value } : current)} placeholder="What makes this preset useful?" /></label>
        <div className="studio-field"><span>Preview images <small>Optional · up to 20</small></span><PresetPreviewUploader urls={editTarget?.previews ?? []} onChange={previews => setEditTarget(current => current ? { ...current, previews } : current)} upload={api.uploadPresetPreview} /></div>
        <label className="studio-check"><input type="checkbox" checked={editTarget?.isPublic ?? false} onChange={event => setEditTarget(current => current ? { ...current, isPublic: event.target.checked } : current)} /><span>Make this preset public<small>Other creators can use it.</small></span></label>
        {editNote && <p className="studio-live-note" role="alert">{editNote}</p>}
        <div className="studio-dialog-actions"><button type="button" className="studio-button" onClick={() => editDialog.current?.close()}>Cancel</button><button type="submit" className="studio-button studio-button-primary" disabled={busy}>{busy ? "Saving…" : "Save changes"}</button></div>
      </form>
    </dialog>

    <dialog ref={deleteDialog} className="studio-confirm-dialog" aria-labelledby="preset-delete-title" onClose={() => setDeleteTarget(null)}>
      <h2 id="preset-delete-title">Delete this preset?</h2>
      <p>“{deleteTarget?.name}” will be removed. Generations created from it stay in your library.</p>
      <div className="studio-dialog-actions"><button type="button" className="studio-button" onClick={() => deleteDialog.current?.close()}>Keep it</button><button type="button" className="studio-button studio-button-danger" disabled={busy} onClick={() => void remove()}>{busy ? "Deleting…" : "Delete preset"}</button></div>
    </dialog>

    <LoraPreviewViewer key={preview?.session ?? 0} preview={preview?.request ?? null} onClose={() => setPreview(null)} />
  </>;
}

function PresetPreviews({ urls, name }: { urls: string[]; name: string }) {
  const shown = urls.slice(0, 3);
  const extra = urls.length - shown.length;
  const layout = shown.length === 1 ? " is-single" : shown.length === 2 ? " is-double" : "";
  return <span className={`studio-preset-previews${layout}`}>
    {shown.map((url, index) => <PresetPreview key={`${url}:${index}`} url={url} name={name} index={index} extra={index === shown.length - 1 ? extra : 0} />)}
  </span>;
}

function PresetPreview({ url, name, index, extra }: { url: string; name: string; index: number; extra: number }) {
  const [failed, setFailed] = useState(false);
  return <span className="studio-preset-preview">
    {failed
      ? <span className="studio-preset-preview-fallback"><StudioIcon name="image" size={22} /></span>
      : <Image src={url} alt={`${name} preview ${index + 1}`} width={400} height={500} unoptimized onError={() => setFailed(true)} />}
    {extra > 0 && <span className="studio-preset-preview-more" title={`${extra} more ${extra === 1 ? "preview" : "previews"}`}>+{extra}</span>}
  </span>;
}
