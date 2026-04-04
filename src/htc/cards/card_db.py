from __future__ import annotations

import csv
import re
from pathlib import Path

from htc.cards.card import CardDefinition
from htc.enums import Color, Keyword, classify_type_string


# ---------------------------------------------------------------------------
# Inherent vs conditional keyword detection
# ---------------------------------------------------------------------------
# The Fabrary dataset "Card Keywords" field lists ALL keywords mentioned on a
# card, including ones that are only conditionally granted by ability text
# (e.g. "this gets **go again**").  We need to distinguish inherent keywords
# (standalone bold text like "**Go again**") from conditional ones that are
# preceded in the same sentence by verbs like "gets", "gains", "has", "loses".
#
# "with" is NOT treated as a conditional word — cards that say "with go again"
# are granting inherently.

_CONDITIONAL_VERBS = {"gets", "gains", "has", "loses"}


def _is_keyword_inherent(keyword: Keyword, functional_text: str) -> bool:
    """Check whether a keyword appears as inherent (standalone) in functional text.

    A keyword is inherent if it appears as standalone bold text (e.g. ``**Go again**``)
    without being preceded in the same sentence by a conditional verb
    ("gets", "gains", "has", "loses").  Note that "with" is NOT treated as
    conditional — cards like "attack with go again" use "with" in a
    descriptive sense, not a conditional grant.

    Returns True if the keyword is inherent OR if it doesn't appear in the text
    at all (trust the Card Keywords field for keywords not mentioned in text).
    """
    kw_name = keyword.value  # e.g. "Go again"
    # Case-insensitive search: the text may have "go again" while enum is "Go again"
    text_lower = functional_text.lower()
    bold_pattern_lower = f"**{kw_name.lower()}**"

    if bold_pattern_lower not in text_lower:
        # Keyword not mentioned in text at all — trust the Card Keywords field
        return True

    # Split into sentences (period-space boundary)
    sentences = text_lower.replace(". ", ".\n").split("\n")

    for sentence in sentences:
        if bold_pattern_lower not in sentence:
            continue

        # Check if any conditional verb precedes the keyword in this sentence
        kw_pos = sentence.find(bold_pattern_lower)

        # Look at the text before the keyword in this sentence
        prefix = sentence[:kw_pos]
        words = prefix.split()

        has_conditional_verb = any(w.rstrip(",.;:") in _CONDITIONAL_VERBS for w in words)

        if not has_conditional_verb:
            # Found standalone bold keyword — it's inherent
            return True

    # Every occurrence was preceded by a conditional verb — not inherent
    return False


def _parse_int(value: str) -> int | None:
    """Parse an integer from a TSV field, returning None for blank/non-numeric."""
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_color(value: str) -> Color | None:
    value = value.strip()
    if not value:
        return None
    try:
        return Color(value)
    except ValueError:
        return None


# Map keyword names (lowered) to Keyword enum. Some keywords have X/N suffixes
# in the TSV like "Ward 10" or "Arcane Barrier 1" — we strip the number.
_KEYWORD_BY_NAME: dict[str, Keyword] = {}
for _kw in Keyword:
    _KEYWORD_BY_NAME[_kw.value.lower()] = _kw

_KEYWORD_WITH_NUMBER = re.compile(r"^(.+?)\s+\d+$")


def _parse_keywords(value: str) -> tuple[frozenset[Keyword], dict[Keyword, int]]:
    """Parse the 'Card Keywords' TSV field into keywords and their numeric values.

    Returns (keywords_set, keyword_values) where keyword_values maps
    parameterized keywords to their number, e.g. "Arcane Barrier 2" → {ARCANE_BARRIER: 2}.
    """
    result: set[Keyword] = set()
    values: dict[Keyword, int] = {}
    for raw in value.split(","):
        raw = raw.strip()
        if not raw:
            continue
        key = raw.lower()
        if key in _KEYWORD_BY_NAME:
            result.add(_KEYWORD_BY_NAME[key])
            continue
        # Try stripping a trailing number (e.g. "Ward 10" -> "Ward", value=10)
        m = _KEYWORD_WITH_NUMBER.match(raw)
        if m:
            key2 = m.group(1).strip().lower()
            if key2 in _KEYWORD_BY_NAME:
                kw = _KEYWORD_BY_NAME[key2]
                result.add(kw)
                try:
                    values[kw] = int(raw[len(m.group(1)):].strip())
                except ValueError:
                    pass
    return frozenset(result), values


class CardDatabase:
    """Loads and indexes card definitions from the Fabrary card dataset TSV."""

    def __init__(self) -> None:
        self._by_id: dict[str, CardDefinition] = {}
        self._by_name: dict[str, list[CardDefinition]] = {}

    @classmethod
    def load(cls, tsv_path: str | Path) -> CardDatabase:
        db = cls()
        path = Path(tsv_path)
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                card = db._parse_row(row)
                if card is not None:
                    db._by_id[card.unique_id] = card
                    db._by_name.setdefault(card.name, []).append(card)
        return db

    def get_by_id(self, unique_id: str) -> CardDefinition | None:
        return self._by_id.get(unique_id)

    def get_by_name(self, name: str, color: Color | None = None) -> CardDefinition | None:
        """Look up a card by name. If color is given, return that variant."""
        cards = self._by_name.get(name, [])
        if not cards:
            return None
        if color is not None:
            for c in cards:
                if c.color == color:
                    return c
        return cards[0]

    def get_all_by_name(self, name: str) -> list[CardDefinition]:
        return self._by_name.get(name, [])

    def search(self, name_substring: str) -> list[CardDefinition]:
        """Search for cards whose name contains the substring (case-insensitive)."""
        lower = name_substring.lower()
        results = []
        for name, cards in self._by_name.items():
            if lower in name.lower():
                results.extend(cards)
        return results

    @property
    def all_cards(self) -> list[CardDefinition]:
        return list(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)

    def _parse_row(self, row: dict[str, str]) -> CardDefinition | None:
        types_str = row.get("Types", "")
        if not types_str.strip():
            return None

        card_types, sub_types, super_types = classify_type_string(types_str)
        keywords, keyword_values = _parse_keywords(row.get("Card Keywords", ""))

        # Filter out non-inherent keywords using functional text analysis
        functional_text = row.get("Functional Text", "")
        if functional_text:
            keywords = frozenset(
                kw for kw in keywords
                if _is_keyword_inherent(kw, functional_text)
            )

        return CardDefinition(
            unique_id=row["Unique ID"],
            name=row["Name"],
            color=_parse_color(row.get("Color", "")),
            pitch=_parse_int(row.get("Pitch", "")),
            cost=_parse_int(row.get("Cost", "")),
            power=_parse_int(row.get("Power", "")),
            defense=_parse_int(row.get("Defense", "")),
            health=_parse_int(row.get("Health", "")),
            intellect=_parse_int(row.get("Intelligence", "")),
            arcane=_parse_int(row.get("Arcane", "")),
            types=frozenset(card_types),
            subtypes=frozenset(sub_types),
            supertypes=frozenset(super_types),
            keywords=keywords,
            functional_text=row.get("Functional Text", ""),
            type_text=row.get("Type Text", ""),
            keyword_values=keyword_values,
        )
