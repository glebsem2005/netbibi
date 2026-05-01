"""Unit tests for netbibi.crawler — TDD, grouped by function."""

from __future__ import annotations

from netbibi import crawler


def test_crawler_module_imports() -> None:
    assert hasattr(crawler, "CrawlerConfig")
    assert hasattr(crawler, "CrawlStats")
    assert hasattr(crawler, "normalize_url")
    assert hasattr(crawler, "is_valid_link")
    assert hasattr(crawler, "parse_page")
    assert hasattr(crawler, "crawl")


# --- normalize_url ---


def test_normalize_url_strips_fragment() -> None:
    assert crawler.normalize_url("https://Example.com/page#section") == "https://example.com/page"


def test_normalize_url_lowercases_netloc_only_not_path() -> None:
    # path keeps case; only netloc is lowercased
    result = crawler.normalize_url("https://Example.COM/Some/Path")
    assert result == "https://example.com/Some/Path"


def test_normalize_url_strips_trailing_slash() -> None:
    assert crawler.normalize_url("https://example.com/page/") == "https://example.com/page"
    # root-level trailing slash also stripped (matches original fsn_parser behavior)
    assert crawler.normalize_url("https://example.com/") == "https://example.com"
