// LoRA strengths use [0, 2]: values above 1 and exactly 2 are valid.
const MAX_LORA_STRENGTH = 2;

export const studioModels = [
  { id: "qwen", name: "Qwen Image 2.1", family: "Qwen Image 2.1", description: "Text prompts & reference photos", image: "/images/qwen-image-2-1/example.png" },
  { id: "turbo", name: "Krea 2 Turbo", family: "Krea 2", description: "Explore your next idea", image: "/images/krea-2-turbo.png" },
] as const;

export type ModelId = typeof studioModels[number]["id"];
export type StudioImage = {
  id: string;
  title: string;
  src: string;
  width: number;
  height: number;
  model: ModelId;
  modelLabel?: string;
  /** LoRA used for the example, shown as a caption under the card. */
  lora?: string;
  category: "SFW" | "NSFW";
  promptIdea: string;
};

export const studioImages: StudioImage[] = [
  { id: "mint-portrait", title: "A softer perspective", src: "/images/qwen-image-2-1/example.png", width: 2048, height: 3072, model: "qwen", category: "SFW", promptIdea: "An intimate, candid portrait with silver and mint hair, soft natural light, a denim top and delicate jewelry. Natural skin texture, a quiet afternoon at home." },
  { id: "studio-portrait", title: "After hours, on air", src: "/images/krea-2-turbo.png", width: 832, height: 1248, model: "turbo", category: "SFW", promptIdea: "A candid portrait of a woman with glasses beside a studio microphone, colorful ambient lighting, a relaxed expression and a photographic feel." },
  { id: "glasshouse", title: "Under the glass", src: "/images/krea-2-raw.png", width: 450, height: 600, model: "turbo", modelLabel: "Krea 2", category: "SFW", promptIdea: "A woman with long black hair in a black outfit beneath the glass roof of a sunlit conservatory. Architectural lines, natural light and a candid composition." },
  { id: "night-market", title: "A night to wander", src: "/images/krea-2-character/sfw-1.png", width: 1024, height: 1536, model: "turbo", modelLabel: "Krea 2", category: "SFW", promptIdea: "A lively night market portrait, a black and white outfit, glowing signs and a crepe in hand. A spontaneous street photograph." },
  { id: "night-drive", title: "City lights", src: "/images/krea-2-character/sfw-2.png", width: 1024, height: 1536, model: "turbo", modelLabel: "Krea 2", category: "SFW", promptIdea: "A nighttime portrait seated on a black car, a black and white outfit, colorful reflections on polished paint, relaxed pose and candid framing." },
  { id: "bar-portrait", title: "One more story", src: "/images/qwen-image-2-1/sfw.png", width: 896, height: 1184, model: "qwen", category: "SFW", promptIdea: "A woman with long dark hair holding a glass at a dimly lit bar, warm amber lights, a black outfit and a cinematic atmosphere." },
  { id: "winter", title: "A little winter", src: "/images/loras/qwen-lenovo-ultrareal-sfw-1.png", width: 1088, height: 1440, model: "qwen", lora: "Lenovo UltraReal", category: "SFW", promptIdea: "A playful outdoor portrait beside snow-covered pine branches, long brown hair, a charcoal T-shirt and soft overcast winter light." },
  { id: "morning", title: "Slow mornings", src: "/images/loras/qwen-nicegirls-ultrareal-sfw-2.png", width: 896, height: 1184, model: "qwen", lora: "NiceGirls UltraReal", category: "SFW", promptIdea: "A quiet morning in a lived-in kitchen, cooking breakfast by a bright window, soft natural light and the texture of everyday life." },
  { id: "lora-realistic-snapshot-adult", title: "Realistic Snapshot adult study", src: "/images/loras/realistic-snapshot-nsfw-1.png", width: 1088, height: 1928, model: "turbo", modelLabel: "Krea 2", lora: "Realistic Snapshot", category: "NSFW", promptIdea: "" },
  { id: "lora-mystic-xxx-adult", title: "Mystic XXX adult study", src: "/images/loras/mystic-xxx-nsfw-1.png", width: 1224, height: 1632, model: "turbo", modelLabel: "Krea 2", lora: "[KREA 2] Mystic XXX", category: "NSFW", promptIdea: "" },
  { id: "lora-qwen-femaledvaginus-adult", title: "FemaledVaginus adult study", src: "/images/loras/qwen-femaledvaginus-nsfw-1.png", width: 1536, height: 2048, model: "qwen", lora: "FemaledVaginus-NSFW", category: "NSFW", promptIdea: "" },
  { id: "lora-qwen-femaledvaginus-adult-2", title: "FemaledVaginus portrait", src: "/images/loras/qwen-femaledvaginus-nsfw-2.png", width: 450, height: 681, model: "qwen", lora: "FemaledVaginus-NSFW", category: "NSFW", promptIdea: "" },
];

