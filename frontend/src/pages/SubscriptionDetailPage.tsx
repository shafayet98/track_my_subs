import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useFetch } from "../lib/useFetch";
import { isoDate, money } from "../lib/format";

export default function SubscriptionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, error, loading } = useFetch(
    () => api.getSubscription(id!),
    [id],
  );

  if (loading) return <div className="page muted">Loading…</div>;
  if (error) return <div className="page error">{error}</div>;
  if (!data) return null;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <Link to="/" className="muted">
            ← Dashboard
          </Link>
          <h2>{data.merchant_name}</h2>
        </div>
        <span className={`pill pill-${data.status}`}>{data.status}</span>
      </div>

      <div className="stat-row">
        <div className="stat">
          <span className="stat-label">Total spent</span>
          <span className="stat-value">
            {money(data.total_spent, data.currency)}
          </span>
        </div>
        <div className="stat">
          <span className="stat-label">Last month</span>
          <span className="stat-value">
            {money(data.last_month_spent, data.currency)}
          </span>
        </div>
        <div className="stat">
          <span className="stat-label">Next payment</span>
          <span className="stat-value">{isoDate(data.next_payment_date)}</span>
          <span className="muted">
            {money(data.next_payment_amount, data.currency)}
          </span>
        </div>
        <div className="stat">
          <span className="stat-label">Overdue</span>
          <span className="stat-value">
            {money(data.overdue_total, data.currency)}
          </span>
          <span className="muted">{data.missing_count} missing/overdue</span>
        </div>
      </div>

      <section className="panel">
        <h3>Details</h3>
        <dl className="detail-grid">
          <div>
            <dt>Billing cycle</dt>
            <dd>{data.billing_cycle}</dd>
          </div>
          <div>
            <dt>Expected amount</dt>
            <dd>{money(data.amount, data.currency)}</dd>
          </div>
          <div>
            <dt>Category</dt>
            <dd>{data.category ?? "—"}</dd>
          </div>
          <div>
            <dt>Confidence</dt>
            <dd>
              {data.confidence !== null
                ? `${Math.round(data.confidence * 100)}%`
                : "—"}
            </dd>
          </div>
        </dl>
      </section>

      <section className="panel">
        <h3>Payment history</h3>
        {data.payments.length === 0 ? (
          <p className="muted">No payments recorded yet.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Amount</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.payments.map((p) => (
                <tr key={p.id}>
                  <td>{isoDate(p.occurred_on)}</td>
                  <td>{money(p.amount, p.currency)}</td>
                  <td>
                    <span className={`pill pill-${p.status}`}>{p.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
