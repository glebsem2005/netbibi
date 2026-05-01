"""Smoke tests for the netbibi package."""

from __future__ import annotations

import netbibi
from netbibi.__main__ import main


def test_version_is_nonempty_string() -> None:
    assert isinstance(netbibi.__version__, str)
    assert netbibi.__version__


def test_main_returns_zero() -> None:
    assert main() == 0
