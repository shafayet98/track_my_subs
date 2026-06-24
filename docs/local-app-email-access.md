# Local app: avoiding the Google OAuth verification problem

## The question

> I am thinking about a local app which will run on the user's machine locally,
> where the user connects their email and uses the LLM to do the same thing we
> are doing. What would actually be the way so that we don't have to go through
> this Google issue?

## The real answer

"The Google issue" = **verification + CASA (the annual third-party security
assessment) for the restricted `gmail.readonly` scope.** There are exactly two
ways to never deal with that, and they split on **whether you use Google's OAuth
restricted-scope flow at all.**

---

## Path 1 — Don't use OAuth at all: IMAP + App Password ⭐

This is the one most people miss, and for a local app it's the cleanest by far.

- The user enables 2-Step Verification on their Google account and generates a
  16-character **App Password**.
- The local app connects to `imap.gmail.com` over SSL with that app password and
  reads mail directly via IMAP.
- **No Google Cloud project. No OAuth consent screen. No restricted scopes. No
  verification. Ever.**

**Why it fits a local app so well:**

- The credential lives only on the user's machine — it never touches a server you
  operate, which is exactly the privacy posture this project already wants.
- **Provider-agnostic bonus:** IMAP is universal, so the same code works for
  Outlook / Yahoo / Fastmail / etc., not just Gmail. The subscription tracker
  instantly supports any mailbox.

**Trade-offs, to be honest about:**

- Requires the user to have 2FA on (most do).
- An IMAP app password grants **full mailbox access**, not the narrow read-only
  that `gmail.readonly` gives. You'd only *read*, but the credential itself is
  broad — that's a real step back from this repo's read-only security rule
  (`.claude/rules/security.md`), so it's a deliberate trade.
- App passwords are a Gmail feature that Google could tighten someday; today they
  work fine.

---

## Path 2 — Keep OAuth, but each user is their own developer

Stay on the Gmail API (keeps true read-only scope), but the app is local and
**each user supplies their own OAuth client**:

- The user creates a Google Cloud project, enables the Gmail API, makes a
  **Desktop** OAuth client, adds themselves as a test user, and pastes the client
  ID / secret into the local app.
- Since they own the app and only they use it, there's nothing for **you** to
  verify.
- Keeps the clean `gmail.readonly` read-only access.

**Trade-off:** the one-time Google Cloud Console setup per user is fiddly, and
Testing-mode refresh tokens expire every 7 days (re-consent weekly).

---

## Recommendation

| Approach | Setup friction | Access scope | Multi-provider | Verification |
| --- | --- | --- | --- | --- |
| **IMAP + App Password** | Low (generate 1 password) | Full mailbox (read only by you) | ✅ Any provider | None, ever |
| **BYO OAuth client** | High (Cloud Console dance) | True read-only | ❌ Gmail only | None (you never publish) |

For a **local, self-hosted subscription tracker, go IMAP + App Password.** It
kills the Google problem outright, is dramatically simpler to onboard, and makes
the app work with any email provider — which is a strategic win for the product.
The cost is a broader credential and dropping the Gmail API's narrow read-only
scope, which should be documented as a conscious decision.

## What changes (and what doesn't)

The LLM / agent half doesn't change at all in either path — the agent loop,
tools, and prompts stay identical. Only the **email-fetching layer** swaps from
Gmail-API-over-OAuth to IMAP. So this is a contained change to
`backend/app/integrations/gmail.py` (it'd become more like an `email_imap.py`)
plus the connect-account flow — **not** a rewrite of the agent.
