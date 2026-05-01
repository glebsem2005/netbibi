"""Match crawled text against the special dictionary, minus general Russian.

For every word in every crawled page, lemmatize via pymorphy3 and emit
the row when both:

  (a) the lemma IS in our special dictionary (data/unique_words.csv); AND
  (b) the lemma is NOT in the general Russian thesaurus (data/ru.csv).

The output is `(lemma, original_form, url)`, deduplicated by
(lemma, url) so a page that repeats the same word doesn't produce
multiple rows.

Usage:
    uv run python scripts/word_matching.py \\
        --texts data/fsn_texts.csv \\
        --special data/unique_words.csv \\
        --general data/ru.csv \\
        --output data/rare_words_per_url.csv

Real end-to-end run is blocked on data/ru.csv (Gleb will land it).
The script is built and tested against synthetic inputs; once ru.csv
arrives, only the --general path needs pointing at the real file.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymorphy3  # type: ignore[import-untyped]

# Cyrillic word boundary — keeps tokenization simple and consistent with
# the corpus we crawl. Hyphens not treated as splits (Соловьёв-Седой).
_TOKEN_RE = re.compile(r"[А-ЯЁа-яё]+(?:-[А-ЯЁа-яё]+)*")


@dataclass(frozen=True)
class MatchRow:
    lemma: str
    original_form: str
    url: str


def read_word_set(path: Path, column: str) -> set[str]:
    """Read a single-column word list from a CSV; lowercase the values."""
    out: set[str] = set()
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or column not in reader.fieldnames:
            raise ValueError(f"{path} missing required column '{column}'; got {reader.fieldnames}")
        for row in reader:
            v = (row.get(column) or "").strip().lower()
            if v:
                out.add(v)
    return out


def read_texts(path: Path) -> Iterator[tuple[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or not {"url", "text"}.issubset(reader.fieldnames):
            raise ValueError(f"{path} must have 'url' and 'text' columns; got {reader.fieldnames}")
        for row in reader:
            yield (row["url"], row.get("text") or "")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def match_page(
    url: str,
    text: str,
    special: set[str],
    general: set[str],
    morph: Any,
) -> list[MatchRow]:
    seen: set[str] = set()
    out: list[MatchRow] = []
    for token in tokenize(text):
        # First parse wins for lemma — pymorphy returns parses ordered
        # by likelihood, so this is the maximum-a-posteriori lemma.
        parses = morph.parse(token)
        if not parses:
            continue
        lemma = str(parses[0].normal_form).lower()
        if lemma in seen:
            continue
        if lemma not in special:
            continue
        if lemma in general:
            continue
        seen.add(lemma)
        out.append(MatchRow(lemma=lemma, original_form=token, url=url))
    return out


def write_csv(rows: Iterable[MatchRow], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["lemma", "original_form", "url"])
        for r in rows:
            writer.writerow([r.lemma, r.original_form, r.url])
            count += 1
    return count


def run(
    texts_path: Path,
    special_path: Path,
    general_path: Path,
    output_path: Path,
) -> tuple[int, int, float]:
    """Returns (rows_written, unique_lemmas, coverage_fraction).

    coverage_fraction = unique_lemmas / |special|, the share of our
    special dictionary actually observed in the corpus.
    """
    special = read_word_set(special_path, column="слово")
    general = read_word_set(general_path, column="слово")
    morph = pymorphy3.MorphAnalyzer()

    all_rows: list[MatchRow] = []
    for url, text in read_texts(texts_path):
        all_rows.extend(match_page(url, text, special, general, morph))

    written = write_csv(all_rows, output_path)
    unique_lemmas = len({r.lemma for r in all_rows})
    coverage = unique_lemmas / len(special) if special else 0.0
    return written, unique_lemmas, coverage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--texts", type=Path, required=True)
    parser.add_argument("--special", type=Path, required=True)
    parser.add_argument("--general", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    written, unique_lemmas, coverage = run(args.texts, args.special, args.general, args.output)
    print(
        f"word_matching: wrote {written} rows ({unique_lemmas} unique lemmas, "
        f"coverage of special dict={coverage:.2%}) to {args.output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
