# netbibi — Claude project context

> Загружается автоматически в начало каждой сессии Claude Code.
> Здесь — сжатые правила и привязки. Подробности — в README.md, deploy/README.md и тикетах в Plane.

## Что за проект

Краулер по поддоменам `*.social.hse.ru`: собирает страницы преподавателей, студентов и сотрудников факультета социальных наук НИУ ВШЭ. Страницы из основного `hse.ru` отбрасываются. Параллельно есть `unique_words.csv` (37 232 слова) — словарь, который позже расширится морфологически через `pymorphy3` и будет опубликован как артефакт в GitHub Releases.

**Текущий статус:** каркас CI/CD есть, кода краулера ещё нет. `__main__.py` — stub: в `MODE=daemon` спит вечно, в `MODE=once`/`manual` сразу выходит. Это сделано намеренно, чтобы прод-контейнер не падал в restart-loop.

## Стек

- **Python 3.12** (фиксируем минор: `requires-python = ">=3.12,<3.13"`).
- **uv** + hatchling. Лок-файл `uv.lock` коммитится. **Не использовать pip / poetry / pdm** для добавления зависимостей.
- **ruff** (lint + format), **mypy --strict**, **pytest**.
- **Docker multi-stage** (uv builder → `python:3.12-slim-bookworm` runtime, non-root, healthcheck).
- **docker compose** (плагин v2). На VPS есть. Локальная разработка — через `compose.dev.yml`.

## Что уже настроено и НЕ нужно переделывать

CI/CD каркас полностью рабочий. **Если что-то «выглядит странно» — сначала прочитай комментарии и историю, а не предлагай переделать.**

| Компонент | Статус | Не трогать без причины |
|---|---|---|
| `Dockerfile` (multi-stage uv → slim) | ✓ работает, образ ~150 MB | Не менять стек на pip / poetry. Не запекать venv в одну стадию. |
| `unique_words.csv` запекается в образ | ✓ намеренно | Не выносить в volume — словарь меняется через PR в репо, не на VPS вручную. |
| `compose.prod.yml` joins `shared` network | ✓ | `shared` — внешняя docker-сеть alerter'а. `external: true` обязательно. |
| `restart: unless-stopped` + idle sleep в daemon | ✓ | Если контейнер падает — это **не** значит что нужно убрать `restart`. Сначала исправь падение. |
| `.github/workflows/build-and-deploy.yml` | ✓ деплой работает end-to-end | image_tag берётся из metadata-action с `priority=1000` для sha. Без приоритета приходит `:main` — вернётся баг. |
| Уведомления через alerter | ✓ | TG-токенов в GH Secrets **нет** и не должно быть — токен alerter'а живёт на VPS. |
| `infra-watcher` мониторит контейнер | ✓ автоматически | Имя контейнера `netbibi-crawler` — менять нельзя без согласования (infra-watcher идентифицирует по имени). |

## Команды

```bash
uv sync --all-groups          # установить deps
uv run pytest                 # тесты
uv run ruff check . && uv run ruff format --check .
uv run mypy src tests
docker build -t netbibi:dev . # локальная сборка
```

## Деплой

- **Production:** `213.165.220.144` (alias `antopkin-vps`), пользователь `deploy`, путь `/home/deploy/apps/netbibi/`.
- **Образ:** `ghcr.io/glebsem2005/netbibi:sha-XXXXXXX`.
- **Pipeline:** push в `main` → GHA gate → ghcr push → SSH к VPS → `bash /home/deploy/apps/netbibi/deploy.sh sha-XXXXXXX` → `docker compose pull && up -d` → POST в alerter `DEPLOYED`.
- **Откат:** `ssh antopkin-vps 'cd /home/deploy/apps/netbibi && TAG=sha-OLDSHA docker compose up -d'`.

## Project management — Plane

Плэйн (self-hosted Jira-like) — единственный source of truth по бэклогу. Тикеты заводим там, не в GitHub Issues.

- **MCP сервер:** `plane-consulting` (через `uvx plane-mcp-server stdio`, конфиг в `.mcp.json`).
- **API ключ:** в `.env` (`PLANE_API_KEY`). `.env` в `.gitignore`, не коммитим.
- **Workspace:** `consulting` на `https://tasks.antopkin.ru`.
- **Project:** `Стукал против англицизмов` (id `eaccfa8f-cdc0-4537-bf42-8febf9548b97`, identifier `12`).
- **Members:** Олег (oleg.antopkin), Глеб (glebsem2005), Даниил (boss.dany2005).
- **Default state:** `Backlog` (id `f9474c25-...`). Флоу: Backlog → Todo → In Progress → Done | Cancelled.
- **Labels (27 штук, 5 групп):** `type:*` (bug/security/infra/coding/research/content/refactor), `area:*` (cloud/edge/gateway/db/ml/docs/ci/deploy/tests), `effort:*` (XS/S/M/L), `risk:*` (low/med/high), `severity:*` (blocker/critical/major/minor). Каждый тикет помечать минимум `type:*` + `area:*` + `effort:*`.
- **Branch naming:** `<type>/<id>-<slug>`, например `feat/12-7-pymorphy3-ingest`. Имя ветки совпадает с issue prefix Plane.
- **MCP tools:** `mcp__plane-consulting__*` (доступны автоматически после подгрузки MCP).

