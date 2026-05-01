"""Entrypoint for `python -m netbibi`."""

from __future__ import annotations

import os
import sys

from netbibi import __version__


def main() -> int:
    mode = os.environ.get("MODE", "manual").lower()
    print(f"netbibi v{__version__} [MODE={mode}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
