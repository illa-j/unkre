"use client";

import { useSyncExternalStore } from "react";

const storageKey = "unkre.reference-consent.v1";
const changeEvent = "unkre:reference-consent-change";
let memoryConsent = false;

export function hasReferenceConsent(): boolean {
  if (memoryConsent) return true;
  try {
    return localStorage.getItem(storageKey) === "1";
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

export function setReferenceConsent(value: boolean) {
  memoryConsent = value;
  try {
    if (value) localStorage.setItem(storageKey, "1");
    else localStorage.removeItem(storageKey);
  } catch { /* The confirmation still applies to this page view. */ }
  window.dispatchEvent(new Event(changeEvent));
}

export function useReferenceConsent() {
  return useSyncExternalStore(subscribe, hasReferenceConsent, () => false);
}
