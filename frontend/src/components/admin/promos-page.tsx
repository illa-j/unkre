"use client";

import { useRef, useState } from "react";
import { adminApi } from "@/lib/admin-api";
import { formatDate, formatNumber } from "@/lib/admin-format";
import { errorMessage } from "@/lib/api";
import type { AdminPromoCode, AdminRedemptionPage } from "@/lib/admin-types";
import { useApiData } from "@/lib/use-api-data";
import { AdminForm, AsyncState, Badge, ErrorLine, PageHead } from "./admin-ui";

export function PromosPage() {
  const data = useApiData("admin:promos", adminApi.promoCodes);
  const [code, setCode] = useState("");
  const [credits, setCredits] = useState("25");
  const [maxRedemptions, setMaxRedemptions] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [redemptions, setRedemptions] = useState<AdminRedemptionPage | null>(null);
  const [redemptionCode, setRedemptionCode] = useState<AdminPromoCode | null>(null);
  const createDialog = useRef<HTMLDialogElement>(null);
  const redemptionsDialog = useRef<HTMLDialogElement>(null);

  function openCreate() {
    setCode("");
    setCredits("25");
    setMaxRedemptions("");
    setExpiresAt("");
    setNote("");
    createDialog.current?.showModal();
  }

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setNote("");
    try {
      await adminApi.createPromoCode({
        code: code.trim().toUpperCase(),
        credits: Number(credits),
        max_redemptions: maxRedemptions ? Number(maxRedemptions) : null,
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
        is_active: true,
      });
      createDialog.current?.close();
      data.reload();
    } catch (cause) {
      setNote(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function toggle(item: AdminPromoCode) {
    setNote("");
    try {
      await adminApi.setPromoActive(item.id, !item.is_active);
      data.reload();
    } catch (cause) {
      setNote(errorMessage(cause));
    }
  }

  async function viewRedemptions(item: AdminPromoCode) {
    setRedemptionCode(item);
    setRedemptions(null);
    redemptionsDialog.current?.showModal();
    try {
      setRedemptions(await adminApi.redemptions(item.id));
    } catch (cause) {
      setNote(errorMessage(cause));
    }
  }

  return <>
    <PageHead eyebrow="Growth" title="Promo codes" description="Hand out credits without a payment." actions={<button type="button" className="admin-button admin-button-primary admin-button-small" onClick={openCreate}>Create code</button>} />
    <ErrorLine error={data.error} />
    {data.loading && <AsyncState loading />}
    {data.data && data.data.length > 0 && <div className="admin-panel">
      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead><tr><th>Code</th><th>Credits</th><th>Redeemed</th><th>Expires</th><th>Created</th><th>State</th><th /></tr></thead>
          <tbody>{data.data.map(item => <tr key={item.id}>
            <td><span className="admin-user-name" style={{ letterSpacing: ".08em" }}>{item.code}</span></td>
            <td className="num">{formatNumber(item.credits)}</td>
            <td className="num">{formatNumber(item.redeemed_count)}{item.max_redemptions ? ` / ${formatNumber(item.max_redemptions)}` : ""}</td>
            <td className="muted">{formatDate(item.expires_at)}</td>
            <td className="muted">{formatDate(item.created_at)}</td>
            <td><Badge value={item.is_active ? "active" : "cancelled"} /></td>
            <td><div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}><button type="button" className="admin-button admin-button-small" onClick={() => void viewRedemptions(item)}>Redemptions</button><button type="button" className="admin-button admin-button-small" onClick={() => void toggle(item)}>{item.is_active ? "Disable" : "Enable"}</button></div></td>
          </tr>)}</tbody>
        </table>
      </div>
    </div>}
    {data.data && !data.data.length && <div className="admin-panel"><AsyncState loading={false} empty={<><h2>No promo codes yet</h2><p>Create the first code to hand out credits.</p></>} /></div>}
    {note && <div className="admin-error" role="alert">{note}</div>}

    <dialog ref={createDialog} className="admin-dialog" aria-labelledby="promo-create-title">
      <h2 id="promo-create-title">New promo code</h2>
      <p>Codes are case-insensitive for users and must be unique.</p>
      <AdminForm onSubmit={create} actions={<><button type="button" className="admin-button" onClick={() => createDialog.current?.close()}>Cancel</button>
          <button type="submit" className="admin-button admin-button-primary" disabled={busy}>{busy ? "Creating…" : "Create"}</button></>}>
        <label className="admin-field">Code
          <input className="admin-input" required minLength={3} maxLength={64} value={code} onChange={event => setCode(event.target.value.toUpperCase())} placeholder="WELCOME25" />
        </label>
        <label className="admin-field">Credits
          <input className="admin-input" required type="number" min={1} max={2147483647} step={1} value={credits} onChange={event => setCredits(event.target.value)} />
        </label>
        <label className="admin-field">Max redemptions <span className="admin-card-note">Leave empty for unlimited.</span>
          <input className="admin-input" type="number" min={1} max={2147483647} step={1} value={maxRedemptions} onChange={event => setMaxRedemptions(event.target.value)} />
        </label>
        <label className="admin-field">Expires at <span className="admin-card-note">Leave empty to never expire.</span>
          <input className="admin-input" type="datetime-local" value={expiresAt} onChange={event => setExpiresAt(event.target.value)} />
        </label>
        {note && <div className="admin-error" role="alert">{note}</div>}
        
      </AdminForm>
    </dialog>

    <dialog ref={redemptionsDialog} className="admin-dialog" style={{ width: "min(620px, calc(100vw - 32px))" }} aria-labelledby="redemptions-title">
      <h2 id="redemptions-title">Redemptions</h2>
      <p>{redemptionCode?.code} · {formatNumber(redemptionCode?.redeemed_count ?? 0)} redeemed</p>
      <div className="admin-table-wrap" style={{ marginTop: 14 }}>
        {!redemptions && <p style={{ padding: "18px 0" }}>Loading…</p>}
        {redemptions && redemptions.items.length > 0 && <table className="admin-table">
          <thead><tr><th>User</th><th>Credits</th><th>Redeemed</th></tr></thead>
          <tbody>{redemptions.items.map(item => <tr key={item.id}>
            <td><span className="admin-user-name">{item.user_name}</span><span className="admin-user-meta">{item.user_email ?? item.user_id.slice(0, 8)}</span></td>
            <td className="num">{formatNumber(item.credits)}</td>
            <td className="muted">{formatDate(item.created_at)}</td>
          </tr>)}</tbody>
        </table>}
        {redemptions && !redemptions.items.length && <p style={{ padding: "18px 0" }}>Nobody has redeemed this code yet.</p>}
      </div>
      <div className="admin-dialog-actions"><button type="button" className="admin-button" onClick={() => redemptionsDialog.current?.close()}>Close</button></div>
    </dialog>
  </>;
}
