"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useSession } from "../session-provider";
import { studioDestination } from "@/lib/creation-intent";
import { trackEvent } from "@/lib/analytics";

export function CreateLink({ children, href = "/studio", className = "button button-primary", placement, preset }: { children: ReactNode; href?: string; className?: string; placement: string; preset?: string }) {
  const session = useSession();
  const destination = studioDestination(href);
  return <Link href={destination} className={className} prefetch={false} onClick={event => {
    trackEvent("cta_click", { placement, preset });
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    if (!session.user) { event.preventDefault(); session.openLogin("signup", destination); }
  }}>{children}</Link>;
}
