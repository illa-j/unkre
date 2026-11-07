"use client";

import { api } from "./api";
import type { Generation } from "./api-types";

/**
 * Generated images live in this browser only: IndexedDB when it is available,
 * an in-memory map otherwise. The backend keeps the generation record, never
 * the file, and Runpod deletes results after a while — so a copy is taken the
 * first time the browser can reach the image.
 */
const databaseName = "unkre.library";
const storeName = "images";
const databaseVersion = 1;
const concurrency = 4;

const memory = new Map<string, Blob>();
const unavailable = new Set<string>();
const inflight = new Map<string, Promise<Blob | undefined>>();
const attempted = new Set<string>();
const listeners = new Set<() => void>();
let opening: Promise<IDBDatabase | null> | undefined;

const entryKey = (userId: string, id: string) => `${userId}:${id}`;

function notify() {
  for (const listener of listeners) listener();
}

export function subscribeLibrary(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

function openDatabase(): Promise<IDBDatabase | null> {
  if (typeof indexedDB === "undefined") return Promise.resolve(null);
  opening ??= new Promise<IDBDatabase | null>(resolve => {
    let request: IDBOpenDBRequest;
    try { request = indexedDB.open(databaseName, databaseVersion); } catch { resolve(null); return; }
    request.onupgradeneeded = () => {
      const store = request.result.createObjectStore(storeName, { keyPath: "key" });
      store.createIndex("userId", "userId", { unique: false });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => resolve(null);
    request.onblocked = () => resolve(null);
  });
  return opening;
}

function result<T>(request: IDBRequest<T>): Promise<T | undefined> {
  return new Promise(resolve => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => resolve(undefined);
  });
}

export async function readLocalImage(userId: string, id: string): Promise<Blob | undefined> {
  const key = entryKey(userId, id);
  const cached = memory.get(key);
  if (cached) return cached;
  const database = await openDatabase();
  if (!database) return undefined;
  try {
    const entry = await result(database.transaction(storeName, "readonly").objectStore(storeName).get(key) as IDBRequest<{ blob?: Blob } | undefined>);
    return entry?.blob;
  } catch { return undefined; }
}

export async function saveLocalImage(userId: string, id: string, blob: Blob): Promise<void> {
  const key = entryKey(userId, id);
  memory.set(key, blob);
  unavailable.delete(key);
  notify();
  const database = await openDatabase();
  if (!database) return;
  try {
    const transaction = database.transaction(storeName, "readwrite");
    transaction.objectStore(storeName).put({ key, userId, id, blob, savedAt: Date.now() });
  } catch { /* Quota or a blocked database: the in-memory copy still serves this session. */ }
}

export async function listLocalImageIds(userId: string): Promise<Set<string>> {
  const ids = new Set<string>();
  const prefix = `${userId}:`;
  for (const key of memory.keys()) if (key.startsWith(prefix)) ids.add(key.slice(prefix.length));
  const database = await openDatabase();
  if (database) {
    try {
      const keys = await result(database.transaction(storeName, "readonly").objectStore(storeName).index("userId").getAllKeys(userId) as IDBRequest<IDBValidKey[]>);
      for (const key of keys ?? []) if (String(key).startsWith(prefix)) ids.add(String(key).slice(prefix.length));
    } catch { /* Keep the in-memory list. */ }
  }
  return ids;
}

export async function deleteLocalImage(userId: string, id: string): Promise<void> {
  const key = entryKey(userId, id);
  memory.delete(key);
  unavailable.delete(key);
  attempted.delete(key);
  notify();
  const database = await openDatabase();
  if (!database) return;
  try { database.transaction(storeName, "readwrite").objectStore(storeName).delete(key); } catch { /* Nothing to remove. */ }
}

export function forgetUnavailableImage(userId: string, id: string): void {
  unavailable.delete(entryKey(userId, id));
  attempted.delete(entryKey(userId, id));
}

/** Resolves with the image the user owns: the local copy first, the provider second. */
export function loadGenerationImage(userId: string, generation: Pick<Generation, "id" | "status">): Promise<Blob | undefined> {
  if (generation.status !== "completed") return Promise.resolve(undefined);
  const key = entryKey(userId, generation.id);
  const running = inflight.get(key);
  if (running) return running;
  const task = (async () => {
    const cached = await readLocalImage(userId, generation.id);
    if (cached) return cached;
    if (unavailable.has(key)) return undefined;
    try {
      const blob = await api.image(generation.id);
      await saveLocalImage(userId, generation.id, blob);
      return blob;
    } catch {
      unavailable.add(key);
      notify();
      return undefined;
    }
  })().finally(() => inflight.delete(key));
  inflight.set(key, task);
  return task;
}

/** Copies every completed generation of this page into the browser, four at a time. */
export async function syncGenerationImages(userId: string, generations: Array<Pick<Generation, "id" | "status">>): Promise<void> {
  const queue = generations.filter(item => item.status === "completed" && !attempted.has(entryKey(userId, item.id)));
  for (const item of queue) attempted.add(entryKey(userId, item.id));
  const workers = Array.from({ length: Math.min(concurrency, queue.length) }, async () => {
    for (let item = queue.shift(); item; item = queue.shift()) await loadGenerationImage(userId, item);
  });
  await Promise.all(workers);
}
