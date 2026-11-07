"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, errorMessage } from "@/lib/api";
import type { Generation, GenerationPreset } from "@/lib/api-types";
import { findLora, loraLabel } from "@/lib/lora";
import { LORA_STRENGTH_MAX } from "@/lib/lora-strength";
import { workflowTitle } from "@/lib/catalog";
import { useApiData } from "@/lib/use-api-data";
import { useSession } from "../session-provider";
import { useCatalog } from "./catalog-provider";
import { activeGeneration, GenerationArt } from "./generation-art";
import { MAX_REFERENCE_IMAGES, useGenerator } from "./generator-provider";
import { setReferenceConsent, useReferenceConsent } from "@/lib/reference-consent";
import { legal } from "@/lib/legal";
import { SessionNotice } from "./session-notice";
import { PreviewPlaceholder } from "./preview-placeholder";
import { PresetPreviewUploader } from "./preset-preview-uploader";
import { StudioIcon } from "./studio-icon";
import { Select } from "@/components/ui/select";

const generationLabels: Record<Generation["status"], string> = {
  pending: "Pending", queued: "In queue", processing: "Generating", completed: "Ready",
  failed: "Failed", cancelled: "Cancelled", timed_out: "Timed out",
};

export function Generator({ initialQuery = {} }: { initialQuery?: { model?: string; lora?: string; prompt?: string; seed?: string; preset?: string; reference?: boolean } }) {
  const session = useSession();
  const catalog = useCatalog();
  const presets = useApiData(session.user ? `${session.user.id}:presets` : null, api.presets);
  const {
    selection, prompt, negativePrompt, advancedOpen, seed, seedMode, references, busy, note,
    workflow, canUseReference, workflowLoras, selectedLoras, unselectedLoras, generation, trackedError,
    activePreset, presetStatus,
    setPrompt, setNegativePrompt, setAdvancedOpen, setSeed, setSeedMode, setNote,
    setActivePreset, setPresetStatus, applyDraft, selectModel, addLora, removeLora, setLoraStrength,
    upload, removeReference, generate, claimQuery,
  } = useGenerator();
  const referenceConsent = useReferenceConsent();
  const [presetName, setPresetName] = useState("");
  const [presetDescription, setPresetDescription] = useState("");
  const [presetPublic, setPresetPublic] = useState(false);
  const [presetPreviews, setPresetPreviews] = useState<string[]>([]);
  const [presetBusy, setPresetBusy] = useState(false);
  const [presetNote, setPresetNote] = useState("");
  const [loraToAdd, setLoraToAdd] = useState("");
  const generatorRef = useRef<HTMLDivElement>(null);
  const presetDialog = useRef<HTMLDialogElement>(null);
  const referenceInput = useRef<HTMLInputElement>(null);
  const referenceAddButton = useRef<HTMLButtonElement>(null);
  const hadReference = useRef(false);
  const requestedLoras = initialQuery.lora ? initialQuery.lora.split(",").map(value => value.trim()).filter(Boolean).slice(0, 100) : [];
  const loraNote = workflow && selectedLoras.length === 0 && requestedLoras.some(value => !findLora(workflow.loras, value))
    ? "This example’s LoRA is not available for the selected model. Choose an available LoRA or continue without one."
    : "";
  const activePresetOwned = Boolean(activePreset && activePreset.type === "user" && activePreset.user_id === session.user?.id);

  useEffect(() => {
    const container = generatorRef.current;
    if (!container) return;
    // Account for the heading and session notices above the preview, including
    // changes after sign-in, font loading and viewport resizing.
    const measure = () => {
      const offset = `${Math.ceil(container.getBoundingClientRect().top + window.scrollY)}px`;
      if (container.style.getPropertyValue("--studio-preview-offset") !== offset) {
        container.style.setProperty("--studio-preview-offset", offset);
      }
    };
    const observer = new ResizeObserver(measure);
    observer.observe(container);
    if (container.parentElement) {
      observer.observe(container.parentElement);
      for (const sibling of container.parentElement.children) {
        if (sibling === container) break;
        observer.observe(sibling);
      }
    }
    const topbar = container.closest(".studio-body")?.querySelector(".studio-topbar");
    if (topbar) observer.observe(topbar);
    window.addEventListener("resize", measure);
    measure();
    return () => { observer.disconnect(); window.removeEventListener("resize", measure); };
  }, []);

  const queryKey = JSON.stringify(initialQuery);
  useEffect(() => {
    if (!initialQuery.model && !initialQuery.prompt && !initialQuery.seed && !initialQuery.lora) return;
    if (!claimQuery(`form:${queryKey}`)) return;
    setActivePreset(null);
    setPresetStatus("");
    if (initialQuery.model) selectModel(initialQuery.model);
    if (initialQuery.prompt !== undefined) setPrompt(initialQuery.prompt);
    if (initialQuery.seed) { setSeed(initialQuery.seed); setSeedMode("fixed"); }
    if (initialQuery.lora) {
      const seen = new Set<string>();
      const next = initialQuery.lora.split(",").map(value => value.trim()).filter(Boolean).slice(0, 100).flatMap(id => {
        if (!id || seen.has(id.toLowerCase())) return [];
        seen.add(id.toLowerCase());
        return [{ id, strength: 0.7 }];
      });
      applyDraft({ loras: next });
    }
  }, [queryKey, initialQuery.model, initialQuery.prompt, initialQuery.seed, initialQuery.lora, claimQuery, selectModel, applyDraft, setActivePreset, setPresetStatus, setPrompt, setSeed, setSeedMode]);

  useEffect(() => {
    if (!initialQuery.reference || !canUseReference) return;
    queueMicrotask(() => {
      referenceAddButton.current?.scrollIntoView({ block: "center" });
      referenceAddButton.current?.focus();
    });
  }, [initialQuery.reference, canUseReference]);
  useEffect(() => {
    const count = references.length;
    if (!count && hadReference.current) referenceAddButton.current?.focus();
    hadReference.current = count > 0;
  }, [references]);

  function openPresetDialog() {
    if (!session.user) { session.openLogin(); return; }
    setPresetName((prompt.trim().slice(0, 100) || (workflow ? workflowTitle(workflow) : "") || "My preset").slice(0, 100));
    setPresetDescription("");
    setPresetPublic(false);
    setPresetPreviews([]);
    setPresetNote("");
    presetDialog.current?.showModal();
  }

  async function savePreset(event: FormEvent) {
    event.preventDefault();
    if (!session.user || !workflow || presetBusy) return;
    const name = presetName.trim();
    if (!name) { setPresetNote("Name your preset first."); return; }
    if (presetPreviews.length > 20) { setPresetNote("At most 20 preview images are allowed."); return; }
    setPresetBusy(true); setPresetNote("");
    try {
      const created = await api.createPreset({
        name,
        workflow_id: workflow.id,
        prompt,
        description: presetDescription.trim(),
        negative_prompt: negativePrompt,
        loras_strength: Object.fromEntries(selectedLoras.map(item => [item.lora.id, item.strength])),
        is_public: presetPublic,
        preview_urls: presetPreviews,
        ...(seedMode === "fixed" && seed ? { seed } : {}),
      });
      setActivePreset(created);
      setPresetStatus(`Preset “${created.name}” saved.`);
      presets.reload();
      presetDialog.current?.close();
    } catch (error) { setPresetNote(errorMessage(error)); }
    finally { setPresetBusy(false); }
  }

  useEffect(() => {
    if (!initialQuery.lora || !workflow || !claimQuery(`lora:${initialQuery.lora}`)) return;
    const recommended = workflow.recommended_strengths ?? {};
    const seen = new Set<string>();
    const next = initialQuery.lora.split(",").map(value => value.trim()).filter(Boolean).slice(0, 100).flatMap(id => {
      if (!id || seen.has(id.toLowerCase())) return [];
      seen.add(id.toLowerCase());
      return [{ id, strength: recommended[id] ?? 0.7 }];
    });
    applyDraft({ loras: next });
  }, [initialQuery.lora, workflow, claimQuery, applyDraft]);

  const applyPreset = useCallback((preset: GenerationPreset) => {
    applyDraft({
      activePreset: preset,
      presetStatus: "",
      selection: preset.workflow_id,
      prompt: preset.prompt,
      negativePrompt: preset.negative_prompt,
      advancedOpen: preset.negative_prompt.trim().length > 0,
      loras: Object.entries(preset.loras_strength).map(([id, strength]) => ({ id, strength })),
      seedMode: preset.seed == null ? "randomize" : "fixed",
      seed: preset.seed == null ? "0" : String(preset.seed),
    });
    setNote("");
  }, [applyDraft, setNote]);

  // Deep links from the preset library apply once, after the list arrives.
  useEffect(() => {
    if (!initialQuery.preset || !session.user || presets.loading || presets.error) return;
    const key = initialQuery.preset;
    const preset = presets.data?.find(item => item.id === key);
    if (preset) {
      if (!claimQuery(`preset:${key}`)) return;
      queueMicrotask(() => applyPreset(preset));
      return;
    }
    if (!claimQuery(`preset-fetch:${key}`)) return;
    let active = true;
    api.preset(key)
      .then(item => { if (active && claimQuery(`preset:${key}`)) applyPreset(item); })
      .catch(error => { if (active) setNote(errorMessage(error)); });
    return () => { active = false; };
  }, [applyPreset, initialQuery.preset, presets.data, presets.error, presets.loading, session.user, claimQuery, setNote]);

  async function updateActivePreset() {
    if (!activePreset || !workflow || presetBusy) return;
    setPresetBusy(true); setPresetStatus("");
    try {
      const updated = await api.updatePreset(activePreset.id, {
        workflow_id: workflow.id,
        prompt,
        negative_prompt: negativePrompt,
        loras_strength: Object.fromEntries(selectedLoras.map(item => [item.lora.id, item.strength])),
        seed: seedMode === "fixed" && seed ? seed : null,
      });
      setActivePreset(updated);
      setPresetStatus(`Preset “${updated.name}” updated.`);
      presets.reload();
    } catch (error) { setNote(errorMessage(error)); }
    finally { setPresetBusy(false); }
  }

  function changeReferenceConsent(checked: boolean) {
    setReferenceConsent(checked);
    if (!checked && references.length) setNote("Remove the reference images or confirm the consent statement before generating.");
    else if (checked) setNote("");
  }

  function submitShortcut(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  async function submitGeneration(event: FormEvent) {
    event.preventDefault();
    if (references.length > 0 && !referenceConsent) {
      setNote("Confirm that every person in your reference photos is an adult and that you have permission to use their image.");
      return;
    }
    const result = await generate();
    if (result && window.matchMedia("(max-width: 760px)").matches) {
      requestAnimationFrame(() => requestAnimationFrame(() => {
        generatorRef.current?.querySelector(".studio-canvas")?.scrollIntoView({ behavior: "smooth", block: "start" });
      }));
    }
  }

  return <>
    <div className="studio-page-heading">
      <div><h1>Create an image</h1><p>Describe your idea, choose a model, and make it yours.</p></div>
      <Link className="studio-text-link" href="/studio/gallery">My images <StudioIcon name="arrow" size={17} /></Link>
    </div>
    <div><SessionNotice /></div>
    <div ref={generatorRef} className="studio-generator">
      <form id="image-generator" className="studio-controls studio-panel" onSubmit={submitGeneration} aria-label="Image generator">
        <div className="studio-composer-primary">
          <div className="studio-panel-heading"><StudioIcon name="create" size={18} /><h2>Your idea</h2></div>
          <div className="studio-preset-bar">
            <span className="studio-eyebrow">PRESETS</span>
            <div className="studio-preset-controls">
              {presets.data?.length ? <Select ariaLabel="Load a preset" value="" options={[{ value: "", label: "Load a preset…" }, ...presets.data.map(preset => ({ value: preset.id, label: `${preset.name}${preset.type === "admin" ? " · Official" : preset.is_public && preset.user_id !== session.user?.id ? " · Public" : ""}` }))]} onChange={value => { const preset = presets.data?.find(item => item.id === value); if (preset) applyPreset(preset); }} /> : <small>{presets.loading ? "Loading presets…" : session.user ? "No saved presets yet." : "Sign in to save presets."}</small>}
              <button type="button" className="studio-button studio-button-small" onClick={openPresetDialog} disabled={busy || (Boolean(session.user) && !workflow)}>{session.user ? "Save" : "Sign in to save"}</button>
              {session.user && <Link className="studio-text-button" href="/studio/presets">Manage</Link>}
            </div>
            {presets.error && <p className="studio-field-note" role="alert">{presets.error} <button type="button" className="studio-text-button" onClick={presets.reload}>Retry</button></p>}
          </div>
          {activePreset && <div className="studio-preset-active"><span>{activePresetOwned ? "Loaded" : activePreset.type === "admin" ? "Using official preset" : "Using public preset"} <strong>{activePreset.name}</strong></span>{activePresetOwned && <button type="button" className="studio-button studio-button-small" disabled={presetBusy || busy || !workflow} onClick={() => void updateActivePreset()}>{presetBusy ? "Saving…" : "Update preset"}</button>}<button type="button" className="studio-text-button" onClick={() => { setActivePreset(null); setPresetStatus(""); }}>Detach</button></div>}
          {presetStatus && <p className="studio-field-note" role="status">{presetStatus}</p>}
          <label className="studio-field studio-prompt">
            <span>Positive prompt <small>{prompt.length.toLocaleString("en-US")} / 8,192</small></span>
            <textarea rows={4} maxLength={8192} required value={prompt} onChange={event => setPrompt(event.target.value)} onKeyDown={submitShortcut} placeholder="Describe your subject, style, lighting, and mood…" />
          </label>
          <details className="studio-advanced" open={advancedOpen} onToggle={event => setAdvancedOpen(event.currentTarget.open)}>
            <summary><span>Negative prompt</span><small>{negativePrompt.trim() ? `${negativePrompt.length.toLocaleString("en-US")} / 8,192` : "Optional — what to avoid"}</small></summary>
            <label className="studio-field studio-prompt">
              <span className="studio-sr-only">Negative prompt</span>
              <textarea rows={3} maxLength={8192} value={negativePrompt} onChange={event => setNegativePrompt(event.target.value)} onKeyDown={submitShortcut} placeholder="Describe what to avoid: blur, extra fingers, text, bad anatomy…" />
            </label>
          </details>
        </div>
        <section id="generator-settings" className="studio-model-settings" aria-labelledby="image-settings-title">
          <div className="studio-settings-heading"><h2 id="image-settings-title">Image settings</h2></div>
          <div className="studio-field"><span>Model</span><Select ariaLabel="Model" value={workflow?.id ?? ""} disabled={catalog.loading || !catalog.workflows.length || busy} options={[{ value: "", label: catalog.loading ? "Loading models…" : "Choose a model", disabled: true }, ...catalog.workflows.map(item => ({ value: item.id, label: workflowTitle(item) }))]} onChange={value => { selectModel(value); setLoraToAdd(""); }} /></div>
          {selection && !workflow && !catalog.loading && catalog.workflows.length > 0 && <p className="studio-field-note" role="status">The example’s model is not currently available. Choose an available model to continue with your prompt.</p>}
          {workflow?.description && <p className="studio-field-note">{workflow.description}</p>}
          {workflow && <p className="studio-field-note">{workflow.generation_credits === 0 ? "Free generation." : `${workflow.generation_credits} credit${workflow.generation_credits === 1 ? "" : "s"} per generation.`}</p>}
          {session.user && !catalog.loading && !catalog.workflows.length && <div className="studio-field-note" role={catalog.error ? "alert" : "status"}><p>{catalog.error ?? "No models are available yet. Please check back soon."}</p><button type="button" className="studio-text-button" onClick={catalog.reload}>Reload models</button></div>}
          <div className="studio-field"><span>Reference images <small>Optional · up to {MAX_REFERENCE_IMAGES}</small></span>
            {canUseReference && <label className="studio-reference-consent">
              <input type="checkbox" checked={referenceConsent} onChange={event => changeReferenceConsent(event.target.checked)} />
              <span>I confirm every person in these photos is {legal.minimumAge} or older and that I have permission to use their image. <Link href="/acceptable-use">Content rules</Link>.</span>
            </label>}
            <input ref={referenceInput} className="studio-file-input" type="file" tabIndex={-1} multiple aria-label="Upload reference images" accept="image/png,image/jpeg,image/webp" disabled={!canUseReference || busy || !referenceConsent} onChange={upload} />
            {canUseReference && references.length > 0 && <ul className="studio-reference-list">{references.map((reference, index) => <li className="studio-reference-tile" key={reference.id} title={reference.file.name}><Image src={reference.url} width={120} height={160} alt={`Reference ${index + 1}: ${reference.file.name}`} unoptimized /><span className="studio-reference-index">{index + 1}</span><button type="button" className="studio-reference-remove" aria-label={`Remove reference ${index + 1}`} disabled={busy} onClick={() => removeReference(reference.id)}><StudioIcon name="close" size={14} /></button></li>)}</ul>}
            {canUseReference && references.length < MAX_REFERENCE_IMAGES && <button type="button" ref={referenceAddButton} className="studio-upload" disabled={!canUseReference || busy || !referenceConsent} aria-describedby={!canUseReference ? "reference-model-note" : undefined} onClick={() => referenceInput.current?.click()}><StudioIcon name="upload" size={20} /><span>{references.length ? "Add another reference image" : "Add reference images"}<small>PNG, JPG or WebP · 10 MB each · up to 30 MB total · {MAX_REFERENCE_IMAGES - references.length} left</small></span><StudioIcon name="plus" size={16} /></button>}
            {!canUseReference && <p id="reference-model-note" className="studio-field-note">Select Qwen Image 2.1 to upload reference photos.</p>}
            {canUseReference && !referenceConsent && <p className="studio-field-note">Confirm the consent statement above to enable reference uploads.</p>}
          </div>
          <div className="studio-field">
            <span>{selectedLoras.length ? `LoRA (${selectedLoras.length})` : "LoRA"} <Link href="/studio/loras">Browse LoRAs ↗</Link></span>
            {selectedLoras.length > 0 && <ul className="studio-lora-list">
              {selectedLoras.map(({ lora, strength }) => <li key={lora.id} className="studio-lora-entry">
                <div className="studio-lora-entry-head">
                  <strong>{loraLabel(lora)}{lora.is_nsfw && <span className="studio-lora-age">18+</span>}</strong>
                  <button type="button" className="studio-icon-button" aria-label={`Remove ${loraLabel(lora)}`} disabled={busy} onClick={() => removeLora(lora.id)}><StudioIcon name="close" size={16} /></button>
                </div>
                <label className="studio-lora-strength">
                  <span>Strength <small>{strength.toFixed(2)}{workflow?.recommended_strengths?.[lora.id] != null ? ` · recommended ${workflow.recommended_strengths[lora.id].toFixed(2)}` : ""}</small></span>
                  <input type="range" min="0" max={LORA_STRENGTH_MAX} step="0.01" value={strength} disabled={busy} onChange={event => setLoraStrength(lora.id, Number(event.target.value))} />
                </label>
              </li>)}
            </ul>}
            {workflow && unselectedLoras.length > 0 && <div className="studio-lora-add"><Select ariaLabel="Add a LoRA" value={loraToAdd} disabled={busy} options={[{ value: "", label: "Add a LoRA…" }, ...unselectedLoras.map(lora => ({ value: lora.id, label: `${loraLabel(lora)}${lora.is_nsfw ? " · 18+" : ""}` }))]} onChange={addLora} /></div>}
            {workflow && !workflowLoras.length && <p className="studio-field-note">No LoRAs are configured for this model.</p>}
            {!workflow && <p className="studio-field-note">Choose a model to add LoRAs.</p>}
            {loraNote && <p className="studio-field-note" role="status">{loraNote}</p>}
          </div>
          <div className="studio-field">
            <span id="seed-mode-label">Seed</span>
            <div className="studio-seed-modes" role="group" aria-labelledby="seed-mode-label">
              <button type="button" aria-pressed={seedMode === "fixed"} disabled={busy} onClick={() => setSeedMode("fixed")}>Fixed</button>
              <button type="button" aria-pressed={seedMode === "randomize"} disabled={busy} onClick={() => setSeedMode("randomize")}>Randomize</button>
            </div>
            <input aria-label="Fixed seed" aria-describedby="seed-mode-note" inputMode="numeric" pattern="[0-9]*" maxLength={19} required={seedMode === "fixed"} disabled={seedMode === "randomize" || busy} placeholder={seedMode === "randomize" ? "New seed for every image" : "Enter a seed"} value={seedMode === "fixed" ? seed : ""} onChange={event => setSeed(event.target.value.replace(/\D/g, ""))} />
            <p id="seed-mode-note" className="studio-field-note">{seedMode === "fixed" ? "Use the same seed for each generation." : "A new random seed is chosen for each generation."}</p>
          </div>
          <p className="studio-field-note">Image dimensions are set by your model.</p>
        </section>
        <div className="studio-generate-action">
          <div className="studio-generate-meta">
            <span>{workflow ? workflowTitle(workflow) : "Choose a model"}</span>
            {selectedLoras.length > 0 && <span>{selectedLoras.length} LoRA</span>}
            <span>{seedMode === "randomize" ? "Random seed" : "Fixed seed"}</span>
            {workflow && <span>{workflow.generation_credits === 0 ? "Free" : `${workflow.generation_credits} credit${workflow.generation_credits === 1 ? "" : "s"}`}</span>}
            <small>⌘↵ to generate</small>
          </div>
          <button type="submit" className="studio-button studio-button-primary" disabled={busy || session.loading || Boolean(session.user && !workflow) || (references.length > 0 && !referenceConsent)}><StudioIcon name="create" size={18} />{busy ? "Submitting…" : session.user ? "Generate image" : "Sign in to create"}<StudioIcon name="arrow" size={18} /></button>
          {(note || trackedError) && <p className="studio-generator-note" role="alert">{note || trackedError}</p>}
        </div>
      </form>
      <div className="studio-canvas-column"><section className="studio-canvas studio-panel" aria-labelledby="canvas-title">
        <header><div><StudioIcon name="image" size={18} /><h2 id="canvas-title">Preview</h2></div><span className="studio-canvas-status" data-status={busy ? "pending" : generation?.status ?? "idle"} role="status">{busy ? "Submitting" : generation ? generationLabels[generation.status] : "Ready to create"}</span></header>
        {busy ? <PreviewPlaceholder state="submitting" /> : generation ? <GenerationArt animated generation={generation} userId={session.user?.id} download /> : <PreviewPlaceholder />}
        <footer><p>{busy ? "Sending your generation request… Usually under a minute, up to 5 minutes at peak times." : generation ? activeGeneration(generation) ? "Your image will appear here. Usually under a minute; up to 5 minutes at peak times." : generation.status === "completed" ? "Your image is ready." : generation.error || "Try adjusting your prompt and generate again." : "Describe your idea and generate. Your image will appear here."}</p>{generation?.credits_spent != null && <span>{generation.credits_spent} credits used</span>}</footer>
      </section>
      </div>
    </div>
    <dialog ref={presetDialog} className="studio-confirm-dialog studio-preset-dialog" aria-labelledby="preset-dialog-title">
      <h2 id="preset-dialog-title">Save a preset</h2>
      <p>Keep the current model, prompts, seed and LoRA strengths for a one-click start later.</p>
      <form onSubmit={savePreset}>
        <label className="studio-field"><span>Preset name</span><input autoFocus maxLength={100} value={presetName} onChange={event => setPresetName(event.target.value)} placeholder="My portrait preset" required /></label>
        <label className="studio-field"><span>Description <small>Optional · 1,000 characters</small></span><textarea rows={3} maxLength={1000} value={presetDescription} onChange={event => setPresetDescription(event.target.value)} placeholder="What makes this preset useful? Lighting, mood, character notes…" /></label>
        <div className="studio-field"><span>Preview images <small>Optional · up to 20</small></span><PresetPreviewUploader urls={presetPreviews} onChange={setPresetPreviews} upload={api.uploadPresetPreview} /></div>
        <label className="studio-check"><input type="checkbox" checked={presetPublic} onChange={event => setPresetPublic(event.target.checked)} /><span>Make this preset public<small>Other creators can use it.</small></span></label>
        <div className="studio-dialog-actions"><button type="button" className="studio-button" onClick={() => presetDialog.current?.close()}>Cancel</button><button type="submit" className="studio-button studio-button-primary" disabled={presetBusy}>{presetBusy ? "Saving…" : "Save preset"}</button></div>
      </form>
      <p className="studio-field-note"><Link className="studio-text-button" href="/studio/presets">Manage all presets <StudioIcon name="arrow" size={15} /></Link></p>
      {presetNote && <p className="studio-live-note" role="alert">{presetNote}</p>}
    </dialog>
  </>;
}
