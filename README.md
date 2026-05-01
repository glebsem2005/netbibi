# netbibi

Crawler of `social.hse.ru` subdomains for the HSE Faculty of Social Sciences.
Goal: collect pages of faculty, students, and research staff. Pages from the main
`hse.ru` are filtered out — only `*.social.hse.ru` is in scope.

## Status

Reusable async BFS crawler in `src/netbibi/crawler.py`, configurable via env
vars to crawl any site. Originally a one-off script for `social.hse.ru`
(see `fsn_*.csv` in repo root for the historical dataset); now generalized.

Also in repo:

- `unique_words.csv` — seed dictionary (37 232 entries) for future morphological
  enrichment via `pymorphy3` (planned).
- Full CI/CD plumbing: lint, test, type check, multi-stage Docker build,
  automated deploy to VPS, alerts via the existing on-host alerter, manual
  rollback workflow.

## Local development

Requires Python 3.12, [uv](https://docs.astral.sh/uv/), and Docker.

```bash
uv sync --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest

docker build -t netbibi:dev .
docker run --rm -e MODE=once netbibi:dev   # exits 1 — needs crawl config
```

`compose.dev.yml` is provided for running the dev image locally with mounted
`output/` and `logs/` directories.

## Modes

The container reacts to the `MODE` environment variable:

- `daemon` — sleeps forever (compose `restart=unless-stopped` keeps it alive
  between scheduled runs).
- `once` — runs one BFS crawl using `CrawlerConfig.from_env()`, then exits.
- `manual` — prints version and exits (used for smoke tests).

## Crawler configuration (MODE=once)

Required env vars:

| Var          | Example                          | Notes                                   |
|--------------|----------------------------------|-----------------------------------------|
| `SEED_URL`   | `https://example.com`            | Where BFS starts                        |
| `HOST_FILTER`| `.*\.example\.com\|example\.com` | Python regex; `re.fullmatch` vs netloc  |
| `OUTPUT_DIR` | `/app/output`                    | Writes `text.csv` and `links.csv` here  |

Optional (defaults shown):

| Var                 | Default | Notes                                        |
|---------------------|---------|----------------------------------------------|
| `MAX_DEPTH`         | `5`     | BFS depth gate                               |
| `CONCURRENCY`       | `12`    | Parallel `aiohttp` requests                  |
| `REQUEST_DELAY_MS`  | `0`     | Between BFS levels (politeness)              |
| `REQUEST_TIMEOUT_S` | `30`    | Per request                                  |
| `USER_AGENT`        | `netbibi/0.1 ...` | Sent on every request                  |

### Examples

```bash
# Crawl example.com only
docker run --rm \
  -e MODE=once \
  -e SEED_URL=https://example.com \
  -e HOST_FILTER='example\.com' \
  -e OUTPUT_DIR=/out \
  -e MAX_DEPTH=3 \
  -v "$PWD/out:/out" \
  netbibi:dev

# Crawl all *.social.hse.ru subdomains (the original use case)
docker run --rm \
  -e MODE=once \
  -e SEED_URL=https://social.hse.ru \
  -e HOST_FILTER='.*\.social\.hse\.ru|social\.hse\.ru' \
  -e OUTPUT_DIR=/out \
  -e MAX_DEPTH=8 \
  -v "$PWD/out:/out" \
  netbibi:dev
```

Output is two QUOTE_ALL CSVs in `OUTPUT_DIR`:

- `text.csv` — `url, text` (one row per crawled page).
- `links.csv` — `from_url, to_url` (one row per discovered intra-host edge).

## Deployment

Production runs on `antopkin-vps` (Debian 12) in `/home/deploy/apps/netbibi/`.
Every merge into `main` triggers an automatic deploy via GitHub Actions.
See [`deploy/README.md`](deploy/README.md) for the full setup, secrets list,
and rollback instructions.
