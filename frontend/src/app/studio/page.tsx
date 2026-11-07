import type { Metadata } from "next";
import { Generator } from "@/components/studio/generator";

export const metadata: Metadata = { title: "Create — UNKRE Studio" };
export default async function StudioPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const query = await searchParams;
  const initialQuery = { model: typeof query.model === "string" ? query.model : undefined, lora: typeof query.lora === "string" ? query.lora : undefined, prompt: typeof query.prompt === "string" ? query.prompt.slice(0, 8192) : undefined, seed: typeof query.seed === "string" ? query.seed : undefined, preset: typeof query.preset === "string" ? query.preset.slice(0, 64) : undefined, reference: query.reference === "1" };
  return <Generator key={JSON.stringify(initialQuery)} initialQuery={initialQuery} />;
}
