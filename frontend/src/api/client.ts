// Thin typed API client. Every component calls this — never `fetch` directly.
// Attaches the JWT, throws ApiError on non-2xx, and clears a stale token on 401.

import type {
  ConnectUrl,
  DashboardSummary,
  EmailAccount,
  NotificationPreferences,
  ScanRun,
  SubscriptionCard,
  SubscriptionDetail,
  TokenResponse,
  User,
} from "./types";

const BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

const TOKEN_KEY = "tms_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${BASE_URL}${path}`, { ...init, headers });

  if (res.status === 401) {
    clearToken();
    throw new ApiError(401, "Session expired. Please sign in again.");
  }

  if (!res.ok) {
    const detail = await res
      .json()
      .then((b) => (b as { detail?: string }).detail)
      .catch(() => undefined);
    throw new ApiError(res.status, detail ?? `Request failed (${res.status})`);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  // --- auth ---
  register: (email: string, password: string, name: string | null) =>
    request<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    }),
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<User>("/auth/me"),

  // --- accounts ---
  listAccounts: () => request<EmailAccount[]>("/accounts"),
  gmailConnectUrl: () => request<ConnectUrl>("/accounts/gmail/connect"),

  // --- scans ---
  startScan: () => request<ScanRun>("/scans", { method: "POST" }),
  getScan: (id: string) => request<ScanRun>(`/scans/${id}`),

  // --- dashboard ---
  dashboardSummary: () => request<DashboardSummary>("/dashboard/summary"),
  listSubscriptions: () => request<SubscriptionCard[]>("/subscriptions"),
  getSubscription: (id: string) =>
    request<SubscriptionDetail>(`/subscriptions/${id}`),

  // --- notification preferences ---
  getNotificationPreferences: () =>
    request<NotificationPreferences>("/notifications/preferences"),
  updateNotificationPreferences: (prefs: Partial<NotificationPreferences>) =>
    request<NotificationPreferences>("/notifications/preferences", {
      method: "PUT",
      body: JSON.stringify(prefs),
    }),
};
