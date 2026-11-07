"use client";

import Link from "next/link";
import { useState } from "react";
import { errorMessage } from "@/lib/api";
import { updateWorkspace, useWorkspace } from "@/lib/workspace";
import { UserAvatar } from "../user-avatar";
import { useSession } from "../session-provider";
import { AccountLinks } from "./account-links";
import { SessionNotice } from "./session-notice";
import { StudioIcon } from "./studio-icon";

export function Settings() {
  const workspace = useWorkspace();
  const session = useSession();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  async function logout() { setBusy(true); try { await session.logout(); setNote("You’re signed out."); } catch (error) { setNote(errorMessage(error)); } finally { setBusy(false); } }
  return <>
    <div className="studio-page-heading"><div><h1>Profile &amp; settings</h1><p>Manage your account and preferences for this browser.</p></div></div>
    <SessionNotice />
    <div className="studio-settings-layout"><div className="studio-settings-sections"><section className="studio-panel studio-settings-card"><header><div><h2>Your profile</h2><p>Your connected account.</p></div><span className="studio-tag">ACCOUNT</span></header>
      {session.user ? <><div className="studio-profile-edit"><UserAvatar name={`${session.user.first_name} ${session.user.last_name ?? ""}`.trim()} photoUrl={session.user.photo_url} className="studio-avatar studio-avatar-large" size={65} /><div><strong>{session.user.first_name} {session.user.last_name}{session.user.is_premium ? <span className="studio-premium-tag">Premium</span> : null}</strong><p>{session.user.google_email || (session.user.username ? `@${session.user.username}` : "Telegram account")}</p></div></div><dl className="studio-image-properties"><div><dt>Credits</dt><dd>{session.user.credits}</dd></div><div><dt>Joined</dt><dd>{new Date(session.user.registered_at).toLocaleDateString()}</dd></div><div><dt>Referral code</dt><dd><Link className="studio-text-link" href="/studio/referrals">{session.user.referral_code} ↗</Link></dd></div></dl><p className="studio-field-note">Your name and photo come from your sign-in provider.</p><button type="button" className="studio-button" disabled={busy} onClick={() => void logout()}>{busy ? "Signing out…" : "Sign out"}</button></> : <p className="studio-field-note">Sign in to view your profile.</p>}
    </section><AccountLinks /><section className="studio-panel studio-settings-card"><header><div><h2>Your creative defaults</h2><p>Preferences for this browser.</p></div><StudioIcon name="settings" size={22} /></header><label className="studio-setting-toggle"><span><strong>Show adult examples</strong><small>Reveal NSFW model examples.</small></span><input type="checkbox" role="switch" checked={workspace.settings.showAdult} onChange={event => updateWorkspace(current => ({ ...current, settings: { ...current.settings, showAdult: event.target.checked } }))} /></label></section>
    <p className="studio-live-note" role="status" aria-live="polite">{note}</p></div><aside className="studio-settings-aside"><div className="studio-settings-monogram" aria-hidden="true">u<span>.</span></div><p className="studio-eyebrow">YOUR IDEAS BELONG TO YOU</p><h2>A quiet place<br />to <em>create.</em></h2><p>Your images, your account, your next idea.</p></aside></div>
  </>;
}
