"""Tests for scripts/build_dictionary.py."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

# scripts/ isn't a package; add it to path so we can import the module.
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import build_dictionary  # type: ignore[import-not-found]  # noqa: E402


def _write_input(path: Path, words: list[str], with_origin: bool = True) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if with_origin:
            w.writerow(["слово", "происхождение"])
            for word in words:
                w.writerow([word, "русское"])
        else:
            w.writerow(["слово"])
            for word in words:
                w.writerow([word])


def test_read_words_yields_word_column_only(tmp_path: Path) -> None:
    src = tmp_path / "in.csv"
    _write_input(src, ["город", "школа"])
    assert list(build_dictionary.read_words(src)) == ["город", "школа"]


def test_read_words_strips_whitespace_and_drops_empty(tmp_path: Path) -> None:
    src = tmp_path / "in.csv"
    with src.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["слово"])
        w.writerow(["  город  "])
        w.writerow([""])
        w.writerow(["школа"])
    assert list(build_dictionary.read_words(src)) == ["город", "школа"]


def test_read_words_raises_when_слово_column_missing(tmp_path: Path) -> None:
    src = tmp_path / "in.csv"
    with src.open("w", encoding="utf-8", newline="") as f:
        f.write("foo,bar\n1,2\n")
    with pytest.raises(ValueError, match="слово"):
        list(build_dictionary.read_words(src))


def test_expand_word_produces_multiple_forms_for_simple_noun() -> None:
    import pymorphy3  # type: ignore[import-untyped]

    morph = pymorphy3.MorphAnalyzer()
    rows = build_dictionary.expand_word("город", morph)
    forms = {r[1] for r in rows}
    # at minimum nominative + genitive + plural variants must be present
    assert "город" in forms
    assert "города" in forms
    assert "городов" in forms
    # all rows reference the same lemma and a non-empty POS
    assert all(r[0] == "город" for r in rows)
    assert all(r[2] for r in rows)


def test_expand_word_dedupes_within_lemma() -> None:
    import pymorphy3

    morph = pymorphy3.MorphAnalyzer()
    rows = build_dictionary.expand_word("город", morph)
    seen = set()
    for lemma, form, pos, _ in rows:
        key = (lemma, form, pos)
        assert key not in seen
        seen.add(key)


def test_build_end_to_end_writes_csv_with_expected_schema(tmp_path: Path) -> None:
    src = tmp_path / "in.csv"
    out = tmp_path / "out.csv"
    _write_input(src, ["город", "школа"])
    written = build_dictionary.build(src, out)
    assert written > 0
    with out.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == ["lemma", "form", "pos", "grammemes"]
        rows = list(reader)
    assert len(rows) == written
    lemmas = {r[0] for r in rows}
    assert "город" in lemmas
    assert "школа" in lemmas


def test_main_via_cli(tmp_path: Path) -> None:
    src = tmp_path / "in.csv"
    out = tmp_path / "out.csv"
    _write_input(src, ["город"])
    rc = build_dictionary.main(["--input", str(src), "--output", str(out)])
    assert rc == 0
    assert out.exists()
