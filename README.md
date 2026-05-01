# netbibi

Crawler of `social.hse.ru` subdomains for the HSE Faculty of Social Sciences.
Goal: collect pages of faculty, students, and research staff. Pages from the main
`hse.ru` are filtered out — only `*.social.hse.ru` is in scope.

## Status

Early scaffold. The crawler logic is not yet implemented. Currently in the repo:

- `unique_words.csv` — seed dictionary (37 232 entries) for future morphological
  enrichment via `pymorphy3` (planned, see `backlogged.md` locally).
- Project skeleton with full CI/CD plumbing: lint, test, type check, multi-stage
  Docker build, automated deploy to VPS, alerts via the existing on-host alerter.

## Local development

Requires Python 3.12, [uv](https://docs.astral.sh/uv/), and Docker.

```bash
uv sync --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest

docker build -t netbibi:dev .
docker run --rm -e MODE=once netbibi:dev
```

`compose.dev.yml` is provided for running the dev image locally with mounted
`output/` and `logs/` directories.

## Modes

The container reacts to the `MODE` environment variable:

- `daemon` — long-running with internal scheduler (production default).
- `once` — single run and exit.
- `manual` — print version and exit (useful for smoke tests).

## Deployment

Production runs on `antopkin-vps` (Debian 12) in `/home/deploy/apps/netbibi/`.
Every merge into `main` triggers an automatic deploy via GitHub Actions.
See [`deploy/README.md`](deploy/README.md) for the full setup, secrets list,
and rollback instructions.
