#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# FloodGuard AWS Bootstrap — run ONCE to provision the full stack.
# Prerequisites: aws CLI v2, docker, jq installed and AWS credentials set.
#   aws configure   (or set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY env vars)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-ap-south-1}"
ENV="${FLOODGUARD_ENV:-production}"
STACK_NAME="floodguard-${ENV}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CF_TEMPLATE="${SCRIPT_DIR}/../cloudformation/floodguard-infra.yml"
PROJECT_ROOT="${SCRIPT_DIR}/../../.."   # floodguard/

log()  { echo "  [bootstrap] $*"; }
warn() { echo "  [WARN] $*" >&2; }
die()  { echo "  [ERROR] $*" >&2; exit 1; }

# ── Preflight checks ──────────────────────────────────────────────────────────
command -v aws   >/dev/null 2>&1 || die "aws CLI not found. Install: https://aws.amazon.com/cli/"
command -v docker >/dev/null 2>&1 || die "docker not found."
command -v jq    >/dev/null 2>&1 || die "jq not found. brew install jq / apt install jq"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$REGION")
log "AWS account: ${ACCOUNT_ID} | region: ${REGION} | env: ${ENV}"

# ── Collect secrets interactively ────────────────────────────────────────────
echo ""
echo "=== FloodGuard AWS Bootstrap ==="
echo "You will be prompted for sensitive values. These are stored in AWS"
echo "Secrets Manager and NEVER written to disk or printed."
echo ""

read -rsp "Django SECRET_KEY (run: python -c \"import secrets; print(secrets.token_urlsafe(64))\"): " DJANGO_SECRET_KEY
echo ""
[[ ${#DJANGO_SECRET_KEY} -lt 50 ]] && die "SECRET_KEY too short (need ≥50 chars)"

read -rsp "RDS master password (16+ chars, no @/\"/space): " DB_PASSWORD
echo ""
[[ ${#DB_PASSWORD} -lt 16 ]] && die "DB password too short (need ≥16 chars)"

read -rsp "Firebase credentials JSON (base64-encoded, press Enter to skip): " FIREBASE_JSON
echo ""
FIREBASE_JSON="${FIREBASE_JSON:-not-configured}"

read -rp "CORS allowed origins for admin dashboard (e.g. https://admin.yourapp.com, press Enter to skip): " CORS_ORIGINS
CORS_ORIGINS="${CORS_ORIGINS:-not-configured}"

# ── Build & push initial Docker image ────────────────────────────────────────
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/floodguard"

log "Creating ECR repository (idempotent)..."
aws ecr create-repository \
    --repository-name floodguard \
    --region "$REGION" \
    --image-scanning-configuration scanOnPush=true \
    2>/dev/null || log "ECR repo already exists."

log "Authenticating Docker to ECR..."
aws ecr get-login-password --region "$REGION" \
    | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

log "Building backend image (linux/amd64)..."
docker buildx build \
    --platform linux/amd64 \
    --tag "${ECR_URI}:latest" \
    --tag "${ECR_URI}:bootstrap" \
    --file "${PROJECT_ROOT}/backend/Dockerfile" \
    --push \
    "${PROJECT_ROOT}/backend"

# ── Deploy CloudFormation stack ───────────────────────────────────────────────
log "Deploying CloudFormation stack '${STACK_NAME}' (this takes ~15 min for RDS)..."
aws cloudformation deploy \
    --stack-name "${STACK_NAME}" \
    --template-file "${CF_TEMPLATE}" \
    --region "${REGION}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides \
        Environment="${ENV}" \
        DBPassword="${DB_PASSWORD}" \
        DjangoSecretKey="${DJANGO_SECRET_KEY}" \
        FirebaseCredentialsJson="${FIREBASE_JSON}" \
        CorsAllowedOrigins="${CORS_ORIGINS}" \
        EcrImageTag="latest" \
    --tags \
        Project=FloodGuard \
        Environment="${ENV}" \
    --no-fail-on-empty-changeset

# ── Read stack outputs ────────────────────────────────────────────────────────
log "Reading stack outputs..."
OUTPUTS=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --query "Stacks[0].Outputs" \
    --output json)

ALB_DNS=$(echo "$OUTPUTS"     | jq -r '.[] | select(.OutputKey=="ALBDnsName")    | .OutputValue')
ECR_URI_OUT=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="ECRRepositoryUri") | .OutputValue')
CLUSTER=$(echo "$OUTPUTS"     | jq -r '.[] | select(.OutputKey=="ECSClusterName") | .OutputValue')

# ── Run Django migrations via ECS exec ───────────────────────────────────────
log "Waiting for web service to stabilize..."
aws ecs wait services-stable \
    --cluster "${CLUSTER}" \
    --services "floodguard-web-${ENV}" \
    --region "${REGION}" || warn "Service not yet stable — migrations may need to be run manually."

# ── Seed the hex grid ─────────────────────────────────────────────────────────
log "Running build_hexgrid management command..."
TASK_ARN=$(aws ecs run-task \
    --cluster "${CLUSTER}" \
    --launch-type FARGATE \
    --task-definition "floodguard-web-${ENV}" \
    --network-configuration "$(aws ecs describe-services \
        --cluster "${CLUSTER}" \
        --services "floodguard-web-${ENV}" \
        --region "${REGION}" \
        --query "services[0].networkConfiguration" \
        --output json)" \
    --overrides '{"containerOverrides":[{"name":"web","command":["python","manage.py","build_hexgrid"]}]}' \
    --region "${REGION}" \
    --query "tasks[0].taskArn" \
    --output text)
log "build_hexgrid task launched: ${TASK_ARN}"

# ── Print summary ─────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║             FloodGuard AWS Bootstrap Complete!                   ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  API URL  : ${ALB_DNS}"
echo "║  ECR URI  : ${ECR_URI_OUT}"
echo "║  Cluster  : ${CLUSTER}"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  Next steps:                                                     ║"
echo "║  1. Set API_BASE_URL in mobile/admin to the ALB URL above        ║"
echo "║  2. Add your custom domain to Route 53 and update ALLOWED_HOSTS  ║"
echo "║  3. Run: infra/aws/scripts/deploy.sh for future deploys          ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
