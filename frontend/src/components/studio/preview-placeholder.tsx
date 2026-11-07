"use client";

import { useEffect, useRef, useState } from "react";

export type PreviewState = "idle" | "submitting" | "pending" | "queued" | "processing" | "opening";

const messages: Record<PreviewState, [string, string]> = {
  idle: ["Imagine what comes next.", "Describe your idea. Make it yours."],
  submitting: ["Sending your idea.", "Preparing your generation request."],
  pending: ["Getting things ready.", "Your generation is being prepared."],
  queued: ["A little anticipation.", "Your image is in the queue."],
  processing: ["Taking shape.", "Your image is being generated."],
  opening: ["Almost in view.", "Loading your finished image."],
};

function DiffusionCanvas({ active, paused }: { active: boolean; paused: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pausedRef = useRef(paused);
  const syncRef = useRef<(() => void) | null>(null);
  useEffect(() => { pausedRef.current = paused; syncRef.current?.(); }, [paused]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let width = 0;
    let height = 0;
    let frame = 0;
    let elapsed = active ? 0 : 3.5;
    let previous = 0;
    let lastPaint = 0;
    let visible = false;
    let disposed = false;
    // Stable particle positions keep the composition intact across pauses and resizes.
    let randomSeed = 731;
    const random = () => { randomSeed = (randomSeed * 16807) % 2147483647; return (randomSeed - 1) / 2147483646; };
    const particles = Array.from({ length: 2400 }, (_, index) => {
      const u = random();
      const v = random();
      const angle = u * Math.PI * 2;
      const latitude = Math.acos(2 * v - 1);
      return {
        x: random() - .5, y: random() - .5,
        sphereX: Math.sin(latitude) * Math.cos(angle),
        sphereY: Math.cos(latitude),
        sphereZ: Math.sin(latitude) * Math.sin(angle),
        u, v, phase: random() * Math.PI * 2,
        size: index % 9 === 0 ? 1.7 : 1,
        brightness: .3 + random() * .7,
      };
    });

    function draw(time: number) {
      if (!context || !canvas || !width || !height) return;
      context.clearRect(0, 0, width, height);
      const scale = Math.min(width * .38, height * .35, 245);
      const centerX = width / 2;
      const centerY = height * .42;
      const cycle = time / (active ? 6 : 14);
      const gather = active ? .82 + Math.sin(time * .7) * .1 : Math.pow((1 - Math.cos(cycle * Math.PI * 2)) / 2, .65);
      const rotation = time * (active ? .16 : .065);
      const cos = Math.cos(rotation);
      const sin = Math.sin(rotation);
      const shape = Math.floor(cycle / 2) % 2;

      for (const p of particles) {
        const rotatedX = p.sphereX * cos + p.sphereZ * sin;
        const depth = -p.sphereX * sin + p.sphereZ * cos;
        // Idle alternates a breathing sphere and a rippling sheet; active resolves
        // a dense, portrait-shaped field with waves moving through its particles.
        const wave = Math.sin(p.u * 15 + time * .55) * Math.cos(p.v * 10 - time * .3);
        const targetX = active ? (p.u - .5) * 1.65 + wave * .09 : shape ? (p.u - .5) * 2.4 : rotatedX;
        const targetY = active ? (p.v - .5) * 2.1 + Math.sin(p.u * 9 + time) * .08 : shape ? (p.v - .5) * 1.6 + wave * .25 : p.sphereY;
        const scatterX = p.x * 3.4 + Math.sin(time * .15 + p.phase) * .18;
        const scatterY = p.y * 2.8 + Math.cos(time * .13 + p.phase) * .18;
        const x = centerX + (scatterX * (1 - gather) + targetX * gather) * scale;
        const y = centerY + (scatterY * (1 - gather) + targetY * gather) * scale;
        const scan = active ? Math.pow(Math.max(0, Math.cos(p.v * 8 - time * 1.7)), 8) : 0;
        const alpha = Math.min(.95, (.22 + gather * .5 + scan * .4) * p.brightness * (active ? 1 : .6 + (depth + 1) * .2));
        context.fillStyle = active && scan > .4 ? `rgba(244,210,170,${alpha})` : `rgba(${active ? "195,211,207" : "213,208,197"},${alpha})`;
        const size = p.size * (active ? 1 + scan * .45 : 1);
        context.fillRect(x, y, size, size);
      }
    }

    function tick(now: number) {
      frame = 0;
      if (disposed || !visible || document.hidden || pausedRef.current || motion.matches) return;
      if (previous) elapsed += Math.min(now - previous, 64) / 1000;
      previous = now;
      if (now - lastPaint >= 1000 / 30) { draw(elapsed); lastPaint = now; }
      frame = requestAnimationFrame(tick);
    }
    function sync() {
      cancelAnimationFrame(frame);
      frame = 0;
      previous = 0;
      if (disposed) return;
      if (pausedRef.current || motion.matches) draw(motion.matches ? (active ? 1 : 7) : elapsed);
      else if (visible && !document.hidden) frame = requestAnimationFrame(tick);
    }
    syncRef.current = sync;
    const resize = new ResizeObserver(([entry]) => {
      width = entry.contentRect.width;
      height = entry.contentRect.height;
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw(motion.matches ? (active ? 1 : 7) : elapsed);
    });
    const intersection = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; sync(); });
    resize.observe(canvas);
    intersection.observe(canvas);
    motion.addEventListener("change", sync);
    document.addEventListener("visibilitychange", sync);
    return () => {
      disposed = true;
      syncRef.current = null;
      cancelAnimationFrame(frame);
      resize.disconnect();
      intersection.disconnect();
      motion.removeEventListener("change", sync);
      document.removeEventListener("visibilitychange", sync);
    };
  }, [active]);

  return <canvas ref={canvasRef} className="studio-diffusion-canvas" aria-hidden="true" />;
}

export function PreviewPlaceholder({ state = "idle" }: { state?: PreviewState }) {
  const [paused, setPaused] = useState(false);
  const active = state !== "idle";
  const [title, description] = messages[state];

  return <div className={`studio-diffusion${active ? " is-generating" : ""}`} data-preview-state={state}>
    <DiffusionCanvas active={active} paused={paused} />
    <div className="studio-diffusion-caption">
      <span className="studio-diffusion-label">{active ? "CREATION IN MOTION" : "A SPACE FOR YOUR IDEAS"}</span>
      <h3>{title}</h3>
      <p role={active ? "status" : undefined}>{description}</p>
      {active && <p className="studio-diffusion-eta">Usually under a minute — up to 5 minutes at peak times.</p>}
      <button type="button" className="studio-preview-motion" aria-pressed={paused} onClick={() => setPaused(value => !value)}>{paused ? "Resume animation" : "Pause animation"}</button>
    </div>
  </div>;
}
