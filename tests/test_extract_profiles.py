"""Tests for scripts/extract_profiles.py."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import extract_profiles  # type: ignore[import-not-found]  # noqa: E402, I001


# --- score ---


def test_score_url_only_match_is_half_a_point() -> None:
    assert extract_profiles.score("https://x.hse.ru/staff/123", "") == 0.5


def test_score_text_markers_each_add_a_tenth() -> None:
    text = "Должность: профессор. Контакты: e@x. Публикации: 50."
    assert extract_profiles.score("https://x.hse.ru", text) == pytest.approx(0.3, abs=0.01)


def test_score_url_and_text_combined() -> None:
    text = "должность профессор, контакты e@x"
    s = extract_profiles.score("https://x.hse.ru/people/42", text)
    assert s == pytest.approx(0.7, abs=0.01)


def test_score_zero_for_unrelated_page() -> None:
    assert extract_profiles.score("https://x.hse.ru/news/2025-01-01", "Лекция в среду") == 0.0


# --- filter_rows + extract ---


def test_filter_keeps_pages_above_threshold() -> None:
    rows = iter(
        [
            ("https://x.hse.ru/staff/42", "должность профессор контакты e@x"),
            ("https://x.hse.ru/news/", "Афиша мероприятий на неделю"),
        ]
    )
    profiles = list(extract_profiles.filter_rows(rows, threshold=0.5))
    assert len(profiles) == 1
    assert profiles[0].profile_url == "https://x.hse.ru/staff/42"


def test_extract_pulls_email_from_text() -> None:
    p = extract_profiles.extract("https://x.hse.ru/staff/1", "Контакты: someone@hse.ru", 0.5)
    assert p.email == "someone@hse.ru"


def test_extract_recognizes_russian_full_name() -> None:
    text = "Иван Иванович Иванов, должность: доцент."
    p = extract_profiles.extract("https://x.hse.ru/staff/1", text, 0.5)
    assert p.name == "Иван Иванович Иванов"
    assert p.role is not None
    assert "доцент" in p.role.lower()


def test_extract_returns_none_fields_when_nothing_matches() -> None:
    p = extract_profiles.extract("https://x.hse.ru/staff/1", "Просто текст без шаблонов", 0.5)
    assert p.email is None
    assert p.name is None
    assert p.role is None
    assert p.chair is None


# --- read_text_csv ---


def _write_text_csv(path: Path, rows: list[tuple[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["url", "text"])
        for url, text in rows:
            w.writerow([url, text])


def test_read_text_csv_yields_url_text_tuples(tmp_path: Path) -> None:
    src = tmp_path / "in.csv"
    _write_text_csv(src, [("https://a", "txt-a"), ("https://b", "txt-b")])
    assert list(extract_profiles.read_text_csv(src)) == [
        ("https://a", "txt-a"),
        ("https://b", "txt-b"),
    ]


def test_read_text_csv_raises_on_missing_columns(tmp_path: Path) -> None:
    src = tmp_path / "in.csv"
    with src.open("w", encoding="utf-8", newline="") as f:
        f.write("foo,bar\n1,2\n")
    with pytest.raises(ValueError, match=r"url.*text|text.*url"):
        list(extract_profiles.read_text_csv(src))


# --- end-to-end ---


def test_main_end_to_end_writes_only_profile_rows(tmp_path: Path) -> None:
    src = tmp_path / "in.csv"
    out = tmp_path / "out.jsonl"
    _write_text_csv(
        src,
        [
            (
                "https://x.hse.ru/staff/42",
                "Иван Иванович Иванов. Должность: профессор. Контакты: i@x.ru",
            ),
            ("https://x.hse.ru/news/", "Афиша мероприятий"),
            ("https://x.hse.ru/people/13", "должность доцент"),
        ],
    )
    rc = extract_profiles.main(
        [
            "--input",
            str(src),
            "--output",
            str(out),
            "--threshold",
            "0.5",
        ]
    )
    assert rc == 0
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2  # only the two staff/people pages
    parsed = [json.loads(line) for line in lines]
    urls = {p["profile_url"] for p in parsed}
    assert urls == {
        "https://x.hse.ru/staff/42",
        "https://x.hse.ru/people/13",
    }
    # First record has full extraction
    first = next(p for p in parsed if p["profile_url"].endswith("/staff/42"))
    assert first["name"] == "Иван Иванович Иванов"
    assert first["email"] == "i@x.ru"
    assert "профессор" in (first["role"] or "").lower()