export type StudioLora = { id: string; strength: number };
export type StudioDraft = { model: ModelId; prompt: string; ratio: string; loras: StudioLora[]; seed: string; negativePrompt: string; batch: number };
const LEGACY_DEFAULT_PROMPTS = new Set([
  studioImages[0].promptIdea,
  "A natural portrait of the adult person in my reference photo, soft daylight, realistic skin texture and a photographic feel.",
]);
export const defaultDraft: StudioDraft = { model: "qwen", prompt: "", ratio: "2:3", loras: [], seed: "", negativePrompt: "", batch: 1 };
export type SavedImage = { id: string; sourceId: string; createdAt: string; draft: StudioDraft };
export type WorkspaceSettings = { name: string; defaultModel: ModelId; showAdult: boolean; preferredPlan: string };
export type Workspace = { favorites: string[]; saved: SavedImage[]; settings: WorkspaceSettings; draft: StudioDraft };
export const defaultWorkspace: Workspace = { favorites: [], saved: [], settings: { name: "", defaultModel: "qwen", showAdult: false, preferredPlan: "" }, draft: defaultDraft };

export function modelName(id: ModelId) { return studioModels.find(model => model.id === id)?.name ?? "Qwen Image 2.1"; }
export function modelFamily(id: ModelId) { return studioModels.find(model => model.id === id)?.family ?? "Qwen Image 2.1"; }
export function isModelId(value: unknown): value is ModelId { return studioModels.some(model => model.id === value); }

function normalizeLoras(draft: Record<string, unknown>): StudioLora[] {
  const legacy = typeof draft.lora === "string" && draft.lora.trim()
    ? [{ id: draft.lora, strength: draft.strength }]
    : [];
  const raw = Array.isArray(draft.loras) ? draft.loras : legacy;
  const result: StudioLora[] = [];
  const seen = new Set<string>();
  for (const item of raw) {
    const record = item && typeof item === "object" ? item as Record<string, unknown> : typeof item === "string" ? { id: item } : null;
    if (!record || typeof record.id !== "string") continue;
    const id = record.id.trim().slice(0, 255);
    if (!id || seen.has(id.toLowerCase())) continue;
    seen.add(id.toLowerCase());
    const strength = typeof record.strength === "number" && Number.isFinite(record.strength)
      ? Math.max(0, Math.min(MAX_LORA_STRENGTH, record.strength))
      : 0.7;
    result.push({ id, strength });
    if (result.length >= 100) break;
  }
  return result;
}

function normalizeDraft(value: unknown, clearLegacyDefault = false): StudioDraft {
  const draft = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const prompt = typeof draft.prompt === "string" ? draft.prompt.slice(0, 4000) : "";
  return {
    model: isModelId(draft.model) ? draft.model : "qwen",
    prompt: clearLegacyDefault && LEGACY_DEFAULT_PROMPTS.has(prompt) ? "" : prompt,
    ratio: typeof draft.ratio === "string" && ["1:1", "2:3", "3:2", "9:16"].includes(draft.ratio) ? draft.ratio : "2:3",
    loras: normalizeLoras(draft),
    seed: typeof draft.seed === "string" ? draft.seed.replace(/\D/g, "").slice(0, 16) : "",
    negativePrompt: typeof draft.negativePrompt === "string" ? draft.negativePrompt.slice(0, 8192) : "",
    batch: typeof draft.batch === "number" && [1, 2, 4].includes(draft.batch) ? draft.batch : 1,
  };
}

export function readWorkspace(raw: string | null): Workspace {
  if (!raw) return defaultWorkspace;
  try {
    const value = JSON.parse(raw);
    const settings = value?.settings;
    const draft = value?.draft;
    return {
      favorites: Array.isArray(value?.favorites) ? value.favorites.filter((id: unknown) => typeof id === "string").slice(0, 300) : [],
      saved: Array.isArray(value?.saved) ? value.saved.filter((item: SavedImage) => typeof item?.id === "string" && studioImages.some(image => image.id === item.sourceId) && typeof item.createdAt === "string" && Number.isFinite(Date.parse(item.createdAt)) && isModelId(item.draft?.model) && typeof item.draft?.prompt === "string").slice(0, 100).map((item: SavedImage) => ({ id: item.id, sourceId: item.sourceId, createdAt: item.createdAt, draft: normalizeDraft(item.draft) })) : [],
      settings: { name: typeof settings?.name === "string" ? settings.name.slice(0, 60) : "", defaultModel: isModelId(settings?.defaultModel) ? settings.defaultModel : "qwen", showAdult: settings?.showAdult === true, preferredPlan: typeof settings?.preferredPlan === "string" ? settings.preferredPlan : "" },
      draft: normalizeDraft(draft, true),
    };
  } catch { return defaultWorkspace; }
}

export function galleryItems(workspace: Workspace) {
  return workspace.saved.map(saved => {
    const source = studioImages.find(image => image.id === saved.sourceId)!;
    return { ...source, id: saved.id, sourceId: source.id, createdAt: saved.createdAt, draft: saved.draft };
  });
}
