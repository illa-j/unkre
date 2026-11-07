import type { Metadata } from "next";
import { Credits } from "@/components/studio/credits";
export const metadata: Metadata = { title: "Credits & plans" };
export default function CreditsPage() { return <Credits />; }
