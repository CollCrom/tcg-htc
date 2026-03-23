"""Tests for Phase 1: Priority, Stack, and Combat Chain Steps."""
import logging
from pathlib import Path

from htc.cards.card_db import CardDatabase
from htc.decks.loader import parse_deck_list
from htc.engine.game import Game, GameResult
from htc.player.random_player import RandomPlayer

DATA_DIR = Path(__file__).parent.parent / "data"

WARRIOR_DECK = """\
Hero: Bravo, Showstopper
Weapons: Anothos
Equipment: Crater Fist, Helm of Isen's Peak, Tectonic Plating, Ironrot Legs
---
3x Adrenaline Rush (Red)
3x Adrenaline Rush (Yellow)
3x Adrenaline Rush (Blue)
3x Debilitate (Red)
3x Debilitate (Yellow)
3x Debilitate (Blue)
3x Pummel (Red)
3x Pummel (Yellow)
3x Pummel (Blue)
3x Cartilage Crush (Red)
3x Cartilage Crush (Yellow)
3x Cartilage Crush (Blue)
3x Disable (Red)
3x Disable (Yellow)
3x Disable (Blue)
3x Sink Below (Red)
3x Sink Below (Yellow)
3x Sink Below (Blue)
3x Sigil of Solace (Red)
3x Sigil of Solace (Blue)
"""


def _run_game(seed: int = 7, p1_seed: int = 42, p2_seed: int = 123) -> GameResult:
    db = CardDatabase.load(DATA_DIR / "cards.csv")
    deck1 = parse_deck_list(WARRIOR_DECK)
    deck2 = parse_deck_list(WARRIOR_DECK)
    p1 = RandomPlayer(seed=p1_seed)
    p2 = RandomPlayer(seed=p2_seed)
    game = Game(db, deck1, deck2, p1, p2, seed=seed)
    return game.play()


def test_game_completes_with_winner():
    """Game should complete with a winner in under 200 turns."""
    result = _run_game()
    assert result.winner is not None
    assert result.turns < 200
    assert result.turns > 0


def test_game_deterministic():
    """Same seeds should produce the same result."""
    r1 = _run_game(seed=42, p1_seed=1, p2_seed=2)
    r2 = _run_game(seed=42, p1_seed=1, p2_seed=2)
    assert r1.winner == r2.winner
    assert r1.turns == r2.turns
    assert r1.final_life == r2.final_life


def test_different_seeds_different_games():
    """Different seeds should produce different results (usually)."""
    results = [_run_game(seed=i, p1_seed=i * 10, p2_seed=i * 20) for i in range(5)]
    # At least some variation in turn counts
    turn_counts = {r.turns for r in results}
    assert len(turn_counts) > 1, "All 5 games had identical turn counts — suspicious"


def test_life_totals_consistent():
    """Winner should have positive life, loser should have <= 0."""
    result = _run_game()
    assert result.winner is not None
    winner_life = result.final_life[result.winner]
    loser_life = result.final_life[1 - result.winner]
    assert winner_life > 0, f"Winner has {winner_life} life"
    assert loser_life <= 0, f"Loser has {loser_life} life"


def test_no_duplicate_game_over_message(caplog):
    """Game over message should only appear once."""
    with caplog.at_level(logging.INFO):
        _run_game()
    game_over_messages = [r for r in caplog.records if "defeated" in r.message]
    assert len(game_over_messages) == 1, f"Got {len(game_over_messages)} game-over messages"


def test_multiple_games_all_complete():
    """Run 10 games with different seeds to stress-test the engine."""
    for i in range(10):
        result = _run_game(seed=i * 7, p1_seed=i * 3, p2_seed=i * 5 + 1)
        assert result.winner is not None or result.turns >= 200, (
            f"Game {i} ended without winner in {result.turns} turns"
        )
        assert result.turns > 0
