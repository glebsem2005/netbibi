# deploy/

Files for deploying netbibi on the existing VPS (`antopkin-vps`, `213.165.220.144`).

## Files

- `compose.prod.yml` — production compose. Joins the existing `shared` Docker network so it can reach `alerter`.
- `init-vps.sh` — idempotent first-time setup. Verifies docker/compose/`shared` network and creates `/home/deploy/apps/netbibi/{output,logs}`.
- `deploy.sh` — invoked from GitHub Actions over SSH. Pulls the new image, restarts the container, and posts a `DEPLOYED` event to the existing alerter.
- `image-cleanup.service` / `image-cleanup.timer` — systemd units (reference copy) that prune old netbibi images. The runtime copy lives in `/etc/systemd/system/` on the VPS.
- `install-image-cleanup.sh` — installer for the cleanup timer (run once via SSH; idempotent).

## First-time setup (manual)

Run once from your laptop:

```bash
# 1. SSH and run init script
ssh antopkin-vps 'bash -s' < deploy/init-vps.sh

# 2. Copy compose.prod.yml as compose.yml
scp deploy/compose.prod.yml antopkin-vps:/home/deploy/apps/netbibi/compose.yml

# 3. Copy .env, then fill ALERT_SHARED_TOKEN from the existing alerter
scp .env.example antopkin-vps:/home/deploy/apps/netbibi/.env
ssh antopkin-vps 'grep ALERT_SHARED_TOKEN /home/deploy/apps/alerter/.env >> /home/deploy/apps/netbibi/.env && sort -u /home/deploy/apps/netbibi/.env -o /home/deploy/apps/netbibi/.env'

# 4. Authorise the GHA SSH key
ssh-copy-id -i ~/.ssh/github_deploy.pub deploy@213.165.220.144

# 5. Login to ghcr.io with a PAT (read:packages)
ssh antopkin-vps 'read -s -p "PAT: " PAT; echo; echo "$PAT" | docker login ghcr.io -u <gh-user> --password-stdin'

# 6. First manual pull and up (verify)
ssh antopkin-vps 'cd /home/deploy/apps/netbibi && docker compose pull && docker compose up -d && docker compose ps'
```

## How CI/CD works

1. PR → CI runs ruff/mypy/pytest + docker build check.
2. Merge to `main` → workflow `Build and Deploy`:
   1. `gate` repeats lint+test (uv cache makes it cheap).
   2. `build-and-push` builds image and pushes to `ghcr.io/glebsem2005/netbibi:sha-XXXXXX` and `:latest`.
   3. `deploy` SSHes into the VPS and runs `bash /home/deploy/apps/netbibi/deploy.sh sha-XXXXXX`.
   4. `deploy.sh` pulls the new image, `docker compose up -d`, and posts `DEPLOYED` to alerter.
3. On any failure, `notify-failure` job posts `DEPLOY_FAILED` to alerter.
4. The existing `infra-watcher` watches `netbibi-crawler` and posts `CONTAINER_RESTARTING` / `UNHEALTHY` / `RECOVERED` events automatically.

## Image cleanup

`deploy.sh` only prunes dangling untagged images, so old `sha-XXX` tagged
images would accumulate over months. A weekly systemd timer prunes them
label-scoped (only netbibi images, leaving the other ~7 projects on the
VPS alone).

Install once:

```bash
ssh antopkin-vps 'bash -s' < deploy/install-image-cleanup.sh
```

Verify:

```bash
ssh antopkin-vps 'systemctl status image-cleanup.timer'
ssh antopkin-vps 'journalctl -u image-cleanup.service --since "8 days ago"'
ssh antopkin-vps 'docker images --filter "label=org.opencontainers.image.source=https://github.com/glebsem2005/netbibi"'
```

If the label filter shows zero images **after** a normal deploy, the
`LABEL` in `Dockerfile` is missing — check the runtime stage.

## Rollback

SSH into the VPS and pin a previous SHA tag:

```bash
ssh antopkin-vps 'cd /home/deploy/apps/netbibi && TAG=sha-OLDSHA docker compose up -d'
```
