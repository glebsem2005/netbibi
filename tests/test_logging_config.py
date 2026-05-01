"""Tests for netbibi.logging_config."""

from __future__ import annotations

import json
import logging

import pytest

from netbibi.logging_config import configure_logging


def test_emits_one_line_json_per_record(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    log = logging.getLogger("netbibi.test")
    log.info("crawl_started", extra={"url": "https://x.com", "depth": 1})
    err = capsys.readouterr().err.strip()
    payload = json.loads(err)
    assert payload["event"] == "crawl_started"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "netbibi.test"
    assert payload["url"] == "https://x.com"
    assert payload["depth"] == 1
    assert "ts" in payload


def test_log_level_env_var_filters_below_threshold(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    configure_logging()
    log = logging.getLogger("netbibi.test")
    log.info("ignored")
    log.warning("kept")
    err = capsys.readouterr().err
    assert "ignored" not in err
    assert "kept" in err


def test_explicit_level_arg_overrides_env(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "ERROR")
    configure_logging(level="DEBUG")
    log = logging.getLogger("netbibi.test")
    log.debug("kept")
    err = capsys.readouterr().err
    assert "kept" in err


def test_exception_info_included_when_logged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging()
    log = logging.getLogger("netbibi.test")
    try:
        raise ValueError("boom")
    except ValueError:
        log.exception("oops")
    err = capsys.readouterr().err.strip()
    payload = json.loads(err)
    assert payload["event"] == "oops"
    assert payload["error_type"] == "ValueError"
    assert "boom" in payload["traceback"]


def test_configure_logging_is_idempotent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging()
    configure_logging()
    log = logging.getLogger("netbibi.test")
    log.info("once")
    err = capsys.readouterr().err.strip()
    # exactly one line — second configure replaced the first handler
    assert len(err.splitlines()) == 1
