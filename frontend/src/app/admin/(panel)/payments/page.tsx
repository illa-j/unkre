import type { Metadata } from "next";
import { PaymentsPage } from "@/components/admin/payments-page";

export const metadata: Metadata = { title: "Payments" };

export default function AdminPaymentsPageRoute() {
  return <PaymentsPage />;
}
