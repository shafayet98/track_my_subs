import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useFetch } from "../lib/useFetch";
import { money } from "../lib/format";
import { SpendChart } from "../components/SpendChart";
import { SubscriptionCardView } from "../components/SubscriptionCard";

export default function DashboardPage() {
  const summary = useFetch(() => api.dashboardSummary(), []);
  const subs = useFetch(() => api.listSubscriptions(), []);

  const delta =
    summary.data && summary.data.last_month > 0
      ? ((summary.data.this_month - summary.data.last_month) /
          summary.data.last_month) *
        100
      : null;

  return (
    <div className="page">
      <div className="page-head">
        <h2>Dashboard</h2>
        <Link className="btn" to="/connect">
          Connect &amp; scan
        </Link>
      </div>

      {summary.error && <div className="error">{summary.error}</div>}

      {summary.data && (
        <>
          <div className="stat-row">
            <div className="stat">
              <span className="stat-label">This month</span>
              <span className="stat-value">
                {money(summary.data.this_month, null)}
              </span>
              {delta !== null && (
                <span className={delta > 0 ? "down" : "up"}>
                  {delta > 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(0)}% vs last
                  month
                </span>
              )}
            </div>
            <div className="stat">
              <span className="stat-label">Last month</span>
              <span className="stat-value">
                {money(summary.data.last_month, null)}
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">Active subscriptions</span>
              <span className="stat-value">
                {summary.data.active_subscriptions}
              </span>
            </div>
          </div>

          <section className="panel">
            <h3>Spend (last 12 months)</h3>
            <SpendChart data={summary.data.monthly_spend} />
          </section>
        </>
      )}

      <section>
        <h3>Subscriptions</h3>
        {subs.loading && <p className="muted">Loading…</p>}
        {subs.error && <div className="error">{subs.error}</div>}
        {subs.data && subs.data.length === 0 && (
          <p className="muted">
            No subscriptions yet. <Link to="/connect">Connect Gmail</Link> and
            run a scan to populate your dashboard.
          </p>
        )}
        {subs.data && subs.data.length > 0 && (
          <div className="card-grid">
            {subs.data.map((c) => (
              <SubscriptionCardView key={c.id} card={c} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
