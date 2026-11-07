"use client";

import Link from "next/link";
import { adminApi } from "@/lib/admin-api";
import { formatMoney, formatNumber, isoDay, statusTone } from "@/lib/admin-format";
import { useApiData } from "@/lib/use-api-data";
import { PageHead, StatCard, AsyncState } from "./admin-ui";

export function OverviewPage() {
  const data = useApiData("admin:overview", adminApi.overview, 30000, () => true);
  const overview = data.data;

  return <>
    <PageHead eyebrow="Control room" title="Overview" description="Live health of the store: people, generations and money." actions={<Link href="/admin/generations" className="admin-button admin-button-small">Active generations</Link>} />
    <AsyncState loading={data.loading} error={data.error} onRetry={data.reload} />
    {overview && <>
      <div className="admin-cards">
        <StatCard label="Users" value={formatNumber(overview.users_total)} note={<><b>{formatNumber(overview.users_new_7d)}</b> new in 7 days · <b>{formatNumber(overview.users_blocked)}</b> blocked</>} />
        <StatCard label="Generations" value={formatNumber(overview.generations_total)} note={<><b>{formatNumber(overview.generations_24h)}</b> today · <b>{formatNumber(overview.generations_active)}</b> in flight</>} />
        <StatCard label="Credits spent · 24h" value={formatNumber(overview.credits_spent_24h)} note={<><b>{formatNumber(overview.credits_spent_7d)}</b> in 7 days</>} />
        <StatCard label="Revenue · 30d" value={formatMoney(overview.revenue_30d, "USD")} note={<><b>{formatMoney(overview.revenue_total, "USD")}</b> all time · <b>{formatNumber(overview.credits_sold_30d)}</b> credits sold</>} emphasis />
        <StatCard label="Pending payments" value={formatNumber(overview.payments_pending)} note="Awaiting provider confirmation" />
        <StatCard label="Promo redemptions" value={formatNumber(overview.promo_redemptions)} note={<><b>{formatNumber(overview.users_new_30d)}</b> new users in 30 days</>} />
      </div>

      <div className="admin-panel">
        <div className="admin-panel-head">
          <div><h2>Last 14 days</h2><p>Generations created compared with new accounts.</p></div>
          <div className="admin-chart-legend"><span><i />Generations</span><span><i />New users</span></div>
        </div>
        <div className="admin-panel-body">
          <div className="admin-chart" role="img" aria-label="Daily generations and new users for the last 14 days">
            {(() => {
              const max = Math.max(1, ...overview.daily.map(item => Math.max(item.generations, item.users)));
              return overview.daily.map(point => {
              const generationHeight = Math.round((point.generations / max) * 110);
              const userHeight = Math.round((point.users / max) * 110);
              return <div className="admin-chart-col" key={point.date} title={`${point.date}: ${point.generations} generations, ${point.users} users, ${point.credits_spent} credits`}>
                <div className="admin-chart-bars">
                  <i style={{ height: Math.max(2, generationHeight) }} />
                  <i style={{ height: Math.max(2, userHeight) }} />
                </div>
                <small>{isoDay(point.date)}</small>
              </div>;
              });
            })()}
          </div>
        </div>
      </div>

      <div className="admin-split">
        <div className="admin-panel">
          <div className="admin-panel-head"><div><h2>Generation states</h2><p>All time, by lifecycle stage.</p></div></div>
          <div className="admin-panel-body"><div className="admin-statuses">{Object.entries(overview.generations_by_status).sort((a, b) => b[1] - a[1]).map(([status, count]) => <span key={status} className={`admin-badge admin-badge-${statusTone(status)}`}>{status.replaceAll("_", " ")} · {formatNumber(count)}</span>)}</div></div>
        </div>
        <div className="admin-panel">
          <div className="admin-panel-head"><div><h2>Jump back in</h2><p>The places you open most often.</p></div></div>
          <div className="admin-panel-body">
            <div className="admin-statuses">
              <Link href="/admin/users" className="admin-button admin-button-small">Blocked users</Link>
              <Link href="/admin/generations" className="admin-button admin-button-small">Failed generations</Link>
              <Link href="/admin/payments" className="admin-button admin-button-small">Pending payments</Link>
              <Link href="/admin/promos" className="admin-button admin-button-small">Promo codes</Link>
              <Link href="/admin/settings" className="admin-button admin-button-small">Pricing settings</Link>
            </div>
          </div>
        </div>
      </div>
    </>}
  </>;
}
