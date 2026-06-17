# Plan: API custom domain + HTTPS

## Goal

Serve the backend API at `https://api.shafcode.xyz` so Google OAuth (which
requires an `https` redirect on an owned domain) works in the deployed app.
Follow-up to Phase 7 (the CDK infra).

## Scope

- DNS: a Route 53 hosted zone for `shafcode.xyz` in the **audrie98** account
  (the registrar's nameservers are repointed to it). Done out-of-band; CDK
  references the zone by id (no lookup, keeps CI synth offline).
- ACM certificate for `api.shafcode.xyz` (ap-southeast-2), DNS-validated against
  that zone; referenced in CDK by ARN.
- Backend stack: HTTPS:443 listener on the ALB with the cert, HTTP→HTTPS redirect,
  and an auto-created `api.shafcode.xyz` A-alias to the ALB.
- `GOOGLE_OAUTH_REDIRECT_URI` becomes a fixed task env var
  (`https://api.shafcode.xyz/api/accounts/gmail/callback`) instead of a secret
  placeholder; drop it from the app-secrets template.

### Out of scope

- A custom domain for the frontend (stays on the default CloudFront https URL;
  needs a us-east-1 cert — later).
- The actual `cdk deploy` (gated; and blocked until the cert is `Issued`).

## Steps

1. Create the hosted zone in audrie98; repoint Namecheap nameservers (manual).
2. Request the ACM cert; stage its DNS validation record in the zone.
3. Wire HTTPS into the backend stack (cert + zone + domain + redirect).
4. Move the OAuth redirect URI to a task env var; trim the secret template.
5. `cdk synth` + ruff; update README/progress.

## Acceptance criteria

- `cdk synth` is clean and the backend template has: an HTTPS:443 listener using
  the cert, an HTTP:80 → HTTPS redirect, and an `api.shafcode.xyz` Route 53 record.
- CI synth stays offline (zone/cert referenced by id/arn, no lookups).
- (Gated) after the cert is `Issued` and the stack deploys, `https://api.shafcode.xyz`
  serves the API and the Gmail OAuth callback works.
