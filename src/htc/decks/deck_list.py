from __future__ import annotations

from dataclasses import dataclass, field

from htc.enums import Color


@dataclass
class DeckEntry:
    """A single entry in a deck list: card name + optional color + count."""

    name: str
    color: Color | None = None
    count: int = 1


@dataclass
class DeckList:
    """A complete deck configuration for a player."""

    hero_name: str
    weapons: list[str] = field(default_factory=list)
    equipment: list[str] = field(default_factory=list)  # head, chest, arms, legs
    cards: list[DeckEntry] = field(default_factory=list)

    @property
    def total_deck_cards(self) -> int:
        return sum(e.count for e in self.cards)
