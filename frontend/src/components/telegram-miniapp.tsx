"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

type TelegramUser = { id: number; first_name?: string; last_name?: string; username?: string; language_code?: string; photo_url?: string };
type SafeArea = { top: number; bottom: number; left: number; right: number };
type BackButton = { show(): void; hide(): void; onClick(handler: () => void): void; offClick(handler: () => void): void };

type TelegramWebApp = {
  initData: string;
  initDataUnsafe?: { user?: TelegramUser };
  ready(): void;
  expand(): void;
  viewportHeight?: number;
  viewportStableHeight?: number;
  contentSafeAreaInset?: SafeArea;
  setHeaderColor?(color: string): void;
  setBackgroundColor?(color: string): void;
  disableVerticalSwipes?(): void;
  onEvent?(event: string, handler: () => void): void;
  offEvent?(event: string, handler: () => void): void;
  openInvoice?(url: string, callback?: (status: "paid" | "cancelled" | "failed" | "pending") => void): void;
  openLink?(url: string, options?: { try_instant_view?: boolean }): void;
  BackButton?: BackButton;
};

type TelegramLogin = {
  auth: (
    options: { client_id: number; scope: string[]; nonce: string },
    callback: (value: { id_token?: string; error?: string } | null) => void,
  ) => void;
};

declare global {
  interface Window { Telegram?: { WebApp?: TelegramWebApp; Login?: TelegramLogin } }
}

type InvoiceStatus = "paid" | "cancelled" | "failed" | "pending";

type TelegramContext = {
  inTelegram: boolean;
  initData: string;
  user?: TelegramUser;
  openInvoice: (url: string, callback?: (status: InvoiceStatus) => void) => boolean;
  openLink: (url: string) => boolean;
};

const Context = createContext<TelegramContext>({
  inTelegram: false,
  initData: "",
  openInvoice: () => false,
  openLink: () => false,
});

const ROOT_PATHS = new Set(["/", "/studio", "/admin"]);

function isTelegramContext() {
  if (typeof window === "undefined") return false;
  if (/Telegram/i.test(navigator.userAgent)) return true;
  const search = new URLSearchParams(window.location.search);
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  return search.has("tgWebAppData") || hash.has("tgWebAppData");
}

export function TelegramMiniAppProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [webApp, setWebApp] = useState<TelegramWebApp | null>(null);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    let app: TelegramWebApp | null = null;

    const syncViewport = () => {
      if (!app) return;
      const height = app.viewportStableHeight || app.viewportHeight;
      if (height) document.documentElement.style.setProperty("--tg-vh", `${height}px`);
      const top = app.contentSafeAreaInset?.top ?? 0;
      if (top) document.documentElement.style.setProperty("--tg-safe-top", `${top}px`);
    };
    const apply = (candidate: TelegramWebApp) => {
      app = candidate;
      setWebApp(candidate);
      candidate.ready();
      candidate.expand();
      candidate.setHeaderColor?.("#090e12");
      candidate.setBackgroundColor?.("#090e12");
      candidate.disableVerticalSwipes?.();
      document.body.classList.add("telegram-miniapp");
      syncViewport();
      candidate.onEvent?.("viewportChanged", syncViewport);
    };
    const tryInit = () => {
      if (!active || app) return true;
      const candidate = window.Telegram?.WebApp;
      if (!candidate || !candidate.initData) return false;
      apply(candidate);
      return true;
    };

    const inTelegram = isTelegramContext();
    if (inTelegram && !window.Telegram?.WebApp && !document.querySelector('script[src*="telegram-web-app.js"]')) {
      // Load Telegram's SDK only inside a Mini App. Loading it for regular
      // visitors sets third-party cookies on telegram.org for no benefit.
      const script = document.createElement("script");
      script.src = "https://telegram.org/js/telegram-web-app.js";
      script.async = true;
      document.head.appendChild(script);
    }
    if (!tryInit() && inTelegram) {
      // Telegram's SDK is an external script and can finish after React
      // hydration on a slow mobile connection. Keep checking briefly.
      let attempts = 0;
      timer = window.setInterval(() => {
        attempts += 1;
        if (tryInit() || attempts >= 50) {
          if (timer !== undefined) { window.clearInterval(timer); timer = undefined; }
        }
      }, 100);
    }

    return () => {
      active = false;
      if (timer !== undefined) window.clearInterval(timer);
      if (app) {
        document.body.classList.remove("telegram-miniapp");
        document.documentElement.style.removeProperty("--tg-vh");
        document.documentElement.style.removeProperty("--tg-safe-top");
        app.offEvent?.("viewportChanged", syncViewport);
      }
    };
  }, []);

  useEffect(() => {
    const button = webApp?.BackButton;
    if (!button) return;
    if (ROOT_PATHS.has(pathname)) button.hide();
    else button.show();
  }, [webApp, pathname]);

  useEffect(() => {
    const button = webApp?.BackButton;
    if (!button) return;
    const handler = () => router.back();
    button.onClick(handler);
    return () => button.offClick(handler);
  }, [webApp, router]);

  const value = useMemo<TelegramContext>(() => ({
    inTelegram: Boolean(webApp),
    initData: webApp?.initData ?? "",
    user: webApp?.initDataUnsafe?.user,
    openInvoice: (url, callback) => {
      if (!webApp?.openInvoice) return false;
      webApp.openInvoice(url, callback);
      return true;
    },
    openLink: url => {
      if (!webApp?.openLink) return false;
      webApp.openLink(url);
      return true;
    },
  }), [webApp]);

  return <Context value={value}>{children}</Context>;
}

export function useTelegramMiniApp() {
  return useContext(Context);
}
