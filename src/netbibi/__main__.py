"""Entrypoint for `python -m netbibi`."""

from __future__ import annotations

import logging
import os
import sys
import time

from netbibi import __version__
from netbibi.logging_config import configure_logging


def main() -> int:
    configure_logging()
    log = logging.getLogger("netbibi")
    mode = os.environ.get("MODE", "manual").lower()
    log.info("startup", extra={"version": __version__, "mode": mode})

    if mode == "daemon":
        # Keep the container alive until real crawler logic exists.
        while True:
            time.sleep(3600)

    return 0


if __name__ == "__main__":
    sys.exit(main())
