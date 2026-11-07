"use client";

import Image from "next/image";
import { useState } from "react";

export function UserAvatar({ name, photoUrl, className = "", size = 35 }: { name: string; photoUrl?: string | null; className?: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  const initials = name.trim().split(/\s+/).slice(0, 2).map(part => part[0]?.toUpperCase() ?? "").join("") || "U";
  return <span className={`user-avatar ${className}`.trim()} style={{ width: size, height: size }} aria-hidden="true">
    {photoUrl && !failed
      ? <Image src={photoUrl} alt="" width={size} height={size} unoptimized onError={() => setFailed(true)} />
      : initials}
  </span>;
}
