"use client";

import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import { adminApi } from "@/lib/admin-api";
import { loraTitle } from "@/lib/catalog";
import { errorMessage } from "@/lib/api";
import type { AdminLora } from "@/lib/admin-types";
import { useApiData } from "@/lib/use-api-data";
import { AdminForm, AsyncState, ErrorLine, PageHead, Pagination } from "./admin-ui";
import { PresetPreviewUploader } from "@/components/studio/preset-preview-uploader";

const limit = 25;

export function LorasPage() {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [note, setNote] = useState("");

  const [selected, setSelected] = useState<AdminLora | null>(null);
  const createDialog = useRef<HTMLDialogElement>(null);
  const editDialog = useRef<HTMLDialogElement>(null);
  const deleteDialog = useRef<HTMLDialogElement>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [previews, setPreviews] = useState<string[]>([]);
  const [createNsfw, setCreateNsfw] = useState(false);
  const [createNote, setCreateNote] = useState("");
  const [createBusy, setCreateBusy] = useState(false);

  const [editDescription, setEditDescription] = useState("");
  const [editPreviews, setEditPreviews] = useState<string[]>([]);
  const [editNsfw, setEditNsfw] = useState(false);
  const [editNote, setEditNote] = useState("");
  const [editBusy, setEditBusy] = useState(false);

  const [deleteNote, setDeleteNote] = useState("");
  const [deleteBusy, setDeleteBusy] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => { setQuery(search.trim()); setOffset(0); }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const load = useCallback(() => adminApi.loras({ query, offset, limit }), [query, offset]);
  const data = useApiData(`admin:loras:${query}:${offset}`, load);
  const loras = data.data?.items ?? [];

  function openCreate() {
    setName("");
    setDescription("");
    setPreviews([]);
    setCreateNsfw(false);
    setCreateNote("");
    createDialog.current?.showModal();
  }

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setCreateNote("");
    if (previews.length > 20) {
      setCreateNote("At most 20 preview images are allowed.");
      return;
    }
    setCreateBusy(true);
    try {
      await adminApi.createLora({
        name: name.trim(),
        description: description.trim() || null,
        preview_urls: previews,
        is_nsfw: createNsfw,
      });
      createDialog.current?.close();
      setNote("LoRA added to the catalog.");
      data.reload();
    } catch (cause) {
      setCreateNote(errorMessage(cause));
    } finally {
      setCreateBusy(false);
    }
  }

  function openEdit(item: AdminLora) {
    setSelected(item);
    setEditDescription(item.description ?? "");
    setEditPreviews(item.preview_urls);
    setEditNsfw(item.is_nsfw);
    setEditNote("");
    editDialog.current?.showModal();
  }

  async function edit(event: React.FormEvent) {
    event.preventDefault();
    if (!selected) return;
    setEditNote("");
    if (editPreviews.length > 20) {
      setEditNote("At most 20 preview images are allowed.");
      return;
    }
    setEditBusy(true);
    try {
      await adminApi.updateLora(selected.id, {
        description: editDescription.trim() || null,
        preview_urls: editPreviews,
        is_nsfw: editNsfw,
      });
      editDialog.current?.close();
      setNote("LoRA updated.");
      data.reload();
    } catch (cause) {
      setEditNote(errorMessage(cause));
    } finally {
      setEditBusy(false);
    }
  }

  function openDelete(item: AdminLora) {
    setSelected(item);
    setDeleteNote("");
    deleteDialog.current?.showModal();
  }

  async function remove() {
    if (!selected) return;
    setDeleteNote("");
    setDeleteBusy(true);
    try {
      await adminApi.deleteLora(selected.id);
      deleteDialog.current?.close();
      setNote("LoRA deleted.");
      data.reload();
    } catch (cause) {
      setDeleteNote(errorMessage(cause));
    } finally {
      setDeleteBusy(false);
    }
  }

  return <>
    <PageHead
      eyebrow="Catalog"
      title="LoRAs"
      description="Style adapters shared by the generation models."
      actions={<button type="button" className="admin-button admin-button-primary admin-button-small" onClick={openCreate}>Add LoRA</button>}
    />
    <ErrorLine error={data.error} />
    {note && <div className="admin-note" role="status">{note}</div>}
    <div className="admin-panel">
      <div className="admin-panel-head">
        <div className="admin-toolbar" style={{ flex: 1 }}>
          <input className="admin-input admin-search" aria-label="Search LoRAs" placeholder="Search by file name or description…" value={search} onChange={event => setSearch(event.target.value)} />
        </div>
        <span className="admin-card-note">{data.data?.total ?? 0} LoRAs</span>
      </div>
      {data.loading && <AsyncState loading />}
      {data.data && loras.length > 0 && <div className="admin-table-wrap">
        <table className="admin-table">
          <thead><tr><th>LoRA</th><th>File</th><th>Previews</th><th>Used by</th><th /></tr></thead>
          <tbody>{loras.map(item => <tr key={item.id}>
            <td>
              <div className="admin-user">
                {item.preview_urls[0] && <LoraPreview key={item.preview_urls[0]} url={item.preview_urls[0]} size={38} />}
                <span>
                  <span className="admin-user-name">{loraTitle(item)}{item.is_nsfw && <span className="admin-badge admin-badge-warn" style={{ marginLeft: 8 }}>NSFW · 18+</span>}</span>
                  {item.description && item.description !== loraTitle(item) && <span className="admin-user-meta admin-lora-description">{item.description}</span>}
                </span>
              </div>
            </td>
            <td><code>{item.name}</code></td>
            <td>
              <div className="admin-lora-previews">
                {item.preview_urls.slice(0, 3).map(url => <LoraPreview key={url} url={url} size={28} />)}
                {item.preview_urls.length > 3 && <span className="admin-user-meta">+{item.preview_urls.length - 3}</span>}
                {!item.preview_urls.length && <span className="muted">None</span>}
              </div>
            </td>
            <td className="num">{item.workflow_count} model{item.workflow_count === 1 ? "" : "s"}</td>
            <td><div className="admin-row-actions">
              <button type="button" className="admin-button admin-button-small" onClick={() => openEdit(item)}>Edit</button>
              <button type="button" className="admin-button admin-button-small admin-button-danger" onClick={() => openDelete(item)}>Delete</button>
            </div></td>
          </tr>)}</tbody>
        </table>
      </div>}
      {data.data && !loras.length && <AsyncState loading={false} empty={<><h2>{query ? "No LoRAs found" : "No LoRAs yet"}</h2><p>{query ? "Try a different search." : "Add the first LoRA to attach it to a model."}</p></>} />}
      {data.data && <Pagination total={data.data.total} offset={offset} limit={limit} onChange={setOffset} />}
    </div>

    <dialog ref={createDialog} className="admin-dialog" aria-labelledby="lora-create-title">
      <h2 id="lora-create-title">New LoRA</h2>
      <p>The file name must match the LoRA file in the Runpod worker and cannot be changed later.</p>
      <AdminForm onSubmit={create} actions={<><button type="button" className="admin-button" onClick={() => createDialog.current?.close()}>Cancel</button>
          <button type="submit" className="admin-button admin-button-primary" disabled={createBusy}>{createBusy ? "Creating…" : "Create"}</button></>}>
        <label className="admin-field">File name
          <input className="admin-input" required maxLength={255} value={name} onChange={event => setName(event.target.value)} placeholder="style_v2.safetensors" autoComplete="off" />
        </label>
        <label className="admin-field">Description
          <textarea className="admin-textarea" rows={3} maxLength={4096} value={description} onChange={event => setDescription(event.target.value)} placeholder="What this LoRA does" />
        </label>
        <div className="admin-field">Preview images <span className="admin-card-note">Uploaded to MinIO, up to 20.</span>
          <PresetPreviewUploader urls={previews} onChange={setPreviews} upload={adminApi.uploadLoraPreview} />
        </div>
        <label className="admin-field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <input type="checkbox" checked={createNsfw} onChange={event => setCreateNsfw(event.target.checked)} /> NSFW (18+) — show an age label with this LoRA
        </label>
        {createNote && <div className="admin-error" role="alert">{createNote}</div>}
        
      </AdminForm>
    </dialog>

    <dialog ref={editDialog} className="admin-dialog" aria-labelledby="lora-edit-title">
      <h2 id="lora-edit-title">Edit LoRA</h2>
      <p><code>{selected?.name}</code> · the file name is immutable.</p>
      <AdminForm onSubmit={edit} actions={<><button type="button" className="admin-button" onClick={() => editDialog.current?.close()}>Cancel</button>
          <button type="submit" className="admin-button admin-button-primary" disabled={editBusy}>{editBusy ? "Saving…" : "Save changes"}</button></>}>
        <label className="admin-field">Description
          <textarea className="admin-textarea" rows={3} maxLength={4096} value={editDescription} onChange={event => setEditDescription(event.target.value)} />
        </label>
        <div className="admin-field">Preview images <span className="admin-card-note">Uploaded to MinIO, up to 20.</span>
          <PresetPreviewUploader urls={editPreviews} onChange={setEditPreviews} upload={adminApi.uploadLoraPreview} />
        </div>
        <label className="admin-field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <input type="checkbox" checked={editNsfw} onChange={event => setEditNsfw(event.target.checked)} /> NSFW (18+) — show an age label with this LoRA
        </label>
        {editNote && <div className="admin-error" role="alert">{editNote}</div>}
        
      </AdminForm>
    </dialog>

    <dialog ref={deleteDialog} className="admin-dialog" aria-labelledby="lora-delete-title">
      <h2 id="lora-delete-title">Delete LoRA?</h2>
      <p><strong>{selected?.name}</strong> will be removed from the catalog. LoRAs attached to a model cannot be deleted — detach them first.</p>
      {deleteNote && <div className="admin-error" role="alert" style={{ marginTop: 14 }}>{deleteNote}</div>}
      <div className="admin-dialog-actions">
        <button type="button" className="admin-button" onClick={() => deleteDialog.current?.close()}>Keep it</button>
        <button type="button" className="admin-button admin-button-danger" disabled={deleteBusy} onClick={() => void remove()}>{deleteBusy ? "Deleting…" : "Delete LoRA"}</button>
      </div>
    </dialog>
  </>;
}

function LoraPreview({ url, size }: { url: string; size: number }) {
  const [failed, setFailed] = useState(false);
  if (failed) return null;
  return <Image className="admin-lora-preview" src={url} alt="" width={size} height={size} style={{ width: size, height: size }} unoptimized onError={() => setFailed(true)} />;
}
