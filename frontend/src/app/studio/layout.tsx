import type { Metadata } from "next";
import type { ReactNode } from "react";
import { StudioShell } from "@/components/studio/studio-shell";
import { StudioGate } from "@/components/studio/studio-gate";
import { CatalogProvider } from "@/components/studio/catalog-provider";
import { GeneratorProvider } from "@/components/studio/generator-provider";
import "./studio.css";

export const metadata: Metadata = { title: { default: "Studio — UNKRE", template: "%s — UNKRE Studio" }, robots: { index: false, follow: false }, alternates: { canonical: null, languages: {} } };

export default function StudioLayout({ children }: { children: ReactNode }) {
  return <StudioGate><CatalogProvider><GeneratorProvider><StudioShell>{children}</StudioShell></GeneratorProvider></CatalogProvider></StudioGate>;
}
