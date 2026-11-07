"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ChangeEvent, type ReactNode } from "react";
import { api, errorMessage } from "@/lib/api";
import type { Generation, GenerationPreset, Lora, Workflow } from "@/lib/api-types";
import { trackEvent } from "@/lib/analytics";
import { workflowTitle } from "@/lib/catalog";
import { resolveCreationModel, supportsReferenceImages } from "@/lib/creation-intent";
import { findLora } from "@/lib/lora";
import { clampLoraStrength } from "@/lib/lora-strength";
import { hasReferenceConsent } from "@/lib/reference-consent";
import type { StudioLora } from "@/lib/studio";
import { useApiData } from "@/lib/use-api-data";
import { updateWorkspace, useWorkspace } from "@/lib/workspace";
import { useSession } from "../session-provider";
import { useCatalog } from "./catalog-provider";
import { activeGeneration } from "./generation-art";

export const MAX_REFERENCE_IMAGES = 16;
// nginx accepts 50 MB per API request; base64 inflates the payload by ~33%.
const MAX_REFERENCE_TOTAL_BYTES = 30 * 1024 * 1024;

export type ReferenceImage = { id: string; url: string; file: File };

type GeneratorDraft = {
  selection?: string;
  prompt?: string;
  negativePrompt?: string;
  advancedOpen?: boolean;
  loras?: StudioLora[];
  seed?: string;
  seedMode?: "fixed" | "randomize";
  activePreset?: GenerationPreset | null;
  presetStatus?: string;
};

type GeneratorContextValue = {
  selection: string;
  prompt: string;
  negativePrompt: string;
  advancedOpen: boolean;
  loras: StudioLora[];
  seed: string;
  seedMode: "fixed" | "randomize";
  references: ReferenceImage[];
  busy: boolean;
  note: string;
  workflow: Workflow | undefined;
  canUseReference: boolean;
  workflowLoras: Lora[];
  selectedLoras: { lora: Lora; strength: number }[];
  unselectedLoras: Lora[];
  generation: Generation | null;
  finished: boolean;
  trackedError?: string;
  activePreset: GenerationPreset | null;
  presetStatus: string;
  setPrompt: (value: string) => void;
  setNegativePrompt: (value: string) => void;
  setAdvancedOpen: (value: boolean) => void;
  setSeed: (value: string) => void;
  setSeedMode: (value: "fixed" | "randomize") => void;
  setNote: (value: string) => void;
  setActivePreset: (value: GenerationPreset | null) => void;
  setPresetStatus: (value: string) => void;
  applyDraft: (values: GeneratorDraft) => void;
  selectModel: (value: string) => void;
  addLora: (id: string) => void;
  removeLora: (id: string) => void;
  setLoraStrength: (id: string, value: number) => void;
  upload: (event: ChangeEvent<HTMLInputElement>) => void;
  removeReference: (id: string) => void;
  generate: () => Promise<Generation | null>;
  claimQuery: (key: string) => boolean;
};

const GeneratorContext = createContext<GeneratorContextValue | null>(null);

