"""Entrypoint for `python -m netbibi`.

MODE env var dispatches:
- daemon  : block forever (compose's restart=unless-stopped + idle keeps the
            container alive between scheduled crawls)
- once    : run one full crawl using CrawlerConfig.from_env(), then exit
- manual  : print version and exit (used for smoke tests / quick checks)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

from netbibi import __version__
from netbibi.crawler import CrawlerConfig, crawl
from netbibi.logging_config import configure_logging


def main() -> int:
    configure_logging()
    log = logging.getLogger("netbibi")
    mode = os.environ.get("MODE", "manual").lower()
    log.info("startup", extra={"version": __version__, "mode": mode})

    if mode == "daemon":
        while True:
            time.sleep(3600)

    if mode == "once":
        try:
            config = CrawlerConfig.from_env()
        except ValueError as exc:
            log.error("config_error", extra={"error": str(exc)})
            return 1
        stats = asyncio.run(crawl(config))
        log.info(
            "crawl_finished",
            extra={
                "pages_saved": stats.pages_saved,
                "urls_visited": stats.urls_visited,
                "errors": stats.errors,
            },
        )
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
