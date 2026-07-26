# FloodGuard — AWS Operations Runbook

**Stack:** ECS Fargate (web / worker / beat) · RDS PostGIS · ElastiCache Redis · S3  
**Region:** ap-south-1 (Mumbai)

---

## 1. First-Time Setup

### Prerequisites
- AWS CLI v2: `aws --version`
- Docker with Buildx: `docker buildx version`
- jq: `brew install jq` / `apt install jq`
- AWS credentials configured: `aws configure`
- AWS Session Manager plugin (for ECS Exec): [install guide](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html)

### Run bootstrap (one-time)
```bash
cd floodguard/
AWS_DEFAULT_REGION=ap-south-1 FLOODGUARD_ENV=production \
  bash infra/aws/scripts/bootstrap.sh
```

Bootstrap takes ~15 minutes (RDS provisioning). It will:
1. Create ECR repository
2. Build and push the initial Docker image
3. Deploy the full CloudFormation stack (VPC, RDS, Redis, ECS, ALB, S3, IAM)
4. Wait for services to start and run the hex grid seed

---

## 2. Service Map

| Service | ECS service name | Health check |
|---|---|---|
| Django API | `floodguard-web-production` | `GET /api/v1/readyz/` → 200 |
| Celery worker | `floodguard-worker-production` | CloudWatch logs |
| Celery beat | `floodguard-beat-production` | CloudWatch logs |
| PostgreSQL | RDS `floodguard-production` | RDS console |
| Redis | ElastiCache `floodguard-production` | ElastiCache console |

---

## 3. Deploy a New Release

### Option A — Manual deploy
```bash
cd floodguard/
AWS_DEFAULT_REGION=ap-south-1 FLOODGUARD_ENV=production \
  bash infra/aws/scripts/deploy.sh v1.2.3
```

### Option B — Automated via GitHub Actions
Push a semver tag — the `deploy-aws.yml` workflow builds, pushes to ECR, and updates all ECS services:
```bash
git tag v1.2.3 && git push origin v1.2.3
```

### Option C — Manual trigger
GitHub → Actions → "Deploy to AWS" → Run workflow → choose environment.

### GitHub Secrets required for CI
| Secret | Value |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | IAM role ARN with ECR+ECS+CloudFormation permissions |

### GitHub Variables for CI
| Variable | Example |
|---|---|
| `API_BASE_URL` | `http://floodguard-production.ap-south-1.elb.amazonaws.com` |
| `ADMIN_BUCKET_NAME` | S3 bucket name for admin SPA (optional) |

---

## 4. Run Management Commands

Requires AWS Session Manager plugin installed locally.

```bash
# Django migrations
bash infra/aws/scripts/migrate.sh

# Custom command
bash infra/aws/scripts/migrate.sh "python manage.py build_hexgrid"

# Seed data
bash infra/aws/scripts/migrate.sh "python manage.py seed_p11"

# Create superuser (interactive)
bash infra/aws/scripts/migrate.sh "python manage.py createsuperuser"

# Check migration status
bash infra/aws/scripts/migrate.sh "python manage.py showmigrations"

# Clear cache
bash infra/aws/scripts/migrate.sh "python -c \"import django; django.setup(); from django.core.cache import cache; cache.clear(); print('cache cleared')\""
```

---

## 5. View Logs

```bash
# Web / API logs (last 100 lines)
aws logs tail /floodguard/production/web --follow --region ap-south-1

# Celery worker
aws logs tail /floodguard/production/worker --follow --region ap-south-1

# Celery beat
aws logs tail /floodguard/production/beat --follow --region ap-south-1
```

Or open CloudWatch Logs in the AWS Console → Log groups → `/floodguard/production/`.

---

## 6. Scale Services

```bash
# Scale web to 2 replicas
aws ecs update-service \
  --cluster floodguard-production \
  --service floodguard-web-production \
  --desired-count 2 \
  --region ap-south-1

# Scale back to 1
aws ecs update-service \
  --cluster floodguard-production \
  --service floodguard-web-production \
  --desired-count 1 \
  --region ap-south-1
```

---

## 7. Update Secrets

Secrets live in AWS Secrets Manager under `/floodguard/production/`.

```bash
# Rotate Django SECRET_KEY
NEW_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
aws secretsmanager update-secret \
  --secret-id /floodguard/production/SECRET_KEY \
  --secret-string "$NEW_KEY" \
  --region ap-south-1

# Force ECS to pick up the new secret
bash infra/aws/scripts/deploy.sh
```

