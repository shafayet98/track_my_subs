# Triage GitHub issues

> Requirement spec. This will eventually run as a scheduled cloud agent, but for
> now it is just the description of what that task must do.

## Goal

Read every open issue in the repo and label each one so its scope is visible at
a glance in the GitHub issues list.

## Requirements

1. Read **all open issues** of the repo on GitHub
   (`shafayet98/track_my_subs`).
2. For **each** issue, analyse its scope and apply the following labels:
   - **effort:** `effort:low` / `effort:medium` / `effort:high`
   - **priority:** `priority:low` / `priority:medium` / `priority:high`
   - **risk:** `risk:low` / `risk:medium` / `risk:high`
   - **area:** one (or more, if it genuinely spans) of
     `area:infra`, `area:security`, `area:frontend`, `area:api`, `area:docs`

   Pick exactly one level for effort, priority, and risk. Pick the area(s) that
   best match where the work lands.

## Done

Done when **every open issue** has an `effort`, a `risk`, a `priority`, and at
least one `area` label.
