# Scan lookback window

## Goal

Change the mailbox scan from a count-based window (the 100 most-recent candidate
emails, no date filter) to a time-based window: the last 14 days. Each scan then
covers a consistent recent window regardless of mailbox size. Closes #14.

## Scope

- Add a single configurable lookback value.
- Pass an `after` date into the existing `search_candidates(after=...)` support.
- Update/add tests at the Gmail boundary (no live network).

## Out of scope

- Pagination / raising the result cap (history synthesis is a separate, larger
  piece — see issue #14 notes and progress.md follow-ups).
- Any DB migration, LLM, or Gmail-scope change.

## Approach

- `app/core/config.py` — add `scan_lookback_days: int = 14` (env alias
  `SCAN_LOOKBACK_DAYS`), so the window is tunable without code edits.
- `app/agent/loop.py` — compute
  `after = datetime.now(UTC) - timedelta(days=settings.scan_lookback_days)` and
  pass it to `gmail.search_candidates(after=after)`.
- `max_results`: keep the existing cap of 100 as a safety limit (documented). A
  busy 14-day window is far smaller than an all-time mailbox, so truncation risk
  drops; pagination stays deferred.

## Steps

1. Add `scan_lookback_days` to `Settings`.
2. Pass `after` from `run_scan_job` in `loop.py`.
3. Tests: `search_candidates` puts `after:` in the query; loop calls it with the
   expected date. Gmail mocked.
4. `ruff check` + `ruff format --check` + `pytest` green.

## Acceptance criteria

- A scan only considers candidate emails newer than `today - scan_lookback_days`.
- The lookback is one configurable value, no scattered magic number.
- Tests assert the `after` date is applied; Gmail mocked (no network in CI).
