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


# --- is_valid_link ---


import re  # noqa: E402

EXAMPLE_FILTER = re.compile(r".*\.example\.com|example\.com")


def test_is_valid_link_rejects_non_http_schemes() -> None:
    assert not crawler.is_valid_link("javascript:void(0)", EXAMPLE_FILTER)
    assert not crawler.is_valid_link("mailto:a@example.com", EXAMPLE_FILTER)
    assert not crawler.is_valid_link("tel:+12345", EXAMPLE_FILTER)
    assert not crawler.is_valid_link("ftp://example.com/file", EXAMPLE_FILTER)


def test_is_valid_link_accepts_url_whose_netloc_matches_filter() -> None:
    assert crawler.is_valid_link("https://example.com/page", EXAMPLE_FILTER)
    assert crawler.is_valid_link("http://sub.example.com/page", EXAMPLE_FILTER)
    assert crawler.is_valid_link("https://deep.sub.example.com/", EXAMPLE_FILTER)


def test_is_valid_link_rejects_url_whose_netloc_does_not_match_filter() -> None:
    assert not crawler.is_valid_link("https://other.com/page", EXAMPLE_FILTER)
    # fullmatch semantics: 'evilexample.com' must NOT match 'example.com' filter
    assert not crawler.is_valid_link("https://evilexample.com/page", EXAMPLE_FILTER)
