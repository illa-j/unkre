import type { Metadata } from "next";
import { Settings } from "@/components/studio/settings";
export const metadata: Metadata = { title: "Profile & settings" };
export default function SettingsPage() { return <Settings />; }
