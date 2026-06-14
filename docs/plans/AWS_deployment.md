# Plan: AWS deployment — CDK (Phase 7)

## Goal

Infrastructure-as-code (AWS CDK in Python, under `infra/`) that deploys
track_my_subs to AWS: the React SPA on S3 + CloudFront, the FastAPI API on ECS
Fargate behind an ALB, a separate Fargate **scan worker** (scans are long-running
and shouldn't block the API), PostgreSQL on RDS, and all secrets in AWS Secrets
Manager. Target account **audrie98 (`390843337949`)**, region **`ap-southeast-2`**
(see the `aws-deploy-account` memory; CLI profile `audrie98`).

## Scope

- `infra/` CDK Python app that **synthesizes cleanly** (`cdk synth`) with the
  account/region pinned. Stacks:
  - **Network** — a VPC (2 AZs, public + private-with-egress subnets, 1 NAT gateway
    to keep cost down).
  - **Data** — RDS PostgreSQL (single instance, private subnets); DB credentials
    in a Secrets Manager secret (RDS-managed). An **app secrets** Secrets Manager
    secret holding `ANTHROPIC_API_KEY`, Google OAuth client id/secret, `JWT_SECRET`,
    `TOKEN_ENCRYPTION_KEY` — created with placeholder structure, real values filled
    by the owner out-of-band (never in the repo).
  - **Backend** — ECR repository for the API image; an ECS cluster; a Fargate
    **API service** behind an internet-facing ALB (health check `GET /api/health`).
    The task pulls the image from ECR, reads DB creds + app secrets from Secrets
    Manager, runs in private subnets, and connects to RDS. Scans currently run
    **in-process** in the API (Phase 4 background tasks), so there is no separate
    worker service yet.
  - **Frontend** — a private S3 bucket for the SPA build + a CloudFront
    distribution (OAC to the bucket, SPA fallback to `index.html` for client-side
    routing).
- **`DATABASE_URL` assembly:** the backend reads a single `DATABASE_URL`. ECS
  injects the RDS host/port/dbname as env and the username/password from the RDS
  secret; the container entrypoint composes `DATABASE_URL` (asyncpg) from those —
  so the password never sits in a plaintext env var and the backend stays
  unchanged.
- A backend **`Dockerfile`** so the API/worker image can be built and pushed to
  ECR (image referenced by ECR tag, so `cdk synth` does not require Docker).
- `infra/README.md` — how to bootstrap, build/push the image, deploy, and tear
  down; which secret keys to fill in.

### Out of scope (this PR)

- **Actually running `cdk deploy`** — that creates billable resources and needs the
  owner's explicit go-ahead. This PR delivers IaC that synthesizes; deploy is a
  gated follow-up.
- A **dedicated scan-worker service** — scans run in-process in the API today;
  splitting them onto their own Fargate service needs a backend worker entrypoint
  (queue/consumer), which is a separate change.
- Custom domain / ACM certificate / Route53 (use the default CloudFront + ALB DNS
  for now).
- CI/CD pipeline for image build+push and auto-deploy (later).
- Running migrations is a documented one-off task (`alembic upgrade head`), not in
  the container entrypoint, to avoid races across tasks.
- Autoscaling policies, WAF, multi-AZ RDS (single-AZ + sane defaults for now).

## Approach

- **CDK app structure:** `app.py` instantiates the stacks and wires cross-stack
  references (VPC → data/backend; secrets + DB → backend; bucket/distribution
  outputs for the frontend deploy). `env` pinned to account `390843337949` /
  `ap-southeast-2` so synth is deterministic and no environment lookups are needed.
- **Dependencies:** `infra/pyproject.toml` managed by `uv` (matches the backend);
  `aws-cdk-lib` v2 + `constructs`. `cdk.json` runs `uv run python app.py`.
- **Image decoupling:** the Fargate task definitions reference the image by ECR
  tag (`from_ecr_repository`), not a Docker asset — so `cdk synth`/`cdk deploy`
  don't need a local Docker build at synth time. Build + push is a documented step
  (and a future CI job).
- **Secrets:** never in code. The app-secrets secret is created with a JSON
  template of keys; values are set with `aws secretsmanager put-secret-value` by
  the owner. ECS injects them as container env via `secrets=` on the task def.
- **Config mapping:** the backend already reads config from the environment
  (`core/config.py`). ECS maps `DATABASE_URL` (assembled from the RDS secret) and
  the app-secret keys into the container environment — no backend code change
  needed beyond confirming env var names line up.
- **Security/tenancy rules still apply:** read-only Gmail scope, parsed-data-only,
  secrets server-side — none of that changes; this phase just hosts it.

## Steps

1. Scaffold `infra/` — `app.py`, `cdk.json`, `pyproject.toml`, `README.md`,
   `stacks/` package.
2. Network stack (VPC).
3. Data stack (RDS + app-secrets).
4. Backend stack (ECR, cluster, ALB API service, scan-worker service, task roles).
5. Frontend stack (S3 + CloudFront with OAC + SPA fallback).
6. Add `backend/Dockerfile` for the API/worker image.
7. `uv sync` in `infra/`, then `cdk synth` until it produces templates cleanly.
8. `infra/README.md` + `.claude/progress.md` entry.

## Acceptance criteria

- `cd infra && uv sync && uv run cdk synth` produces CloudFormation for all stacks
  with no errors and no Docker build. The only context lookup (availability zones)
  is cached in committed `cdk.context.json`, so CI synth needs no AWS credentials.
- Account/region pinned to `390843337949` / `ap-southeast-2`.
- No secret values committed; the app-secrets secret is structure-only.
- README documents bootstrap → build/push image → deploy → destroy, and which
  secret keys to populate.
- (Deferred, gated) `cdk deploy` brings the stack up and the app runs in AWS —
  done in a follow-up once the owner approves spinning up billable resources.