Available secrets:
- `/floodguard/production/SECRET_KEY` — Django secret key
- `/floodguard/production/DATABASE_URL` — PostGIS connection string
- `/floodguard/production/FIREBASE_CREDENTIALS_JSON` — Firebase service account (base64)
- `/floodguard/production/CORS_ALLOWED_ORIGINS` — Admin dashboard CORS origins

---

## 8. Update Stack Parameters (ALLOWED_HOSTS, instance size, etc.)

```bash
aws cloudformation deploy \
  --stack-name floodguard-production \
  --template-file infra/aws/cloudformation/floodguard-infra.yml \
  --region ap-south-1 \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    Environment=production \
    DBPassword="EXISTING_PASSWORD" \
    DjangoSecretKey="EXISTING_KEY" \
    DBInstanceClass=db.t4g.medium \
  --no-fail-on-empty-changeset
```

---

## 9. Set Up IAM Role for GitHub Actions (OIDC)

Run once to create the GitHub OIDC role:
```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
GITHUB_ORG="your-github-org"
GITHUB_REPO="your-repo-name"

# Create OIDC provider
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# Create role
aws iam create-role \
  --role-name FloodGuardGitHubDeploy \
  --assume-role-policy-document "{
    \"Version\":\"2012-10-17\",
    \"Statement\":[{
      \"Effect\":\"Allow\",
      \"Principal\":{\"Federated\":\"arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com\"},
      \"Action\":\"sts:AssumeRoleWithWebIdentity\",
      \"Condition\":{\"StringLike\":{
        \"token.actions.githubusercontent.com:sub\":\"repo:${GITHUB_ORG}/${GITHUB_REPO}:*\"
      }}
    }]
  }"

# Attach required policies
aws iam attach-role-policy --role-name FloodGuardGitHubDeploy \
  --policy-arn arn:aws:iam::aws:policy/AmazonECS_FullAccess
aws iam attach-role-policy --role-name FloodGuardGitHubDeploy \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

echo "Role ARN: arn:aws:iam::${ACCOUNT_ID}:role/FloodGuardGitHubDeploy"
echo "Add this as GitHub secret: AWS_DEPLOY_ROLE_ARN"
```

---

## 10. Incident Playbook

### API returning 5xx
1. `aws logs tail /floodguard/production/web --follow` — check stack traces
2. `GET /api/v1/readyz/` — identifies DB vs cache vs app issues
3. If DB unavailable: RDS console → check instance status
4. If OOM: scale web task CPU/memory in the CF template and redeploy

### Celery tasks not running
1. Check worker logs: `aws logs tail /floodguard/production/worker --follow`
2. Verify Redis is reachable: check ElastiCache console
3. Force worker restart: `aws ecs update-service --cluster floodguard-production --service floodguard-worker-production --force-new-deployment`

### Risk data stale
```bash
bash infra/aws/scripts/migrate.sh "python manage.py shell -c \"
from apps.ingest.tasks import ingest_ecmwf, ingest_aws_observations, ingest_radar
from apps.risk.tasks import recompute_all_risk
ingest_aws_observations.apply()
ingest_radar.apply()
recompute_all_risk.apply()
print('done')
\""
```

### Media uploads failing
1. Check S3 bucket exists: `aws s3 ls s3://floodguard-media-ACCOUNT_ID-production/`
2. Verify ECS task role has S3 permissions (IAM console → `floodguard-production-ecs-task`)
3. Check web logs for boto3 errors

---

## 11. Cost Estimate (ap-south-1, ~steady state)

| Resource | Size | Est. $/month |
|---|---|---|
| ECS Fargate web | 0.5 vCPU / 1 GB, 1 task | ~$12 |
| ECS Fargate worker | 0.5 vCPU / 1 GB, 1 task | ~$12 |
| ECS Fargate beat | 0.25 vCPU / 0.5 GB, 1 task | ~$5 |
| RDS db.t4g.small | 20 GB gp3 | ~$25 |
| ElastiCache cache.t4g.micro | 1 node | ~$12 |
| ALB | ~1 LCU | ~$20 |
| NAT Gateway | ~5 GB/mo | ~$10 |
| ECR + S3 + CloudWatch | minimal | ~$5 |
| **Total** | | **~$101/month** |

Scale RDS to db.t4g.micro (~$13/mo) for staging to save cost.
