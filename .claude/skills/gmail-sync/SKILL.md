---
name: gmail-sync
description: How Gmail OAuth and email fetching work in this repo — connecting an account, the read-only scope, candidate-email search heuristics, and token storage. Read before touching backend/app/integrations/gmail.py or the accounts API.
---

# Gmail sync

We connect Gmail via Google OAuth2 with the **read-only** scope and use the
Gmail API to find and fetch candidate subscription emails. Privacy rules in
`.claude/rules/security.md` are binding here.

## OAuth flow

- Scope: `https://www.googleapis.com/auth/gmail.readonly` only.
- `GET /api/accounts/gmail/connect` → builds Google's consent URL (state =
  signed `user_id`) and returns it; the SPA redirects the user there.
- `GET /api/accounts/gmail/callback` → exchanges the code, stores the
  **encrypted** refresh token in `email_accounts`, and records the account.
- Access tokens are short-lived and refreshed in memory per scan; never stored.
- Client id/secret come from `GOOGLE_OAUTH_CLIENT_ID` /
  `GOOGLE_OAUTH_CLIENT_SECRET`.

## Candidate-email search (the pre-filter)

`integrations/gmail.py` runs the heuristic narrowing before the LLM is involved:

- Gmail search queries combining subscription signals, e.g.:
  `subscription OR receipt OR invoice OR "payment received" OR "your plan" OR
  renewal OR "payment failed"`.
- Optionally restrict by date window (e.g. last 12–18 months) for the spend
  charts.
- Known-merchant senders can be added to widen recall (netflix.com,
  aws.amazon.com, stan.com.au, etc.).

The function returns lightweight candidates — `message_id`, `from`, `subject`,
`date` — which the agent summarizes and triages. The agent calls `get_email`
only for the ones worth reading.

## Fetching one email

`get_email(message_id)` returns headers + a trimmed **plaintext** body for the
agent to inspect. Strip HTML to text; cap length. Do not return raw MIME, and
do not persist the body anywhere.

## Storage

- Only `source_message_id` is stored on `payments` (provenance + dedup).
- Use it to avoid double-recording a payment across re-scans.

## Testing

Mock the Gmail client. Provide fixture emails (a clean receipt, a renewal
notice, a failed-payment alert, a non-subscription newsletter) and assert the
candidate search + `get_email` shape. Never hit the real Gmail API in tests.
