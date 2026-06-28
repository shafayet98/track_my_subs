# Plan: IMAP + App Password email access

## Context

`docs/local-app-email-access.md` asks how to avoid Google's OAuth
verification + CASA burden for the restricted `gmail.readonly` scope. The doc's
recommended answer (Path 1) is to drop OAuth entirely and read mail over **IMAP
with a user-generated App Password**. This kills the Google verification problem
outright, onboards in one step (paste a 16-char password), and works with **any**
IMAP provider — not just Gmail.

This is feasible and **contained**: the agent half (tools schemas, prompts) does
not change. Only the email-fetch layer, account selection, and connect flow swap
from Gmail-API-over-OAuth to IMAP. Confirmed consumers of the email layer:

- `backend/app/agent/loop.py:103-126` — selects `provider=="gmail"` accounts with
  `oauth_refresh_token_encrypted`, then `GmailClient.from_refresh_token` →
  `search_candidates(after=...)`. **This selection + client build changes.**
- `backend/app/agent/tools.py:159` — `ScanContext.gmail: GmailClient`; used at
  `tools.py:199` as `ctx.gmail.get_email(message_id)` (duck-typed — only needs
  `get_email`).
- `backend/app/api/accounts.py` — connect/callback OAuth flow.
- `backend/app/api/scans.py:45` — gates scan on stored credential presence.
- `backend/app/models/email_account.py` — stores encrypted credential (nullable).
- `backend/app/core/security.py:84,88` — `encrypt_token` / `decrypt_token` reused
  verbatim for the app password.

## Scope

**In:** an IMAP email client mirroring the current `GmailClient` interface;
a connect-account endpoint that accepts host/email/app-password instead of OAuth;
encrypted-at-rest storage of the app password; wiring in loop/tools/scans;
a `security.md` amendment documenting the credential trade-off; tests.

**Out:** removing the existing Gmail OAuth code in this PR (leave it; flip the
default to IMAP). Provider auto-detection beyond a host field. Frontend redesign
beyond the connect form. Anything in the agent loop/prompts/tools schemas.

## Approach

### 0. Shared interface — `EmailReader` Protocol

Define a `typing.Protocol` (`EmailReader`) with `search_candidates(*, after)` and
`get_email(message_id)`. Retype `ScanContext.gmail: EmailReader` (keep the field
**name** `gmail` so `tools.py:199` needs zero change). `GmailClient` and the new
`ImapClient` both satisfy it structurally — no inheritance needed.

### 1. New email layer — `backend/app/integrations/email_imap.py`

Reuse the **same dataclasses and method names** so tool/loop call sites are
untouched: import/share `EmailCandidate`, `EmailContent`, and expose
`search_candidates(*, after)` and `get_email(message_id)`.

- Use Python stdlib `imaplib` + `email` (no new heavy dep). `imaplib.IMAP4_SSL`
  to `imap.gmail.com:993`, login with email + app password.
- `search_candidates`: translate `CANDIDATE_QUERY` into IMAP `SEARCH` criteria.
  IMAP has no Gmail-style OR-text query, so either:
  - use Gmail's `X-GM-RAW` extension (`SEARCH X-GM-RAW "<gmail query>"`) when
    host is Gmail — reuses the exact existing heuristic; OR
  - generic fallback: `OR SUBJECT "receipt" SUBJECT "invoice" ...` for non-Gmail.
  Fetch only headers (`BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)]`) for triage
  — never bodies, preserving the "no body during triage" rule.
  `message_id` = use the IMAP UID (stable per mailbox) as the provenance id.
- `get_email`: `UID FETCH <uid> BODY.PEEK[]`, parse with
  `email.message_from_bytes`, walk parts with `msg.walk()`/`get_content_type()`,
  prefer `text/plain` else strip `text/html` with BeautifulSoup. Note: the
  existing `_collect_bodies`/`_extract_plaintext` walk the **Gmail-API payload
  dict** shape, so they can't be reused verbatim — write a small parallel walker
  over `email.message.Message`, but reuse the existing `MAX_BODY_CHARS` cap and
  the same HTML-strip + per-line `.strip()` normalization (factor that tail into a
  shared `_normalize_text(text)` helper used by both clients). Use `BODY.PEEK`
  (not `BODY`) so the `\Seen` flag is never set — preserves read-only behavior.

### 2. Model + storage — `email_account.py`

