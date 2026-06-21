# Scan all connected accounts + remove the 100-email candidate cap (#23)

## Goal

Make a scan **comprehensive**: cover every connected Gmail mailbox for the user,
and within the lookback window take *all* matching candidate emails instead of
just the first 100. Aggregate the results into the one scan run.

## Scope

- **Part A** — `GmailClient.search_candidates` paginates the full window
  (follow `nextPageToken`), no fixed cap. Drop the `max_results` argument.
- **Part B** — `run_scan_job` iterates every connected Gmail account, runs the
  agent loop per account (each with its own client/token-scoped `ScanContext`),
  and aggregates `emails_scanned` / `subscriptions_found` / `summary`.
- Update tests (Gmail mocked at the boundary): pagination in `search_candidates`,
  multi-account iteration in `run_scan_job`, and the dropped-cap call sites.

## Out of scope

- Subscription dedup / merchant-name normalization (the companion concern noted
  in the issue) — left as a follow-up to keep this PR focused.
- Window size (stays 60 days, from #20/#21).
- A high safety bound on candidates (accepted trade-off: unbounded by default).

## Approach

### Part A — pagination (`backend/app/integrations/gmail.py`)
- Signature becomes `search_candidates(self, *, after=None)`.
- Loop `messages().list(...)` following `nextPageToken`, accumulating ids until
  no token remains. Use a 500-page size internally (Gmail's per-page max) to
  minimise list round-trips — this is a page size, not a total cap.
- Keep `format=metadata` for the per-message `get` (no bodies during triage).

### Part B — all accounts (`backend/app/agent/loop.py`)
- Replace the single-`scalar` account fetch with `scalars(...).all()`, keep only
  rows that have an encrypted refresh token; raise if none.
- For each account: decrypt token → build its own `GmailClient` → paginated
  candidate search → `ScanContext` scoped to that mailbox → `run_agent_loop`.
- Aggregate counts; join per-account summaries (prefixed with the mailbox
  address for provenance); status is `succeeded` only if every account completed.
- Set `last_synced_at` per account.

## Steps
1. Plan (this file). ✅
2. Part A: paginate `search_candidates`, drop `max_results`.
3. Part B: loop accounts in `run_scan_job`, aggregate.
4. Tests: pagination, multi-account aggregation; fix the `max_results` call site.
5. Run `ruff` + `pytest`; update `.claude/progress.md`.

## Acceptance criteria
- `search_candidates` returns all matching emails in the window (paginated), no
  fixed cap.
- A scan processes all connected Gmail accounts; a second account's subs/payments
  show up.
- Counts and summary reflect the aggregate across accounts.
- Tests updated, Gmail mocked (no live calls).
