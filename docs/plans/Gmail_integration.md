# Gmail integration (Phase 3)

## Goal

Let a user connect a Gmail account via Google OAuth2 (read-only) and give the
backend the ability to (a) find candidate subscription emails with a heuristic
search and (b) fetch a single email's headers + trimmed plaintext body for the
agent to read in-memory. This unblocks Phase 4 (the agent), which consumes these
two read-only operations as tools.

## Scope

In scope:

- `integrations/gmail.py`: OAuth helpers (build consent URL, exchange code for a
  refresh token + email address, build credentials from a stored refresh token)
  and a `GmailClient` with `search_candidates()` and `get_email()`.
- Wire `GET /api/accounts/gmail/connect` and `/gmail/callback` to the real flow.
  Connect returns the consent URL; callback exchanges the code and stores the
  **encrypted** refresh token in `email_accounts` (upsert per email address).
- Signed, short-lived OAuth `state` carrying the `user_id` (the callback is hit
  by the browser, unauthenticated) — added to `core/security.py`.
- Tests with the Gmail boundary mocked: candidate search shape, `get_email`
  HTML→plaintext + length cap, connect URL, callback upsert + token encryption,
  and tenant scoping / bad-state rejection.

Out of scope:

- The agent loop and tools (Phase 4) — this only provides the integration.
- Live network calls in tests / CI (always mocked).
- Scheduled re-scans, multi-provider email.

## Approach

- **No raw bodies persisted** (`.claude/rules/security.md`): candidate search
  uses Gmail `format="metadata"` (From/Subject/Date only); `get_email` returns a
  trimmed plaintext body for in-memory use; only `source_message_id` is ever
  stored (on `payments`, later). Scope is `gmail.readonly` only.
- **OAuth**: `google_auth_oauthlib.flow.Flow.from_client_config` builds the
  consent URL and exchanges the code (pure string-building for the URL; network
  only on exchange). `access_type=offline` + `prompt=consent` so we get a
  refresh token. The email address comes from `users().getProfile`.
- **Sync SDK off the event loop**: googleapiclient/oauthlib are synchronous, so
  the callback runs `exchange_code` via `run_in_threadpool`.
- **State**: a dedicated short-lived JWT with a `purpose` claim (not an auth
  token), signed with `JWT_SECRET`.
- **Testability**: `GmailClient` wraps a googleapiclient `service`; tests inject
  a tiny fake service (the real `users().messages().list()/get()` builder shape),
  and patch `gmail.exchange_code` for the callback test.

## Steps

1. Plan (this file) + branch `feat/gmail-integration`.
2. `core/security.py`: `create_oauth_state` / `verify_oauth_state`.
3. `integrations/__init__.py`, `integrations/gmail.py` (OAuth + `GmailClient`).
4. Wire `api/accounts.py` connect + callback; upsert encrypted token.
5. Tests: `test_gmail.py` (client parsing) + `test_accounts_oauth.py` (endpoints).
6. `ruff check` / `ruff format`, run the full suite.
7. Update `.claude/progress.md`, open PR.

## Acceptance criteria

- A user can hit `/gmail/connect` and get a Google consent URL; the callback
  stores an encrypted refresh token and records the account (upsert).
- `search_candidates` returns lightweight candidates (id/from/subject/date) from
  a heuristic query; `get_email` returns headers + capped plaintext (HTML
  stripped); no raw body is persisted.
- `uv run pytest` green and `uv run ruff check` clean; no live network in tests.
