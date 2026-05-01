"""Unit tests for netbibi.crawler — TDD, grouped by function."""

from __future__ import annotations

import re

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


# --- parse_page ---


def test_parse_page_strips_script_style_footer_before_text_extraction() -> None:
    html = """
    <html><body>
      <header>Top</header>
      <main>Main content</main>
      <script>alert('x')</script>
      <style>.hidden{display:none}</style>
      <footer>Footer noise</footer>
      <div class="page-footer">More footer</div>
    </body></html>
    """
    text, _ = crawler.parse_page(html, "https://example.com", EXAMPLE_FILTER)
    assert "Main content" in text
    assert "Top" in text
    assert "alert" not in text
    assert "display:none" not in text
    assert "Footer noise" not in text
    assert "More footer" not in text


def test_parse_page_extracts_absolute_links_resolving_relative() -> None:
    html = """
    <html><body>
      <a href="/about">About</a>
      <a href="https://example.com/contact">Contact</a>
      <a href="https://other.com/external">External</a>
      <a href="javascript:void(0)">JS</a>
      <a href="mailto:a@example.com">Mail</a>
      <a href="#anchor">Anchor</a>
      <a href="">Empty</a>
    </body></html>
    """
    _, links = crawler.parse_page(html, "https://example.com/page", EXAMPLE_FILTER)
    assert "https://example.com/about" in links
    assert "https://example.com/contact" in links
    assert "https://other.com/external" not in links  # filtered by host
    assert not any("javascript" in lk for lk in links)
    assert not any("mailto" in lk for lk in links)


def test_parse_page_collapses_whitespace() -> None:
    html = "<html><body><p>foo     bar\n\n\n\n\nbaz</p></body></html>"
    text, _ = crawler.parse_page(html, "https://example.com", EXAMPLE_FILTER)
    # 2+ spaces collapse to 1
    assert "foo bar" in text
    # 3+ newlines collapse to 2
    assert "\n\n\n" not in text
