"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { UserAvatar } from "../user-avatar";
import { useSession } from "../session-provider";
import { CreditIcon } from "./credit-icon";
import { StudioIcon, type StudioIconName } from "./studio-icon";

const primaryNavigation: { href: string; label: string; icon: StudioIconName }[] = [
  { href: "/studio", label: "Create", icon: "create" },
  { href: "/studio/gallery", label: "My images", icon: "gallery" },
  { href: "/studio/presets", label: "Presets", icon: "preset" },
  { href: "/studio/loras", label: "LoRAs", icon: "lora" },
];

const accountNavigation: { href: string; label: string; icon: StudioIconName }[] = [
  { href: "/studio/credits", label: "Credits & plans", icon: "credits" },
  { href: "/studio/referrals", label: "Invite friends", icon: "gift" },
  { href: "/studio/settings", label: "Profile & settings", icon: "settings" },
];

export function StudioShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const session = useSession();
  const name = session.user ? [session.user.first_name, session.user.last_name].filter(Boolean).join(" ") : "Your studio";
  const [menuOpen, setMenuOpen] = useState(false);
  const sidebar = useRef<HTMLElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!menuOpen) return;
    const trigger = menuButton.current;
    const desktop = window.matchMedia("(min-width: 861px)");
    function onResize() {
      if (desktop.matches) setMenuOpen(false);
    }
    const links = Array.from(sidebar.current?.querySelectorAll<HTMLElement>("a, button") ?? []).filter(element => element.getClientRects().length > 0);
    links[0]?.focus();
    document.body.classList.add("dialog-open");
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
      if (event.key === "Tab" && links.length) {
        const first = links[0];
        const last = links[links.length - 1];
        if (event.shiftKey && (document.activeElement === first || !sidebar.current?.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && (document.activeElement === last || !sidebar.current?.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
      }
    }
    document.addEventListener("keydown", onKey);
    desktop.addEventListener("change", onResize);
    return () => {
      document.body.classList.remove("dialog-open");
      document.removeEventListener("keydown", onKey);
      desktop.removeEventListener("change", onResize);
      if (trigger?.getClientRects().length) trigger.focus();
    };
  }, [menuOpen]);
  const current = [...primaryNavigation, ...accountNavigation].find(item => item.href === pathname)?.label ?? "Image details";
  const navigationLinks = (items: typeof primaryNavigation) => items.map(item => (
    <Link
      key={item.href}
      href={item.href}
      aria-current={pathname === item.href || (item.href === "/studio/gallery" && pathname.startsWith("/studio/images/")) ? "page" : undefined}
      onClick={() => setMenuOpen(false)}
    >
      <StudioIcon name={item.icon} /><span>{item.label}</span>
    </Link>
  ));
  return (
    <div className="studio-app">
      <a className="skip-link" href="#studio-main" inert={menuOpen}>Skip to workspace</a>
      {menuOpen && <button type="button" className="studio-nav-backdrop" aria-label="Close navigation" tabIndex={-1} onClick={() => setMenuOpen(false)} />}
      <aside ref={sidebar} id="studio-sidebar" className={`studio-sidebar${menuOpen ? " is-open" : ""}`} role={menuOpen ? "dialog" : undefined} aria-modal={menuOpen ? true : undefined} aria-label="Studio navigation panel">
        <div className="studio-brand"><Link href="/" className="wordmark" aria-label="UNKRE home"><Image className="wordmark-mark" src="/brand/unkre-mark-ui.webp" alt="" width={204} height={256} />unkre<span>.</span></Link><span>The Studio</span><button type="button" className="studio-icon-button studio-mobile-close" aria-label="Close navigation" onClick={() => setMenuOpen(false)}><StudioIcon name="close" /></button></div>
        <div className="studio-nav-group">
          <nav aria-label="Studio navigation">{navigationLinks(primaryNavigation)}</nav>
        </div>
        <div className="studio-sidebar-bottom">
          <div className="studio-nav-group studio-nav-secondary">
            <p className="studio-nav-label">ACCOUNT</p>
            <nav aria-label="Account navigation">{navigationLinks(accountNavigation)}</nav>
          </div>
          <div className="studio-profile"><UserAvatar name={name} photoUrl={session.user?.photo_url} className="studio-avatar" /><span>{name}{session.user?.is_premium ? <span className="studio-premium-tag">Premium</span> : null}<small>{session.user ? "Personal workspace" : "Welcome to UNKRE"}</small></span></div>
          <Link href="/" className="studio-back-home">← Back to UNKRE</Link>
        </div>
      </aside>
      <div className="studio-body" inert={menuOpen}>
        <header className="studio-topbar"><div className="studio-breadcrumb"><button ref={menuButton} type="button" className="studio-icon-button studio-menu-button" aria-label="Open navigation" aria-expanded={menuOpen} aria-controls="studio-sidebar" onClick={() => setMenuOpen(true)}><StudioIcon name="menu" /></button><span>Studio</span><span aria-hidden="true">/</span><strong>{current}</strong></div><div className="studio-topbar-right"><button type="button" className="studio-preview-badge" disabled={session.loading} aria-label={session.user ? `${session.user.credits} credits, refresh balance` : undefined} onClick={() => session.user ? void session.reloadUser() : session.openLogin()}><CreditIcon />{session.loading ? "Connecting…" : session.user ? `${session.user.credits} credits` : "Sign in"}</button></div></header>
        <main id="studio-main" className="studio-main" tabIndex={-1}>{children}</main>
        <footer className="studio-footer"><span>ROOM FOR YOUR IMAGINATION.</span><span>UNKRE</span></footer>
      </div>
    </div>
  );
}
