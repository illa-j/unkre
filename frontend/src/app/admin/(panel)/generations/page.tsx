import type { Metadata } from "next";
import { GenerationsPage } from "@/components/admin/generations-page";

export const metadata: Metadata = { title: "Generations" };

export default function AdminGenerationsPageRoute() {
  return <GenerationsPage />;
}
