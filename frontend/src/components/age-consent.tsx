"use client";

import Link from "next/link";
import { createContext, useCallback, useContext, useMemo, useSyncExternalStore, type ReactNode } from "react";
import { legal } from "@/lib/legal";

const storageKey = "unkre.adult.v1";
const changeEvent = "unkre:adult-change";
const consentVersion = 1;
let memoryConsent = false;

type AgeConsent = {
  adult: boolean;
  ready: boolean;
  confirm: () => void;
};

const Context = createContext<AgeConsent | null>(null);

function readConsent(): boolean {
  if (memoryConsent) return true;
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return false;
    const value = JSON.parse(raw) as { version?: unknown; adult?: unknown };
    return value.version === consentVersion && value.adult === true;
  } catch {
    return false;
  }
}

function subscribe(listener: () => void) {
  const onStorage = (event: StorageEvent) => { if (event.key === storageKey || event.key === null) listener(); };
  window.addEventListener("storage", onStorage);
  window.addEventListener(changeEvent, listener);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(changeEvent, listener);
  };
}

const subscribeHydration = () => () => {};

export function AgeConsentProvider({ children }: { children: ReactNode }) {
  const adult = useSyncExternalStore(subscribe, readConsent, () => false);
  const ready = useSyncExternalStore(subscribeHydration, () => true, () => false);

  const confirm = useCallback(() => {
    memoryConsent = true;
    try {
      localStorage.setItem(storageKey, JSON.stringify({
        version: consentVersion,
        adult: true,
        confirmedAt: new Date().toISOString(),
      }));
    } catch { /* The confirmation still applies to this page view. */ }
    window.dispatchEvent(new Event(changeEvent));
  }, []);

  const value = useMemo(() => ({ adult, ready, confirm }), [adult, ready, confirm]);
  return <Context value={value}>{children}</Context>;
}

export function useAgeConsent() {
  const value = useContext(Context);
  if (!value) throw new Error("AgeConsentProvider is missing");
  return value;
}

export function AdultDetails({ className, summary, children }: {
  className?: string;
  summary: ReactNode;
  children: ReactNode;
}) {
  const { adult, ready, confirm } = useAgeConsent();
  return <details className={className}>
    <summary>{summary}</summary>
    {!ready
      ? <p className="adult-consent-note" role="status">Checking your adult-content preference…</p>
      : adult
        ? children
        : <div className="adult-consent">
          <p><strong>Adults only.</strong> This section contains NSFW examples. Confirm that you are at least {legal.minimumAge} to view them.</p>
          <div className="adult-consent-actions">
            <button type="button" className="button button-primary button-small" onClick={confirm}>I am {legal.minimumAge} or older</button>
            <Link href="/acceptable-use">Content rules</Link>
          </div>
        </div>}
  </details>;
}
