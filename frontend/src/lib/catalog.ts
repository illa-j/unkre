import type { Lora } from "./api-types";

/**
 * Workflow names are technical Runpod graph keys ("krea2_turbo_all_api").
 * Customers only ever see these titles.
 */
const workflowTitles: Record<string, string> = {
  krea2_turbo_all_api: "Krea 2 Turbo",
  krea2_turbo_all_ui: "Krea 2 Turbo",
  krea2_raw_t2image_api: "Krea 2 Raw",
  krea2_raw_t2image_ui: "Krea 2 Raw",
  qwen_image21: "Qwen Image 2.1",
  qwen_image21_api: "Qwen Image 2.1",
};

const technicalSuffixes = new Set(["api", "ui", "all", "t2image", "t2img", "graph", "endpoint"]);
const titleLength = 64;

function splitWords(value: string): string[] {
  return value.replace(/\.safetensors$/i, "").split(/[\s_-]+/).filter(Boolean);
}

function capitalize(value: string): string {
  return value.replace(/(^|\s)([a-z])/g, (_, space: string, letter: string) => `${space}${letter.toUpperCase()}`);
}

function readable(words: string[]): string {
  const spaced = words.join(" ").replace(/\b([A-Za-z]{3,})(\d{1,2})\b/g, (_, stem: string, digits: string) => `${stem} ${digits}`);
  return capitalize(spaced).replace(/\b(nsfw|sfw|ai|lora)\b/gi, word => word.toUpperCase()).trim();
}

/** "krea2_turbo_all_api" → "Krea 2 Turbo" */
export function workflowTitle(workflow: { name: string }): string {
  const raw = workflow.name.trim();
  const known = workflowTitles[raw.toLowerCase().replace(/\.(safetensors|json)$/i, "")];
  if (known) return known;
  const words = splitWords(raw);
  while (words.length > 1 && technicalSuffixes.has(words[words.length - 1].toLowerCase())) words.pop();
  return readable(words) || raw;
}

/** The manifest title lives in `description`; the file name is the fallback. */
export function loraTitle(lora: Lora): string {
  const description = lora.description?.trim() ?? "";
  if (description && description.length <= titleLength && !/[.!?]$/.test(description)) return description;
  return readable(splitWords(lora.name)) || lora.name;
}
