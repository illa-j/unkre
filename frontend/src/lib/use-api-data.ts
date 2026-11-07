"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "./api";

export function useApiData<T>(key: string | null, load: () => Promise<T>, interval = 0, pollWhile?: (data: T) => boolean) {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<{ key: string; data?: T; error?: string; loading: boolean }>();
  // Callers often pass inline closures. Reading them through refs keeps the
  // request effect keyed on `key`/`interval` instead of refetching on every
  // render, which previously caused a request loop and rate limiting.
  const loadRef = useRef(load);
  const pollWhileRef = useRef(pollWhile);

  useEffect(() => {
    loadRef.current = load;
    pollWhileRef.current = pollWhile;
  });

  useEffect(() => {
    if (!key) return;
    let active = true;
    let busy = false;
    let polling = true;
    async function run() {
      if (busy) return;
      busy = true;
      try {
        const data = await loadRef.current();
        polling = pollWhileRef.current ? pollWhileRef.current(data) : true;
        if (active) setState({ key: key!, data, loading: false });
      } catch (error) {
        polling = false;
        if (active) setState(current => ({ key: key!, data: current?.key === key ? current.data : undefined, error: errorMessage(error), loading: false }));
      } finally { busy = false; }
    }
    void run();
    const onFocus = () => { if (document.visibilityState === "visible") void run(); };
    window.addEventListener("focus", onFocus);
    const timer = interval ? setInterval(() => { if (polling && document.visibilityState === "visible") void run(); }, interval) : undefined;
    return () => { active = false; clearInterval(timer); window.removeEventListener("focus", onFocus); };
  }, [key, interval, revision]);
  const reload = useCallback(() => setRevision(value => value + 1), []);
  const current = state?.key === key ? state : undefined;
  return { data: current?.data, error: current?.error, loading: Boolean(key) && !current, reload };
}
