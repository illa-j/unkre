"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { adminApi } from "@/lib/admin-api";
import { Select } from "@/components/ui/select";
import { displayUser, formatDate, formatNumber } from "@/lib/admin-format";
import { UserAvatar } from "@/components/user-avatar";
import { errorMessage } from "@/lib/api";
import type { AdminUser } from "@/lib/admin-types";
import { useApiData } from "@/lib/use-api-data";
import { AdminForm, AsyncState, Badge, ErrorLine, PageHead, Pagination } from "./admin-ui";

const limit = 25;

export function UsersPage() {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [state, setState] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<AdminUser | null>(null);
  const [amount, setAmount] = useState("10");
  const [description, setDescription] = useState("Manual adjustment");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => { setQuery(search.trim()); setOffset(0); }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const load = useCallback(() => adminApi.users({ query, state, offset, limit }), [query, state, offset]);
  const data = useApiData(`admin:users:${query}:${state}:${offset}`, load);
  const users = data.data?.items ?? [];

  async function toggleBlock(user: AdminUser) {
    setError("");
    try {
      await adminApi.setBlocked(user.id, !user.is_blocked);
      data.reload();
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  function openCredits(user: AdminUser) {
    setSelected(user);
    setAmount("10");
    setDescription("Manual adjustment");
    setNote("");
    dialog.current?.showModal();
  }

  async function adjust(event: React.FormEvent) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setNote("");
    try {
      const result = await adminApi.adjustCredits(selected.id, Number(amount), description.trim());
      setNote(`Balance is now ${result.credits} credits.`);
      data.reload();
    } catch (cause) {
      setNote(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return <>
    <PageHead eyebrow="Accounts" title="Users" description="Search accounts, inspect balances and adjust access." />
    <div className="admin-panel">
      <div className="admin-panel-head">
        <div className="admin-toolbar" style={{ flex: 1 }}>
          <input className="admin-input admin-search" aria-label="Search users" placeholder="Search by name, username, email or Telegram ID…" value={search} onChange={event => setSearch(event.target.value)} />
          <Select className="admin-select" ariaLabel="Filter by state" value={state} options={[{ value: "", label: "All accounts" }, { value: "active", label: "Active" }, { value: "blocked", label: "Blocked" }]} onChange={value => { setState(value); setOffset(0); }} />
        </div>
        <span className="admin-card-note">{formatNumber(data.data?.total ?? 0)} accounts</span>
      </div>
      <ErrorLine error={error || data.error} />
      {data.loading && <AsyncState loading />}
      {data.data && users.length > 0 && <div className="admin-table-wrap">
        <table className="admin-table">
          <thead><tr><th>User</th><th>Credits</th><th>Generations</th><th>Spent</th><th>Registered</th><th>Last active</th><th>State</th><th /></tr></thead>
          <tbody>{users.map(user => <tr key={user.id}>
            <td><div className="admin-user"><UserAvatar name={displayUser(user.first_name, user.last_name, user.username)} photoUrl={user.photo_url} className="admin-avatar" size={30} /><span><span className="admin-user-name">{displayUser(user.first_name, user.last_name, user.username)}</span><span className="admin-user-meta">{user.google_email ?? (user.telegram_id ? `Telegram ${user.telegram_id}` : `@${user.username ?? "unknown"}`)}</span></span></div></td>
            <td className="num">{formatNumber(user.credits)}</td>
            <td className="num">{formatNumber(user.generations)}</td>
            <td className="num">{formatNumber(user.credits_spent)}</td>
            <td className="muted">{formatDate(user.registered_at)}</td>
            <td className="muted">{formatDate(user.last_active_at)}</td>
            <td>{user.is_blocked ? <Badge value="blocked" /> : <Badge value="active" />}</td>
            <td><div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}><button type="button" className="admin-button admin-button-small" onClick={() => openCredits(user)}>Credits</button><button type="button" className={`admin-button admin-button-small${user.is_blocked ? "" : " admin-button-danger"}`} onClick={() => void toggleBlock(user)}>{user.is_blocked ? "Unblock" : "Block"}</button></div></td>
          </tr>)}</tbody>
        </table>
      </div>}
      {data.data && !users.length && <AsyncState loading={false} empty={<><h2>No accounts found</h2><p>Try a different search or filter.</p></>} />}
      {data.data && <Pagination total={data.data.total} offset={offset} limit={limit} onChange={setOffset} />}
    </div>

    <dialog ref={dialog} className="admin-dialog" aria-labelledby="credits-title">
      <h2 id="credits-title">Adjust credits</h2>
      <p>{selected ? displayUser(selected.first_name, selected.last_name, selected.username) : ""} · {formatNumber(selected?.credits ?? 0)} credits right now.</p>
      <AdminForm onSubmit={adjust} actions={<><button type="button" className="admin-button" onClick={() => dialog.current?.close()}>Close</button>
          <button type="submit" className="admin-button admin-button-primary" disabled={busy}>{busy ? "Saving…" : "Apply"}</button></>}>
        <label className="admin-field">Amount <span className="admin-card-note">Positive adds, negative deducts.</span>
          <input className="admin-input" type="number" required step="1" value={amount} onChange={event => setAmount(event.target.value)} />
        </label>
        <label className="admin-field">Reason
          <input className="admin-input" required minLength={3} maxLength={200} value={description} onChange={event => setDescription(event.target.value)} />
        </label>
        {note && <div className={note.startsWith("Balance") ? "admin-note" : "admin-error"} role="status">{note}</div>}
        
      </AdminForm>
    </dialog>
  </>;
}
