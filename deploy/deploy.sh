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

# Run a command with exponential backoff. Usage: retry_with_backoff <attempts> <base_seconds> <cmd...>
# base 2s, multiplier 2 -> sleeps 2s, 4s, 8s before attempts 2, 3, 4 respectively.
retry_with_backoff() {
    local attempts="$1"
    local base_delay="$2"
    shift 2
    local attempt=1
    local delay="$base_delay"
    while true; do
        if "$@"; then
            return 0
        fi
        if (( attempt >= attempts )); then
            echo "[deploy] giving up after $attempts attempt(s): $*" >&2
            return 1
        fi
        echo "[deploy] attempt $attempt/$attempts failed; sleeping ${delay}s then retrying" >&2
        sleep "$delay"
        attempt=$(( attempt + 1 ))
        delay=$(( delay * 2 ))
    done
}

# POST a JSON event to the alerter (best-effort, never aborts the script unless caller checks).
# Usage: alerter_post <key> <details_string>
alerter_post() {
    local key="$1"
    local details="$2"
    if [[ -z "${ALERT_SHARED_TOKEN:-}" ]]; then
        echo "[deploy] ALERT_SHARED_TOKEN not set in .env — skipping notification ($key)" >&2
        return 0
    fi
    local payload
    payload="$(jq -cn \
        --arg src "netbibi" \
        --arg k "$key" \
        --arg d "$details" \
        '{source: $src, key: $k, details: $d}')"
    docker run --rm --network shared curlimages/curl:8.10.1 \
        -fsS -X POST "${ALERTER_URL:-http://alerter:8080/alert}" \
        -H "X-Alert-Token: $ALERT_SHARED_TOKEN" \
        -H "Content-Type: application/json" \
        --data "$payload" \
        || echo "[deploy] alerter notify ($key) failed (non-fatal)" >&2
}

echo "[deploy] pulling ghcr.io/glebsem2005/netbibi:$TAG"
if ! retry_with_backoff 3 2 docker compose pull crawler; then
    alerter_post "PULL_FAILED" "tag=$TAG"
    exit 1
fi

echo "[deploy] up -d --remove-orphans"
docker compose up -d --remove-orphans crawler

echo "[deploy] image prune (keep last 72h)"
docker image prune -f --filter "until=72h" >/dev/null 2>&1 || true

alerter_post "DEPLOYED" "tag=$TAG"

echo "[deploy] done $TAG"
