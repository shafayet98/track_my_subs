# Rule: Security & privacy

This app reads people's email. Treat that access as a privilege with hard limits.

- **Gmail scope is read-only** (`gmail.readonly`). Never request write/send/delete
  scopes.
- **IMAP App Password path (conscious trade-off).** The local/self-hosted IMAP
  path (`integrations/email_imap.py`) avoids Google's restricted-scope
  verification by reading mail with a user-generated App Password instead of
  OAuth. An app password is a **full-mailbox** credential — broader than
  `gmail.readonly`'s narrow read-only scope — so this is a deliberate step back,
  taken only because we never write: the mailbox is opened with `readonly=True`
  (IMAP `EXAMINE`) and bodies are fetched with `BODY.PEEK`, so scanning never
  sets `\Seen` or mutates the mailbox. The app password is encrypted at rest
  (same `TOKEN_ENCRYPTION_KEY` path as OAuth tokens), server-side only, and never
  logged. All other rules below (parsed facts only, no raw bodies, tenant
  isolation) apply unchanged.
- **Store parsed facts only.** Never persist raw email bodies or full headers.
  The agent may read a body in-memory during a scan; it is discarded afterward.
  We store `source_message_id` for provenance/dedup — not content.
- **Secrets live server-side only.** `ANTHROPIC_API_KEY`, Google OAuth client
  secret, JWT secret, and the token-encryption key never reach the frontend and
  never get logged.
- **Encrypt OAuth refresh tokens at rest** using `TOKEN_ENCRYPTION_KEY`. Access
  tokens are short-lived and held in memory only.
- **Tenant isolation:** every user-data query filters on the authenticated
  `user_id`. Agent tool executors are bound to the current `user_id` and
  `scan_run_id` so the agent cannot read or write across tenants.
- **No secrets in the repo.** `.env` is git-ignored; commit `.env.example` with
  placeholder keys only.
- **Don't log PII or email content.** Log message IDs, counts, and statuses —
  not subjects or bodies.
- **Frontend never calls Gmail or Anthropic directly.** All third-party traffic
  is proxied through the backend.
