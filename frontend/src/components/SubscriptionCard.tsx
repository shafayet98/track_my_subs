import { Link } from "react-router-dom";
import type { SubscriptionCard as Card } from "../api/types";
import { initials, isoDate, money } from "../lib/format";

export function SubscriptionCardView({ card }: { card: Card }) {
  const hasIssues = card.missing_count > 0;
  return (
    <Link to={`/subscriptions/${card.id}`} className="card">
      <div className="card-head">
        <span className="avatar">{initials(card.merchant_name)}</span>
        <span className="card-title">{card.merchant_name}</span>
        <span className={`pill pill-${card.status}`}>{card.status}</span>
      </div>
      <div className="card-amount">
        {money(card.amount, card.currency)}
        <span className="per"> / {card.billing_cycle}</span>
      </div>
      <dl className="card-stats">
        <div>
          <dt>Total spent</dt>
          <dd>{money(card.total_spent, card.currency)}</dd>
        </div>
        <div>
          <dt>Last month</dt>
          <dd>{money(card.last_month_spent, card.currency)}</dd>
        </div>
        <div>
          <dt>Next payment</dt>
          <dd>{isoDate(card.next_payment_date)}</dd>
        </div>
      </dl>
      {hasIssues && (
        <div className="card-warn">
          {card.missing_count} missing/overdue
          {card.overdue_total > 0 &&
            ` · ${money(card.overdue_total, card.currency)} overdue`}
        </div>
      )}
    </Link>
  );
}
