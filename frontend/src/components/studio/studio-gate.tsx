"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { useAgeConsent } from "@/components/age-consent";
import { legal } from "@/lib/legal";

export function StudioGate({ children }: { children: ReactNode }) {
  const { adult, confirm } = useAgeConsent();
  const [checked, setChecked] = useState(false);

  if (adult) return children;

  return <div className="age-gate">
    <div className="age-gate-card" role="dialog" aria-modal="true" aria-labelledby="age-gate-title" aria-describedby="age-gate-description">
      <p className="eyebrow">ADULTS ONLY · {legal.minimumAge}+</p>
      <h1 id="age-gate-title">Your studio is for adults.</h1>
      <p id="age-gate-description">UNKRE creates realistic SFW and NSFW images, including images based on reference photos. Access is limited to adults who understand the content rules.</p>
      <ul>
        <li>I am at least {legal.minimumAge} years old.</li>
        <li>I will not use a minor, a non-consenting person or someone else’s private image.</li>
        <li>I accept the <Link href="/terms">Terms of Service</Link>, <Link href="/privacy">Privacy Policy</Link> and <Link href="/acceptable-use">Acceptable Use Policy</Link>.</li>
      </ul>
      <label className="age-gate-check">
        <input type="checkbox" checked={checked} onChange={event => setChecked(event.target.checked)} />
        <span>I confirm that I am {legal.minimumAge} or older and agree to these rules.</span>
      </label>
      <button type="button" className="button button-primary" disabled={!checked} onClick={confirm}>Enter Studio</button>
      <Link className="age-gate-leave" href="/">Leave this page</Link>
      <p className="age-gate-note">Your confirmation is stored in this browser. You can clear it through your browser’s site-data settings.</p>
    </div>
  </div>;
}
