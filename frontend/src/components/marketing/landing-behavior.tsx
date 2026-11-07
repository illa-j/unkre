"use client";

import { useEffect, useRef, useState } from "react";
import { CreateLink } from "./create-link";
import { ArrowIcon } from "../icons";
import { trackEvent } from "@/lib/analytics";

export function LandingBehavior() {
  const [visible, setVisible] = useState(false);
  const viewed = useRef(false);
  useEffect(() => {
    if (!viewed.current) { trackEvent("landing_view"); viewed.current = true; }
    const hero = document.getElementById("hero-action");
    const final = document.getElementById("create");
    if (!hero || !final) return;
    let heroVisible = true;
    let finalVisible = false;
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (entry.target === hero) heroVisible = entry.isIntersecting;
        if (entry.target === final) finalVisible = entry.isIntersecting;
      }
      setVisible(!heroVisible && !finalVisible && hero.getBoundingClientRect().bottom < 0);
    });
    observer.observe(hero); observer.observe(final);
    return () => observer.disconnect();
  }, []);
  return <div className={`mobile-create-bar${visible ? " is-visible" : ""}`} inert={!visible} aria-hidden={!visible}><span>Your next image starts here.</span><CreateLink placement="mobile_sticky">Create an image <ArrowIcon diagonal /></CreateLink></div>;
}
