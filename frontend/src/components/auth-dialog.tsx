"use client";

import Script from "next/script";
import { welcomeOffer } from "@/lib/site";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import type { AuthChallenge, AuthProvider } from "@/lib/api-types";
import { useSession } from "./session-provider";
import { useTelegramMiniApp } from "./telegram-miniapp";

declare global {
  interface Window {
    google?: { accounts: { id: {
      initialize: (options: { client_id: string; nonce: string; callback: (value: { credential: string }) => void }) => void;
      renderButton: (element: HTMLElement, options: Record<string, string | number>) => void;
      disableAutoSelect: () => void;
    } } };
  }
}

function LoginProviders() {
  const session = useSession();
  const [challenges, setChallenges] = useState<Partial<Record<AuthProvider, AuthChallenge>>>({});
  const [errors, setErrors] = useState<Partial<Record<AuthProvider, string>>>({});
  const [ready, setReady] = useState({ google: false, telegram: false });
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const googleButton = useRef<HTMLDivElement>(null);
  const active = useRef(true);
  const submitting = useRef(false);
  const preparedAt = useRef(0);
  const completeLogin = useRef(session.completeLogin);
  useEffect(() => { completeLogin.current = session.completeLogin; }, [session.completeLogin]);

  useEffect(() => {
    active.current = true;
    preparedAt.current = Date.now();
    for (const provider of ["google", "telegram"] as const) {
      api.challenge(provider).then(value => {
        if (active.current) { setChallenges(current => ({ ...current, [provider]: value })); setErrors(current => ({ ...current, [provider]: undefined })); }
      }).catch(error => { if (active.current) setErrors(current => ({ ...current, [provider]: errorMessage(error) })); });
    }
    return () => { active.current = false; };
  }, [revision]);

  const submit = useCallback((provider: AuthProvider, token: string, nonce: string) => {
    if (submitting.current) return;
    submitting.current = true; setBusy(true); setError("");
    void completeLogin.current(provider, token, nonce).catch(error => {
      if (active.current) { setError(errorMessage(error)); setRevision(value => value + 1); }
    }).finally(() => { submitting.current = false; if (active.current) setBusy(false); });
  }, []);

  useEffect(() => {
    const challenge = challenges.google;
    const element = googleButton.current;
    if (!ready.google || !challenge || !element || !window.google) return;
    window.google.accounts.id.initialize({ client_id: challenge.client_id, nonce: challenge.nonce, callback: result => {
      if (active.current && result.credential) submit("google", result.credential, challenge.nonce);
    } });
    element.replaceChildren();
    window.google.accounts.id.renderButton(element, { theme: "outline", size: "large", width: Math.min(300, element.clientWidth), shape: "pill", text: "continue_with" });
    return () => element.replaceChildren();
  }, [ready.google, challenges.google, submit]);

  function telegramLogin() {
    const challenge = challenges.telegram;
    const telegram = window.Telegram?.Login;
    if (!challenge || !telegram || busy) return;
    if (Date.now() - preparedAt.current > challenge.expires_in * 1000) { setError("Sign-in expired. Please retry."); setRevision(value => value + 1); return; }
    setError("");
    telegram.auth({ client_id: Number(challenge.client_id), scope: ["profile"], nonce: challenge.nonce }, result => {
      if (!active.current) return;
      if (result?.id_token) submit("telegram", result.id_token, challenge.nonce);
      else if (result?.error) setError("Telegram sign-in was not completed. Please try again.");
    });
  }

  return <div className="auth-providers" aria-busy={busy}>
    <Script src="https://accounts.google.com/gsi/client" onReady={() => setReady(value => ({ ...value, google: true }))} onError={() => setErrors(value => ({ ...value, google: "Google sign-in could not load." }))} />
    <Script src="https://oauth.telegram.org/js/telegram-login.js?6" onReady={() => setReady(value => ({ ...value, telegram: true }))} onError={() => setErrors(value => ({ ...value, telegram: "Telegram sign-in could not load." }))} />
    <div ref={googleButton} className={busy ? "auth-google is-busy" : "auth-google"} />
    {!challenges.google && <p>{errors.google || "Preparing Google sign-in…"}</p>}
    <div className="auth-divider" aria-hidden="true"><span />or<span /></div>
    <button type="button" className="button auth-telegram" disabled={!challenges.telegram || !ready.telegram || busy} onClick={telegramLogin}><svg aria-hidden="true" viewBox="0 0 24 24" fill="currentColor"><path d="M21.4 4.6 18.2 19.7c-.2 1.1-.9 1.4-1.8.9l-4.9-3.6-2.4 2.3c-.3.3-.5.5-1 .5l.4-5 9.1-8.2c.4-.4-.1-.6-.6-.2L5.8 13.5 1 12c-1-.3-1-1 .2-1.5L20 3.3c.9-.3 1.7.2 1.4 1.3Z" /></svg>Continue with Telegram</button>
    {errors.telegram && <p>{errors.telegram}</p>}
    {busy && <p role="status">Signing you in…</p>}
    {error && <p className="auth-error" role="alert">{error}</p>}
    {(error || errors.google || errors.telegram) && <button type="button" className="auth-retry" disabled={busy} onClick={() => { setError(""); setRevision(value => value + 1); }}>Retry sign-in options</button>}
  </div>;
}

