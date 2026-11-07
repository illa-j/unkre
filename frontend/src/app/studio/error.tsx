"use client";

import { StudioIcon } from "@/components/studio/studio-icon";
export default function StudioError({ reset }: { reset: () => void }) {
  return <div className="studio-empty"><StudioIcon name="image" size={32} /><h2>Let’s try that again.</h2><p>Something interrupted the workspace. Your saved data is still on this device.</p><button type="button" className="studio-button studio-button-primary" onClick={reset}>Try again</button></div>;
}
