#!/usr/bin/env bash
# Idempotent first-time setup of /home/deploy/apps/netbibi/ on the VPS.
# Run as user `deploy`.
set -euo pipefail

if [[ "$(whoami)" != "deploy" ]]; then
    echo "ERROR: must run as user 'deploy', got '$(whoami)'" >&2
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker not installed" >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "ERROR: docker compose plugin not available" >&2
    exit 1
fi

if ! docker network inspect shared >/dev/null 2>&1; then
    echo "ERROR: docker network 'shared' does not exist (alerter is expected to have created it)" >&2
    exit 1
fi

APP_DIR="/home/deploy/apps/netbibi"
mkdir -p "$APP_DIR/output" "$APP_DIR/logs"

echo "[init] $APP_DIR is ready"

if [[ ! -f "$APP_DIR/compose.yml" ]]; then
    echo "[init] no compose.yml in $APP_DIR — copy deploy/compose.prod.yml to $APP_DIR/compose.yml"
fi

if [[ ! -f "$APP_DIR/.env" ]]; then
    echo "[init] no .env in $APP_DIR — copy .env.example, then fill ALERT_SHARED_TOKEN from /home/deploy/apps/alerter/.env"
fi

if [[ ! -f "$HOME/.docker/config.json" ]]; then
    echo "[init] WARNING: no ghcr.io credentials. Run: echo \$PAT | docker login ghcr.io -u <username> --password-stdin"
fi

echo
echo "[init] Final manual steps:"
echo "  1. scp deploy/compose.prod.yml deploy@<host>:$APP_DIR/compose.yml"
echo "  2. Place github_deploy.pub into /home/deploy/.ssh/authorized_keys"
echo "  3. Create $APP_DIR/.env from .env.example (fill ALERT_SHARED_TOKEN)"
echo "  4. docker login ghcr.io with a PAT (read:packages scope)"
echo "  5. cd $APP_DIR && docker compose pull && docker compose up -d (verify)"
