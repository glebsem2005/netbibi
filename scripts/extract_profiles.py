"""Filter crawler output down to staff/student profile pages.

Reads a text CSV (columns: url, text) produced by the netbibi crawler,
scores each row against URL + text heuristics, and emits a JSONL file
containing only the rows that score above a confidence threshold.

Heuristics are deliberately rule-based for now — predictable, easy to
audit, and easy to extend. Phase-2 work (12-7 onomastic classifier)
will plug in to lift recall on profiles that have no clear URL/DOM
markers but contain person names.

Usage:
    uv run python scripts/extract_profiles.py \\
        --input data/fsn_texts.csv \\
        --output data/profiles.jsonl \\
        --threshold 0.5
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

# URL fragments that almost always mean "this page is a person profile".
# Each contributes +0.5 to confidence. One match is enough by itself.
_URL_PROFILE_FRAGMENTS = (
    "/staff/",
    "/people/",
    "/persons/",
    "/profile/",
    "/employees/",
    "/faculty/profile/",
    "/teachers/",
)

# Russian text markers; each contributes +0.1.
_TEXT_PROFILE_MARKERS = (
    "должность",
    "контакты",
    "публикации",
    "учёная степень",
    "ученая степень",
    "кандидат наук",
    "доктор наук",
    "приглашённый преподаватель",
    "научные интересы",
)

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# A loose pattern for "Имя Отчество Фамилия" with Russian capitalized words.
_RUS_NAME_RE = re.compile(
    r"\b([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+(?:вич|вна|ьич|ьна))\s+([А-ЯЁ][а-яё]+)\b"
)
# After "должность" / "кафедра" capture the next short phrase up to a
# delimiter that ends a typical bio sentence.
_ROLE_RE = re.compile(r"должность[\s:—–-]*([^.\n,;]+)", re.IGNORECASE)
_CHAIR_RE = re.compile(r"кафедр[аыеуо][\s:—–-]*([^.\n,;]+)", re.IGNORECASE)


@dataclass(frozen=True)
class Profile:
    profile_url: str
    name: str | None
    role: str | None
    chair: str | None
    email: str | None
    confidence: float


def score(url: str, text: str) -> float:
    """Confidence in 'this page is a profile'. Range 0.0..~1.0+."""
    s = 0.0
    url_l = url.lower()
    if any(frag in url_l for frag in _URL_PROFILE_FRAGMENTS):
        s += 0.5
    text_l = text.lower()
    for marker in _TEXT_PROFILE_MARKERS:
        if marker in text_l:
            s += 0.1
    return round(s, 3)


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    m = pattern.search(text)
    if not m:
        return None
    if m.groups():
        # If the regex has groups, prefer the captured "content" group.
        # _RUS_NAME_RE captures three groups — join them.
        if len(m.groups()) == 3:
            return " ".join(g.strip() for g in m.groups())
        return m.group(1).strip()
    return m.group(0).strip()


def extract(url: str, text: str, confidence: float) -> Profile:
    return Profile(
        profile_url=url,
        name=_first_match(_RUS_NAME_RE, text),
        role=_first_match(_ROLE_RE, text),
        chair=_first_match(_CHAIR_RE, text),
        email=_first_match(_EMAIL_RE, text),
        confidence=confidence,
    )


def filter_rows(rows: Iterator[tuple[str, str]], threshold: float) -> Iterator[Profile]:
    for url, text in rows:
        c = score(url, text)
        if c >= threshold:
            yield extract(url, text, c)


def read_text_csv(path: Path) -> Iterator[tuple[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or not {"url", "text"}.issubset(reader.fieldnames):
            raise ValueError(f"{path} must have 'url' and 'text' columns; got {reader.fieldnames}")
        for row in reader:
            yield (row["url"], row.get("text") or "")


def write_jsonl(profiles: Iterator[Profile], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for p in profiles:
            f.write(json.dumps(asdict(p), ensure_ascii=False) + "\n")
            count += 1
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args(argv)
    written = write_jsonl(filter_rows(read_text_csv(args.input), args.threshold), args.output)
    print(
        f"extract_profiles: wrote {written} profiles to {args.output} (threshold={args.threshold})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
