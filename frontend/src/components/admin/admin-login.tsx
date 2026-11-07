"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { adminApi } from "@/lib/admin-api";
import { errorMessage } from "@/lib/api";

export function AdminLogin() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    adminApi.me().then(() => { if (active) router.replace("/admin"); }).catch(() => { /* Stay on the form. */ });
    return () => { active = false; };
  }, [router]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setNote("");
    try {
      await adminApi.login(username.trim(), password);
      router.replace("/admin");
    } catch (error) {
      setNote(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return <div className="admin-login">
    <div className="admin-login-card">
      <Link href="/" className="wordmark" aria-label="UNKRE home">
        <Image className="wordmark-mark" src="/brand/unkre-mark-ui.webp" alt="" width={204} height={256} priority />
        unkre<span>.</span>
      </Link>
      <h1>Admin access</h1>
      <p>Sign in with an administrator account to manage the store.</p>
      <form onSubmit={submit}>
        <label className="admin-field">Username
          <input className="admin-input" name="username" autoComplete="username" required minLength={2} maxLength={100} value={username} onChange={event => setUsername(event.target.value)} />
        </label>
        <label className="admin-field">Password
          <input className="admin-input" name="password" type="password" autoComplete="current-password" required maxLength={1024} value={password} onChange={event => setPassword(event.target.value)} />
        </label>
        {note && <div className="admin-error" role="alert">{note}</div>}
        <button className="admin-button admin-button-primary" type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
      <p className="admin-login-foot">Access is restricted to invited administrators. Sessions expire automatically.</p>
    </div>
  </div>;
}
