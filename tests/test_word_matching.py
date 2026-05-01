"""Tests for scripts/word_matching.py."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import word_matching as wm  # type: ignore[import-not-found]  # noqa: E402


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


# --- read_word_set / read_texts ---


def test_read_word_set_lowercases_and_strips(tmp_path: Path) -> None:
    src = tmp_path / "list.csv"
    _write_csv(src, ["слово"], [["Город "], [" школа"], [""], ["Москва"]])
    assert wm.read_word_set(src, column="слово") == {"город", "школа", "москва"}


def test_read_word_set_raises_on_missing_column(tmp_path: Path) -> None:
    src = tmp_path / "list.csv"
    _write_csv(src, ["foo"], [["bar"]])
    with pytest.raises(ValueError, match="слово"):
        wm.read_word_set(src, column="слово")


def test_read_texts_yields_url_text_pairs(tmp_path: Path) -> None:
    src = tmp_path / "texts.csv"
    _write_csv(src, ["url", "text"], [["https://a", "txt-a"], ["https://b", "txt-b"]])
    assert list(wm.read_texts(src)) == [
        ("https://a", "txt-a"),
        ("https://b", "txt-b"),
    ]


# --- tokenize ---


def test_tokenize_extracts_cyrillic_words() -> None:
    tokens = wm.tokenize("Москва - столица; Санкт-Петербург — нет.")
    assert "Москва" in tokens
    assert "столица" in tokens
    # Hyphenated tokens are kept together
    assert "Санкт-Петербург" in tokens


def test_tokenize_skips_punctuation_and_digits() -> None:
    tokens = wm.tokenize("Иванов И.И., 1990 г.")
    # Numbers excluded; surnames retained
    assert "1990" not in tokens
    assert "Иванов" in tokens


# --- match_page (uses real pymorphy3) ---


def test_match_page_emits_only_lemmas_in_special_and_not_in_general() -> None:
    import pymorphy3  # type: ignore[import-untyped]

    morph = pymorphy3.MorphAnalyzer()
    text = "В городе живёт человек и смотрит на дерево."
    special = {"город", "дерево"}  # we look for these
    general = {"человек"}  # this is excluded as 'too common'
    rows = wm.match_page("https://x", text, special, general, morph)
    lemmas = {r.lemma for r in rows}
    assert "город" in lemmas
    assert "дерево" in lemmas
    assert "человек" not in lemmas


def test_match_page_dedupes_within_a_page() -> None:
    import pymorphy3

    morph = pymorphy3.MorphAnalyzer()
    text = "город город города городов"  # all forms of one lemma
    special = {"город"}
    rows = wm.match_page("https://x", text, special, set(), morph)
    assert len(rows) == 1
    assert rows[0].lemma == "город"


def test_match_page_returns_empty_when_no_overlap() -> None:
    import pymorphy3

    morph = pymorphy3.MorphAnalyzer()
    text = "никаких особых слов"
    special = {"уникальный"}
    rows = wm.match_page("https://x", text, special, set(), morph)
    assert rows == []


# --- end-to-end run ---


def test_run_end_to_end(tmp_path: Path) -> None:
    texts = tmp_path / "texts.csv"
    special = tmp_path / "special.csv"
    general = tmp_path / "general.csv"
    output = tmp_path / "out.csv"

    _write_csv(
        texts,
        ["url", "text"],
        [
            ["https://a", "Город старый и улица. Дерево и человек."],
            ["https://b", "Совсем другой текст без особых слов."],
        ],
    )
    _write_csv(special, ["слово"], [["город"], ["улица"], ["дерево"]])
    _write_csv(general, ["слово"], [["человек"]])

    written, unique_lemmas, coverage = wm.run(texts, special, general, output)

    assert written == 3  # город, улица, дерево all from page A
    assert unique_lemmas == 3
    assert coverage == pytest.approx(1.0)  # all 3 special words seen at least once

    with output.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    assert header == ["lemma", "original_form", "url"]
    urls_per_lemma = {r[0]: r[2] for r in rows}
    assert urls_per_lemma["город"] == "https://a"
    assert urls_per_lemma["улица"] == "https://a"
    assert urls_per_lemma["дерево"] == "https://a"


def test_main_via_cli(tmp_path: Path) -> None:
    texts = tmp_path / "texts.csv"
    special = tmp_path / "special.csv"
    general = tmp_path / "general.csv"
    output = tmp_path / "out.csv"
    _write_csv(texts, ["url", "text"], [["https://a", "город"]])
    _write_csv(special, ["слово"], [["город"]])
    _write_csv(general, ["слово"], [])
    rc = wm.main(
        [
            "--texts",
            str(texts),
            "--special",
            str(special),
            "--general",
            str(general),
            "--output",
            str(output),
        ]
    )
    assert rc == 0
    assert output.exists()
