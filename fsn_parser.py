"""
BFS-краулер social.hse.ru
  - глубина до 5 уровней
  - параллельный сбор текста на каждом уровне
  - принимает любые *.hse.ru, кроме голой домашней hse.ru
  - пропускает футер; хедер — собирается
  - бинарные файлы отсеиваются по Content-Type ответа, не по расширению URL
  - fsn_texts.csv : url, text
  - fsn_links.csv : from_url, to_url
"""

import asyncio
import aiohttp
import csv
import re
import sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
from pathlib import Path
from collections import deque

MAX_DEPTH = 8
CONCURRENCY = 12
REQUEST_TIMEOUT = 30

OUTPUT_DIR = Path("/Users/glebsemenov/Desktop/stukal_voc")
TEXTS_CSV = OUTPUT_DIR / "fsn_texts.csv"
LINKS_CSV = OUTPUT_DIR / "fsn_links.csv"

FOOTER_SELECTORS = [
    "footer",
    '[class*="footer"]',
    '[id*="footer"]',
    '[class*="Footer"]',
    '[id*="Footer"]',
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

# Голый корень hse.ru — мусор, не берём
HSE_ROOT_URLS = {
    "https://hse.ru",
    "https://www.hse.ru",
    "http://hse.ru",
    "http://www.hse.ru",
}

# ── Фильтры URL ───────────────────────────────────────────────────────────────


def normalize_url(url: str) -> str:
    p = urlparse(url)
    clean = urlunparse((p.scheme, p.netloc.lower(), p.path, p.params, p.query, ""))
    return clean.rstrip("/")


def is_valid_link(url: str) -> bool:
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return False
    host = p.netloc.lower()
    # Принимаем hse.ru и любой поддомен *.hse.ru (social.hse.ru, www.hse.ru и т.д.)
    # Всё остальное (vk.com, youtube.com, ...) — не берём
    if host != "hse.ru" and not host.endswith(".hse.ru"):
        return False
    # Голый корень hse.ru — не берём
    if url.rstrip("/") in HSE_ROOT_URLS:
        return False
    # Бинарные форматы отсеиваются в fetch() по Content-Type, не здесь
    return True


# ── Извлечение текста и ссылок ────────────────────────────────────────────────


def parse_page(html: str, page_url: str):
    soup = BeautifulSoup(html, "lxml")

    # Сначала вырезаем футер — чтобы его ссылки тоже не попали в граф
    for sel in FOOTER_SELECTORS:
        for el in soup.select(sel):
            el.decompose()

    for tag in soup.find_all(["script", "style", "noscript", "meta", "head"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    links = []
    for a in soup.find_all("a", href=True):
        raw = a["href"].strip()
        if not raw or raw.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        full = normalize_url(urljoin(page_url, raw))
        if is_valid_link(full):
            links.append(full)

    return text, links


# ── Асинхронная загрузка ──────────────────────────────────────────────────────


async def fetch(session: aiohttp.ClientSession, url: str) -> str | None:
    try:
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            allow_redirects=True,
            max_redirects=5,
        ) as resp:
            if resp.status != 200:
                return None
            # Единственный фильтр бинарных файлов — Content-Type сервера
            if "text/html" not in resp.headers.get("content-type", ""):
                return None
            return await resp.text(errors="replace")
    except Exception as exc:
        print(f"  [WARN] {url}: {exc}", file=sys.stderr)
        return None


# ── BFS-краулер ───────────────────────────────────────────────────────────────


async def crawl():
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque()

    start = normalize_url("https://social.hse.ru")
    visited.add(start)
    queue.append((start, 0))

    texts_f = open(TEXTS_CSV, "w", newline="", encoding="utf-8")
    links_f = open(LINKS_CSV, "w", newline="", encoding="utf-8")
    texts_w = csv.writer(texts_f, quoting=csv.QUOTE_ALL)
    links_w = csv.writer(links_f, quoting=csv.QUOTE_ALL)
    texts_w.writerow(["url", "text"])
    links_w.writerow(["from_url", "to_url"])

    total_pages = 0

    conn = aiohttp.TCPConnector(limit=CONCURRENCY, ssl=False)
    async with aiohttp.ClientSession(connector=conn, headers=HEADERS) as session:
        while queue:
            # Снимаем весь текущий уровень
            cur_depth = queue[0][1]
            level: list[tuple[str, int]] = []
            while queue and queue[0][1] == cur_depth:
                level.append(queue.popleft())

            if cur_depth > MAX_DEPTH:
                break

            print(f"Уровень {cur_depth}: {len(level)} страниц...")

            # Параллельная загрузка всего уровня
            htmls = await asyncio.gather(*[fetch(session, url) for url, _ in level])

            for (url, depth), html in zip(level, htmls):
                if html is None:
                    continue

                text, links = parse_page(html, url)
                texts_w.writerow([url, text])
                total_pages += 1

                for link in set(links):
                    # Ребро графа пишем всегда — оно отражает реальную структуру сайта
                    links_w.writerow([url, link])
                    # В очередь — только если ещё не видели
                    if link not in visited and depth < MAX_DEPTH:
                        visited.add(link)
                        queue.append((link, depth + 1))

            texts_f.flush()
            links_f.flush()
            print(f"  страниц сохранено: {total_pages}, в очереди: {len(queue)}")

    texts_f.close()
    links_f.close()

    print(f"\nГотово!")
    print(f"  Всего страниц: {total_pages}")
    print(f"  Уникальных URL (visited): {len(visited)}")
    print(f"  Тексты  → {TEXTS_CSV}")
    print(f"  Граф    → {LINKS_CSV}")


if __name__ == "__main__":
    asyncio.run(crawl())
