#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# FloodGuard AWS Deploy — build, push to ECR, update ECS services.
# Usage:
#   ./deploy.sh                  # deploy current git HEAD
#   ./deploy.sh v1.2.3           # deploy specific tag
#   IMAGE_TAG=abc123 ./deploy.sh # deploy specific image tag
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-ap-south-1}"
ENV="${FLOODGUARD_ENV:-production}"
STACK_NAME="floodguard-${ENV}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/../../.."

log()  { echo "  [deploy] $*"; }
die()  { echo "  [ERROR] $*" >&2; exit 1; }

# ── Resolve image tag ────────────────────────────────────────────────────────
TAG="${IMAGE_TAG:-}"
if [[ -z "$TAG" ]]; then
    if [[ -n "${1:-}" ]]; then
        TAG="$1"
    else
        TAG=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "latest")
    fi
fi
log "Deploying tag: ${TAG}"

# ── Get ECR URI from stack outputs ───────────────────────────────────────────
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$REGION")
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/floodguard"

OUTPUTS=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --query "Stacks[0].Outputs" \
    --output json)

CLUSTER=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="ECSClusterName") | .OutputValue')
[[ -z "$CLUSTER" || "$CLUSTER" == "null" ]] && die "Stack '${STACK_NAME}' not found. Run bootstrap.sh first."

# ── Build & push Docker image ─────────────────────────────────────────────────
log "Authenticating Docker to ECR..."
aws ecr get-login-password --region "$REGION" \
    | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

log "Building image (linux/amd64)..."
docker buildx build \
    --platform linux/amd64 \
    --tag "${ECR_URI}:${TAG}" \
    --tag "${ECR_URI}:latest" \
    --file "${PROJECT_ROOT}/backend/Dockerfile" \
    --push \
    --cache-from "type=registry,ref=${ECR_URI}:latest" \
    "${PROJECT_ROOT}/backend"

log "Image pushed: ${ECR_URI}:${TAG}"

# ── Update ECS task definitions with new image tag ────────────────────────────
update_task_def() {
    local FAMILY="$1"
    local CONTAINER="$2"
    log "Updating task definition: ${FAMILY}..."

    CURRENT=$(aws ecs describe-task-definition \
        --task-definition "${FAMILY}" \
        --region "${REGION}" \
        --query "taskDefinition" \
        --output json)

    NEW=$(echo "$CURRENT" | jq \
        --arg img "${ECR_URI}:${TAG}" \
        --arg name "$CONTAINER" \
        'del(.taskDefinitionArn,.revision,.status,.requiresAttributes,.compatibilities,.registeredAt,.registeredBy)
         | .containerDefinitions = [.containerDefinitions[] | if .name == $name then .image = $img else . end]')

    aws ecs register-task-definition \
        --cli-input-json "$NEW" \
        --region "${REGION}" \
        --output json > /dev/null
}

update_task_def "floodguard-web-${ENV}"    "web"
update_task_def "floodguard-worker-${ENV}" "worker"
update_task_def "floodguard-beat-${ENV}"   "beat"

# ── Force new deployment on all services ─────────────────────────────────────
for SVC in web worker beat; do
    SVC_NAME="floodguard-${SVC}-${ENV}"
    log "Forcing new deployment: ${SVC_NAME}..."
    aws ecs update-service \
        --cluster "${CLUSTER}" \
        --service "${SVC_NAME}" \
        --task-definition "floodguard-${SVC}-${ENV}" \
        --force-new-deployment \
        --region "${REGION}" \
        --output json > /dev/null
done

# ── Wait for web service to stabilize ────────────────────────────────────────
log "Waiting for web service to become stable (up to 10 min)..."
aws ecs wait services-stable \
    --cluster "${CLUSTER}" \
    --services "floodguard-web-${ENV}" \
    --region "${REGION}"

ALB_DNS=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="ALBDnsName") | .OutputValue')
log "Deploy complete!  API: ${ALB_DNS}"
