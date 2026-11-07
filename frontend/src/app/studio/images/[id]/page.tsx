import type { Metadata } from "next";
import { ImageDetail } from "@/components/studio/image-detail";
import { GenerationDetail } from "@/components/studio/generation-detail";
export const metadata: Metadata = { title: "Image details" };
export default async function ImagePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id) ? <GenerationDetail id={id} /> : <ImageDetail id={id} />;
}
