"use client";

import { useCallback, useState, useSyncExternalStore } from "react";
import { api } from "@/lib/api";
import { inviteUrl } from "@/lib/referral";
import { useApiData } from "@/lib/use-api-data";
import { useSession } from "../session-provider";
import { SessionNotice } from "./session-notice";
import { StudioIcon } from "./studio-icon";

const subscribeOrigin = () => () => {};
const getOrigin = () => window.location.origin;
const getServerOrigin = () => "";

export function ReferralProgram() {
  const session = useSession();
  const load = useCallback(() => api.referral(), []);
  const data = useApiData(session.user?.id ?? null, load);
  const origin = useSyncExternalStore(subscribeOrigin, getOrigin, getServerOrigin);
  const [note, setNote] = useState("");
  const stats = data.data;
  const link = stats && origin ? inviteUrl(origin, stats.referral_code) : "";

  async function copy(value: string, message: string) {
    try {
      await navigator.clipboard.writeText(value);
      setNote(message);
    } catch {
      setNote("Clipboard access is unavailable. Select and copy the text instead.");
    }
  }

  return <>
    <div className="studio-page-heading"><div><h1>Invite friends</h1><p>Share your invite link and earn credits when a friend makes their first credit purchase.</p></div></div>
    <SessionNotice />
    {data.loading && session.user && <p className="studio-live-note" role="status">Loading your invite details…</p>}
    {data.error && <div className="studio-api-notice" role="alert"><p>{data.error}</p><button type="button" className="studio-button" onClick={data.reload}>Try again</button></div>}
    {stats && <div className="studio-referral-layout">
      <section className="studio-panel studio-referral-card">
        <p className="studio-eyebrow">YOUR INVITE CODE</p>
        <h2>{stats.referral_code}</h2>
        <p className="studio-referral-copy">Share this code or send the link below. The bonus is applied once, after the new account makes its first credit purchase.</p>
        <div className="studio-referral-actions">
          <button type="button" className="studio-button studio-button-primary" onClick={() => void copy(stats.referral_code, "Invite code copied.")}><StudioIcon name="copy" size={17} /> Copy code</button>
          <button type="button" className="studio-button" disabled={!link} onClick={() => void copy(link, "Invite link copied.")}><StudioIcon name="gift" size={17} /> Copy invite link</button>
        </div>
        <label className="studio-field studio-referral-link"><span>Invite link</span><input readOnly value={link || "Preparing your link…"} onFocus={event => event.currentTarget.select()} /></label>
      </section>
      <div className="studio-referral-stats">
        <article className="studio-panel"><span className="studio-eyebrow">FRIENDS JOINED</span><strong>{stats.invited_count}</strong><p>{stats.pending_count > 0 ? `${stats.pending_count} awaiting first purchase.` : "Accounts created with your code."}</p></article>
        <article className="studio-panel"><span className="studio-eyebrow">CREDITS EARNED</span><strong>{stats.credits_earned}</strong><p>Added after their first purchase.</p></article>
        <article className="studio-panel"><span className="studio-eyebrow">THEIR WELCOME</span><strong>{stats.invitee_credits}</strong><p>Credits your friend receives after their first purchase, on top of their free credits.</p></article>
      </div>
    </div>}
    {stats && <section className="studio-panel studio-referral-how"><header><div><h2>How it works</h2><p>A simple exchange of good ideas.</p></div><StudioIcon name="gift" size={24} /></header><ol><li><span>01</span><p>Send your code or invite link to a friend.<small>They need a new UNKRE account.</small></p></li><li><span>02</span><p>They sign in with Google or Telegram.<small>Your code is attached to that first sign-in.</small></p></li><li><span>03</span><p>They make their first credit purchase. You both receive {stats.referrer_credits} and {stats.invitee_credits} credits.<small>One referral per new account.</small></p></li></ol></section>}
    <p className="studio-live-note" role="status" aria-live="polite">{note}</p>
  </>;
}
