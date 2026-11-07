"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import type { Generation } from "@/lib/api-types";
import { forgetUnavailableImage, loadGenerationImage } from "@/lib/local-images";
import { StudioIcon } from "./studio-icon";
import { PreviewPlaceholder } from "./preview-placeholder";

export const activeGeneration = (generation: Generation) => ["pending", "queued", "processing"].includes(generation.status);

export function GenerationArt({ generation, userId, download = false, animated = false }: { generation: Generation; userId?: string; download?: boolean; animated?: boolean }) {
  const [result, setResult] = useState<{ id: string; src?: string; missing?: boolean }>();
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (generation.status !== "completed" || !userId) return;
    let active = true;
    let src: string | undefined;
    loadGenerationImage(userId, { id: generation.id, status: generation.status }).then(blob => {
      if (!active) return;
      if (!blob) { setResult({ id: generation.id, missing: true }); return; }
      src = URL.createObjectURL(blob);
      setResult({ id: generation.id, src });
    }).catch(() => { if (active) setResult({ id: generation.id, missing: true }); });
    return () => { active = false; if (src) URL.revokeObjectURL(src); };
  }, [generation.id, generation.status, userId, revision]);
  const current = result?.id === generation.id ? result : undefined;
  return <div className={`studio-generation-art${animated ? " studio-generation-art-animated" : ""}${current?.missing ? " studio-generation-art-missing" : ""}`}>
    {current?.src ? <Image src={current.src} alt={generation.prompt} width={1024} height={1024} unoptimized /> : animated && !current?.missing && (activeGeneration(generation) || generation.status === "completed") ? <PreviewPlaceholder state={generation.status === "completed" ? "opening" : generation.status === "queued" ? "queued" : generation.status === "processing" ? "processing" : "pending"} /> : <div className="studio-generation-placeholder"><StudioIcon name="image" size={32} /><p role="status">{current?.missing ? "This image isn’t stored in this browser." : generation.status === "completed" ? "Opening your image…" : activeGeneration(generation) ? "Your image is on its way." : `Generation ${generation.status.replaceAll("_", " ")}.`}</p>{current?.missing && userId && <button type="button" className="studio-text-button" onClick={() => { forgetUnavailableImage(userId, generation.id); setRevision(value => value + 1); }}>Try again</button>}</div>}
    {download && current?.src && <div className="studio-generation-actions">
      <a className="studio-button studio-button-primary" href={current.src} download={`unkre-${generation.id}`}><StudioIcon name="download" size={17} /> Download image</a>
    </div>}
  </div>;
}
