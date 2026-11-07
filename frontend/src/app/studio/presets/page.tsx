import type { Metadata } from "next";
import { PresetsPage } from "@/components/studio/presets-page";

export const metadata: Metadata = { title: "Presets" };

export default function StudioPresetsPage() {
  return <PresetsPage />;
}
