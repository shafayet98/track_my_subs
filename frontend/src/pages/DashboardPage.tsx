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
      </div>

      {summary.error && <div className="error">{summary.error}</div>}

      {summary.data && (
        <div className="summary-grid">
          <div className="summary-card">
            <div className="summary-hero">
              <div className="label">This month</div>
              <div className="hero-value">
                {money(summary.data.this_month, null)}
              </div>
              {delta !== null && (
                <span className={`delta ${delta > 0 ? "down" : "up"}`}>
                  {delta > 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(0)}% vs last
                  month
                </span>
              )}
            </div>
            <div className="summary-sub">
              <div>
                <div className="label">Last month</div>
                <div className="sub-value">
                  {money(summary.data.last_month, null)}
                </div>
              </div>
              <div>
                <div className="label">Active</div>
                <div className="sub-value">
                  {summary.data.active_subscriptions} subs
                </div>
              </div>
            </div>
          </div>

          <section className="chart-card">
            <div className="chart-head">
              <h3>Spend</h3>
              <span className="muted">last 12 months</span>
            </div>
            <SpendChart data={summary.data.monthly_spend} />
          </section>
        </div>
      )}

      <section>
        <div className="section-head">
          <h3>Subscriptions</h3>
          {subs.data && subs.data.length > 0 && (
            <span className="count">{subs.data.length}</span>
          )}
        </div>
        {subs.loading && <p className="empty">Loading…</p>}
        {subs.error && <div className="error">{subs.error}</div>}
        {subs.data && subs.data.length === 0 && (
          <div className="panel">
            <p className="empty">
              No subscriptions yet. <Link to="/connect">Connect Gmail</Link> and
              run a scan to populate your dashboard.
            </p>
          </div>
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
