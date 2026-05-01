"""Generic async BFS crawler.

Configurable via env vars (`CrawlerConfig.from_env`) or programmatically.
Outputs `text.csv` (url, text) and `links.csv` (from_url, to_url) into
`output_dir`. Pure helpers (`normalize_url`, `is_valid_link`, `parse_page`)
are decoupled from I/O so they can be unit-tested without mocks.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

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
        raise NotImplementedError


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


async def crawl(config: CrawlerConfig) -> CrawlStats:
    raise NotImplementedError
