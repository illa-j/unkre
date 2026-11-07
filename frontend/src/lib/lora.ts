import { loraTitle } from "./catalog";
import type { Lora } from "./api-types";

export function loraLabel(lora: Lora): string {
  return loraTitle(lora);
}

export function findLora(loras: Lora[], value: string): Lora | undefined {
  const needle = value.trim().toLowerCase();
  if (!needle) return undefined;
  return loras.find(item => item.id === value)
    ?? loras.find(item => item.name.trim().toLowerCase() === needle)
    ?? loras.find(item => (item.description ?? "").trim().toLowerCase() === needle)
    ?? loras.find(item => loraLabel(item).toLowerCase() === needle)
    ?? loras.find(item => item.name.toLowerCase().includes(needle))
    ?? loras.find(item => (item.description ?? "").toLowerCase().includes(needle))
    ?? loras.find(item => loraLabel(item).toLowerCase().includes(needle));
}
