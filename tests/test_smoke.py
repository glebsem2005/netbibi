"""Smoke tests for the netbibi package."""

from __future__ import annotations

import pytest

import netbibi
from netbibi.__main__ import main


def test_version_is_nonempty_string() -> None:
    assert isinstance(netbibi.__version__, str)
    assert netbibi.__version__


@pytest.mark.parametrize("mode", ["manual", "once"])
def test_main_returns_zero(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    monkeypatch.setenv("MODE", mode)
    assert main() == 0
