"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi } from "@/lib/admin-api";
import { Select } from "@/components/ui/select";
import { workflowTitle } from "@/lib/catalog";
import { formatDateTime, formatNumber } from "@/lib/admin-format";
import { useApiData } from "@/lib/use-api-data";
import { AsyncState, Badge, ErrorLine, PageHead, Pagination } from "./admin-ui";

const limit = 25;
const states = ["pending", "queued", "processing", "completed", "failed", "cancelled", "timed_out"];

export function GenerationsPage() {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [state, setState] = useState("");
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => { setQuery(search.trim()); setOffset(0); }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const load = useCallback(() => adminApi.generations({ state, query, offset, limit }), [state, query, offset]);
  const data = useApiData(`admin:generations:${state}:${query}:${offset}`, load, 15000, page => page.items.some(item => ["pending", "queued", "processing"].includes(item.status)));

  return <>
    <PageHead eyebrow="Activity" title="Generations" description="Every request, its model, spend and outcome." />
    <div className="admin-panel">
      <div className="admin-panel-head">
        <div className="admin-toolbar" style={{ flex: 1 }}>
          <input className="admin-input admin-search" aria-label="Search generations" placeholder="Search prompts or users…" value={search} onChange={event => setSearch(event.target.value)} />
          <Select className="admin-select" ariaLabel="Filter by status" value={state} options={[{ value: "", label: "All states" }, ...states.map(item => ({ value: item, label: item.replaceAll("_", " ") }))]} onChange={value => { setState(value); setOffset(0); }} />
        </div>
        <span className="admin-card-note">{formatNumber(data.data?.total ?? 0)} generations</span>
      </div>
      <ErrorLine error={data.error} />
      {data.loading && <AsyncState loading />}
      {data.data && data.data.items.length > 0 && <div className="admin-table-wrap">
        <table className="admin-table">
          <thead><tr><th>Prompt</th><th>User</th><th>Model</th><th>State</th><th>Credits</th><th>Seed</th><th>Created</th></tr></thead>
          <tbody>{data.data.items.map(item => <tr key={item.id}>
            <td><span className="admin-prompt">{item.prompt}</span>{item.error && <span className="admin-user-meta" style={{ color: "#e7a598" }}>{item.error}</span>}</td>
            <td><span className="admin-user-name">{item.user_name}</span><span className="admin-user-meta">{item.user_email ?? item.user_id.slice(0, 8)}</span></td>
            <td className="muted">{workflowTitle({ name: item.workflow })}</td>
            <td><Badge value={item.status} /></td>
            <td className="num">{item.credits_spent == null ? "—" : formatNumber(item.credits_spent)}</td>
            <td className="muted num">{item.seed ?? "random"}</td>
            <td className="muted">{formatDateTime(item.created_at)}</td>
          </tr>)}</tbody>
        </table>
      </div>}
      {data.data && !data.data.items.length && <AsyncState loading={false} empty={<><h2>No generations found</h2><p>Try a different search or state.</p></>} />}
      {data.data && <Pagination total={data.data.total} offset={offset} limit={limit} onChange={setOffset} />}
    </div>
  </>;
}
