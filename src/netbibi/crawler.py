"""Generic async BFS crawler.

Configurable via env vars (`CrawlerConfig.from_env`) or programmatically.
Outputs `text.csv` (url, text) and `links.csv` (from_url, to_url) into
`output_dir`. Pure helpers (`normalize_url`, `is_valid_link`, `parse_page`)
are decoupled from I/O so they can be unit-tested without mocks.
"""

from __future__ import annotations

import asyncio
import csv
import os
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import aiohttp
from bs4 import BeautifulSoup

# CSS selectors removed before text/link extraction. Mirrors the original
# fsn_parser.FOOTER_SELECTORS so footer navigation does not leak into
# the page text or the discovered link graph.
_FOOTER_SELECTORS = (
    "footer",
    "[class*='footer']",
    "[id*='footer']",
    "[class*='Footer']",
    "[id*='Footer']",
)
_BOILERPLATE_TAGS = ("script", "style", "noscript", "meta", "head")
_SKIP_HREF_PREFIXES = ("javascript:", "mailto:", "tel:", "#")


@dataclass(frozen=True)
class CrawlerConfig:
    seed_url: str
    host_filter: re.Pattern[str]
    output_dir: Path
    max_depth: int = 5
    concurrency: int = 12
    request_delay_ms: int = 0
    request_timeout_s: int = 30
    user_agent: str = "netbibi/0.1 (+https://github.com/glebsem2005/netbibi)"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> CrawlerConfig:
        e: Mapping[str, str] = env if env is not None else os.environ
        required = ("SEED_URL", "HOST_FILTER", "OUTPUT_DIR")
        missing = [k for k in required if not e.get(k)]
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")
        return cls(
            seed_url=e["SEED_URL"],
            host_filter=re.compile(e["HOST_FILTER"]),
            output_dir=Path(e["OUTPUT_DIR"]),
            max_depth=int(e.get("MAX_DEPTH", "5")),
            concurrency=int(e.get("CONCURRENCY", "12")),
            request_delay_ms=int(e.get("REQUEST_DELAY_MS", "0")),
            request_timeout_s=int(e.get("REQUEST_TIMEOUT_S", "30")),
            user_agent=e.get(
                "USER_AGENT",
                "netbibi/0.1 (+https://github.com/glebsem2005/netbibi)",
            ),
        )


@dataclass(frozen=True)
class CrawlStats:
    pages_saved: int
    urls_visited: int
    errors: int


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    cleaned = parsed._replace(netloc=parsed.netloc.lower(), fragment="")
    return urlunparse(cleaned).rstrip("/")


def is_valid_link(url: str, host_filter: re.Pattern[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    return host_filter.fullmatch(parsed.netloc) is not None


def parse_page(html: str, page_url: str, host_filter: re.Pattern[str]) -> tuple[str, list[str]]:
    soup = BeautifulSoup(html, "lxml")
    for selector in _FOOTER_SELECTORS:
        for el in soup.select(selector):
            el.decompose()
    for tag in _BOILERPLATE_TAGS:
        for el in soup.find_all(tag):
            el.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    links: list[str] = []
    for a in soup.find_all("a", href=True):
        raw = str(a["href"]).strip()
        if not raw or raw.startswith(_SKIP_HREF_PREFIXES):
            continue
        absolute = normalize_url(urljoin(page_url, raw))
        if is_valid_link(absolute, host_filter):
            links.append(absolute)
    return text, links


async def _fetch(session: Any, url: str, timeout_s: int) -> str | None:
    """Fetch one URL; returns HTML on 200 + text/html, else None.

    Mirrors the silent-failure semantics of fsn_parser.fetch
    (errors logged to stderr, return None) — a single bad URL must not
    abort a long crawl.
    """
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    try:
        async with session.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            max_redirects=5,
        ) as resp:
            if resp.status != 200:
                return None
            ctype = resp.headers.get("content-type", "")
            if "text/html" not in ctype:
                return None
            text: str = await resp.text(errors="replace")
            return text
    except Exception as exc:
        print(f"[crawler] fetch error {url}: {exc}", file=sys.stderr)
        return None


def _default_session_factory(config: CrawlerConfig) -> Callable[[], Any]:
    def factory() -> Any:
        return aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=config.concurrency),
            headers={"User-Agent": config.user_agent},
        )

    return factory


async def crawl(
    config: CrawlerConfig,
    *,
    session_factory: Callable[[], Any] | None = None,
) -> CrawlStats:
    """BFS crawl from `config.seed_url` constrained by `config.host_filter`.

    Writes `text.csv` (url, text) and `links.csv` (from_url, to_url) into
    `config.output_dir`, streamed and flushed per BFS level.
    `session_factory` is a test seam: defaults to a real aiohttp session.
    """
    factory = session_factory or _default_session_factory(config)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    pages_saved = 0
    urls_visited = 0
    errors = 0

    seed = normalize_url(config.seed_url)
    visited: set[str] = {seed}
    queue: list[tuple[str, int]] = [(seed, 0)]

    text_path = config.output_dir / "text.csv"
    links_path = config.output_dir / "links.csv"

    async with factory() as session:
        with (
            text_path.open("w", encoding="utf-8", newline="") as text_f,
            links_path.open("w", encoding="utf-8", newline="") as links_f,
        ):
            text_w = csv.writer(text_f, quoting=csv.QUOTE_ALL)
            links_w = csv.writer(links_f, quoting=csv.QUOTE_ALL)
            text_w.writerow(["url", "text"])
            links_w.writerow(["from_url", "to_url"])

            while queue:
                level = queue
                queue = []
                cur_depth = level[0][1]
                if cur_depth > config.max_depth:
                    break

                if config.request_delay_ms:
                    await asyncio.sleep(config.request_delay_ms / 1000)

                results = await asyncio.gather(
                    *(_fetch(session, url, config.request_timeout_s) for url, _ in level)
                )

                for (url, depth), html in zip(level, results, strict=True):
                    urls_visited += 1
                    if html is None:
                        errors += 1
                        continue
                    text, links = parse_page(html, url, config.host_filter)
                    text_w.writerow([url, text])
                    pages_saved += 1
                    for link in set(links):
                        links_w.writerow([url, link])
                        if link not in visited and depth + 1 <= config.max_depth:
                            visited.add(link)
                            queue.append((link, depth + 1))

                text_f.flush()
                links_f.flush()

    return CrawlStats(
        pages_saved=pages_saved,
        urls_visited=urls_visited,
        errors=errors,
    )
