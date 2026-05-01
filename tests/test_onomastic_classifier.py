"""Tests for scripts/onomastic_classifier.py."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import onomastic_classifier as oc  # type: ignore[import-not-found]  # noqa: E402, I001


# --- patronymics (highest-precision rule) ---


def test_classify_recognizes_male_patronymic() -> None:
    c = oc.classify("Иванович")
    assert c.is_person is True
    assert c.kind == "patronymic"
    assert c.confidence >= 0.9


def test_classify_recognizes_female_patronymic() -> None:
    c = oc.classify("Ивановна")
    assert c.is_person is True
    assert c.kind == "patronymic"


def test_classify_recognizes_ich_patronymic() -> None:
    c = oc.classify("Ильинична")
    assert c.is_person is True
    assert c.kind == "patronymic"


# --- first names ---


def test_classify_recognizes_common_male_name() -> None:
    c = oc.classify("Иван")
    assert c.is_person is True
    assert c.kind == "name"


def test_classify_recognizes_common_female_name() -> None:
    c = oc.classify("Анастасия")
    assert c.is_person is True
    assert c.kind == "name"


# --- surnames ---


def test_classify_recognizes_ov_surname() -> None:
    c = oc.classify("Иванов")
    assert c.is_person is True
    assert c.kind == "surname"


def test_classify_recognizes_female_ova_surname() -> None:
    c = oc.classify("Иванова")
    assert c.is_person is True
    assert c.kind == "surname"


def test_classify_recognizes_skij_surname() -> None:
    c = oc.classify("Достоевский")
    assert c.is_person is True
    assert c.kind == "surname"


def test_classify_recognizes_enko_surname() -> None:
    c = oc.classify("Шевченко")
    assert c.is_person is True
    assert c.kind == "surname"


# --- non-person tokens ---


def test_classify_rejects_lowercase_word() -> None:
    c = oc.classify("книга")
    assert c.is_person is False
    assert c.kind is None
    assert c.confidence == 0.0


def test_classify_rejects_non_cyrillic_word() -> None:
    c = oc.classify("Smith")
    assert c.is_person is False


def test_classify_rejects_unknown_capitalized_noun() -> None:
    # "Москва" is a city, not a person, and doesn't match any name suffix
    c = oc.classify("Москва")
    assert c.is_person is False


def test_classify_rejects_empty_string() -> None:
    c = oc.classify("")
    assert c.is_person is False


# --- phrase-level helpers ---


def test_classify_phrase_returns_one_classification_per_token() -> None:
    classifications = oc.classify_phrase("Иван Иванович Иванов")
    assert len(classifications) == 3
    kinds = [c.kind for c in classifications]
    assert kinds == ["name", "patronymic", "surname"]


def test_is_person_name_phrase_accepts_name_patronymic_surname() -> None:
    assert oc.is_person_name_phrase("Иван Иванович Иванов") is True


def test_is_person_name_phrase_accepts_name_surname() -> None:
    assert oc.is_person_name_phrase("Иван Иванов") is True


def test_is_person_name_phrase_rejects_two_surnames_alone() -> None:
    # Two surname-shaped tokens without a recognized first name or
    # patronymic shouldn't satisfy the phrase predicate — that pattern
    # is more often a place-place than a person-person.
    assert oc.is_person_name_phrase("Иванов Петров") is False


def test_is_person_name_phrase_rejects_single_token() -> None:
    assert oc.is_person_name_phrase("Иванов") is False


def test_is_person_name_phrase_rejects_nonsense() -> None:
    assert oc.is_person_name_phrase("книга стол") is False
