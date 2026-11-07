"use client";

import { useRef, useState } from "react";
import { adminApi } from "@/lib/admin-api";
import { formatDate } from "@/lib/admin-format";
import { errorMessage } from "@/lib/api";
import { useApiData } from "@/lib/use-api-data";
import { AdminForm, AsyncState, ErrorLine, PageHead } from "./admin-ui";

export function TeamPage() {
  const data = useApiData("admin:team", adminApi.team);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isOwner, setIsOwner] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);

  function openCreate() {
    setUsername("");
    setPassword("");
    setIsOwner(false);
    setNote("");
    dialog.current?.showModal();
  }

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setNote("");
    try {
      await adminApi.createTeamMember({ username: username.trim(), password, is_owner: isOwner });
      dialog.current?.close();
      data.reload();
    } catch (cause) {
      setNote(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  const denied = Boolean(data.error && (data.error.includes("owner") || data.error.includes("403")));

  return <>
    <PageHead eyebrow="Access" title="Team" description="Administrator accounts and owner rights." actions={<button type="button" className="admin-button admin-button-primary admin-button-small" onClick={openCreate}>Add administrator</button>} />
    <ErrorLine error={denied ? undefined : data.error} />
    {denied && <div className="admin-note">Only owner accounts can view and manage the team.</div>}
    {data.loading && <AsyncState loading />}
    {data.data && <div className="admin-panel">
      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead><tr><th>Account</th><th>Role</th><th>Created</th></tr></thead>
          <tbody>{data.data.items.map(item => <tr key={item.id}>
            <td><span className="admin-user-name">{item.username}</span><span className="admin-user-meta">{item.id.slice(0, 8)}</span></td>
            <td><span className="admin-user-name" style={{ fontSize: 12.5 }}>{item.is_owner ? "Owner" : "Administrator"}</span></td>
            <td className="muted">{formatDate(item.created_at)}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </div>}

    <dialog ref={dialog} className="admin-dialog" aria-labelledby="team-create-title">
      <h2 id="team-create-title">New administrator</h2>
      <p>Share the credentials over a secure channel. The password is stored hashed.</p>
      <AdminForm onSubmit={create} actions={<><button type="button" className="admin-button" onClick={() => dialog.current?.close()}>Cancel</button>
          <button type="submit" className="admin-button admin-button-primary" disabled={busy}>{busy ? "Creating…" : "Create"}</button></>}>
        <label className="admin-field">Username
          <input className="admin-input" required minLength={2} maxLength={100} value={username} onChange={event => setUsername(event.target.value)} />
        </label>
        <label className="admin-field">Password
          <input className="admin-input" type="password" autoComplete="new-password" required minLength={10} maxLength={1024} value={password} onChange={event => setPassword(event.target.value)} />
        </label>
        <label className="admin-field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <input type="checkbox" checked={isOwner} onChange={event => setIsOwner(event.target.checked)} /> Owner rights
        </label>
        {note && <div className="admin-error" role="alert">{note}</div>}
        
      </AdminForm>
    </dialog>
  </>;
}
