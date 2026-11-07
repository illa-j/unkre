"use client";

import Image from "next/image";
import { useRef, useState } from "react";
import { adminApi } from "@/lib/admin-api";
import { workflowTitle } from "@/lib/catalog";
import { isValidLoraStrength, LORA_STRENGTH_MAX } from "@/lib/lora-strength";
import { errorMessage } from "@/lib/api";
import type { AdminLora, Workflow } from "@/lib/admin-types";
import { useApiData } from "@/lib/use-api-data";
import { AdminForm, AsyncState, Badge, ErrorLine, PageHead } from "./admin-ui";

const creditsMax = 2147483647;

export function ModelsPage() {
  const data = useApiData("admin:workflows", adminApi.workflows);
  const [note, setNote] = useState("");

  const [selected, setSelected] = useState<Workflow | null>(null);
  const createDialog = useRef<HTMLDialogElement>(null);
  const editDialog = useRef<HTMLDialogElement>(null);
  const deleteDialog = useRef<HTMLDialogElement>(null);
  const lorasDialog = useRef<HTMLDialogElement>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [credits, setCredits] = useState("1");
  const [active, setActive] = useState(true);
  const [createNote, setCreateNote] = useState("");
  const [createBusy, setCreateBusy] = useState(false);

  const [editDescription, setEditDescription] = useState("");
  const [editCredits, setEditCredits] = useState("1");
  const [editActive, setEditActive] = useState(true);
  const [editNote, setEditNote] = useState("");
  const [editBusy, setEditBusy] = useState(false);

  const [deleteNote, setDeleteNote] = useState("");
  const [deleteBusy, setDeleteBusy] = useState(false);

  const [loraList, setLoraList] = useState<AdminLora[]>([]);
  const [loraSelection, setLoraSelection] = useState<Record<string, string>>({});
  const [loraFilter, setLoraFilter] = useState("");
  const [loraLoading, setLoraLoading] = useState(false);
  const [loraNote, setLoraNote] = useState("");
  const [loraBusy, setLoraBusy] = useState(false);
  const loraRequest = useRef(0);

  function openCreate() {
    setName("");
    setDescription("");
    setCredits("1");
    setActive(true);
    setCreateNote("");
    createDialog.current?.showModal();
  }

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setCreateNote("");
    const value = Number(credits);
    if (!Number.isInteger(value) || value < 0) {
      setCreateNote("Credits must be a whole number of 0 or more.");
      return;
    }
    setCreateBusy(true);
    try {
      await adminApi.createWorkflow({
        name: name.trim(),
        description: description.trim() || null,
        generation_credits: value,
        is_active: active,
      });
      createDialog.current?.close();
      setNote("Model created. Attach LoRAs from the LoRAs column.");
      data.reload();
    } catch (cause) {
      setCreateNote(errorMessage(cause));
    } finally {
      setCreateBusy(false);
    }
  }

  function openEdit(item: Workflow) {
    setSelected(item);
    setEditDescription(item.description ?? "");
    setEditCredits(String(item.generation_credits));
    setEditActive(item.is_active !== false);
    setEditNote("");
    editDialog.current?.showModal();
  }

  async function edit(event: React.FormEvent) {
    event.preventDefault();
    if (!selected) return;
    setEditNote("");
    const value = Number(editCredits);
    if (!Number.isInteger(value) || value < 0) {
      setEditNote("Credits must be a whole number of 0 or more.");
      return;
    }
    setEditBusy(true);
    try {
      await adminApi.updateWorkflow(selected.id, {
        description: editDescription.trim() || null,
        generation_credits: value,
        is_active: editActive,
      });
      editDialog.current?.close();
      setNote("Model updated.");
      data.reload();
    } catch (cause) {
      setEditNote(errorMessage(cause));
    } finally {
      setEditBusy(false);
    }
  }

  function openDelete(item: Workflow) {
    setSelected(item);
    setDeleteNote("");
    deleteDialog.current?.showModal();
  }

  async function remove() {
    if (!selected) return;
    setDeleteNote("");
    setDeleteBusy(true);
    try {
      await adminApi.deleteWorkflow(selected.id);
      deleteDialog.current?.close();
      setNote("Model deleted.");
      data.reload();
    } catch (cause) {
      setDeleteNote(errorMessage(cause));
    } finally {
      setDeleteBusy(false);
    }
  }

  function openLoras(item: Workflow) {
    setSelected(item);
    const selection: Record<string, string> = {};
    for (const lora of item.loras) {
      const strength = item.recommended_strengths?.[lora.id];
      selection[lora.id] = strength === undefined ? "" : String(strength);
    }
    setLoraSelection(selection);
    setLoraFilter("");
    setLoraNote("");
    setLoraList([]);
    setLoraLoading(true);
    lorasDialog.current?.showModal();
    const request = ++loraRequest.current;
    adminApi.allLoras()
      .then(list => { if (loraRequest.current === request) setLoraList(list); })
      .catch(cause => { if (loraRequest.current === request) setLoraNote(errorMessage(cause)); })
      .finally(() => { if (loraRequest.current === request) setLoraLoading(false); });
  }

  function toggleLora(lora: AdminLora) {
    setLoraSelection(current => {
      const next = { ...current };
      if (lora.id in next) delete next[lora.id];
      else next[lora.id] = "";
      return next;
    });
  }

  function setStrength(loraId: string, value: string) {
    setLoraSelection(current => loraId in current ? { ...current, [loraId]: value } : current);
  }

  async function saveLoras() {
    if (!selected) return;
    setLoraNote("");
    const items: { lora_id: string; recommended_strength: number | null }[] = [];
    for (const [loraId, raw] of Object.entries(loraSelection)) {
      const text = raw.trim();
      const strength = text === "" ? null : Number(text);
      if (strength !== null && !isValidLoraStrength(strength)) {
        const lora = loraList.find(entry => entry.id === loraId);
        setLoraNote(`Strength for ${lora?.name ?? "this LoRA"} must be between 0 and 2.`);
        return;
      }
      items.push({ lora_id: loraId, recommended_strength: strength });
    }
    setLoraBusy(true);
    try {
      await adminApi.setWorkflowLoras(selected.id, items);
      lorasDialog.current?.close();
      setNote(`LoRA coverage for ${workflowTitle(selected)} updated.`);
      data.reload();
    } catch (cause) {
      setLoraNote(errorMessage(cause));
    } finally {
      setLoraBusy(false);
    }
  }

  const attached = Object.keys(loraSelection).length;
  const visibleLoras = loraList.filter(item => {
    const needle = loraFilter.trim().toLowerCase();
    return !needle || `${item.name} ${item.description ?? ""}`.toLowerCase().includes(needle);
  });

  return <>
    <PageHead
      eyebrow="Catalog"
      title="Models"
      description="Generation engines, credit price and LoRA coverage."
      actions={<button type="button" className="admin-button admin-button-primary admin-button-small" onClick={openCreate}>Add model</button>}
    />
    <ErrorLine error={data.error} />
    {note && <div className="admin-note" role="status">{note}</div>}
    {data.loading && <AsyncState loading />}
    {data.data && data.data.length > 0 && <div className="admin-panel">
      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead><tr><th>Model</th><th>Credits</th><th>LoRAs</th><th>State</th><th /></tr></thead>
          <tbody>{data.data.map(item => <tr key={item.id}>
            <td>
              <span className="admin-user-name">{workflowTitle(item)}</span>
              <span className="admin-user-meta"><code>{item.name}</code></span>
              {item.description && <span className="admin-user-meta" style={{ maxWidth: 420 }}>{item.description}</span>}
            </td>
            <td className="num">{item.generation_credits}</td>
            <td className="num">{item.loras.length}</td>
            <td><Badge value={item.is_active === false ? "inactive" : "active"} /></td>
            <td><div className="admin-row-actions">
              <button type="button" className="admin-button admin-button-small" onClick={() => openLoras(item)}>LoRAs</button>
              <button type="button" className="admin-button admin-button-small" onClick={() => openEdit(item)}>Edit</button>
              <button type="button" className="admin-button admin-button-small admin-button-danger" onClick={() => openDelete(item)}>Delete</button>
            </div></td>
          </tr>)}</tbody>
        </table>
      </div>
    </div>}
    {data.data && !data.data.length && <div className="admin-panel"><AsyncState loading={false} empty={<><h2>No models yet</h2><p>Add the first workflow to make it available in the studio.</p><button type="button" className="admin-button admin-button-primary" style={{ marginTop: 16 }} onClick={openCreate}>Add model</button></>} /></div>}

    <dialog ref={createDialog} className="admin-dialog" aria-labelledby="model-create-title">
      <h2 id="model-create-title">New model</h2>
      <p>The workflow key must match the graph key in the Runpod worker and cannot be changed later.</p>
      <AdminForm onSubmit={create} actions={<><button type="button" className="admin-button" onClick={() => createDialog.current?.close()}>Cancel</button>
          <button type="submit" className="admin-button admin-button-primary" disabled={createBusy}>{createBusy ? "Creating…" : "Create"}</button></>}>
        <label className="admin-field">Workflow key
          <input className="admin-input" required maxLength={255} value={name} onChange={event => setName(event.target.value)} placeholder="krea2_turbo_all_api" autoComplete="off" />
        </label>
        <label className="admin-field">Description
          <textarea className="admin-textarea" rows={3} maxLength={4096} value={description} onChange={event => setDescription(event.target.value)} placeholder="What this model is good at" />
        </label>
        <label className="admin-field">Credits per image
          <input className="admin-input" required type="number" min={0} max={creditsMax} step={1} value={credits} onChange={event => setCredits(event.target.value)} />
        </label>
        <label className="admin-field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <input type="checkbox" checked={active} onChange={event => setActive(event.target.checked)} /> Available in studio
        </label>
        {createNote && <div className="admin-error" role="alert">{createNote}</div>}
        
      </AdminForm>
    </dialog>

    <dialog ref={editDialog} className="admin-dialog" aria-labelledby="model-edit-title">
      <h2 id="model-edit-title">Edit model</h2>
      <p><code>{selected?.name}</code> · the workflow key is immutable.</p>
      <AdminForm onSubmit={edit} actions={<><button type="button" className="admin-button" onClick={() => editDialog.current?.close()}>Cancel</button>
          <button type="submit" className="admin-button admin-button-primary" disabled={editBusy}>{editBusy ? "Saving…" : "Save changes"}</button></>}>
        <label className="admin-field">Description
          <textarea className="admin-textarea" rows={3} maxLength={4096} value={editDescription} onChange={event => setEditDescription(event.target.value)} />
        </label>
        <label className="admin-field">Credits per image
          <input className="admin-input" required type="number" min={0} max={creditsMax} step={1} value={editCredits} onChange={event => setEditCredits(event.target.value)} />
        </label>
        <label className="admin-field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <input type="checkbox" checked={editActive} onChange={event => setEditActive(event.target.checked)} /> Available in studio
        </label>
        {editNote && <div className="admin-error" role="alert">{editNote}</div>}
        
      </AdminForm>
    </dialog>

    <dialog ref={deleteDialog} className="admin-dialog" aria-labelledby="model-delete-title">
      <h2 id="model-delete-title">Delete model?</h2>
      <p><strong>{selected ? workflowTitle(selected) : ""}</strong> will disappear from the studio. Models with generations or presets cannot be deleted — deactivate them instead.</p>
      {deleteNote && <div className="admin-error" role="alert" style={{ marginTop: 14 }}>{deleteNote}</div>}
      <div className="admin-dialog-actions">
        <button type="button" className="admin-button" onClick={() => deleteDialog.current?.close()}>Keep it</button>
        <button type="button" className="admin-button admin-button-danger" disabled={deleteBusy} onClick={() => void remove()}>{deleteBusy ? "Deleting…" : "Delete model"}</button>
      </div>
    </dialog>

    <dialog ref={lorasDialog} className="admin-dialog admin-dialog-wide" aria-labelledby="model-loras-title">
      <h2 id="model-loras-title">LoRA coverage</h2>
      <p>{selected ? workflowTitle(selected) : ""} · {attached} attached. Recommended strength is optional and shown as the default in the studio.</p>
      <div className="admin-toolbar" style={{ marginTop: 16 }}>
        <input className="admin-input admin-search" aria-label="Find a LoRA" placeholder="Find a LoRA by name…" value={loraFilter} onChange={event => setLoraFilter(event.target.value)} />
        <span className="admin-card-note">{loraList.length} in the catalog</span>
      </div>
      <div className="admin-lora-picker">
        {loraLoading && <p>Loading LoRAs…</p>}
        {!loraLoading && visibleLoras.map(item => {
          const isOn = item.id in loraSelection;
          return <div key={item.id} className={`admin-lora-option${isOn ? " is-on" : ""}`}>
            <input type="checkbox" checked={isOn} onChange={() => toggleLora(item)} aria-label={`Attach ${item.name}`} />
            <LoraThumb key={item.preview_urls[0]} url={item.preview_urls[0]} />
            <div className="admin-lora-option-main">
              <span className="admin-user-name">{item.name}{item.is_nsfw && <span className="admin-badge admin-badge-warn" style={{ marginLeft: 8 }}>18+</span>}</span>
              <span className="admin-user-meta">{item.description || "No description"} · used by {item.workflow_count} model{item.workflow_count === 1 ? "" : "s"}</span>
            </div>
            <input
              className="admin-input"
              style={{ width: 88 }}
              type="number"
              min={0}
              max={LORA_STRENGTH_MAX}
              step={0.01}
              placeholder="auto"
              aria-label={`Recommended strength for ${item.name}`}
              disabled={!isOn}
              value={isOn ? loraSelection[item.id] : ""}
              onChange={event => setStrength(item.id, event.target.value)}
            />
          </div>;
        })}
        {!loraLoading && !visibleLoras.length && <p>{loraList.length ? "No LoRAs match this search." : "The LoRA catalog is empty. Add LoRAs from the LoRAs section first."}</p>}
      </div>
      {loraNote && <div className="admin-error" role="alert" style={{ marginTop: 12 }}>{loraNote}</div>}
      <div className="admin-dialog-actions">
        <button type="button" className="admin-button" onClick={() => lorasDialog.current?.close()}>Cancel</button>
        <button type="button" className="admin-button admin-button-primary" disabled={loraBusy || loraLoading} onClick={() => void saveLoras()}>{loraBusy ? "Saving…" : "Save LoRAs"}</button>
      </div>
    </dialog>
  </>;
}

function LoraThumb({ url }: { url?: string }) {
  const [failed, setFailed] = useState(false);
  if (!url || failed) return null;
  return <Image className="admin-lora-preview" src={url} alt="" width={34} height={34} style={{ width: 34, height: 34 }} unoptimized onError={() => setFailed(true)} />;
}
