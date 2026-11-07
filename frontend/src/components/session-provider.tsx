"use client";

import { studioDestination } from "@/lib/creation-intent";
import { trackEvent } from "@/lib/analytics";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, ApiError, errorMessage } from "@/lib/api";
import type { AuthProvider, User } from "@/lib/api-types";
import { forgetReferralCode, readReferralCode, rememberReferralCode } from "@/lib/referral";
import { useTelegramMiniApp } from "./telegram-miniapp";

type Session = {
  user: User | null; loading: boolean; error: string; loginMode: "signup" | "login" | null;
  openLogin: (mode?: "signup" | "login", destination?: string) => void; closeLogin: () => void;
  completeLogin: (provider: AuthProvider, token: string, nonce: string) => Promise<void>;
  reloadUser: () => Promise<void>; logout: () => Promise<void>;
};
const SessionContext = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const adminArea = Boolean(pathname?.startsWith("/admin"));
  const { initData } = useTelegramMiniApp();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [loginMode, setLoginMode] = useState<Session["loginMode"]>(null);
  const epoch = useRef(0);
  const loginDestination = useRef("/studio");
  const telegramAttempt = useRef("");
  const telegramLogin = useCallback(async () => {
    if (!initData || telegramAttempt.current === initData) return false;
    telegramAttempt.current = initData;
    const version = epoch.current;
    try {
      // Telegram MiniApp: the signed launch payload replaces the login widget.
      const session = await api.miniappLogin(initData, readReferralCode() || undefined);
      forgetReferralCode();
      if (version === epoch.current) {
        setUser(session.user); setError(""); setLoginMode(null); setLoading(false);
      }
      return true;
    } catch (loginError) {
      if (!(loginError instanceof ApiError)) setError(errorMessage(loginError));
      return false;
    }
  }, [initData]);

  const reloadUser = useCallback(async () => {
    const version = epoch.current;
    try {
      const value = await api.session();
      if (version === epoch.current) { setUser(value); setError(""); setLoginMode(null); }
    } catch (error) {
      if (version !== epoch.current) return;
      if (error instanceof ApiError && [401, 403].includes(error.status) && await telegramLogin()) return;
      if (error instanceof ApiError && [401, 403].includes(error.status)) { setUser(null); setError(error.status === 403 ? error.message : ""); }
      else setError(errorMessage(error));
    } finally { if (version === epoch.current) setLoading(false); }
  }, [telegramLogin]);

  // The landing page and the MiniApp can open without any authenticated
  // request. Once Telegram hands us initData, sign in without user action.
  useEffect(() => {
    if (adminArea || !initData || user || loading) return;
    queueMicrotask(() => { void telegramLogin(); });
  }, [adminArea, initData, user, loading, telegramLogin]);
  useEffect(() => { rememberReferralCode(window.location.search); }, []);
  useEffect(() => {
    let active = true;
    if (adminArea) { queueMicrotask(() => { if (active) setLoading(false); }); return () => { active = false; }; }
    queueMicrotask(() => { if (active) void reloadUser(); });
    const sync = () => { if (document.visibilityState === "visible") void reloadUser(); };
    window.addEventListener("focus", sync);
    window.addEventListener("storage", sync);
    const timer = setInterval(sync, 60000);
    return () => { active = false; clearInterval(timer); window.removeEventListener("focus", sync); window.removeEventListener("storage", sync); };
  }, [reloadUser, adminArea]);

  function broadcast() {
    try { localStorage.setItem("unkre.session.changed", String(Date.now())); } catch { /* Cookies do not depend on local storage. */ }
  }
  async function completeLogin(provider: AuthProvider, token: string, nonce: string) {
    epoch.current += 1;
    const session = await api.login(provider, token, nonce, readReferralCode() || undefined);
    forgetReferralCode();
    setUser(session.user); setError(""); setLoading(false); setLoginMode(null); broadcast();
    trackEvent(session.is_new_user ? "signup_completed" : "signin_completed", { placement: "auth_dialog" });
    router.push(loginDestination.current);
  }
  async function logout() {
    epoch.current += 1;
    try { await api.logout(); } catch (error) { if (!(error instanceof ApiError && error.status === 401)) throw error; }
    setUser(null); setError(""); broadcast();
  }
  return <SessionContext value={{ user, loading, error, loginMode, openLogin: (mode = "login", destination) => { loginDestination.current = studioDestination(destination ?? `${window.location.pathname}${window.location.search}`); setLoginMode(mode); }, closeLogin: () => setLoginMode(null), completeLogin, reloadUser, logout }}>{children}</SessionContext>;
}

export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("SessionProvider is missing");
  return value;
}
