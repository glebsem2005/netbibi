#!/usr/bin/env bash
# Deploy or roll back a netbibi image on the VPS.
# Usage: bash deploy.sh <image-tag> [event_key=DEPLOYED] [actor=system]
# Invoked from GitHub Actions over SSH (build-and-deploy.yml, dispatch-rollback.yml).
set -euo pipefail

TAG="${1:?Usage: deploy.sh <image-tag> [event_key] [actor]}"
EVENT_KEY="${2:-DEPLOYED}"
ACTOR="${3:-system}"
APP_DIR="/home/deploy/apps/netbibi"

cd "$APP_DIR"
export TAG

if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

echo "[deploy] event=$EVENT_KEY pulling ghcr.io/glebsem2005/netbibi:$TAG"
docker compose pull crawler

echo "[deploy] up -d --remove-orphans"
docker compose up -d --remove-orphans crawler

echo "[deploy] image prune (keep last 72h)"
docker image prune -f --filter "until=72h" >/dev/null 2>&1 || true

if [[ -n "${ALERT_SHARED_TOKEN:-}" ]]; then
    echo "[deploy] notify alerter ($EVENT_KEY)"
    # Keep DEPLOYED payload backward-compatible (no actor field);
    # add actor only for ROLLBACK / non-default events for audit trail.
    if [[ "$EVENT_KEY" == "DEPLOYED" ]]; then
        DETAILS="tag=$TAG"
    else
        DETAILS="tag=$TAG actor=$ACTOR"
    fi
    docker run --rm --network shared curlimages/curl:8.10.1 \
        -fsS -X POST "${ALERTER_URL:-http://alerter:8080/alert}" \
        -H "X-Alert-Token: $ALERT_SHARED_TOKEN" \
        -H "Content-Type: application/json" \
        --data "{\"source\":\"netbibi\",\"key\":\"$EVENT_KEY\",\"details\":\"$DETAILS\"}" \
        || echo "[deploy] alerter notify failed (non-fatal)"
else
    echo "[deploy] ALERT_SHARED_TOKEN not set in .env — skipping notification"
fi

echo "[deploy] done $EVENT_KEY tag=$TAG"
