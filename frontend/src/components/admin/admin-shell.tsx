"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { adminApi } from "@/lib/admin-api";
import type { AdminAccount } from "@/lib/admin-types";

const navigation = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/generations", label: "Generations" },
  { href: "/admin/payments", label: "Payments" },
  { href: "/admin/promos", label: "Promo codes" },
  { href: "/admin/models", label: "Models" },
  { href: "/admin/loras", label: "LoRAs" },
  { href: "/admin/presets", label: "Presets" },
  { href: "/admin/settings", label: "Settings" },
  { href: "/admin/team", label: "Team", owner: true },
];

export function AdminShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [admin, setAdmin] = useState<AdminAccount | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "denied">("loading");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    adminApi.me()
      .then(value => { if (active) { setAdmin(value); setState("ready"); } })
      .catch(() => { if (active) { setState("denied"); router.replace("/admin/login"); } });
    return () => { active = false; };
  }, [router]);

  async function signOut() {
    setBusy(true);
    try { await adminApi.logout(); } catch { /* The cookie may already be gone. */ }
    router.replace("/admin/login");
  }

  if (state !== "ready" || !admin) {
    return <div className="admin-app"><div className="admin-main"><div className="admin-loading">{state === "denied" ? "Redirecting to sign in…" : "Opening the panel…"}</div></div></div>;
  }

  const section = navigation.find(item => item.href === "/admin" ? pathname === "/admin" : pathname.startsWith(item.href));

  return <div className="admin-app">
    <aside className="admin-sidebar">
      <div className="admin-brand">
        <Link href="/admin" className="wordmark" aria-label="UNKRE admin home">
          <Image className="wordmark-mark" src="/brand/unkre-mark-ui.webp" alt="" width={204} height={256} />
          unkre<span>.</span>
        </Link>
        <span><small>ADMIN PANEL</small></span>
      </div>
      <nav className="admin-nav" aria-label="Admin sections">{navigation.map(item => item.owner && !admin.is_owner ? null : <Link key={item.href} href={item.href} aria-current={section?.href === item.href ? "page" : undefined}>{item.label}</Link>)}</nav>
      <div className="admin-sidebar-foot">
        <span><strong>{admin.username}</strong>{admin.is_owner ? "Owner" : "Administrator"}</span>
        <Link href="/">← Back to store</Link>
        <button type="button" onClick={() => void signOut()} disabled={busy}>{busy ? "Signing out…" : "Sign out"}</button>
        <span>UNKRE</span>
      </div>
    </aside>
    <div className="admin-main">
      <header className="admin-topbar"><p>{section?.label ?? "Admin"} · {admin.is_owner ? "owner access" : "limited access"}</p><div className="admin-topbar-actions"><Link href="/studio" className="admin-button admin-button-small">Open studio</Link></div></header>
      <main className="admin-content">{children}</main>
    </div>
  </div>;
}
