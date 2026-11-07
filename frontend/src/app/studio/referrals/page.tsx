import type { Metadata } from "next";
import { ReferralProgram } from "@/components/studio/referral-program";

export const metadata: Metadata = { title: "Invite friends" };
export default function ReferralsPage() { return <ReferralProgram />; }
