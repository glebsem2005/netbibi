"""Expand the seed `unique_words.csv` into all morphological forms.

Reads a CSV with at least a "слово" (word) column — the "происхождение"
column, if present, is dropped because it isn't used downstream. For
each word we ask pymorphy3 for every parse, then for each parse expand
to all `lexeme` forms, deduped within a lemma. The result is written
as a flat CSV with columns: lemma, form, pos, grammemes.

Usage:
    uv run python scripts/build_dictionary.py \\
        --input data/unique_words.csv \\
        --output data/lemmatized_dictionary.csv

Designed to run both locally and from
.github/workflows/dictionary-release.yml — the workflow uploads the
output as a release asset on dict-vN tag pushes.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

import pymorphy3  # type: ignore[import-untyped]


def read_words(path: Path) -> Iterator[str]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "слово" not in reader.fieldnames:
            raise ValueError(f"{path} must have a 'слово' column; got {reader.fieldnames}")
        for row in reader:
            word = (row.get("слово") or "").strip()
            if word:
                yield word


def expand_word(word: str, morph: pymorphy3.MorphAnalyzer) -> list[tuple[str, str, str, str]]:
    """Return rows (lemma, form, pos, grammemes) for one input word.

    Multiple parses → multiple lemmas → multiple lexemes; we dedupe by
    (lemma, form, pos) so the same form doesn't appear twice for the
    same lemma even if pymorphy returns it from two parses.
    """
    seen: set[tuple[str, str, str]] = set()
    out: list[tuple[str, str, str, str]] = []
    for parse in morph.parse(word):
        lemma = parse.normal_form
        for form in parse.lexeme:
            tag = form.tag
            # str() on a pymorphy3 grammeme (which is a str subclass with a
            # picky __eq__) collapses to a plain str so we can sort/compare
            # across attribute namespaces without the tag namespace check.
            pos_str = str(tag.POS) if tag and tag.POS else ""
            grammeme_strs = sorted(str(g) for g in tag.grammemes) if tag else []
            other_grammemes = [g for g in grammeme_strs if g != pos_str]
            grammemes = ",".join(other_grammemes)
            key = (lemma, form.word, pos_str)
            if key in seen:
                continue
            seen.add(key)
            out.append((lemma, form.word, pos_str, grammemes))
    return out


def write_lemmatized(rows: Iterable[tuple[str, str, str, str]], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["lemma", "form", "pos", "grammemes"])
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def build(input_path: Path, output_path: Path) -> int:
    morph = pymorphy3.MorphAnalyzer()
    rows: list[tuple[str, str, str, str]] = []
    for word in read_words(input_path):
        rows.extend(expand_word(word, morph))
    return write_lemmatized(rows, output_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    written = build(args.input, args.output)
    print(f"build_dictionary: wrote {written} rows to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