## Конвенции

- **Язык кода и комментариев:** английский. **Язык общения с пользователем и тикетов в Plane:** русский.
- **Никогда не коммитить** `.env`, секреты, токены, `backlogged.md` (личные заметки).
- **PR через GitHub.** Squash merge по умолчанию. Title в imperative («Add X», «Fix Y»). После merge — ветка удаляется.
- **Структура `src/netbibi/`** — все исходники здесь. `tests/` отдельно. `data/` (внутри образа) — для словаря, `output/` (volume на VPS) — для результатов краулинга.
- **Не добавлять зависимости впрок** — добавлять только когда нужно для конкретного PR.

## Workflow для работы с тикетами Plane (важно для автономных сессий)

Когда пользователь просит «возьми тикеты», «работай по бэклогу», «начинай 12-N» или похожее — следуй этому протоколу. Он одинаков для всех сессий.

### 1. Перед каждым тикетом — один открытый вопрос пользователю

До любых изменений в коде:

1. Прочитать тикет через `mcp__plane-consulting__*` (или REST API).
2. Сформулировать **один открытый вопрос на простом, нетехническом языке**, в котором:
   - 1-2 фразы — что я понял про задачу (своими словами, без жаргона);
   - перечислены развилки/неоднозначности, которые ты увидел;
   - для каждой развилки — **pros и cons** в 1-2 строки (в человеческих терминах: «быстрее / медленнее», «проще поддерживать / сложнее», «больше зависимостей от внешнего», а не «O(n) vs O(n log n)»);
   - твоя рекомендация и какой ответ нужен от пользователя.

Никаких терминов типа «idempotent», «monotonic clock», «GIL» в этом вопросе. Если сомневаешься — заменяй на бытовой синоним или объясняй парой слов.

После ответа пользователя — продолжаешь автономно.

### 2. Технические вопросы — субагенты, НЕ пользователю

Если в процессе работы возникает вопрос «как настроить X в библиотеке Y», «какой best practice для Z», «как ведёт себя API W» — **не таскай пользователя**. Запускай тематического субагента:

- `architect` — архитектурные решения внутри кодобазы (где что должно жить, как разбивать модули).
- `python-pro`, `backend-developer`, `frontend-developer` — стек-специфичные имплементационные вопросы.
- `docker-expert` — Dockerfile/compose/registry.
- `ai-engineer`, `data-engineer` — для ML/NLP-частей (12-1, 12-6, 12-7).
- `general-purpose` (с `mcp__context7__resolve-library-id` + `mcp__context7__query-docs`) — для свежей документации библиотек.
- `claude-code-guide` — вопросы про сам Claude Code / SDK / API.
- `code-reviewer` / `silent-failure-hunter` — перед merge.

### 3. Использование skill `ticket-start`

Бери тикеты через skill `ticket-start` — он делает Definition-of-Ready check, пишет execution plan в комментарий тикета, переводит state. Закрытие тикета — тоже через `ticket-start` (закрывает в `In Review`, не в `Done`; `Done` помечает человек после merge).

### 4. Порядок взятия

Внутри сессии — по приоритету (urgent → high → medium → low). При равном приоритете — сначала тикеты, разблокирующие другие (см. секцию «Зависит от» в описании тикета).

### 5. Когда писать пользователю всё-таки

- Развилка между **двумя осмысленными подходами**, которая повлияет на пользовательский опыт / процесс (а не на внутреннюю реализацию).
- Решение требует **бизнес-контекста**, которого нет в тикете (приоритет, сроки, договорённости с другими).
- Найдено что-то **вне scope тикета** (другой баг/риск) — спросить, открывать новый тикет или игнорировать.
- Нужна **ручная операция вне репо** (включить branch protection, создать релиз, изменить настройки на VPS).

### 6. Когда НЕ писать пользователю

- Выбор между двумя реализациями одной фичи, где разница только в стиле/перформансе.
- Уточнение синтаксиса / API / семантики библиотеки.
- «У меня тут ошибка ruff/mypy/pytest» — сначала исследуй сам / через субагента.

## Прочие подсказки

- Если просят «настрой CI/CD» — скажи что уже настроено, и предложи fixup конкретного аспекта вместо переделки.
- Если кажется, что MCP `plane-consulting` не работает — проверь, что `.env` существует и содержит `PLANE_API_KEY`. Скопировать значение можно из `~/sandbox/faun/.env`.
- Для добавления нового тикета — `mcp__plane-consulting__create_issue` (или REST API через `curl` если MCP не загружен).
- Healthcheck в Dockerfile — пока заглушка `python -c "import netbibi"`. Заменить на реальный probe, когда появится HTTP-сервис или файл `.heartbeat`.
