import type { Metadata } from "next";
import { AdminLogin } from "@/components/admin/admin-login";

export const metadata: Metadata = { title: "Sign in — UNKRE Admin" };

export default function AdminLoginPage() {
  return <AdminLogin />;
}
