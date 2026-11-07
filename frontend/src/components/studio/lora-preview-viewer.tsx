"use client";

import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import { StudioIcon } from "./studio-icon";

export type LoraPreviewRequest = {
  title: string;
  urls: string[];
  index?: number;
  isNsfw?: boolean;
  /** Shared by the LoRA catalog and the preset library. */
  kind?: "lora" | "preset";
};

export function LoraPreviewViewer({ preview, onClose }: { preview: LoraPreviewRequest | null; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [index, setIndex] = useState(preview?.index ?? 0);
  const count = preview?.urls.length ?? 0;

  useEffect(() => {
    if (!preview) return;
    const element = dialog.current;
    if (element && !element.open) element.showModal();
  }, [preview]);

  // Нативна подія close: React-проп onClose на <dialog> не спрацьовує,
  // тому закриття (хрестик, Escape) обробляємо напряму.
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    const handleClose = () => onClose();
    element.addEventListener("close", handleClose);
    return () => element.removeEventListener("close", handleClose);
  }, [onClose]);

  const step = useCallback((delta: number) => {
    if (!count) return;
    setIndex(current => (current + delta + count) % count);
  }, [count]);

  useEffect(() => {
    if (!preview) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "ArrowRight") {
        event.preventDefault();
        step(1);
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        step(-1);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [preview, step]);

  const current = preview?.urls[index];

  return <dialog ref={dialog} className="studio-lora-viewer" aria-labelledby="lora-viewer-title">
    {preview && current && <>
      <header className="studio-lora-viewer-head">
        <div>
          <p>{preview.kind === "preset" ? "Preset preview" : preview.isNsfw ? "NSFW preview · 18+" : "LoRA preview"}{count > 1 ? ` · ${index + 1} of ${count}` : ""}</p>
          <h2 id="lora-viewer-title">{preview.title}</h2>
        </div>
        <button type="button" className="studio-icon-button" aria-label="Close preview" onClick={() => { dialog.current?.close(); onClose(); }}><StudioIcon name="close" size={20} /></button>
      </header>
      <div className="studio-lora-viewer-stage">
        {count > 1 && <button type="button" className="studio-lora-viewer-nav is-previous" aria-label="Previous preview" onClick={() => step(-1)}><Chevron direction="left" /></button>}
        <Image key={current} src={current} alt={`${preview.title} preview ${index + 1} of ${count}`} width={1200} height={1400} unoptimized />
        {count > 1 && <button type="button" className="studio-lora-viewer-nav is-next" aria-label="Next preview" onClick={() => step(1)}><Chevron direction="right" /></button>}
        {count > 1 && <span className="studio-lora-viewer-count" aria-live="polite">{index + 1} / {count}</span>}
      </div>
      {count > 1 && <div className="studio-lora-viewer-thumbs" aria-label="LoRA previews">
        {preview.urls.map((url, position) => <button
          key={url}
          type="button"
          className="studio-lora-viewer-thumb"
          aria-label={`Show preview ${position + 1}`}
          aria-current={position === index ? "true" : undefined}
          onClick={() => setIndex(position)}
        >
          <Image src={url} alt="" width={160} height={120} unoptimized />
        </button>)}
      </div>}
    </>}
  </dialog>;
}

export function Chevron({ direction }: { direction: "left" | "right" }) {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={direction === "left" ? "m15 5-7 7 7 7" : "m9 5 7 7-7 7"} /></svg>;
}
