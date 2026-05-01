"""Entrypoint for `python -m netbibi`.

MODE env var dispatches:
- daemon  : block forever (compose's restart=unless-stopped + idle keeps the
            container alive between scheduled crawls)
- once    : run one full crawl using CrawlerConfig.from_env(), then exit
- manual  : print version and exit (used for smoke tests / quick checks)
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

from netbibi import __version__
from netbibi.crawler import CrawlerConfig, crawl


def main() -> int:
    mode = os.environ.get("MODE", "manual").lower()
    print(f"netbibi v{__version__} [MODE={mode}]", flush=True)

    if mode == "daemon":
        while True:
            time.sleep(3600)

    if mode == "once":
        try:
            config = CrawlerConfig.from_env()
        except ValueError as exc:
            print(f"netbibi: config error — {exc}", file=sys.stderr)
            return 1
        stats = asyncio.run(crawl(config))
        print(
            f"netbibi: crawl finished — "
            f"pages_saved={stats.pages_saved} "
            f"urls_visited={stats.urls_visited} "
            f"errors={stats.errors}",
            flush=True,
        )
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
