"use client";

import { useSession } from "../session-provider";

export function SessionNotice() {
  const session = useSession();
  if (session.loading) return <p className="studio-live-note" role="status">Opening your studio…</p>;
  if (session.error) return <div className="studio-api-notice" role="alert"><p>{session.error}</p><button type="button" className="studio-button" onClick={() => void session.reloadUser()}>Try again</button></div>;
  if (!session.user) return <div className="studio-api-notice"><p>Sign in to create images and access your account.</p><button type="button" className="studio-button studio-button-primary" onClick={() => session.openLogin()}>Sign in</button></div>;
  return null;
}
