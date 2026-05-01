"""Unit tests for netbibi.crawler — TDD, grouped by function."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

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


# --- CrawlerConfig.from_env ---


def test_from_env_raises_with_all_missing_required_listed() -> None:
    import pytest

    with pytest.raises(ValueError) as exc_info:
        crawler.CrawlerConfig.from_env(env={})
    msg = str(exc_info.value)
    # error names every missing required env var so the user fixes all at once
    assert "SEED_URL" in msg
    assert "HOST_FILTER" in msg
    assert "OUTPUT_DIR" in msg


def test_from_env_applies_defaults_and_compiles_regex(tmp_path: object) -> None:
    env = {
        "SEED_URL": "https://example.com",
        "HOST_FILTER": r".*\.example\.com|example\.com",
        "OUTPUT_DIR": "/tmp/out",
    }
    cfg = crawler.CrawlerConfig.from_env(env=env)
    assert cfg.seed_url == "https://example.com"
    # regex must come back compiled and ready to match
    assert cfg.host_filter.fullmatch("sub.example.com") is not None
    assert cfg.output_dir.as_posix() == "/tmp/out"
    # defaults
    assert cfg.max_depth == 5
    assert cfg.concurrency == 12
    assert cfg.request_delay_ms == 0
    assert cfg.request_timeout_s == 30
    assert "netbibi" in cfg.user_agent


def test_from_env_overrides_defaults_when_present() -> None:
    env = {
        "SEED_URL": "https://x.com",
        "HOST_FILTER": r"x\.com",
        "OUTPUT_DIR": "/o",
        "MAX_DEPTH": "3",
        "CONCURRENCY": "4",
        "REQUEST_DELAY_MS": "100",
        "REQUEST_TIMEOUT_S": "10",
        "USER_AGENT": "custom-agent/1.0",
    }
    cfg = crawler.CrawlerConfig.from_env(env=env)
    assert cfg.max_depth == 3
    assert cfg.concurrency == 4
    assert cfg.request_delay_ms == 100
    assert cfg.request_timeout_s == 10
    assert cfg.user_agent == "custom-agent/1.0"


# --- crawl() smoke test with FakeSession ---


class _FakeResponse:
    def __init__(self, html: str, status: int = 200) -> None:
        self._html = html
        self.status = status
        self.headers = {"content-type": "text/html; charset=utf-8"}

    async def text(self, errors: str = "strict") -> str:
        return self._html

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None


class _FakeSession:
    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages
        self.requested: list[str] = []

    def get(self, url: str, **kwargs: object) -> _FakeResponse:
        self.requested.append(url)
        if url in self._pages:
            return _FakeResponse(self._pages[url], status=200)
        return _FakeResponse("", status=404)

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None


def test_crawl_bfs_writes_text_and_links_csv_into_output_dir(
    tmp_path: Path,
) -> None:
    pages = {
        "https://example.com": (
            '<html><body><a href="/about">About</a><a href="/contact">Contact</a></body></html>'
        ),
        "https://example.com/about": (
            '<html><body><h1>About us</h1><a href="/team">Team</a></body></html>'
        ),
        "https://example.com/contact": ("<html><body><p>Contact details</p></body></html>"),
        "https://example.com/team": ("<html><body><p>Team page</p></body></html>"),
    }
    session = _FakeSession(pages)
    cfg = crawler.CrawlerConfig(
        seed_url="https://example.com",
        host_filter=re.compile(r"example\.com"),
        output_dir=tmp_path,
        max_depth=3,
        concurrency=2,
    )

    stats = asyncio.run(crawler.crawl(cfg, session_factory=lambda: session))

    assert stats.pages_saved == 4  # all four pages reachable within depth 3
    text_csv = tmp_path / "text.csv"
    links_csv = tmp_path / "links.csv"
    assert text_csv.exists()
    assert links_csv.exists()
    text = text_csv.read_text(encoding="utf-8")
    links = links_csv.read_text(encoding="utf-8")
    assert "About us" in text
    assert "Contact details" in text
    assert "Team page" in text
    assert "https://example.com/about" in links
    assert "https://example.com/contact" in links


def test_crawl_respects_max_depth_zero_only_visits_seed(tmp_path: Path) -> None:
    pages = {
        "https://example.com": ('<html><body><a href="/deeper">Deeper</a></body></html>'),
        "https://example.com/deeper": ("<html><body><p>Deeper</p></body></html>"),
    }
    session = _FakeSession(pages)
    cfg = crawler.CrawlerConfig(
        seed_url="https://example.com",
        host_filter=re.compile(r"example\.com"),
        output_dir=tmp_path,
        max_depth=0,
        concurrency=1,
    )
    stats = asyncio.run(crawler.crawl(cfg, session_factory=lambda: session))
    # only seed visited; child URL never fetched
    assert stats.pages_saved == 1
    assert "https://example.com/deeper" not in session.requested
