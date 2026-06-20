# Plan: Frontend redesign + 2-month scan window (issue #20)

## Goal

Give the SPA a polished, consistent, product-grade look matching the provided
screenshots (warm cream background, coral accent, monospace numerals, soft cards),
and expand the default scan window from 14 days to ~2 months.

## Scope

**Part 1 — Frontend redesign (visual only; data/markup already match):**
- A cohesive design system applied across all pages: **Layout/topbar**, **Auth**
  (login/register), **Dashboard**, **Subscription detail**, **Connect & scan**.
- Avatars (merchant/user initials), uppercase tracked labels, status pills
  (active/cancelled/unknown/overdue/…), coral primary buttons, the cream theme,
  monospace for the brand + numbers, responsive layout.
- Better empty/loading states (esp. the "no candidate emails / no subscriptions"
  copy that guides the user to connect the right inbox).

**Part 2 — Scan window:** default `SCAN_LOOKBACK_DAYS` 14 → 60.

### Out of scope
- No backend data/schema changes (the API already returns category, confidence,
  payments, etc. — confirmed in `api/types.ts`).
- The deeper "history synthesis" idea (separate, larger).

## Approach / decisions

- **Styling = refined design-token CSS, not a framework.** The screenshots are a
  precise visual target; hand-authored CSS (a rewritten `index.css` with CSS
  variables) lets me match the exact palette/spacing/typography with the lowest
  risk, and keeps the diff reviewable (no per-component utility-class churn). The
  component structure already fits, so this is mostly CSS + small markup tweaks
  (avatars, the centered brand, label casing, the dashboard summary/chart split).
  *A full Tailwind/shadcn migration remains a valid future step — tracked
  separately if wanted; the visual result here is the same either way.*
- **Design tokens** (from the screenshots): cream `--bg`, white panels, coral
  `--accent`, soft status tints, warm muted text. Fonts: **Space Mono** (brand,
  numbers, labels) via a Google Fonts `<link>` in `index.html`; system sans for
  headings/body.
- **Topbar** restructured to match: left nav (`Dashboard` + a coral `Connect`
  button), centered `Track My Subs` brand, right user (avatar + first name +
  `Sign out`). The dashboard's old in-page "Connect & scan" button moves to the
  topbar.
- Keep architecture rules: presentational components stay dumb; pages fetch via
  hooks; one typed API client; no behavior changes.

## Steps

1. `index.html` — fonts + title.
2. `index.css` — full design-system rewrite (tokens, layout, buttons/inputs,
   auth, stats, cards, pills incl. `cancelled`/`unknown`, tables, avatars,
   responsive).
3. Components/pages — `Layout`, `LoginPage`, `DashboardPage`,
   `SubscriptionCard`, `SubscriptionDetailPage`, `ConnectAccountPage`,
   `SpendChart` (coral bars); a small `initials()` helper.
4. Part 2 — `config.py` `scan_lookback_days` default → 60 (the existing test
   reads `settings.scan_lookback_days`, so it adapts).
5. `npm run lint` + `npm run build` green; `pytest` for the backend change.

## Acceptance criteria

- All pages render in the new cream/coral/monospace design, responsive on mobile.
- Friendlier empty/error states (no-subscriptions, no-candidate-emails).
- `npm run lint` + `npm run build` pass; no behavior regressions.
- Default scan window is ~60 days (still `SCAN_LOOKBACK_DAYS`-overridable); backend
  tests green.
