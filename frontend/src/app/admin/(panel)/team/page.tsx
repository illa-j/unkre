import type { Metadata } from "next";
import { TeamPage } from "@/components/admin/team-page";

export const metadata: Metadata = { title: "Team" };

export default function AdminTeamPageRoute() {
  return <TeamPage />;
}
