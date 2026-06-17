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
2. **Deploy the foundation** (network, data, ECR, ALB):
   ```bash
   uv run cdk deploy TrackMySubs-Network TrackMySubs-Data TrackMySubs-Backend
   ```
   The API tasks won't be healthy yet — the ECR repo has no image.
3. **Build & push the API image** to the ECR repo from the `EcrRepositoryUri`
   output (build for `linux/amd64`):
   ```bash
   ACCOUNT=390843337949; REGION=ap-southeast-2
   REPO=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/track-my-subs-api
   aws ecr get-login-password --region $REGION --profile audrie98 \
     | docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.$REGION.amazonaws.com
   docker build --platform linux/amd64 -t $REPO:latest ../backend
   docker push $REPO:latest
   ```
   Then force a new deployment so ECS pulls it:
   ```bash
   aws ecs update-service --cluster <cluster> --service <service> \
     --force-new-deployment --region $REGION --profile audrie98
   ```
4. **Fill the app secrets** (`track-my-subs/app`). `JWT_SECRET` is generated;
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
5. **Run migrations** once (one-off ECS task or any host that can reach RDS):
   ```bash
   alembic upgrade head   # with DATABASE_URL pointing at the RDS instance
   ```
6. **Deploy the frontend** infra and upload the SPA build:
   ```bash
   uv run cdk deploy TrackMySubs-Frontend
   cd ../frontend && VITE_API_BASE_URL=https://api.shafcode.xyz/api npm run build
   aws s3 sync dist/ s3://<SpaBucketName>/ --delete --profile audrie98
   aws cloudfront create-invalidation --distribution-id <DistributionId> \
     --paths '/*' --profile audrie98
   ```

## Tear down

```bash
uv run cdk destroy --all
```

RDS, the SPA bucket, and the ECR repo are set to delete on teardown (early-stage
convenience — tighten removal policies before holding real data).
