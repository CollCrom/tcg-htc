"""Helpers for engine-driven scenario tests.

Provides ``make_scripted_game()`` which sets up a real game with actual
decklists and ScriptedPlayer instances so scenario tests can drive
specific game sequences through the full engine.
"""

from __future__ import annotations

from engine.cards.card_db import CardDatabase
from engine.decks.deck_list import DeckList, parse_markdown_decklist
from engine.rules.game import Game
from tests._helpers.scripted_player import ScriptedPlayer
from tests.conftest import CARDS_TSV, REF_DIR

# Module-level cache so we don't re-parse on every test
_cached_db: CardDatabase | None = None
_cached_cindra: DeckList | None = None
_cached_arakni: DeckList | None = None


def _get_db() -> CardDatabase:
    global _cached_db
    if _cached_db is None:
        _cached_db = CardDatabase.load(CARDS_TSV)
    return _cached_db


def _get_cindra_deck() -> DeckList:
    global _cached_cindra
    if _cached_cindra is None:
        text = (REF_DIR / "decks" / "decklist-cindra-blue.md").read_text()
        _cached_cindra = parse_markdown_decklist(text)
    return _cached_cindra


def _get_arakni_deck() -> DeckList:
    global _cached_arakni
    if _cached_arakni is None:
        text = (REF_DIR / "decks" / "decklist-arakni.md").read_text()
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
