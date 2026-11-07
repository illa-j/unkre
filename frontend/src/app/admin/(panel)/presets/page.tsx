import type { Metadata } from "next";
import { AdminPresetsPage } from "@/components/admin/presets-page";

export const metadata: Metadata = { title: "Presets" };

export default function AdminPresetsPageRoute() {
  return <AdminPresetsPage />;
}