export function GeneratorProvider({ children }: { children: ReactNode }) {
  const workspace = useWorkspace();
  const session = useSession();
  const catalog = useCatalog();
  const [selection, setSelection] = useState("");
  const [prompt, setPrompt] = useState(workspace.draft.prompt);
  const [negativePrompt, setNegativePrompt] = useState(workspace.draft.negativePrompt);
  const [advancedOpen, setAdvancedOpen] = useState(() => workspace.draft.negativePrompt.trim().length > 0);
  const [loras, setLoras] = useState<StudioLora[]>(() => {
    const seen = new Set<string>();
    return workspace.draft.loras.flatMap(item => {
      const id = item.id.trim();
      if (!id || seen.has(id.toLowerCase())) return [];
      seen.add(id.toLowerCase());
      return [{ id, strength: clampLoraStrength(item.strength) }];
    });
  });
  const [seed, setSeed] = useState("0");
  const [seedMode, setSeedMode] = useState<"fixed" | "randomize">("randomize");
  const [references, setReferences] = useState<ReferenceImage[]>([]);
  const [submitted, setSubmitted] = useState<Generation | null>(null);
  const [submittedOwner, setSubmittedOwner] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [activePreset, setActivePreset] = useState<GenerationPreset | null>(null);
  const [presetStatus, setPresetStatus] = useState("");
  const pending = useRef(false);
  const reportedGeneration = useRef("");
  const referencesRef = useRef<ReferenceImage[]>([]);
  const appliedQueries = useRef(new Set<string>());

  const workflow = resolveCreationModel(catalog.workflows, selection, workflowTitle);
  const canUseReference = supportsReferenceImages(workflow);
  const workflowLoras = workflow?.loras ?? [];
  const selectedLoras = loras.flatMap(choice => {
    const lora = findLora(workflowLoras, choice.id);
    return lora ? [{ lora, strength: choice.strength }] : [];
  });
  const selectedLoraIds = new Set(selectedLoras.map(item => item.lora.id));
  const unselectedLoras = workflowLoras.filter(lora => !selectedLoraIds.has(lora.id));
  const loadGeneration = useCallback(() => api.generation(submitted!.id), [submitted]);
  const owned = submittedOwner === session.user?.id;
  const tracked = useApiData(submitted && owned ? `${submittedOwner}:${submitted.id}` : null, loadGeneration, 5000, activeGeneration);
  const generation = owned ? tracked.data ?? submitted : null;
  const finished = generation ? !activeGeneration(generation) : false;
  const reloadUser = session.reloadUser;

  useEffect(() => {
    if (!generation || !finished || reportedGeneration.current === generation.id) return;
    reportedGeneration.current = generation.id;
    trackEvent(generation.status === "completed" ? "generation_completed" : "generation_failed", { placement: "studio" });
  }, [generation, finished]);
  useEffect(() => { referencesRef.current = references; }, [references]);
  useEffect(() => () => { referencesRef.current.forEach(item => URL.revokeObjectURL(item.url)); }, []);
  useEffect(() => { if (finished) void reloadUser(); }, [finished, reloadUser]);

  function applyDraft(values: GeneratorDraft) {
    if (values.selection !== undefined) setSelection(values.selection);
    if (values.prompt !== undefined) setPrompt(values.prompt);
    if (values.negativePrompt !== undefined) setNegativePrompt(values.negativePrompt);
    if (values.advancedOpen !== undefined) setAdvancedOpen(values.advancedOpen);
    if (values.loras !== undefined) setLoras(values.loras);
    if (values.seed !== undefined) setSeed(values.seed);
    if (values.seedMode !== undefined) setSeedMode(values.seedMode);
    if (values.activePreset !== undefined) setActivePreset(values.activePreset);
    if (values.presetStatus !== undefined) setPresetStatus(values.presetStatus);
  }

  function selectModel(value: string) {
    setSelection(value);
    setLoras([]);
    setReferences(current => {
      current.forEach(item => URL.revokeObjectURL(item.url));
      return [];
    });
  }

  function addLora(id: string) {
    const lora = workflowLoras.find(item => item.id === id);
    if (!lora) return;
    setLoras(current => {
      const normalized = current.flatMap(choice => {
        const match = findLora(workflowLoras, choice.id);
        return match ? [{ id: match.id, strength: choice.strength }] : [];
      });
      if (normalized.some(item => item.id === lora.id)) return normalized;
      return [...normalized, { id: lora.id, strength: workflow?.recommended_strengths?.[lora.id] ?? 0.7 }];
    });
  }

  function removeLora(id: string) {
    setLoras(current => current.flatMap(choice => {
      const match = findLora(workflowLoras, choice.id);
      return match && match.id !== id ? [{ id: match.id, strength: choice.strength }] : [];
    }));
  }

  function setLoraStrength(id: string, value: number) {
    setLoras(current => current.flatMap(choice => {
      const match = findLora(workflowLoras, choice.id);
      if (!match) return [];
      return [{ id: match.id, strength: match.id === id ? value : choice.strength }];
    }));
  }

  function upload(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;
    if (!canUseReference || busy) return;
    if (!hasReferenceConsent()) {
      setNote("Confirm that every person in your reference photos is an adult and that you have permission to use their image.");
      return;
    }
    const room = MAX_REFERENCE_IMAGES - references.length;
    if (room <= 0) return;
    const accepted: File[] = [];
    let total = references.reduce((sum, item) => sum + item.file.size, 0);
    let invalid = false;
    let tooLarge = false;
    for (const file of files.slice(0, room)) {
      if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || file.size > 10 * 1024 * 1024) { invalid = true; continue; }
      if (total + file.size > MAX_REFERENCE_TOTAL_BYTES) { tooLarge = true; continue; }
      accepted.push(file);
      total += file.size;
    }
    if (tooLarge) { setNote("Reference images must stay under 30 MB in total."); return; }
    if (invalid) { setNote("Choose PNG, JPG or WebP images smaller than 10 MB."); return; }
    if (!accepted.length) return;
    setNote("");
    setReferences(current => [...current, ...accepted.map(file => ({ id: crypto.randomUUID(), url: URL.createObjectURL(file), file }))].slice(0, MAX_REFERENCE_IMAGES));
  }

  function removeReference(id: string) {
    setReferences(current => {
      const target = current.find(item => item.id === id);
      if (target) URL.revokeObjectURL(target.url);
      return current.filter(item => item.id !== id);
    });
  }

  async function generate(): Promise<Generation | null> {
    if (!session.user) { session.openLogin(); return null; }
    if (!workflow || pending.current) return null;
    pending.current = true; setBusy(true); setNote("");
    try {
      let images: string[] = [];
      if (canUseReference && references.length) {
        images = await Promise.all(references.map(reference => new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result).split(",")[1]);
          reader.onerror = () => reject(new Error("Reference could not be read"));
          reader.readAsDataURL(reference.file);
        })));
      }
      const lorasStrength = Object.fromEntries(selectedLoras.map(item => [item.lora.id, item.strength]));
      const result = await api.createGeneration({ workflow_id: workflow.id, prompt, negative_prompt: negativePrompt, images, loras_strength: lorasStrength, ...(seedMode === "fixed" ? { seed } : {}) });
      setSubmitted(result); setSubmittedOwner(session.user.id);
      void reloadUser();
      trackEvent("generation_started", { placement: "studio" });
      updateWorkspace(current => ({ ...current, draft: { ...current.draft, prompt: prompt.slice(0, 4000), negativePrompt: negativePrompt.slice(0, 8192), loras: selectedLoras.map(item => ({ id: item.lora.id, strength: item.strength })) } }));
      return result;
    } catch (error) {
      setNote(errorMessage(error));
      return null;
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  const claimQuery = useCallback((key: string) => {
    if (!key || appliedQueries.current.has(key)) return false;
    appliedQueries.current.add(key);
    return true;
  }, []);

  return <GeneratorContext value={{
    selection, prompt, negativePrompt, advancedOpen, loras, seed, seedMode, references, busy, note,
    workflow, canUseReference, workflowLoras, selectedLoras, unselectedLoras, generation, finished,
    trackedError: tracked.error, activePreset, presetStatus,
    setPrompt, setNegativePrompt, setAdvancedOpen, setSeed, setSeedMode, setNote,
    setActivePreset, setPresetStatus, applyDraft, selectModel, addLora, removeLora,
    setLoraStrength, upload, removeReference, generate, claimQuery,
  }}>{children}</GeneratorContext>;
}

export function useGenerator() {
  const value = useContext(GeneratorContext);
  if (!value) throw new Error("GeneratorProvider is missing");
  return value;
}
