"use client";

import type { FormEvent, ReactNode } from "react";
import { errorMessage } from "@/lib/api";
import { statusTone } from "@/lib/admin-format";

export function PageHead({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description?: string; actions?: ReactNode }) {
  return <div className="admin-page-head">
    <div><span className="admin-eyebrow">{eyebrow}</span><h1>{title}</h1>{description && <p>{description}</p>}</div>
    {actions && <div className="admin-topbar-actions">{actions}</div>}
  </div>;
}

export function StatCard({ label, value, note, emphasis }: { label: string; value: string | number; note?: ReactNode; emphasis?: boolean }) {
  return <div className={`admin-card${emphasis ? " admin-card-em" : ""}`}>
    <span className="admin-card-label">{label}</span>
    <span className="admin-card-value">{value}</span>
    {note && <span className="admin-card-note">{note}</span>}
  </div>;
}

export function Badge({ value }: { value: string }) {
  return <span className={`admin-badge admin-badge-${statusTone(value)}`}>{value.replaceAll("_", " ")}</span>;
}

export function AsyncState({ loading, error, onRetry, empty }: { loading: boolean; error?: string; onRetry?: () => void; empty?: ReactNode }) {
  if (error) return <div className="admin-error" role="alert">{error}<button type="button" className="admin-link" onClick={onRetry} style={{ marginLeft: 10 }}>Try again</button></div>;
  if (loading) return <div className="admin-empty"><p>Loading…</p></div>;
  return empty ? <div className="admin-empty">{empty}</div> : null;
}

export function Pagination({ total, offset, limit, onChange }: { total: number; offset: number; limit: number; onChange: (offset: number) => void }) {
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, total);
  return <div className="admin-pagination">
    <span>{from}–{to} of {total}</span>
    <div>
      <button type="button" className="admin-button admin-button-small" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>Previous</button>
      <button type="button" className="admin-button admin-button-small" disabled={to >= total} onClick={() => onChange(offset + limit)}>Next</button>
    </div>
  </div>;
}

export function ErrorLine({ error }: { error: unknown }) {
  return error ? <div className="admin-error" role="alert">{errorMessage(error)}</div> : null;
}

export function AdminForm({ onSubmit, children, actions }: { onSubmit: (event: FormEvent<HTMLFormElement>) => void; children: ReactNode; actions: ReactNode }) {
  return <form onSubmit={onSubmit} className="admin-dialog-form">
    <div className="admin-dialog-body">{children}</div>
    <div className="admin-dialog-actions">{actions}</div>
  </form>;
}
