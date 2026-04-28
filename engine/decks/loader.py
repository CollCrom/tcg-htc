from __future__ import annotations

from engine.decks.deck_list import DeckEntry, DeckList
from engine.enums import Color

_COLOR_MAP = {
    "red": Color.RED,
    "yellow": Color.YELLOW,
    "blue": Color.BLUE,
}

# All Agent of Chaos Demi-Heroes — auto-included for Arakni, Marionette
AGENT_OF_CHAOS_DEMI_HEROES = [
    "Arakni, Black Widow",
    "Arakni, Funnel Web",
    "Arakni, Orb-Weaver",
    "Arakni, Redback",
    "Arakni, Tarantula",
    "Arakni, Trap-Door",
]


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
    demi_heroes: list[str] = []
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
        elif line.lower().startswith("demi-heroes:") or line.lower().startswith("demi heroes:"):
            # Use semicolons as delimiter since card names contain commas
            demi_heroes = [d.strip() for d in line.split(":", 1)[1].split(";") if d.strip()]
        elif in_cards:
            entry = _parse_card_line(line)
            if entry:
                cards.append(entry)

    # Auto-include Agent of Chaos Demi-Heroes for Arakni, Marionette
    if not demi_heroes and "arakni" in hero_name.lower() and "marionette" in hero_name.lower():
        demi_heroes = list(AGENT_OF_CHAOS_DEMI_HEROES)

    return DeckList(
        hero_name=hero_name, weapons=weapons, equipment=equipment,
        cards=cards, demi_heroes=demi_heroes,
    )


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
