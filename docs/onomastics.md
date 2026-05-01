# Onomastic classifier — rules and known limits

`scripts/onomastic_classifier.py` decides whether a Russian-language
token is plausibly part of a person's name and what part. It is a
deliberate, simple rule engine — predictable, auditable, and easy to
extend. No ML, no external dependencies.

## Rules

The classifier checks three things in order, returning the first match.

### 1. Patronymics (confidence 0.95)

Closed set of suffixes — practically zero false positives in modern
Russian text. Suffix is matched against the lowercased token.

| Suffix     | Gender | Example       |
|------------|--------|---------------|
| `-ович`    | male   | Иванович       |
| `-евич`    | male   | Сергеевич      |
| `-ьевич`   | male   | Ильевич        |
| `-овна`    | female | Ивановна       |
| `-евна`    | female | Сергеевна      |
| `-ьевна`   | female | Ильевна        |
| `-ична`    | female | Никитична      |
| `-инична`  | female | Ильинична      |

### 2. Common first names (confidence 0.90)

Direct lookup in a frozenset of ~150 male and female names. Source
material: open lists from Russian RF and Wikipedia category pages.
Lowercase comparison — the source token must be capitalized
(see Token shape below).

The list is intentionally moderate-size: too short loses recall, too
long bloats the module and adds ambiguous tokens (very rare names
that overlap with common words). Updates can land in their own PR.

### 3. Surnames (confidence 0.65)

Suffix match. Confidence is lower than patronymics because some
non-surname nouns end the same way (e.g. `молотов` the noun vs
`Молотов` the surname — capitalization is the only signal).

| Suffix    | Variants                       | Notes                       |
|-----------|--------------------------------|-----------------------------|
| `-ов / -ова` | `-ев / -ева`, `-ёв / -ёва`     | Иванов, Сергеев, Соловьёв   |
| `-ин / -ина` | `-ын / -ына`                   | Пушкин, Куприн             |
| `-ский / -ская` | `-ской`, `-цкий / -цкая` | Достоевский, Луговской      |
| `-ко / -енко` | (gender-neutral)              | Тимошенко, Бойко           |
| `-ук / -юк`   | (gender-neutral, Ukrainian)   | Бондарчук, Костюк           |

## Token shape

Tokens are validated against the regex `^[А-ЯЁ][а-яё]+$` before any
rule runs. This means:

- Must start with a Cyrillic capital letter.
- Must consist only of Cyrillic letters thereafter.
- Hyphenated names (`Римский-Корсаков`) and double-barrel names
  fall outside this shape and need split-then-classify.

## Phrase helpers

Two phrase-level functions sit on top of the per-token classifier.

`classify_phrase(phrase)` returns a list of `Classification`s, one
per whitespace-delimited token.

`is_person_name_phrase(phrase)` returns True iff at least two tokens
classify as person parts AND at least one of them is a name or
patronymic. Two surnames alone do not qualify — that pattern is more
often a place-place than a person-person collocation.

## Known limits (out of scope, by design)

- **Foreign names**: Smith, García, Müller — not handled. Profile
  pages with foreign-named staff would need a separate rule set or
  an external library (we deliberately avoid that complexity for
  the first cut).
- **Initials and abbreviations**: `И. И. Иванов`, `И.И. Иванов` are
  not normalized here. Downstream pipelines should expand them
  before calling `classify`.
- **Aliases for given names**: `Саша`, `Маша`, `Ваня` are common in
  informal contexts but rarely appear on professional staff pages —
  not in the lookup list.
- **Capitalization-only homonyms**: `Иванов` (surname) vs `Иванов`
  in genitive plural of the noun `иван` — both pass the shape test;
  context disambiguation is left to the caller.
- **Hyphenated names**: `Римский-Корсаков` would need pre-split.
- **Caucasian / Asian / Baltic Russian-citizen names**: surname
  suffixes don't cover these families. They will be flagged as
  not-a-person under the current rules.
- **Accuracy ceiling**: by construction, this rule engine cannot
  exceed the precision implied by its closed sets. The intended
  consumer is `scripts/extract_profiles.py`, which combines this
  signal with URL and DOM-keyword signals — multiple weak signals
  beat one mediocre classifier.

## Confidence values

| Source                | Confidence | Justification                            |
|-----------------------|------------|------------------------------------------|
| Patronymic suffix     | 0.95       | Closed suffix set, no homonyms.          |
| Known first name      | 0.90       | Direct lookup; small false-pos rate.     |
| Surname suffix        | 0.65       | Open ending, some homonyms.              |
| No rule fired         | 0.00       | Token is not classified as a name.       |

These are deliberate constants, not learned weights. Tweak via PR
if downstream evaluation shows they are off.
