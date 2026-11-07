"use client";

import Image from "next/image";
import { useRef, useState, type ChangeEvent } from "react";
import { errorMessage } from "@/lib/api";
import { StudioIcon } from "./studio-icon";

const MAX_PREVIEW_BYTES = 10 * 1024 * 1024;
const ACCEPTED = ["image/png", "image/jpeg", "image/webp"];

export function PresetPreviewUploader({ urls, onChange, upload, max = 20, disabled = false }: {
  urls: string[];
  onChange: (urls: string[]) => void;
  upload: (file: File) => Promise<{ url: string }>;
  max?: number;
  disabled?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  async function add(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;
    const room = max - urls.length;
    if (room <= 0) { setNote(`At most ${max} preview images are allowed.`); return; }
    setBusy(true); setNote("");
    const next = [...urls];
    try {
      for (const file of files.slice(0, room)) {
        if (!ACCEPTED.includes(file.type) || file.size > MAX_PREVIEW_BYTES) {
          setNote("Choose PNG, JPG or WebP images up to 10 MB each.");
          continue;
        }
        const stored = await upload(file);
        next.push(stored.url);
        onChange([...next]);
      }
    } catch (error) {
      setNote(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return <div className="preset-preview-uploader">
    {urls.length > 0 && <div className="preset-preview-grid">
      {urls.map((url, index) => <div className="preset-preview-thumb" key={`${url}-${index}`}>
        <Image src={url} alt={`Preset preview ${index + 1}`} width={160} height={200} unoptimized />
        <button type="button" className="preset-preview-remove" aria-label={`Remove preview ${index + 1}`} disabled={disabled || busy} onClick={() => onChange(urls.filter((_, itemIndex) => itemIndex !== index))}><StudioIcon name="close" size={13} /></button>
      </div>)}
    </div>}
    <input ref={input} className="preset-preview-input" type="file" accept="image/png,image/jpeg,image/webp" multiple tabIndex={-1} onChange={add} />
    <button type="button" className="preset-preview-add" disabled={disabled || busy || urls.length >= max} onClick={() => input.current?.click()}>
      <StudioIcon name="upload" size={18} />
      <span>{busy ? "Uploading…" : urls.length ? "Add another preview" : "Upload preview images"}<small>PNG, JPG or WebP · 10 MB each · {Math.max(0, max - urls.length)} left</small></span>
      <StudioIcon name="plus" size={15} />
    </button>
    {note && <p className="preset-preview-note" role="alert">{note}</p>}
  </div>;
}
