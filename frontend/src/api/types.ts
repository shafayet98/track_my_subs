// Response/request shapes mirroring the backend Pydantic schemas.
// Keep these in sync with backend/app/schemas and the API routers.

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  name: string | null;
}

export interface EmailAccount {
  id: string;
  provider: string;
  email_address: string;
}

export interface ConnectUrl {
  authorization_url: string;
}

export interface ScanRun {
  id: string;
  status: string; // "running" | "succeeded" | "failed"
  emails_scanned: number;
  subscriptions_found: number;
  summary: string | null;
}

export interface MonthlySpend {
  month: string; // "YYYY-MM"
  total: number;
}

export interface DashboardSummary {
  monthly_spend: MonthlySpend[];
  this_month: number;
  last_month: number;
  active_subscriptions: number;
}

export interface SubscriptionCard {
  id: string;
  merchant_name: string;
  category: string | null;
  billing_cycle: string;
  amount: number | null;
  currency: string | null;
  status: string;
  next_payment_date: string | null; // ISO date
  next_payment_amount: number | null;
  total_spent: number;
  last_month_spent: number;
  overdue_total: number;
  missing_count: number;
}

export interface Payment {
  id: string;
  amount: number;
  currency: string | null;
  status: string; // "paid" | "upcoming" | "missing" | "overdue"
  occurred_on: string; // ISO date
  source_message_id: string | null;
}

export interface SubscriptionDetail extends SubscriptionCard {
  confidence: number | null;
  payments: Payment[];
}
