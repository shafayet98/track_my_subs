# infra — AWS CDK (Python)

Infrastructure for track_my_subs (Phase 7). Deploys into the **audrie98** account
(`390843337949`), region **`ap-southeast-2`**, via the `audrie98` SSO profile.

## Stacks

| Stack                  | What it creates                                                        |
| ---------------------- | --------------------------------------------------------------------- |
| `TrackMySubs-Network`  | VPC (2 AZ, 1 NAT), public + private subnets                           |
| `TrackMySubs-Data`     | RDS PostgreSQL (private) + app-secrets in Secrets Manager             |
| `TrackMySubs-Backend`  | ECR repo, ECS cluster, Fargate API service on **HTTPS** behind an ALB |
| `TrackMySubs-Frontend` | Private S3 bucket + CloudFront (OAC, SPA fallback) for the React app  |

Scans run **in-process** in the API today; a dedicated scan-worker service is a
later change.

## Domain / DNS / TLS

The API is served at **`https://api.shafcode.xyz`**. The `shafcode.xyz` Route 53
hosted zone (id `Z0858754AS09Y4TNXSF5`) lives in this account, so CDK manages the
DNS record itself — the backend stack creates the `api.shafcode.xyz` A-alias to the
ALB automatically. TLS is an ACM certificate (DNS-validated against the zone),
referenced by ARN in `stacks/backend_stack.py`.

**Before deploying the backend stack, the cert must be `Issued`:**

```bash
aws acm describe-certificate \
  --certificate-arn arn:aws:acm:ap-southeast-2:390843337949:certificate/69731ecd-68f6-4de1-a978-1a3745209036 \
  --region ap-southeast-2 --profile audrie98 --query Certificate.Status --output text
```

If you ever recreate the cert, update `API_CERTIFICATE_ARN` in the backend stack.

## Prereqs

- An active SSO session: `aws sso login --profile audrie98`
- `uv`, Node (for the `cdk` CLI), and Docker (only for building the image).

```bash
cd infra
uv sync
export AWS_PROFILE=audrie98          # or pass --profile to each aws/cdk call
```

## Synthesize (no AWS calls, no Docker)

```bash
uv run cdk synth
```

## Deploy

> Deploying creates **billable** resources (NAT, RDS, ALB, CloudFront). 

1. **Bootstrap** the account/region once:
   ```bash
   uv run cdk bootstrap aws://390843337949/ap-southeast-2
   ```
   > If a deploy later fails with *"No bucket named cdk-hnb659fds-assets-…"*, the
   > bootstrap staging bucket was deleted out-of-band — recreate it (versioning +
   > block-public-access + SSE) or re-bootstrap. (This account also bootstraps the
   > PingList project, so they share that bucket.)
2. **Deploy ECR first, then the foundation** (the repo is a separate stack so the
   image can be pushed before the Fargate service starts — otherwise the service
   can't stabilize without an image, and a rollback would delete the repo):
   ```bash
   uv run cdk deploy TrackMySubs-Network TrackMySubs-Ecr TrackMySubs-Data
   ```
3. **Build & push the API image** to the ECR repo (build for `linux/amd64`).
   Note: use `${REPO}:latest` with braces — bare `$REPO:latest` in zsh triggers
   the `:l` modifier and mangles the tag:
   ```bash
   ACCOUNT=390843337949; REGION=ap-southeast-2
   REPO="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/track-my-subs-api"
   aws ecr get-login-password --region $REGION --profile audrie98 \
     | docker login --username AWS --password-stdin ${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com
   docker build --platform linux/amd64 -t "${REPO}:latest" ../backend
   docker push "${REPO}:latest"
   ```
4. **Deploy the backend service** now that the image exists:
   ```bash
   uv run cdk deploy TrackMySubs-Backend
   ```
   On later image updates, re-push and force a new deployment:
   ```bash
   aws ecs update-service --cluster <cluster> --service <service> \
     --force-new-deployment --region $REGION --profile audrie98
   ```
5. **Fill the app secrets** (`track-my-subs/app`). `JWT_SECRET` is generated;
   set the rest:
   ```bash
   aws secretsmanager put-secret-value --secret-id track-my-subs/app --profile audrie98 \
     --secret-string '{
       "ANTHROPIC_API_KEY": "sk-ant-...",
       "TOKEN_ENCRYPTION_KEY": "<fernet-key>",
       "GOOGLE_OAUTH_CLIENT_ID": "...",
       "GOOGLE_OAUTH_CLIENT_SECRET": "...",
       "FRONTEND_ORIGIN": "https://<cloudfront-domain>",
       "JWT_SECRET": "<keep the generated value>"
     }'
   ```
   (Re-running `put-secret-value` replaces the whole JSON, so include `JWT_SECRET`.)
   `GOOGLE_OAUTH_REDIRECT_URI` is **not** here — it's a fixed env var on the task
   (`https://api.shafcode.xyz/api/accounts/gmail/callback`). Register that exact URI
   as an authorized redirect in the Google OAuth client.
6. **Run migrations** once. RDS is private, so the clean way is a one-off ECS task
   reusing the API task definition with a command override:
   ```bash
   aws ecs run-task --cluster <cluster> --task-definition <taskdef> --launch-type FARGATE \
     --network-configuration "awsvpcConfiguration={subnets=[<private-subnets>],securityGroups=[<api-sg>],assignPublicIp=DISABLED}" \
     --overrides '{"containerOverrides":[{"name":"web","command":["alembic","upgrade","head"]}]}' \
     --profile audrie98
   ```
7. **Deploy the frontend** infra and upload the SPA build:
   ```bash
   uv run cdk deploy TrackMySubs-Frontend
   cd ../frontend && VITE_API_BASE_URL=https://api.shafcode.xyz/api npm run build
   aws s3 sync dist/ s3://<SpaBucketName>/ --delete --profile audrie98
   aws cloudfront create-invalidation --distribution-id <DistributionId> \
     --paths '/*' --profile audrie98
   ```

## CD (auto-deploy on merge to main)

`.github/workflows/cd.yml` deploys automatically on every push to `main`. It
authenticates with **GitHub OIDC → the `github-actions-deploy` IAM role** (no
stored AWS keys), then: builds + pushes the API image tagged with the commit SHA,
`cdk deploy`s the app stacks with `-c imageTag=<sha>`, runs migrations as a one-off
ECS task, and builds + uploads the SPA with a CloudFront invalidation.

The OIDC provider + role live in the **`TrackMySubs-Cicd`** stack. Deploy it once
(it is intentionally **not** redeployed by CD, so the pipeline can't rewrite its
own permissions):

```bash
uv run cdk deploy TrackMySubs-Cicd
```

Trust is scoped to `repo:shafayet98/track_my_subs:ref:refs/heads/main`. Migrations
run *after* the service rolls onto the new image, so keep them backward-compatible.

## Tear down

```bash
uv run cdk destroy --all
```

RDS, the SPA bucket, and the ECR repo are set to delete on teardown (early-stage
convenience — tighten removal policies before holding real data).
