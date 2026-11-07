"use client";

import Script from "next/script";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import type { AuthChallenge, AuthProvider } from "@/lib/api-types";
import { useSession } from "../session-provider";
import { StudioIcon } from "./studio-icon";

declare global {
  interface Window {
    google?: { accounts: { id: {
      initialize: (options: { client_id: string; nonce: string; callback: (value: { credential: string }) => void }) => void;
      renderButton: (element: HTMLElement, options: Record<string, string | number>) => void;
      disableAutoSelect: () => void;
    } } };
  }
}

export function AccountLinks() {
  const session = useSession();
  const [challenges, setChallenges] = useState<Partial<Record<AuthProvider, AuthChallenge>>>({});
  const [errors, setErrors] = useState<Partial<Record<AuthProvider, string>>>({});
  const [ready, setReady] = useState({ google: false, telegram: false });
  const [busy, setBusy] = useState<AuthProvider | null>(null);
  const [note, setNote] = useState("");
  const [revision, setRevision] = useState(0);
  const googleButton = useRef<HTMLDivElement>(null);
  const active = useRef(true);
  const submitting = useRef(false);
  const preparedAt = useRef(0);
  const reloadUser = session.reloadUser;
  const linkedGoogle = Boolean(session.user?.google_email);
  const linkedTelegram = Boolean(session.user?.telegram_id);

  useEffect(() => {
    active.current = true;
    if (!session.user?.id) return;
    preparedAt.current = Date.now();
    const providers: AuthProvider[] = [];
    if (!linkedGoogle) providers.push("google");
    if (!linkedTelegram) providers.push("telegram");
    for (const provider of providers) {
      api.challenge(provider).then(value => {
        if (active.current) {
          setChallenges(current => ({ ...current, [provider]: value }));
          setErrors(current => ({ ...current, [provider]: undefined }));
        }
      }).catch(error => {
        if (active.current) setErrors(current => ({ ...current, [provider]: errorMessage(error) }));
      });
    }
    return () => { active.current = false; };
  }, [session.user?.id, linkedGoogle, linkedTelegram, revision]);

  const link = useCallback(async (provider: AuthProvider, idToken: string, nonce: string) => {
    if (submitting.current) return;
    submitting.current = true; setBusy(provider); setNote(""); setErrors(current => ({ ...current, [provider]: undefined }));
    try {
      await api.linkAccount(provider, idToken, nonce);
      await reloadUser();
      setNote(provider === "google" ? "Google account linked." : "Telegram account linked.");
    } catch (error) {
      setErrors(current => ({ ...current, [provider]: errorMessage(error) }));
      setRevision(value => value + 1);
    } finally {
      submitting.current = false; setBusy(null);
    }
  }, [reloadUser]);

  useEffect(() => {
    const challenge = challenges.google;
    const element = googleButton.current;
    if (!ready.google || !challenge || !element || !window.google || linkedGoogle) return;
    window.google.accounts.id.initialize({
      client_id: challenge.client_id,
      nonce: challenge.nonce,
      callback: result => { if (active.current && result.credential) void link("google", result.credential, challenge.nonce); },
    });
    element.replaceChildren();
    window.google.accounts.id.renderButton(element, {
      theme: "filled_black", size: "large", width: 300, shape: "pill", text: "continue_with",
    });
    return () => element.replaceChildren();
  }, [ready.google, challenges.google, linkedGoogle, link]);

  function telegramLink() {
    const challenge = challenges.telegram;
    const telegram = window.Telegram?.Login;
    if (!challenge || !telegram || busy || linkedTelegram) return;
    if (Date.now() - preparedAt.current > challenge.expires_in * 1000) {
      setErrors(current => ({ ...current, telegram: "Sign-in expired. Please retry." }));
      setRevision(value => value + 1);
      return;
    }
    setErrors(current => ({ ...current, telegram: undefined }));
    telegram.auth({ client_id: Number(challenge.client_id), scope: ["profile"], nonce: challenge.nonce }, result => {
      if (!active.current) return;
      if (result?.id_token) void link("telegram", result.id_token, challenge.nonce);
      else if (result?.error) setErrors(current => ({ ...current, telegram: "Telegram sign-in was not completed. Please try again." }));
    });
  }

  if (!session.user) return null;

  return <section className="studio-panel studio-settings-card">
    <Script src="https://accounts.google.com/gsi/client" onReady={() => setReady(value => ({ ...value, google: true }))} onError={() => setErrors(value => ({ ...value, google: "Google sign-in could not load." }))} />
    <Script src="https://oauth.telegram.org/js/telegram-login.js?6" onReady={() => setReady(value => ({ ...value, telegram: true }))} onError={() => setErrors(value => ({ ...value, telegram: "Telegram sign-in could not load." }))} />
    <header><div><h2>Connected accounts</h2><p>Link Google and Telegram to sign in to the same UNKRE account.</p></div><StudioIcon name="settings" size={22} /></header>
    <div className="studio-account-links">
      <div className="studio-account-link-row">
        <div><strong>Google</strong><small>{linkedGoogle ? session.user.google_email : "Not connected"}</small></div>
        {linkedGoogle ? <span className="studio-tag">CONNECTED</span> : <div ref={googleButton} className="auth-google" />}
      </div>
      <div className="studio-account-link-row">
        <div><strong>Telegram</strong><small>{linkedTelegram ? session.user.username ? `@${session.user.username}` : `ID ${session.user.telegram_id}` : "Not connected"}</small></div>
        {linkedTelegram ? <span className="studio-tag">CONNECTED</span> : <button type="button" className="studio-button studio-button-small" disabled={!challenges.telegram || !ready.telegram || Boolean(busy)} onClick={telegramLink}>{busy === "telegram" ? "Linking…" : "Link Telegram"}</button>}
      </div>
    </div>
    {!linkedGoogle && !challenges.google && !errors.google && <p className="studio-field-note">Preparing Google sign-in…</p>}
    {note && <p className="studio-live-note" role="status">{note}</p>}
    {(errors.google || errors.telegram) && <p className="studio-generator-note" role="alert">{errors.google || errors.telegram}</p>}
  </section>;
}
