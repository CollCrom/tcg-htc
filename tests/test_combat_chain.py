"""Tests for Phase 1: Priority, Stack, and Combat Chain Steps."""
import logging

from tests.conftest import run_game


def test_game_completes_with_winner():
    """Game should complete with a winner in under 200 turns."""
    result = run_game()
    assert result.winner is not None
    assert result.turns < 200
    assert result.turns > 0


def test_game_deterministic():
    """Same seeds should produce the same result."""
    r1 = run_game(seed=42, p1_seed=1, p2_seed=2)
    r2 = run_game(seed=42, p1_seed=1, p2_seed=2)
    assert r1.winner == r2.winner
    assert r1.turns == r2.turns
    assert r1.final_life == r2.final_life


def test_different_seeds_different_games():
    """Different seeds should produce different results (usually)."""
    results = [run_game(seed=i, p1_seed=i * 10, p2_seed=i * 20) for i in range(5)]
    # At least some variation in turn counts
    turn_counts = {r.turns for r in results}
    assert len(turn_counts) > 1, "All 5 games had identical turn counts — suspicious"


def test_life_totals_consistent():
    """Winner should have positive life, loser should have <= 0."""
    result = run_game()
    assert result.winner is not None
    winner_life = result.final_life[result.winner]
    loser_life = result.final_life[1 - result.winner]
    assert winner_life > 0, f"Winner has {winner_life} life"
    assert loser_life <= 0, f"Loser has {loser_life} life"


def test_no_duplicate_game_over_message(caplog):
    """Game over message should only appear once."""
    with caplog.at_level(logging.INFO):
        run_game()
    game_over_messages = [r for r in caplog.records if "defeated" in r.message]
    assert len(game_over_messages) == 1, f"Got {len(game_over_messages)} game-over messages"


def test_multiple_games_all_complete():
    """Run 10 games with different seeds to stress-test the engine."""
    for i in range(10):
        result = run_game(seed=i * 7, p1_seed=i * 3, p2_seed=i * 5 + 1)
        assert result.winner is not None or result.turns >= 200, (
            f"Game {i} ended without winner in {result.turns} turns"
        )
        assert result.turns > 0
