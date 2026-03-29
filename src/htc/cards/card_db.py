from __future__ import annotations

import csv
import re
from pathlib import Path

from htc.cards.card import CardDefinition
from htc.enums import Color, Keyword, classify_type_string


def _parse_int(value: str) -> int | None:
    """Parse an integer from a CSV field, returning None for blank/non-numeric."""
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
# in the CSV like "Ward 10" or "Arcane Barrier 1" — we strip the number.
_KEYWORD_BY_NAME: dict[str, Keyword] = {}
for _kw in Keyword:
    _KEYWORD_BY_NAME[_kw.value.lower()] = _kw

_KEYWORD_WITH_NUMBER = re.compile(r"^(.+?)\s+\d+$")


def _parse_keywords(value: str) -> tuple[frozenset[Keyword], dict[Keyword, int]]:
    """Parse the 'Card Keywords' CSV field into keywords and their numeric values.

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
    def load(cls, csv_path: str | Path) -> CardDatabase:
        db = cls()
        path = Path(csv_path)
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
