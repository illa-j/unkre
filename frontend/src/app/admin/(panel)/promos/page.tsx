import type { Metadata } from "next";
import { PromosPage } from "@/components/admin/promos-page";

export const metadata: Metadata = { title: "Promo codes" };

export default function AdminPromosPageRoute() {
  return <PromosPage />;
}
