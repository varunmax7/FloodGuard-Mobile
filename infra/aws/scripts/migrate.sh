#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# FloodGuard — Run Django management commands via ECS Exec.
# Usage:
#   ./migrate.sh                              # run migrate --noinput
#   ./migrate.sh "python manage.py showmigrations"
#   ./migrate.sh "python manage.py createsuperuser"
#   ./migrate.sh "python manage.py build_hexgrid"
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-ap-south-1}"
ENV="${FLOODGUARD_ENV:-production}"
CLUSTER="floodguard-${ENV}"
SERVICE="floodguard-web-${ENV}"
CMD="${1:-python manage.py migrate --noinput}"

log() { echo "  [migrate] $*"; }
die() { echo "  [ERROR] $*" >&2; exit 1; }

command -v aws    >/dev/null 2>&1 || die "aws CLI not found"
command -v session-manager-plugin >/dev/null 2>&1 || {
    echo "  Session Manager plugin not found."
    echo "  Install: https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html"
    exit 1
}

log "Finding a running web task in cluster '${CLUSTER}'..."
TASK_ARN=$(aws ecs list-tasks \
    --cluster "${CLUSTER}" \
    --service-name "${SERVICE}" \
    --desired-status RUNNING \
    --region "${REGION}" \
    --query "taskArns[0]" \
    --output text)

[[ -z "$TASK_ARN" || "$TASK_ARN" == "None" ]] && die "No running tasks found for ${SERVICE}"
log "Task: ${TASK_ARN}"

log "Executing: ${CMD}"
aws ecs execute-command \
    --cluster "${CLUSTER}" \
    --task "${TASK_ARN}" \
    --container web \
    --command "/bin/sh -c \"${CMD}\"" \
    --interactive \
    --region "${REGION}"
