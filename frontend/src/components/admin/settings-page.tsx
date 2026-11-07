"use client";

import { useState } from "react";
import { adminApi } from "@/lib/admin-api";
import { errorMessage } from "@/lib/api";
import type { SystemSetting } from "@/lib/admin-types";
import { useApiData } from "@/lib/use-api-data";
import { AsyncState, ErrorLine, PageHead } from "./admin-ui";

const groups: Record<string, string> = {
  registration: "Registration",
  referral: "Referrals",
  payments: "Payments",
};

function inputValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

function parseValue(raw: string, sample: unknown): unknown {
  const value = raw.trim();
  if (!value) return null;
  if (typeof sample === "number" || sample === null) {
    return /^-?\d+(\.\d+)?$/.test(value) ? Number(value) : value;
  }
  return value;
}

export function SettingsPage() {
  const data = useApiData("admin:settings", adminApi.settings);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  async function save(item: SystemSetting) {
    setBusy(item.key);
    setNote("");
    setError("");
    try {
      const raw = edits[item.key] ?? inputValue(item.value);
      await adminApi.saveSetting(item.key, parseValue(raw, item.default));
      setNote(`${item.key} saved.`);
      setEdits(current => { const next = { ...current }; delete next[item.key]; return next; });
      data.reload();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy("");
    }
  }

  async function reset(item: SystemSetting) {
    setBusy(item.key);
    setNote("");
    setError("");
    try {
      await adminApi.resetSetting(item.key);
      setNote(`${item.key} reset to the built-in default.`);
      setEdits(current => { const next = { ...current }; delete next[item.key]; return next; });
      data.reload();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy("");
    }
  }

  const settings = data.data ?? [];
  const sections = Object.keys(groups).map(prefix => ({ prefix, label: groups[prefix], items: settings.filter(item => item.key.startsWith(`${prefix}.`)) })).filter(section => section.items.length);

  return <>
    <PageHead eyebrow="Configuration" title="Settings" description="Runtime values with built-in defaults. Changes apply immediately." />
    <ErrorLine error={error || data.error} />
    {note && <div className="admin-note" role="status">{note}</div>}
    {data.loading && <AsyncState loading />}
    {sections.map(section => <div className="admin-panel" key={section.prefix}>
      <div className="admin-panel-head"><div><h2>{section.label}</h2><p>Override defaults without a redeploy.</p></div></div>
      <div className="admin-panel-body admin-settings-group">
        {section.items.map(item => <div className="admin-setting" key={item.key}>
          <div>
            <code>{item.key}</code>
            <p>{item.description}</p>
            <small>{item.source === "database" ? "Overridden in the panel" : "Built-in default"}{item.default !== null ? ` · default ${String(item.default)}` : " · disabled by default"}</small>
          </div>
          <div className="admin-setting-actions">
            <input className="admin-input" aria-label={item.key} value={edits[item.key] ?? inputValue(item.value)} placeholder={item.default === null ? "empty" : String(item.default)} onChange={event => setEdits(current => ({ ...current, [item.key]: event.target.value }))} />
            <div style={{ display: "flex", gap: 6 }}>
              <button type="button" className="admin-button admin-button-small admin-button-primary" style={{ flex: 1, justifyContent: "center" }} disabled={busy === item.key} onClick={() => void save(item)}>{busy === item.key ? "Saving…" : "Save"}</button>
              <button type="button" className="admin-button admin-button-small" disabled={busy === item.key || item.source !== "database"} onClick={() => void reset(item)}>Reset</button>
            </div>
          </div>
        </div>)}
      </div>
    </div>)}
    {!data.loading && !settings.length && <div className="admin-panel"><AsyncState loading={false} empty={<><h2>No settings available</h2><p>The API did not return any editable keys.</p></>} /></div>}
  </>;
}