Add nullable columns (Alembic migration):
- `imap_host: str | None`
- `app_password_encrypted: str | None`  (reuse `core.security.encrypt_token` /
  `decrypt_token` — same encryption path as the OAuth refresh token today).

Keep `oauth_refresh_token_encrypted` for the legacy path. `provider` already
exists (set to `imap` or the provider name).

### 3. Connect flow — `accounts.py`

Add `POST /accounts/imap/connect` (Pydantic body
`{email_address, app_password, imap_host?}`; default host from a new
`settings.imap_default_host="imap.gmail.com"` in `core/config.py`). Auth-guarded
via `get_current_user` — no `state` round-trip (user posts directly, unlike the
OAuth callback). Validate by attempting `IMAP4_SSL` login in `run_in_threadpool`
before storing; on failure → 400. On success, upsert `EmailAccount`
(provider `"imap"`) with the encrypted password, mirroring the upsert in
`gmail_callback` (accounts.py:69-88).

### 4. Wiring

- `loop.py:103-126`: change account selection from `provider=="gmail"` +
  `oauth_refresh_token_encrypted` to selecting accounts that carry **either**
  credential, and per account build the matching client: IMAP
  (`ImapClient.from_credentials(host, email, decrypt_token(app_password_encrypted))`)
  when the app password is set, else the existing `GmailClient.from_refresh_token`.
  This keeps both paths working (doc: "leave OAuth, flip default to IMAP"). The
  per-mailbox loop comment about message ids stays valid — IMAP UIDs are
  mailbox-scoped, so each `ScanContext` must stay scoped to one account.
- `tools.py:159`: retype `ScanContext.gmail: EmailReader` (field name unchanged →
  `tools.py:199` `ctx.gmail.get_email` untouched).
- `scans.py:45`: gate on having any usable credential
  (`app_password_encrypted or oauth_refresh_token_encrypted`).

### 5. Security rule amendment — `.claude/rules/security.md`

Document the conscious trade: the IMAP app password is a **full-mailbox**
credential (we only ever read, using `BODY.PEEK` so messages stay unread), a
deliberate step back from `gmail.readonly`'s narrow scope, chosen to eliminate
Google verification for a local/self-hosted deployment. Reiterate: encrypted at
rest, server-side only, never logged, parsed facts only (no raw bodies stored).

### 6. Plan/progress docs

Per repo rules: add `docs/plans/Imap_email_access.md` (task plan) and a
`.claude/progress.md` entry before the PR.

## Steps

1. Branch `feat/imap-email-access`; write `docs/plans/Imap_email_access.md`.
2. `EmailReader` Protocol + `email_imap.py` — client, shared dataclasses, MIME
   walker over `email.message.Message`, shared `_normalize_text` tail.
3. Model columns + Alembic migration.
4. `POST /accounts/imap/connect` with login validation + encrypted upsert.
5. Wire loop.py / tools.py / scans.py to the IMAP client.
6. Amend `security.md`.
7. Tests — fake the IMAP boundary like `test_gmail.py` fakes the Google builder
   (no network, per coding-standards):
   - `backend/tests/test_imap.py` — a fake `IMAP4_SSL` returning canned
     `search`/`uid fetch` responses. Cover: candidate query build, `get_email`
     MIME extraction (plain + html-fallback), `BODY.PEEK` used (assert no `\Seen`
     store), `MAX_BODY_CHARS` cap.
   - IMAP connect cases alongside `test_accounts_oauth.py` (or a new
     `test_accounts_imap.py`): valid login stores **encrypted** password
     (assert via `decrypt_token`), bad login → 400, requires auth → 401.
   - `test_agent_loop.py` / `test_scans.py`: extend so an IMAP-credential account
     scans end-to-end with the fake client.
8. `.claude/progress.md` entry.

## Acceptance criteria

- User connects a mailbox with email + app password; a scan runs end-to-end and
  records subscriptions/payments — no Google Cloud project, no OAuth consent.
- Triage fetches headers only; bodies fetched only via `get_email`; messages
  stay unread (`BODY.PEEK`); no raw body persisted.
- App password stored encrypted; never logged.
- Agent loop/tools/prompts unchanged in behavior.
- Tests pass with `imaplib` mocked.

## Verification

- Unit: `cd backend && uv run pytest` — IMAP client + connect endpoint tests.
- Manual: generate a Gmail App Password, connect via the new endpoint, trigger a
  scan, confirm dashboard populates. Confirm scanned messages remain unread in
  Gmail (validates `BODY.PEEK`).
