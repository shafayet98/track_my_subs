# Plan: CD pipeline (GitHub Actions → AWS via OIDC)

## Goal

Auto-deploy track_my_subs to AWS on every merge to `main`. No long-lived AWS keys
in GitHub — authenticate via **GitHub OIDC → an IAM role** in the audrie98 account.
This codifies the runbook we ran by hand during the first deploy.

## Scope

- **IAM (CDK, new `cicd_stack.py`):**
  - A GitHub **OIDC identity provider** for `token.actions.githubusercontent.com`
    (none exists in the account yet).
  - A **deploy role** (`github-actions-deploy`, deterministic ARN) whose trust is
    scoped to `repo:shafayet98/track_my_subs:ref:refs/heads/main` (only merges to
    main can assume it), with permissions to:
    - `sts:AssumeRole` the `cdk-hnb659fds-*` bootstrap roles (so `cdk deploy` works),
    - push to ECR, run the migration ECS task (`ecs:RunTask` + `iam:PassRole` +
      describe), sync the SPA S3 bucket, and create CloudFront invalidations.
- **Image tagging (CDK):** parameterize the API image tag in `backend_stack.py`
  via `imageTag` context (default `latest`), so `cdk deploy -c imageTag=<sha>`
  updates the task definition and ECS rolls onto the new image deterministically.
- **Workflow (`.github/workflows/cd.yml`):** on `push` to `main`:
  1. assume the role via OIDC,
  2. build + push the API image tagged with the commit SHA,
  3. `cdk deploy --all -c imageTag=<sha>`,
  4. run migrations as a one-off ECS task (discover cluster/taskdef/network at
     runtime), wait for the service to stabilize,
  5. build the SPA → `s3 sync` → CloudFront invalidation (discover bucket/dist from
     the `TrackMySubs-Frontend` stack outputs).
  - `concurrency` guard so two deploys never overlap.

### Out of scope

- Manual approval gates / GitHub Environments (auto-deploy on merge for now).
- Multi-environment (staging/prod) — single env.
- Rollback automation beyond ECS's built-in deployment circuit breaker.

## Approach / decisions

- **Trust scoping:** subject pinned to the `main` branch ref, audience
  `sts.amazonaws.com`. Tightest sensible scope for a deploy-on-merge role.
- **Permissions:** scoped (assume CDK roles + the specific ECR/ECS/S3/CloudFront
  actions) rather than a broad managed policy — least privilege, since the role is
  assumable by anything that lands on `main`.
- **Discovery over hardcoding:** the workflow resolves cluster/service/taskdef,
  subnets/SG, and the SPA bucket/distribution at runtime (CLI queries + stack
  outputs) so it survives stack recreation.
- **The OIDC provider + role must exist before CD runs** — deploy `TrackMySubs-Cicd`
  once (IAM is free) as part of landing this.

## Steps

1. `cicd_stack.py` — OIDC provider + scoped deploy role; wire into `app.py`.
2. Parameterize `imageTag` in `backend_stack.py`.
3. `.github/workflows/cd.yml`.
4. `uv run cdk synth` + ruff clean.
5. Deploy `TrackMySubs-Cicd` to create the provider + role.
6. README + progress; open PR.

## Acceptance criteria

- `cdk synth` produces the new `TrackMySubs-Cicd` stack; ruff clean.
- The OIDC provider + `github-actions-deploy` role exist in audrie98, trust scoped
  to the repo's `main`.
- After merge, a push to `main` runs `cd.yml` green and the deployed app reflects
  the commit (new image SHA running, SPA updated). [verified post-merge]
