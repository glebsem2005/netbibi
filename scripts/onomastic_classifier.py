"""Heuristic classifier for Russian person-name parts.

Given a single token, decides whether it is plausibly a Russian
имя / отчество / фамилия and returns a small confidence in [0, 1].

Phase-1 implementation: pure pattern + lookup, no ML, no external
deps. Designed to be plugged into scripts/extract_profiles.py (12-3)
as a per-token booster: profile pages whose URL/DOM markers are weak
but whose visible text contains a high density of recognized name
parts can still be picked up.

Not a goal:
- Foreign names (Smith, García) — out of scope.
- Initials and abbreviations — out of scope; downstream pipelines
  handle those separately.
- Disambiguation from non-name lookalikes (e.g. "Иванов" the surname
  vs "иванов" the genitive plural of the noun "иван") — we accept
  capitalization as a strong-enough signal for now.

See `docs/onomastics.md` for the rule catalogue and known limits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

NameKind = Literal["name", "patronymic", "surname"]

# --- Patronymics: very high precision; suffix set is closed. ---
_PATRONYMIC_SUFFIXES = (
    "ович",
    "евич",
    "ьевич",  # masculine
    "овна",
    "евна",
    "ьевна",
    "ична",
    "инична",  # feminine
)

# --- Surname suffixes (with female forms). Together cover the bulk of
# Russian surnames; doesn't catch every dialect form (Ukrainian -ук, -юк
# included; Belarusian, Caucasian, German-Russian families NOT included
# — flagged as a known limit). ---
_SURNAME_SUFFIXES = (
    # -ов / -ова  (Иванов / Иванова)
    "ов",
    "ова",
    "ев",
    "ева",
    "ёв",
    "ёва",
    # -ин / -ина (Пушкин / Пушкина)
    "ин",
    "ина",
    "ын",
    "ына",
    # -ский / -ская (Достоевский / Достоевская)
    "ский",
    "ская",
    "ской",
    "ская",
    "цкий",
    "цкая",
    # Ukrainian / Belarusian -enko, -ko, -uk, -yuk (gender-neutral)
    "ко",
    "енко",
    "ук",
    "юк",
)

# --- Common first-name list, deliberately small.
# 200 most common given names give us decent recall without bloating
# the module. Sourced from open RF / Wikipedia category lists.
# Kept lowercase; matched case-insensitively. ---
_COMMON_FIRST_NAMES = frozenset(
    {
        # Male
        "александр",
        "алексей",
        "анатолий",
        "андрей",
        "антон",
        "аркадий",
        "артём",
        "артем",
        "артур",
        "афанасий",
        "богдан",
        "борис",
        "вадим",
        "валентин",
        "валерий",
        "василий",
        "виктор",
        "виталий",
        "владимир",
        "владислав",
        "всеволод",
        "вячеслав",
        "геннадий",
        "георгий",
        "герман",
        "глеб",
        "григорий",
        "даниил",
        "денис",
        "дмитрий",
        "евгений",
        "егор",
        "захар",
        "иван",
        "игнатий",
        "игорь",
        "илья",
        "иннокентий",
        "иосиф",
        "кирилл",
        "константин",
        "лев",
        "леонид",
        "леонтий",
        "максим",
        "марк",
        "матвей",
        "михаил",
        "никита",
        "николай",
        "олег",
        "павел",
        "пётр",
        "петр",
        "родион",
        "роман",
        "рустам",
        "савва",
        "святослав",
        "семён",
        "семен",
        "сергей",
        "станислав",
        "степан",
        "тимофей",
        "тимур",
        "фёдор",
        "федор",
        "филипп",
        "юрий",
        "ярослав",
        # Female
        "александра",
        "алёна",
        "алена",
        "алина",
        "алиса",
        "алла",
        "анастасия",
        "ангелина",
        "анна",
        "антонина",
        "валентина",
        "валерия",
        "варвара",
        "василиса",
        "вера",
        "вероника",
        "виктория",
        "галина",
        "дарья",
        "дарина",
        "евгения",
        "екатерина",
        "елена",
        "елизавета",
        "жанна",
        "зинаида",
        "зоя",
        "инна",
        "ирина",
        "карина",
        "кира",
        "клавдия",
        "ксения",
        "лариса",
        "лидия",
        "лилия",
        "любовь",
        "людмила",
        "маргарита",
        "марина",
        "мария",
        "надежда",
        "наталья",
        "наталия",
        "нина",
        "ольга",
        "оксана",
        "полина",
        "раиса",
        "регина",
        "светлана",
        "софия",
        "софья",
        "тамара",
        "татьяна",
        "ульяна",
        "юлия",
        "яна",
    }
)

_RUSSIAN_TOKEN_RE = re.compile(r"^[А-ЯЁ][а-яё]+$")


@dataclass(frozen=True)
class Classification:
    is_person: bool
    kind: NameKind | None
    confidence: float


def _is_russian_token(token: str) -> bool:
    return bool(_RUSSIAN_TOKEN_RE.fullmatch(token))


def classify(token: str) -> Classification:
    """Classify a single capitalized Russian token.

    Returns is_person=False with kind=None for tokens that are not
    capitalized Cyrillic words or that don't match any rule.
    """
    if not _is_russian_token(token):
        return Classification(False, None, 0.0)

    lower = token.lower()

    # Patronymic — closed suffix set, near-zero false positive rate.
    if lower.endswith(_PATRONYMIC_SUFFIXES):
        return Classification(True, "patronymic", 0.95)

    # First name — direct lookup against the known list.
    if lower in _COMMON_FIRST_NAMES:
        return Classification(True, "name", 0.90)

    # Surname — suffix-based, lower precision than patronymics
    # (some non-surname nouns end the same way), so confidence trimmed.
    if lower.endswith(_SURNAME_SUFFIXES):
        return Classification(True, "surname", 0.65)

    return Classification(False, None, 0.0)


def classify_phrase(phrase: str) -> list[Classification]:
    """Classify each whitespace-delimited token in a phrase."""
    return [classify(t) for t in phrase.split()]


def is_person_name_phrase(phrase: str) -> bool:
    """Heuristic 'phrase is a person name': two of its tokens classify
    as person parts, and at least one of those is a name or patronymic
    (not just two surnames).
    """
    parts = [c for c in classify_phrase(phrase) if c.is_person]
    if len(parts) < 2:
        return False
    return any(p.kind in ("name", "patronymic") for p in parts)
