import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./admin.css";

export const metadata: Metadata = {
  title: { default: "Admin — UNKRE", template: "%s — UNKRE Admin" },
  description: "UNKRE administration.",
  robots: { index: false, follow: false, nocache: true },
  alternates: { canonical: null, languages: {} },
};

export default function AdminLayout({ children }: { children: ReactNode }) {
  return children;
}
