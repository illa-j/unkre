import type { Metadata } from "next";
import { ModelsPage } from "@/components/admin/models-page";

export const metadata: Metadata = { title: "Models" };

export default function AdminModelsPageRoute() {
  return <ModelsPage />;
}
