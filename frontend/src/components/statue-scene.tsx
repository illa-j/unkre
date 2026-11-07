"use client";

import Image from "next/image";
import { useEffect, useRef } from "react";
import { outlineWords } from "@/lib/outline-words";

const clamp = (value: number, min = 0, max = 1) => Math.min(max, Math.max(min, value));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

const chapterTones = [
  { id: "intro", color: [9, 14, 18] },
  { id: "references", color: [12, 24, 27] },
  { id: "models", color: [10, 21, 30] },
  { id: "loras", color: [27, 14, 24] },
  { id: "create", color: [28, 21, 16] },
] as const;

export function StatueScene() {
  const sceneRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const scene = sceneRef.current;
    const shell = scene?.closest<HTMLElement>("[data-scene-shell]");
    if (!scene || !shell) return;
    const sections = chapterTones.map(({ id }) => shell.querySelector<HTMLElement>(`#${id}`));
    const words = Array.from(scene.querySelectorAll<SVGSVGElement>("[data-scene-word]"));
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    const pointerFine = matchMedia("(hover: hover) and (pointer: fine)");
    const compact = matchMedia("(max-width: 760px)");
    let frame = 0;
    let previousTime = 0;
    let visible = true;
    let position = { x: 0, y: 0, progress: 0, tone: 0 };
    const target = { x: 0, y: 0, progress: 0, tone: 0 };

    function paint() {
      if (!scene) return;
      const middle = Math.sin(position.progress * Math.PI);
      scene.style.setProperty("--pointer-x", `${position.x * 12}px`);
      scene.style.setProperty("--pointer-y", `${position.y * 8}px`);
      scene.style.setProperty("--pointer-rotate", `${position.x * 1.1}deg`);
      scene.style.setProperty("--light-x", `${position.x * 150}px`);
      scene.style.setProperty("--light-y", `${position.y * 110}px`);
      scene.style.setProperty("--scene-scale", `${1 - middle * 0.27}`);
      scene.style.setProperty("--scene-x", `${middle * 22}%`);
      scene.style.setProperty("--statue-light", `${0.69 + middle * 0.08}`);
      scene.style.setProperty("--statue-opacity", `${0.88 - middle * 0.2}`);
      const index = Math.floor(position.tone);
      const from = chapterTones[index].color;
      const to = chapterTones[Math.min(index + 1, chapterTones.length - 1)].color;
      const tone = from.map((channel, i) => lerp(channel, to[i], position.tone - index).toFixed(2)).join(" ");
      scene.style.setProperty("--scene-tone", tone);
      shell!.style.setProperty("--scene-tone", tone);
      words.forEach((word, i) => {
        word.style.opacity = `${clamp(1 - Math.abs(position.tone - i))}`;
      });
    }

    function tick(time: number) {
      frame = 0;
      if (!visible || document.hidden || reduced.matches) return;
      const dt = previousTime ? Math.min(time - previousTime, 64) : 16;
      previousTime = time;
      const t = 1 - Math.exp(-dt / 135);
      position = {
        x: lerp(position.x, target.x, t),
        y: lerp(position.y, target.y, t),
        progress: lerp(position.progress, target.progress, t),
        tone: lerp(position.tone, target.tone, t),
      };
      paint();
      if (Math.abs(position.x - target.x) + Math.abs(position.y - target.y) + Math.abs(position.progress - target.progress) + Math.abs(position.tone - target.tone) > 0.0005) requestTick();
    }

    function requestTick() {
      if (!frame && visible && !document.hidden && !reduced.matches) frame = requestAnimationFrame(tick);
    }

    function updateScroll() {
      const height = innerHeight;
      const shellBounds = shell!.getBoundingClientRect();
      target.progress = clamp(-shellBounds.top / Math.max(1, shellBounds.height - height));
      target.tone = 0;
      for (let i = 1; i < sections.length; i++) {
        const section = sections[i];
        if (!section) continue;
        // Blend across most of the viewport instead of switching at a section boundary.
        const blend = clamp((height * 0.9 - section.getBoundingClientRect().top) / (height * 0.8));
        if (blend === 0) break;
        target.tone = i - 1 + blend * blend * (3 - 2 * blend);
        if (blend < 1) break;
      }
      requestTick();
    }

    function pointer(event: PointerEvent) {
      if (compact.matches || !pointerFine.matches || event.pointerType === "touch") return;
      target.x = clamp(event.clientX / innerWidth * 2 - 1, -1, 1);
      target.y = clamp(event.clientY / innerHeight * 2 - 1, -1, 1);
      requestTick();
    }

    function resetPointer() { target.x = target.y = 0; requestTick(); }
    function preferencesChanged() {
      cancelAnimationFrame(frame);
      frame = previousTime = 0;
      position = { x: 0, y: 0, progress: 0, tone: 0 };
      target.x = target.y = 0;
      paint();
      updateScroll();
    }
    function visibilityChanged() {
      cancelAnimationFrame(frame);
      frame = previousTime = 0;
      if (!document.hidden) updateScroll();
    }

    const visibilityObserver = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible) updateScroll();
      else { cancelAnimationFrame(frame); frame = 0; }
    });
    visibilityObserver.observe(shell);
    const resizeObserver = new ResizeObserver(updateScroll);
    resizeObserver.observe(shell);

    updateScroll();
    window.addEventListener("scroll", updateScroll, { passive: true });
    window.addEventListener("resize", updateScroll, { passive: true });
    window.addEventListener("pointermove", pointer, { passive: true });
    window.addEventListener("blur", resetPointer);
    document.documentElement.addEventListener("pointerleave", resetPointer);
    document.addEventListener("visibilitychange", visibilityChanged);
    reduced.addEventListener("change", preferencesChanged);
    pointerFine.addEventListener("change", resetPointer);
    compact.addEventListener("change", resetPointer);
    return () => {
      cancelAnimationFrame(frame);
      visibilityObserver.disconnect();
      resizeObserver.disconnect();
      window.removeEventListener("scroll", updateScroll);
      window.removeEventListener("resize", updateScroll);
      window.removeEventListener("pointermove", pointer);
      window.removeEventListener("blur", resetPointer);
      document.documentElement.removeEventListener("pointerleave", resetPointer);
      document.removeEventListener("visibilitychange", visibilityChanged);
      reduced.removeEventListener("change", preferencesChanged);
      pointerFine.removeEventListener("change", resetPointer);
      compact.removeEventListener("change", resetPointer);
    };
  }, []);

  return (
    <div className="scene-track" aria-hidden="true">
      <div ref={sceneRef} className="scene-stage">
        <div className="scene-typography">
          {chapterTones.map(({ id }) => {
            const outline = outlineWords[id];
            return (
              <svg
                key={id}
                className={`scene-word scene-word-${id}`}
                data-scene-word
                data-word={outline.label}
                viewBox={`0 0 ${outline.width} 330`}
                preserveAspectRatio="xMinYMid meet"
                style={{ width: `calc(var(--word-size) * ${outline.width / 240})` }}
                focusable="false"
              >
                <path d={outline.path} fill="none" stroke="currentColor" strokeWidth="1" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
              </svg>
            );
          })}
        </div>
        <div className="statue-scroll-layer">
          <div className="statue-glow" />
          <div className="statue-arc" />
          <div className="statue-pointer-layer">
            <Image src="/images/muse.webp" fill alt="" className="statue-image" sizes="(max-width: 760px) 45vw, 30vw" quality={85} loading="eager" fetchPriority="low" />
          </div>
        </div>
        <div className="scene-legibility" />
      </div>
    </div>
  );
}
