#!/usr/bin/env bash
# Deploy a new netbibi image on the VPS.
# Usage: bash deploy.sh <image-tag>
# Invoked from GitHub Actions over SSH.
set -euo pipefail

TAG="${1:?Usage: deploy.sh <image-tag>}"
APP_DIR="/home/deploy/apps/netbibi"

cd "$APP_DIR"
export TAG

if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

echo "[deploy] pulling ghcr.io/glebsem2005/netbibi:$TAG"
docker compose pull crawler

echo "[deploy] up -d --remove-orphans"
docker compose up -d --remove-orphans crawler

echo "[deploy] image prune (keep last 72h)"
docker image prune -f --filter "until=72h" >/dev/null 2>&1 || true

if [[ -n "${ALERT_SHARED_TOKEN:-}" ]]; then
    echo "[deploy] notify alerter"
    docker run --rm --network shared curlimages/curl:8.10.1 \
        -fsS -X POST "${ALERTER_URL:-http://alerter:8080/alert}" \
        -H "X-Alert-Token: $ALERT_SHARED_TOKEN" \
        -H "Content-Type: application/json" \
        --data "{\"source\":\"netbibi\",\"key\":\"DEPLOYED\",\"details\":\"tag=$TAG\"}" \
        || echo "[deploy] alerter notify failed (non-fatal)"
else
    echo "[deploy] ALERT_SHARED_TOKEN not set in .env — skipping notification"
fi

echo "[deploy] done $TAG"
