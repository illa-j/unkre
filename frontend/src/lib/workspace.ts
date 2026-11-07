"use client";

import { useMemo, useSyncExternalStore } from "react";
import { defaultWorkspace, readWorkspace, type Workspace } from "./studio";

const storageKey = "unkre.workspace.v1";
const changeEvent = "unkre:workspace-change";
const initialSnapshot = JSON.stringify(defaultWorkspace);
let memorySnapshot = initialSnapshot;
let storageUnavailable = false;

function getSnapshot() {
  if (storageUnavailable) return memorySnapshot;
  try { memorySnapshot = localStorage.getItem(storageKey) ?? memorySnapshot; } catch { storageUnavailable = true; }
  return memorySnapshot;
}
function subscribe(listener: () => void) {
  function onStorage(event: StorageEvent) { if (event.key === storageKey || event.key === null) { memorySnapshot = initialSnapshot; listener(); } }
  window.addEventListener("storage", onStorage);
  window.addEventListener(changeEvent, listener);
  return () => { window.removeEventListener("storage", onStorage); window.removeEventListener(changeEvent, listener); };
}

export function useWorkspace() {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, () => initialSnapshot);
  return useMemo(() => readWorkspace(snapshot), [snapshot]);
}

export function updateWorkspace(updater: (workspace: Workspace) => Workspace) {
  memorySnapshot = JSON.stringify(updater(readWorkspace(getSnapshot())));
  let persistent = true;
  try { localStorage.setItem(storageKey, memorySnapshot); } catch { persistent = false; storageUnavailable = true; }
  window.dispatchEvent(new Event(changeEvent));
  return persistent;
}

export function toggleFavorite(id: string) {
  updateWorkspace(workspace => ({ ...workspace, favorites: workspace.favorites.includes(id) ? workspace.favorites.filter(item => item !== id) : [...workspace.favorites, id] }));
}

export function resetWorkspace() { return updateWorkspace(() => defaultWorkspace); }

const subscribeHydration = () => () => {};
export function useWorkspaceReady() { return useSyncExternalStore(subscribeHydration, () => true, () => false); }
