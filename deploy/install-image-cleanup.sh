#!/usr/bin/env bash
# Install the netbibi image-cleanup systemd timer on the VPS.
# Run from your laptop:  ssh antopkin-vps 'bash -s' < deploy/install-image-cleanup.sh
# Idempotent — safe to re-run.
set -euo pipefail

SUDO=""
if [[ $EUID -ne 0 ]]; then
    SUDO="sudo"
fi

UNIT_DIR="/etc/systemd/system"

echo "[install] writing image-cleanup.service"
$SUDO tee "$UNIT_DIR/image-cleanup.service" > /dev/null <<'UNIT'
[Unit]
Description=Prune old netbibi images (label-scoped, older than 168h)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/usr/bin/docker image prune -af \
    --filter "until=168h" \
    --filter "label=org.opencontainers.image.source=https://github.com/glebsem2005/netbibi"
UNIT

echo "[install] writing image-cleanup.timer"
$SUDO tee "$UNIT_DIR/image-cleanup.timer" > /dev/null <<'UNIT'
[Unit]
Description=Weekly netbibi image cleanup

[Timer]
OnCalendar=Sun *-*-* 04:00:00
Persistent=true
RandomizedDelaySec=15min
Unit=image-cleanup.service

[Install]
WantedBy=timers.target
UNIT

echo "[install] reloading systemd, enabling and starting timer"
$SUDO systemctl daemon-reload
$SUDO systemctl enable --now image-cleanup.timer

echo "[install] done. Status:"
$SUDO systemctl status image-cleanup.timer --no-pager
