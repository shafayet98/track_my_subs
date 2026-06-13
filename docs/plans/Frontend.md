# Plan: Frontend (Phase 6)

## Goal

A React + Vite + TypeScript SPA that drives the whole flow end-to-end: register/
login, connect a Gmail account, kick off a scan and poll it, then view the
dashboard (spend chart + subscription cards) and a per-subscription detail page.
The browser talks only to the FastAPI backend — never to Gmail or Anthropic.

## Scope

- `frontend/` project: Vite + React + TS, `react-router-dom`, `recharts`.
- One typed API client (`src/api/`) wrapping `fetch` with the JWT; response types
  mirror the backend Pydantic schemas.
- Auth: login/register page, JWT in `localStorage`, an `AuthContext`, a protected-
  route wrapper.
- Pages:
  - **ConnectAccount** — list connected accounts, "Connect Gmail" (redirect to
    the consent URL from `/accounts/gmail/connect`), "Scan now" (`POST /scans`
    then poll `GET /scans/{id}` until terminal), handle the `?gmail=connected`
    return.
  - **Dashboard** — `GET /dashboard/summary` (12-month Recharts spend chart +
    this/last-month + active count) and `GET /subscriptions` (card grid).
  - **SubscriptionDetail** — `GET /subscriptions/{id}`: totals, next payment,
    overdue/missing, payment history.
- CI: add a `frontend` job (install → typecheck/lint → build) and commit the
  lockfile so `npm ci` is reproducible.

### Out of scope

- Styling beyond a clean, minimal stylesheet (no UI framework).
- Tests (no frontend test runner this phase — the build + typecheck is the gate).
- Real Google OAuth credentials / live scans (those need secrets; the UI works
  against whatever the backend returns).

## Approach

- **API base URL** via `import.meta.env.VITE_API_BASE_URL`, default
  `http://localhost:8000/api`. CORS already allows `http://localhost:5173`.
- Thin client: `request()` attaches `Authorization: Bearer <token>`, throws a
  typed `ApiError` on non-2xx (401 → clear token + redirect to login).
- Keep presentational components (cards, chart) dumb; pages fetch via hooks.
- The OAuth callback redirects the browser to `{frontend_origin}/?gmail=connected`
  — the ConnectAccount page reads that query param to show a success note and
  refresh the account list.
- Scan polling: after `POST /scans`, poll `GET /scans/{id}` every ~2s until
  `status` is `succeeded`/`failed`, then refresh the dashboard.

## Steps

1. Scaffold `frontend/` (package.json, tsconfig, vite config, index.html, eslint).
2. API client + types (`src/api/`).
3. Auth context + login/register page + protected route.
4. App shell + routing (`main.tsx`, `App.tsx`, nav).
5. ConnectAccount, Dashboard (chart + cards), SubscriptionDetail pages.
6. Minimal styling.
7. `npm install`, `npm run build` (typecheck + bundle) until green; commit lockfile.
8. Add the frontend CI job; verify the workflow locally (lint + build).

## Acceptance criteria

- `npm run build` (tsc + vite build) is green; `npm run lint` clean.
- App runs locally: register → login → connect Gmail → scan → dashboard charts +
  cards → detail page (against the local backend).
- CI runs both backend and frontend jobs on PRs to `main`.
