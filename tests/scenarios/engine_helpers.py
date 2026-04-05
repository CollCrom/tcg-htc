"""Helpers for engine-driven scenario tests.

Provides ``make_scripted_game()`` which sets up a real game with actual
decklists and ScriptedPlayer instances so scenario tests can drive
specific game sequences through the full engine.
"""

from __future__ import annotations

import re
from pathlib import Path

from htc.cards.card_db import CardDatabase
from htc.decks.deck_list import DeckEntry, DeckList
from htc.engine.game import Game
from htc.enums import Color
from htc.player.scripted_player import ScriptedPlayer

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
REF_DIR = Path(__file__).resolve().parent.parent.parent / "ref"

_COLOR_MAP = {
    "red": Color.RED,
    "yellow": Color.YELLOW,
    "blue": Color.BLUE,
}

# Module-level cache so we don't re-parse on every test
_cached_db: CardDatabase | None = None
_cached_cindra: DeckList | None = None
_cached_arakni: DeckList | None = None


def _get_db() -> CardDatabase:
    global _cached_db
    if _cached_db is None:
        _cached_db = CardDatabase.load(DATA_DIR / "cards.tsv")
    return _cached_db


def _get_cindra_deck() -> DeckList:
    global _cached_cindra
    if _cached_cindra is None:
        text = (REF_DIR / "decklist-cindra-blue.md").read_text()
        _cached_cindra = parse_markdown_decklist(text)
    return _cached_cindra


def _get_arakni_deck() -> DeckList:
    global _cached_arakni
    if _cached_arakni is None:
        text = (REF_DIR / "decklist-arakni.md").read_text()
        _cached_arakni = parse_markdown_decklist(text)
    return _cached_arakni


def make_scripted_game(
    p1_script: list[str | list[str]] | None = None,
    p2_script: list[str | list[str]] | None = None,
    seed: int = 0,
    max_turns: int = 1,
) -> tuple[Game, ScriptedPlayer, ScriptedPlayer]:
    """Create a game with scripted players using real Cindra vs Arakni decklists.

    Player 0 = Cindra (Ninja), Player 1 = Arakni (Assassin).

    Returns (game, p1_scripted, p2_scripted).
    The game has ``_setup_game()`` already called — players have heroes,
    equipment, shuffled decks, and starting hands.

    Call ``game._run_turn()`` to advance turns. The scripted players
    will follow their scripts; when exhausted, they auto-pass.

    Args:
        p1_script: Script for player 0 (Cindra). See ScriptedPlayer docs.
        p2_script: Script for player 1 (Arakni). See ScriptedPlayer docs.
        seed: RNG seed for deterministic games.
        max_turns: Informational only (not enforced here — caller runs turns).
    """
    db = _get_db()
    deck1 = _get_cindra_deck()
    deck2 = _get_arakni_deck()

    p1 = ScriptedPlayer(p1_script)
    p2 = ScriptedPlayer(p2_script)

    game = Game(db, deck1, deck2, p1, p2, seed=seed)
    game._setup_game()

    return game, p1, p2


# ---------------------------------------------------------------------------
# Markdown decklist parser (same logic as test_full_game.py)
# ---------------------------------------------------------------------------


def parse_markdown_decklist(text: str) -> DeckList:
    """Parse a markdown decklist (ref/ format) into a DeckList."""
    hero_name = ""
    weapons: list[str] = []
    equipment: list[str] = []
    cards: list[DeckEntry] = []
    section = ""

    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
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

    from htc.decks.loader import AGENT_OF_CHAOS_DEMI_HEROES
    demi_heroes: list[str] = []
    if "arakni" in hero_name.lower() and "marionette" in hero_name.lower():
        demi_heroes = list(AGENT_OF_CHAOS_DEMI_HEROES)

    return DeckList(
        hero_name=hero_name, weapons=weapons, equipment=equipment,
        cards=cards, demi_heroes=demi_heroes,
    )


def _parse_equipment_line_with_count(line: str) -> tuple[str | None, int]:
    """Parse equipment line, returning (name, count)."""
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
