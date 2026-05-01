"""Smoke tests for the netbibi package."""

from __future__ import annotations

import pytest

import netbibi
from netbibi.__main__ import main


def test_version_is_nonempty_string() -> None:
    assert isinstance(netbibi.__version__, str)
    assert netbibi.__version__


def test_main_returns_zero_in_manual_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODE", "manual")
    assert main() == 0


def test_main_returns_one_in_once_mode_without_required_env(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MODE", "once")
    monkeypatch.delenv("SEED_URL", raising=False)
    monkeypatch.delenv("HOST_FILTER", raising=False)
    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    assert main() == 1
    err = capsys.readouterr().err
    assert "config error" in err


def test_main_invokes_crawl_in_once_mode_with_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """MODE=once with full env runs crawl(); we monkeypatch crawl to skip network."""
    from netbibi import crawler
    from netbibi.crawler import CrawlStats

    async def fake_crawl(config: crawler.CrawlerConfig) -> CrawlStats:
        return CrawlStats(pages_saved=7, urls_visited=10, errors=0)

    monkeypatch.setenv("MODE", "once")
    monkeypatch.setenv("SEED_URL", "https://example.com")
    monkeypatch.setenv("HOST_FILTER", r"example\.com")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr("netbibi.__main__.crawl", fake_crawl)
    assert main() == 0