function TelegramSignIn() {
  const session = useSession();
  const { initData, user } = useTelegramMiniApp();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  async function retry() {
    setBusy(true); setNote("");
    try {
      await api.miniappLogin(initData);
      await session.reloadUser();
      session.closeLogin();
    } catch (error) { setNote(errorMessage(error)); }
    finally { setBusy(false); }
  }
  return <div className="auth-providers" aria-busy={busy}>
    <p>You opened UNKRE inside Telegram. Signing in with your Telegram account{user?.username ? ` @${user.username}` : ""} happens automatically.</p>
    <button type="button" className="button button-primary" disabled={busy || session.loading} onClick={() => void retry()}>{busy ? "Signing you in…" : "Try Telegram sign-in again"}</button>
    {note && <p className="auth-error" role="alert">{note}</p>}
  </div>;
}

export function AuthDialog() {
  const { loginMode, closeLogin } = useSession();
  const { inTelegram } = useTelegramMiniApp();
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    if (loginMode && !element?.open) { element?.showModal(); document.body.classList.add("dialog-open"); }
    if (!loginMode) { element?.close(); document.body.classList.remove("dialog-open"); }
    return () => { document.body.classList.remove("dialog-open"); };
  }, [loginMode]);
  return <dialog ref={dialog} className="preview-dialog auth-dialog" aria-labelledby="auth-title" aria-describedby="auth-description" onClose={closeLogin} onClick={event => { if (event.target === event.currentTarget) { const rect = event.currentTarget.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeLogin(); } }}>
    <button type="button" className="dialog-close" aria-label="Close sign in" onClick={closeLogin}>×</button>
    <div className="auth-header"><span className="auth-brand">UNKRE<span>.</span></span><span className="auth-header-label">YOUR CREATIVE SPACE</span></div>
    <p className="eyebrow auth-eyebrow"><span aria-hidden="true" />YOUR UNKRE STUDIO</p>
    <h2 id="auth-title">{loginMode === "signup" ? "Your first image awaits." : "Welcome back."}<br /><em>Make it yours.</em></h2>
    <p id="auth-description">{loginMode === "signup" ? `${welcomeOffer}. Sign in with Google or Telegram to start creating.` : "Sign in with Google or Telegram to return to your images, settings and credits."}</p>
    {loginMode && (inTelegram ? <TelegramSignIn /> : <LoginProviders key={loginMode} />)}
  </dialog>;
}
