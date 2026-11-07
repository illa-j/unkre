import type { Metadata } from "next";
import { LorasPage } from "@/components/admin/loras-page";

export const metadata: Metadata = { title: "LoRAs" };

export default function AdminLorasPageRoute() {
  return <LorasPage />;
}
