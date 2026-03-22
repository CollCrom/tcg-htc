from __future__ import annotations

from htc.decks.deck_list import DeckEntry, DeckList
from htc.enums import Color

_COLOR_MAP = {
    "red": Color.RED,
    "yellow": Color.YELLOW,
    "blue": Color.BLUE,
}


def parse_deck_list(text: str) -> DeckList:
    """Parse a simple deck list text format.

    Format:
        Hero: Bravo, Showstopper
        Weapons: Anothos
        Equipment: Crater Fist, Nullrune Hood, Nullrune Robe, Nullrune Boots
        ---
        3x Adrenaline Rush (Red)
        3x Adrenaline Rush (Yellow)
        3x Adrenaline Rush (Blue)
        3x Pummel (Red)
        ...
    """
    hero_name = ""
    weapons: list[str] = []
    equipment: list[str] = []
    cards: list[DeckEntry] = []
    in_cards = False

    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if line == "---":
            in_cards = True
            continue

        if line.lower().startswith("hero:"):
            hero_name = line.split(":", 1)[1].strip()
        elif line.lower().startswith("weapons:") or line.lower().startswith("weapon:"):
            weapons = [w.strip() for w in line.split(":", 1)[1].split(",")]
        elif line.lower().startswith("equipment:"):
            equipment = [e.strip() for e in line.split(":", 1)[1].split(",")]
        elif in_cards:
            entry = _parse_card_line(line)
            if entry:
                cards.append(entry)

    return DeckList(hero_name=hero_name, weapons=weapons, equipment=equipment, cards=cards)


def _parse_card_line(line: str) -> DeckEntry | None:
    """Parse a line like '3x Adrenaline Rush (Red)' or 'Pummel (Blue)'."""
    count = 1
    text = line

    # Check for "Nx " prefix
    if "x " in text[:5]:
        parts = text.split("x ", 1)
        try:
            count = int(parts[0].strip())
        except ValueError:
            pass
        text = parts[1].strip()

    # Check for color suffix like "(Red)"
    color: Color | None = None
    for color_name, color_enum in _COLOR_MAP.items():
        suffix = f"({color_name})"
        if text.lower().endswith(suffix):
            color = color_enum
            text = text[: -len(suffix)].strip()
            break

    if not text:
        return None

    return DeckEntry(name=text, color=color, count=count)
