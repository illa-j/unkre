"use client";

import { useCallback, useState } from "react";
import { adminApi } from "@/lib/admin-api";
import { Select } from "@/components/ui/select";
import { formatDateTime, formatMoney, formatNumber } from "@/lib/admin-format";
import { useApiData } from "@/lib/use-api-data";
import { AsyncState, Badge, ErrorLine, PageHead, Pagination } from "./admin-ui";

const limit = 25;
const states = ["pending", "processing", "succeeded", "failed", "expired", "cancelled", "refunded"];

export function PaymentsPage() {
  const [state, setState] = useState("");
  const [provider, setProvider] = useState("");
  const [offset, setOffset] = useState(0);

  const load = useCallback(() => adminApi.payments({ state, provider, offset, limit }), [state, provider, offset]);
  const data = useApiData(`admin:payments:${state}:${provider}:${offset}`, load);

  return <>
    <PageHead eyebrow="Revenue" title="Payments" description="Credit purchases through Telegram Stars and crypto." />
    <div className="admin-panel">
      <div className="admin-panel-head">
        <div className="admin-toolbar" style={{ flex: 1 }}>
          <Select className="admin-select" ariaLabel="Filter by status" value={state} options={[{ value: "", label: "All states" }, ...states.map(item => ({ value: item, label: item.replaceAll("_", " ") }))]} onChange={value => { setState(value); setOffset(0); }} />
          <Select className="admin-select" ariaLabel="Filter by provider" value={provider} options={[{ value: "", label: "All providers" }, { value: "telegram_stars", label: "Telegram Stars" }, { value: "atlos", label: "Crypto (Atlos)" }]} onChange={value => { setProvider(value); setOffset(0); }} />
        </div>
        <span className="admin-card-note">{formatNumber(data.data?.total ?? 0)} payments</span>
      </div>
      <ErrorLine error={data.error} />
      {data.loading && <AsyncState loading />}
      {data.data && data.data.items.length > 0 && <div className="admin-table-wrap">
        <table className="admin-table">
          <thead><tr><th>User</th><th>Provider</th><th>State</th><th>Credits</th><th>Amount</th><th>Created</th><th>Paid</th></tr></thead>
          <tbody>{data.data.items.map(item => <tr key={item.id}>
            <td><span className="admin-user-name">{item.user_name}</span><span className="admin-user-meta">{item.user_id.slice(0, 8)}</span></td>
            <td className="muted">{item.provider.replaceAll("_", " ")}</td>
            <td><Badge value={item.status} /></td>
            <td className="num">{formatNumber(item.credits)}</td>
            <td className="num">{formatMoney(item.paid_amount ?? item.amount, item.currency)}</td>
            <td className="muted">{formatDateTime(item.created_at)}</td>
            <td className="muted">{formatDateTime(item.paid_at)}</td>
          </tr>)}</tbody>
        </table>
      </div>}
      {data.data && !data.data.items.length && <AsyncState loading={false} empty={<><h2>No payments found</h2><p>Try another provider or state.</p></>} />}
      {data.data && <Pagination total={data.data.total} offset={offset} limit={limit} onChange={setOffset} />}
    </div>
  </>;
}
