import type { Metadata } from "next";
import { LoraCatalog } from "@/components/studio/lora-catalog";
export const metadata: Metadata = { title: "Explore LoRAs" };
export default function LorasPage() { return <LoraCatalog />; }
