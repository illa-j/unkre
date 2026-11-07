"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useSession } from "./session-provider";

export function AuthLink({
  mode = "signup",
  className,
  children,
}: {
  mode?: "signup" | "login";
  className?: string;
  children: ReactNode;
}) {
  const session = useSession();
  return session.user ? (
    <Link href="/studio" className={className}>{children}</Link>
  ) : (
    <button type="button" className={className} aria-haspopup="dialog" onClick={() => session.openLogin(mode)}>{children}</button>
  );
}
