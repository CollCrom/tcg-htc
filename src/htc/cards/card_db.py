from __future__ import annotations

import csv
import re
from pathlib import Path

from htc.cards.card import CardDefinition
from htc.enums import Color, Keyword, classify_type_string


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

# Words that precede a keyword to indicate it is conditional (granted by an
# ability), not inherent to the card.
_CONDITIONAL_PREFIXES = re.compile(
    r"\b(?:gets?|gains?|has|lose[s]?)\b",
    re.IGNORECASE,
)


def _is_keyword_inherent(keyword: Keyword, functional_text: str) -> bool:
    """Determine if a keyword from card_keywords is inherent on the card.

    A keyword is inherent if it appears in the functional_text as a standalone
    bold keyword (``**Keyword**`` or ``**Keyword N**``) that is NOT preceded
    in its sentence by conditional words like "gets", "gains", "has", "loses".

    If the keyword does not appear in bold in the text at all, we conservatively
    treat it as inherent (the dataset may have keywords for cards with no
    functional_text, like heroes/equipment with only keyword abilities).
    """
    if not functional_text:
        # No text to check — trust the card_keywords field.
        return True

    kw_name = keyword.value  # e.g. "Go again", "Arcane Barrier"

    # Build pattern to find **Keyword** or **Keyword N** in text.
    # Case-insensitive because text varies (e.g. "**Go again**" vs "**go again**").
    escaped = re.escape(kw_name)
    # Match the bold keyword, optionally followed by a space and digits (for
    # parameterized keywords like **Arcane Barrier 1**).
    pattern = re.compile(
        r"\*\*" + escaped + r"(?:\s+\d+)?" + r"\*\*",
        re.IGNORECASE,
    )

    found_inherent = False
    found_conditional = False

    for match in pattern.finditer(functional_text):
        start = match.start()
        # Look backwards from the match to the start of the line.
        line_start = functional_text.rfind("\n", 0, start)
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1  # skip the newline char

        line_text = functional_text[line_start:start]

        # Use sentence-level context: split on ". " (period + space) and
        # only check the last sentence fragment before the keyword. This
        # avoids false positives where "gets" appears in an earlier,
        # unrelated clause on the same line (e.g. "...gets +1{p}. **Go again**").
        sentence_parts = re.split(r"\.\s", line_text)
        preceding = sentence_parts[-1].strip()

        if not preceding:
            # Keyword is at the start of a line — inherent.
            found_inherent = True
        elif _CONDITIONAL_PREFIXES.search(preceding):
            # Preceded by a conditional word — this is a conditional grant.
            found_conditional = True
        else:
            # Preceded by other text but not conditional words.
            # Examples: "**Combo** - When this attacks..." (Combo at start of
            # ability text is inherent), or "**Viserai Specialization**\n"
            found_inherent = True

    if not found_inherent and not found_conditional:
        # Keyword wasn't found in bold in text at all — trust card_keywords.
        return True

    # If there's at least one inherent occurrence, the keyword is inherent.
    return found_inherent


def _parse_keywords(
    value: str,
    functional_text: str = "",
) -> tuple[frozenset[Keyword], dict[Keyword, int]]:
    """Parse the 'Card Keywords' TSV field into inherent keywords and values.

    Cross-references ``functional_text`` to distinguish inherent keywords
    (standalone bold text like ``**Go again**``) from conditional ones
    (preceded by "gets", "gains", etc.).

    Returns (keywords_set, keyword_values) where keyword_values maps
    parameterized keywords to their number, e.g. "Arcane Barrier 2" → {ARCANE_BARRIER: 2}.
    """
    candidates: set[Keyword] = set()
    values: dict[Keyword, int] = {}
    for raw in value.split(","):
        raw = raw.strip()
        if not raw:
            continue
        key = raw.lower()
        if key in _KEYWORD_BY_NAME:
            candidates.add(_KEYWORD_BY_NAME[key])
            continue
        # Try stripping a trailing number (e.g. "Ward 10" -> "Ward", value=10)
        m = _KEYWORD_WITH_NUMBER.match(raw)
        if m:
            key2 = m.group(1).strip().lower()
            if key2 in _KEYWORD_BY_NAME:
                kw = _KEYWORD_BY_NAME[key2]
                candidates.add(kw)
                try:
                    values[kw] = int(raw[len(m.group(1)):].strip())
                except ValueError:
                    pass

    # Filter to only inherent keywords by cross-referencing functional_text.
    result: set[Keyword] = set()
    for kw in candidates:
        if _is_keyword_inherent(kw, functional_text):
            result.add(kw)
        else:
            # Drop the keyword value too if the keyword is conditional.
            values.pop(kw, None)

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
        functional_text = row.get("Functional Text", "")
        keywords, keyword_values = _parse_keywords(
            row.get("Card Keywords", ""),
            functional_text,
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
            functional_text=functional_text,
            type_text=row.get("Type Text", ""),
            keyword_values=keyword_values,
        )
