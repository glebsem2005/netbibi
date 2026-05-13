"""Find words from fsn_texts.csv that are absent from the lemmatized dictionary.

Filters out:
  - Abbreviations (all-caps tokens or pymorphy3 Abbr tag)
  - Proper nouns (pymorphy3 Name/Surn/Patr/Geox/Orgn/Trad tags)
  - Words that appear capitalized in non-sentence-initial position
    across any page (catches unusual/foreign surnames and trademarks
    that pymorphy3 doesn't know)

Output: analysis/unknown_words.csv  — columns: word, url
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pymorphy3

csv.field_size_limit(10_000_000)

TEXTS_PATH = Path(__file__).parent.parent / "data" / "fsn_texts.csv"
DICT_PATH = Path(__file__).parent.parent / "data" / "unique_words.csv"
OUTPUT_PATH = Path(__file__).parent / "unknown_words.csv"

# Cyrillic word, allows hyphen inside
_TOKEN_RE = re.compile(r"[А-ЯЁа-яё]+(?:-[А-ЯЁа-яё]+)*")

# Characters that end a sentence (word after these is sentence-initial)
_SENTENCE_END_RE = re.compile(r"[.!?»:;]\s*$")

# pymorphy3 grammeme tags that mark words to skip
_SKIP_TAGS = {"Name", "Patr", "Surn", "Geox", "Orgn", "Trad", "Abbr"}


def load_dictionary(path: Path, morph: pymorphy3.MorphAnalyzer) -> set[str]:
    """Load dictionary words, storing pymorphy3 lemmas so comparison is apples-to-apples."""
    words: set[str] = set()
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            w = (row.get("слово") or "").strip().lower()
            if not w:
                continue
            parses = morph.parse(w)
            lemma = str(parses[0].normal_form).lower() if parses else w
            words.add(lemma)
            words.add(w)  # keep original form too, in case lemmatizer disagrees
    return words


def load_pages(path: Path) -> list[tuple[str, str]]:
    pages: list[tuple[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            pages.append((row.get("url", ""), row.get("text") or ""))
    return pages


def collect_mid_sentence_caps(pages: list[tuple[str, str]]) -> set[str]:
    """Return lowercase word forms that appear capitalized mid-sentence.

    A word is considered mid-sentence when the text immediately before it
    (after stripping whitespace) does not end with sentence-ending punctuation
    and the word is not the very first token in the text.
    """
    caps_words: set[str] = set()
    for _, text in pages:
        # Split text into segments around each Cyrillic token
        pos = 0
        first_token = True
        for m in _TOKEN_RE.finditer(text):
            token = m.group()
            if token[0].isupper():
                if first_token:
                    # legitimate sentence start
                    first_token = False
                    pos = m.end()
                    continue
                preceding = text[pos : m.start()]
                if not _SENTENCE_END_RE.search(preceding):
                    caps_words.add(token.lower())
            elif token[0].islower():
                first_token = False
            pos = m.end()
    return caps_words


def is_proper_or_abbr(token: str, morph: pymorphy3.MorphAnalyzer) -> bool:
    """True if all-caps token or pymorphy3 tags it as a proper noun / abbreviation."""
    if token.isupper() and len(token) > 1:
        return True
    for parse in morph.parse(token):
        if _SKIP_TAGS & parse.tag.grammemes:
            return True
    return False


def main() -> None:
    morph = pymorphy3.MorphAnalyzer()

    dictionary = load_dictionary(DICT_PATH, morph)
    print(f"Dictionary: {len(dictionary)} lemmas (after pymorphy3 normalisation)", file=sys.stderr)

    pages = load_pages(TEXTS_PATH)
    print(f"Pages: {len(pages)}", file=sys.stderr)

    print("Collecting mid-sentence capitalised words...", file=sys.stderr)
    mid_caps = collect_mid_sentence_caps(pages)
    print(f"Mid-sentence caps words: {len(mid_caps)}", file=sys.stderr)

    rows: list[tuple[str, str]] = []
    for i, (url, text) in enumerate(pages, 1):
        if i % 100 == 0:
            print(f"  {i}/{len(pages)}", file=sys.stderr)
        seen: set[str] = set()
        for token in _TOKEN_RE.findall(text):
            if is_proper_or_abbr(token, morph):
                continue
            token_lower = token.lower()
            if token_lower in mid_caps:
                continue
            parses = morph.parse(token)
            lemma = str(parses[0].normal_form).lower() if parses else token_lower
            if lemma in seen or lemma in dictionary:
                continue
            seen.add(lemma)
            rows.append((lemma, url))

    print(f"Total entries: {len(rows)}", file=sys.stderr)
    print(f"Unique missing lemmas: {len({r[0] for r in rows})}", file=sys.stderr)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["word", "url"])
        writer.writerows(rows)
    print(f"Written: {OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
