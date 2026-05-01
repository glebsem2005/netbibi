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
from urllib.parse import urlparse, urlunparse


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
    raise NotImplementedError


def parse_page(html: str, page_url: str, host_filter: re.Pattern[str]) -> tuple[str, list[str]]:
    raise NotImplementedError


async def crawl(config: CrawlerConfig) -> CrawlStats:
    raise NotImplementedError
