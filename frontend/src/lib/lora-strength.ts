// LoRA strengths use [0, 2]: values above 1 and exactly 2 are valid.
export const LORA_STRENGTH_MAX = 2;

export function isValidLoraStrength(value: number): boolean {
  return Number.isFinite(value) && value >= 0 && value <= 2;
}

export function clampLoraStrength(value: number): number {
  return Math.max(0, Math.min(LORA_STRENGTH_MAX, value));
}
