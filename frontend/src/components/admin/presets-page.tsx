"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Select } from "@/components/ui/select";
import { adminApi } from "@/lib/admin-api";
import { errorMessage } from "@/lib/api";
import type { GenerationPreset } from "@/lib/api-types";
import { workflowTitle } from "@/lib/catalog";
import { isValidLoraStrength, LORA_STRENGTH_MAX } from "@/lib/lora-strength";
import { PresetPreviewUploader } from "@/components/studio/preset-preview-uploader";
import { useApiData } from "@/lib/use-api-data";
import { AdminForm, AsyncState, ErrorLine, PageHead, Pagination } from "./admin-ui";

const limit = 25;

export function AdminPresetsPage() {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [note, setNote] = useState("");
  const [selected, setSelected] = useState<GenerationPreset | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<GenerationPreset | null>(null);
  const [name, setName] = useState("");
  const [workflowId, setWorkflowId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [description, setDescription] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [seed, setSeed] = useState("");
  const [previews, setPreviews] = useState<string[]>([]);
  const [isPublic, setIsPublic] = useState(true);
  const [loras, setLoras] = useState<Record<string, string>>({});
  const [dialogNote, setDialogNote] = useState("");
  const [busy, setBusy] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const deleteDialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => { setQuery(search.trim()); setOffset(0); }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const load = useCallback(() => adminApi.presets({ query, offset, limit }), [query, offset]);
  const data = useApiData(`admin:presets:${query}:${offset}`, load);
  const workflows = useApiData("admin:workflows", adminApi.workflows);
  const workflow = workflows.data?.find(item => item.id === workflowId);
  const workflowLoras = workflow?.loras ?? [];

  function openCreate() {
    setSelected(null);
    setName("");
    setWorkflowId(workflows.data?.[0]?.id ?? "");
    setPrompt("");
    setDescription("");
    setNegativePrompt("");
    setSeed("");
    setPreviews([]);
    setIsPublic(true);
    setLoras({});
    setDialogNote("");
    dialog.current?.showModal();
  }

  function openEdit(preset: GenerationPreset) {
    setSelected(preset);
    setName(preset.name);
    setWorkflowId(preset.workflow_id);
    setPrompt(preset.prompt);
    setDescription(preset.description);
    setNegativePrompt(preset.negative_prompt);
    setSeed(preset.seed ?? "");
    setPreviews(preset.preview_urls);
    setIsPublic(preset.is_public);
    setLoras(Object.fromEntries(Object.entries(preset.loras_strength).map(([id, strength]) => [id, String(strength)])));
    setDialogNote("");
    dialog.current?.showModal();
  }

  function selectWorkflow(value: string) {
    setWorkflowId(value);
    setLoras({});
  }

  function toggleLora(id: string) {
    setLoras(current => {
      const next = { ...current };
      if (id in next) delete next[id];
      else next[id] = "0.7";
      return next;
    });
  }

  function setLoraStrength(id: string, value: string) {
    setLoras(current => id in current ? { ...current, [id]: value } : current);
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (previews.length > 20) { setDialogNote("At most 20 preview images are allowed."); return; }
    if (!workflowId) { setDialogNote("Choose a model first."); return; }
    if (seed && !/^\d{1,19}$/.test(seed)) { setDialogNote("Seed must be a whole number."); return; }
    const strengthValues: Record<string, number> = {};
    for (const [id, raw] of Object.entries(loras)) {
      if (!workflowLoras.some(lora => lora.id === id)) continue;
      const strength = Number(raw);
      if (!isValidLoraStrength(strength)) {
        setDialogNote("LoRA strength must be between 0 and 2.");
        return;
      }
      strengthValues[id] = strength;
    }
    setBusy(true); setDialogNote("");
    try {
      const payload = {
        name: name.trim(),
        workflow_id: workflowId,
        prompt,
        description: description.trim(),
        negative_prompt: negativePrompt,
        loras_strength: strengthValues,
        seed: seed ? seed : null,
        is_public: isPublic,
        preview_urls: previews,
      };
      if (selected) await adminApi.updatePreset(selected.id, payload);
      else await adminApi.createPreset(payload);
      dialog.current?.close();
      setNote(selected ? "Preset updated." : "Preset created.");
      data.reload();
    } catch (cause) {
      setDialogNote(errorMessage(cause));
    } finally { setBusy(false); }
  }

  async function remove() {
    if (!deleteTarget || busy) return;
    setBusy(true); setNote("");
    try {
      await adminApi.deletePreset(deleteTarget.id);
      deleteDialog.current?.close();
      setNote("Preset deleted.");
      data.reload();
    } catch (cause) {
      setNote(errorMessage(cause));
    } finally { setBusy(false); }
  }

  const presets = data.data?.items ?? [];
  const total = data.data?.total ?? 0;

  return <>
    <PageHead eyebrow="Content" title="Presets" description="Official and shared prompt presets for the studio." actions={<button type="button" className="admin-button admin-button-primary admin-button-small" onClick={openCreate}>Add preset</button>} />
    <ErrorLine error={data.error || workflows.error} />
    {note && <div className="admin-note" role="status">{note}</div>}
    <div className="admin-panel">
      <div className="admin-panel-head">
        <div className="admin-toolbar" style={{ flex: 1 }}>
          <input className="admin-input admin-search" aria-label="Search presets" placeholder="Search by name or prompt…" value={search} onChange={event => setSearch(event.target.value)} />
        </div>
        <span className="admin-card-note">{total} presets</span>
      </div>
      {data.loading && <AsyncState loading />}
      {data.data && presets.length > 0 && <div className="admin-table-wrap">
        <table className="admin-table">
          <thead><tr><th>Preset</th><th>Model</th><th>Prompt</th><th>Previews</th><th>Owner</th><th>Visibility</th><th /></tr></thead>
          <tbody>{presets.map(preset => <tr key={preset.id}>
            <td><span className="admin-user-name">{preset.name}{preset.type === "admin" && <span className="admin-badge admin-badge-warn" style={{ marginLeft: 8 }}>Official</span>}</span><span className="admin-user-meta">{preset.id.slice(0, 8)}</span></td>
            <td>{workflows.data?.find(item => item.id === preset.workflow_id) ? workflowTitle(workflows.data.find(item => item.id === preset.workflow_id)!) : <span className="muted">Unavailable</span>}</td>
            <td><span className="admin-prompt">{preset.prompt || "No prompt"}</span></td>
            <td className="num">{preset.preview_urls.length}</td>
            <td className="muted">{preset.type === "admin" ? "UNKRE team" : preset.user_id?.slice(0, 8) ?? "—"}</td>
            <td>{preset.is_public ? <span className="admin-badge admin-badge-ok">public</span> : <span className="admin-badge admin-badge-muted">private</span>}</td>
            <td><div className="admin-row-actions"><button type="button" className="admin-button admin-button-small" onClick={() => openEdit(preset)}>Edit</button><button type="button" className="admin-button admin-button-small admin-button-danger" onClick={() => { setDeleteTarget(preset); deleteDialog.current?.showModal(); }}>Delete</button></div></td>
          </tr>)}</tbody>
        </table>
      </div>}
      {data.data && !presets.length && <AsyncState loading={false} empty={<><h2>No presets found</h2><p>{query ? "Try a different search." : "Create the first official preset."}</p></>} />}
      {data.data && <Pagination total={total} offset={offset} limit={limit} onChange={setOffset} />}
    </div>

    <dialog ref={dialog} className="admin-dialog admin-dialog-wide" aria-labelledby="admin-preset-title">
      <h2 id="admin-preset-title">{selected ? "Edit preset" : "New official preset"}</h2>
      <p>{selected ? (selected.type === "admin" ? "This preset belongs to the UNKRE team." : "This preset belongs to a user.") : "Official presets are available to every studio user. You can publish them immediately or save them private."}</p>
      <AdminForm
        onSubmit={save}
        actions={<>
          <button type="button" className="admin-button" onClick={() => dialog.current?.close()}>Cancel</button>
          <button type="submit" className="admin-button admin-button-primary" disabled={busy}>{busy ? "Saving…" : selected ? "Save changes" : "Create preset"}</button>
        </>}
      >
        <label className="admin-field">Name
          <input className="admin-input" required maxLength={100} value={name} onChange={event => setName(event.target.value)} />
        </label>
        <label className="admin-field">Model
          <Select className="admin-select" ariaLabel="Model" value={workflowId} options={[{ value: "", label: workflows.loading ? "Loading models…" : "Choose a model", disabled: true }, ...(workflows.data ?? []).map(item => ({ value: item.id, label: workflowTitle(item) }))]} onChange={selectWorkflow} />
        </label>
        <label className="admin-field">Description <span className="admin-card-note">Optional, up to 1,000 characters.</span>
          <textarea className="admin-textarea" rows={3} maxLength={1000} value={description} onChange={event => setDescription(event.target.value)} />
        </label>
        <label className="admin-field">Prompt
          <textarea className="admin-textarea" rows={4} maxLength={8192} value={prompt} onChange={event => setPrompt(event.target.value)} />
        </label>
        <label className="admin-field">Negative prompt
          <textarea className="admin-textarea" rows={3} maxLength={8192} value={negativePrompt} onChange={event => setNegativePrompt(event.target.value)} />
        </label>
        <label className="admin-field">Seed <span className="admin-card-note">Leave empty to randomize.</span>
          <input className="admin-input" inputMode="numeric" maxLength={19} value={seed} onChange={event => setSeed(event.target.value.replace(/\D/g, ""))} />
        </label>
        <div className="admin-field">Preview images <span className="admin-card-note">Uploaded to MinIO, up to 20.</span>
          <PresetPreviewUploader urls={previews} onChange={setPreviews} upload={adminApi.uploadPresetPreview} />
        </div>
        <label className="admin-check">
          <input type="checkbox" checked={isPublic} onChange={event => setIsPublic(event.target.checked)} />
          <span>Public — visible to studio users</span>
        </label>
        {workflowLoras.length > 0 && <div className="admin-field">LoRAs
          <div className="admin-lora-picker">
            {workflowLoras.map(lora => {
              const enabled = lora.id in loras;
              return <div key={lora.id} className={`admin-lora-option${enabled ? " is-on" : ""}`}>
                <input type="checkbox" checked={enabled} onChange={() => toggleLora(lora.id)} aria-label={`Attach ${lora.name}`} />
                <div className="admin-lora-option-main"><span className="admin-user-name">{lora.name}{lora.is_nsfw && <span className="admin-badge admin-badge-warn" style={{ marginLeft: 6 }}>18+</span>}</span><span className="admin-user-meta">{lora.description || "No description"}</span></div>
                <input className="admin-input" style={{ width: 88 }} type="number" min={0} max={LORA_STRENGTH_MAX} step={0.01} aria-label={`Strength for ${lora.name}`} disabled={!enabled} value={enabled ? loras[lora.id] : ""} onChange={event => setLoraStrength(lora.id, event.target.value)} />
              </div>;
            })}
          </div>
        </div>}
        {dialogNote && <div className="admin-error" role="alert">{dialogNote}</div>}
      </AdminForm>
    </dialog>

    <dialog ref={deleteDialog} className="admin-dialog" aria-labelledby="admin-preset-delete-title">
      <h2 id="admin-preset-delete-title">Delete preset?</h2>
      <p><strong>{deleteTarget?.name}</strong> will be removed from the preset library. Generations created from it are not affected.</p>
      <div className="admin-dialog-actions">
        <button type="button" className="admin-button" onClick={() => deleteDialog.current?.close()}>Keep it</button>
        <button type="button" className="admin-button admin-button-danger" disabled={busy} onClick={() => void remove()}>{busy ? "Deleting…" : "Delete preset"}</button>
      </div>
    </dialog>
  </>;
}
