"""Tests for Mark keyword (rules 9.3).

Mark is a condition on a hero. It persists until the hero is hit by
an opponent's source, at which point it is removed.
"""
from engine.rules.events import EventType, GameEvent
from engine.enums import Zone
from tests.conftest import make_card, make_game_shell


def test_mark_set_on_player():
    """Player can be marked."""
    game = make_game_shell()
    state = game.state
    assert state.players[1].is_marked is False
    state.players[1].is_marked = True
    assert state.players[1].is_marked is True


def test_mark_removed_on_hit_by_opponent():
    """Mark is removed when hero is hit by opponent's source (9.3.3)."""
    game = make_game_shell()
    state = game.state
    state.players[1].is_marked = True

    # Simulate a hit from player 0's source
    attack = make_card(instance_id=1, power=5, owner_index=0)
    game.events.emit(GameEvent(
        event_type=EventType.HIT,
        source=attack,
        target_player=1,
        amount=5,
    ))

    assert state.players[1].is_marked is False


def test_mark_not_removed_by_own_source():
    """Mark is NOT removed when hit by own source (self-damage)."""
    game = make_game_shell()
    state = game.state
    state.players[1].is_marked = True

    # Hit from player 1's own source
    own_card = make_card(instance_id=2, power=3, owner_index=1)
    game.events.emit(GameEvent(
        event_type=EventType.HIT,
        source=own_card,
        target_player=1,
        amount=3,
    ))

    assert state.players[1].is_marked is True


def test_mark_not_removed_without_source():
    """Mark is not removed if hit event has no source."""
    game = make_game_shell()
    state = game.state
    state.players[1].is_marked = True

    game.events.emit(GameEvent(
        event_type=EventType.HIT,
        source=None,
        target_player=1,
        amount=3,
    ))

    assert state.players[1].is_marked is True


def test_mark_not_removed_if_not_marked():
    """No error when hit event fires on unmarked player."""
    game = make_game_shell()
    state = game.state
    assert state.players[1].is_marked is False

    attack = make_card(instance_id=1, power=5, owner_index=0)
    game.events.emit(GameEvent(
        event_type=EventType.HIT,
        source=attack,
        target_player=1,
        amount=5,
    ))

    # Should still be False, no error
    assert state.players[1].is_marked is False


def test_mark_persists_across_non_hit_damage():
    """Mark persists through non-hit damage events (only HIT removes it)."""
    game = make_game_shell()
    state = game.state
    state.players[1].is_marked = True

    # Deal damage (not a HIT) — mark should persist
    attack = make_card(instance_id=1, power=5, owner_index=0)
    game.events.emit(GameEvent(
        event_type=EventType.DEAL_DAMAGE,
        source=attack,
        target_player=1,
        amount=5,
    ))

    assert state.players[1].is_marked is True
