"""Entrypoint for `python -m netbibi`."""

from __future__ import annotations

import os
import sys
import time

from netbibi import __version__


def main() -> int:
    mode = os.environ.get("MODE", "manual").lower()
    print(f"netbibi v{__version__} [MODE={mode}]", flush=True)

    if mode == "daemon":
        # Keep the container alive until real crawler logic exists.
        while True:
            time.sleep(3600)

    return 0


if __name__ == "__main__":
    sys.exit(main())
