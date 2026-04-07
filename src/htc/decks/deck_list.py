from __future__ import annotations

import re
from dataclasses import dataclass, field

from htc.enums import Color

_COLOR_MAP = {
    "red": Color.RED,
    "yellow": Color.YELLOW,
    "blue": Color.BLUE,
}


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
    demi_heroes: list[str] = field(default_factory=list)  # Agent of Chaos forms

    @property
    def total_deck_cards(self) -> int:
        return sum(e.count for e in self.cards)


def parse_markdown_decklist(text: str) -> DeckList:
    """Parse a markdown decklist (ref/ format) into a DeckList.

    Handles the markdown structure with ## Hero, ## Weapons, ## Equipment,
    and ## Deck sections. Card lines like '- 3x Card Name (Red)' or
    '- Card Name (Head)'.
    """
    hero_name = ""
    weapons: list[str] = []
    equipment: list[str] = []
    cards: list[DeckEntry] = []
    section = ""

    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        # Detect sections
        if line.startswith("## Hero"):
            section = "hero"
            continue
        elif line.startswith("## Weapon"):
            section = "weapons"
            continue
        elif line.startswith("## Equipment"):
            section = "equipment"
            continue
        elif line.startswith("## Deck"):
            section = "deck"
            continue
        elif line.startswith("### "):
            continue
        elif line.startswith("## ") or line.startswith("# "):
            section = ""
            continue
        elif line.startswith("**"):
            continue

        if section == "hero" and not line.startswith("-"):
            hero_name = line
        elif section == "weapons" and line.startswith("-"):
            wname, count = _parse_equipment_line_with_count(line)
            if wname:
                weapons.extend([wname] * count)
        elif section == "equipment" and line.startswith("-"):
            ename, count = _parse_equipment_line_with_count(line)
            if ename:
                equipment.extend([ename] * count)
        elif section == "deck" and line.startswith("-"):
            entry = _parse_deck_card_line(line)
            if entry:
                cards.append(entry)

    # Auto-include Agent of Chaos Demi-Heroes for Arakni, Marionette
    from htc.decks.loader import AGENT_OF_CHAOS_DEMI_HEROES

    demi_heroes: list[str] = []
    if "arakni" in hero_name.lower() and "marionette" in hero_name.lower():
        demi_heroes = list(AGENT_OF_CHAOS_DEMI_HEROES)

    return DeckList(
        hero_name=hero_name,
        weapons=weapons,
        equipment=equipment,
        cards=cards,
        demi_heroes=demi_heroes,
    )


def _parse_equipment_line_with_count(line: str) -> tuple[str | None, int]:
    """Parse equipment line like '- 2x Kunai (1H Dagger)', returning (name, count)."""
    line = line.lstrip("- ").strip()
    count = 1
    m = re.match(r"(\d+)x\s+", line)
    if m:
        count = int(m.group(1))
        line = line[m.end():]
    line = re.sub(r"\s*\([^)]*\)\s*$", "", line)
    name = line.strip() if line.strip() else None
    return name, count


def _parse_deck_card_line(line: str) -> DeckEntry | None:
    """Parse '- 3x Card Name (Red)' into a DeckEntry."""
    line = line.lstrip("- ").strip()
    count = 1
    m = re.match(r"(\d+)x\s+", line)
    if m:
        count = int(m.group(1))
        line = line[m.end():]

    color: Color | None = None
    for color_name, color_enum in _COLOR_MAP.items():
        suffix = f"({color_name})"
        if line.lower().endswith(suffix):
            color = color_enum
            line = line[: -len(suffix)].strip()
            break

    if not line:
        return None

    return DeckEntry(name=line, color=color, count=count)
