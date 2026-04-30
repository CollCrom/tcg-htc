"""Tests for the forced-single-option decision auto-resolve in Game._ask.

The auto-resolve was introduced in commit 0c4c7c7 ("engine: auto-resolve
forced single-option decisions"). It short-circuits the player-interface
round-trip when a decision has exactly one option AND requires exactly
one selection (``min_selections == max_selections == 1``).

Match ``cindra-blue-vs-arakni-002`` analyst flagged a suspected
mis-fire: Player B closed the chain after a Klaive hit and wondered if
auto-resolve had eaten a go-again decision. These tests lock in the
invariants that the analyst was checking against.
"""
from __future__ import annotations

from engine.enums import ActionType, DecisionType
from engine.rules.actions import ActionOption, Decision, PlayerResponse
from tests.conftest import make_game_shell


class _CountingInterface:
    """A PlayerInterface stub that records every decide() call."""

    def __init__(self, response: PlayerResponse) -> None:
        self.calls: list[Decision] = []
        self.response = response

    def decide(self, state, decision):
        self.calls.append(decision)
        return self.response


def _opt(action_id: str, action_type: ActionType = ActionType.PASS) -> ActionOption:
    return ActionOption(action_id=action_id, description=action_id, action_type=action_type)


def test_auto_resolve_single_pass_option_does_not_call_interface():
    """A decision with one option and min/max == 1 is auto-resolved."""
    game = make_game_shell()
    iface_a = _CountingInterface(PlayerResponse(selected_option_ids=["should_not_be_used"]))
    iface_b = _CountingInterface(PlayerResponse(selected_option_ids=["should_not_be_used"]))
    game.interfaces = [iface_a, iface_b]

    decision = Decision(
        player_index=0,
        decision_type=DecisionType.PLAY_OR_PASS,
        prompt="Auto-resolve me",
        options=[_opt("pass")],
        min_selections=1,
        max_selections=1,
    )
    response = game._ask(decision)

    assert response.first == "pass"
    assert iface_a.calls == []
    assert iface_b.calls == []


def test_two_options_always_asks_interface():
    """Two options means a real choice — always round-trip to the player.

    This is the invariant the analyst was checking when they suspected
    auto-resolve had eaten Klaive's go-again prompt: a resolution-step
    decision with `pass` plus any attack/instant must reach the player.
    """
    game = make_game_shell()
    iface_a = _CountingInterface(PlayerResponse(selected_option_ids=["pass"]))
    iface_b = _CountingInterface(PlayerResponse(selected_option_ids=["pass"]))
    game.interfaces = [iface_a, iface_b]

    decision = Decision(
        player_index=1,
        decision_type=DecisionType.PLAY_OR_PASS,
        prompt="Continue combat chain or pass",
        options=[
            _opt("play_attack_77", ActionType.PLAY_CARD),
            _opt("pass"),
        ],
        min_selections=1,
        max_selections=1,
    )
    response = game._ask(decision)

    assert response.first == "pass"
    assert iface_a.calls == []
    assert len(iface_b.calls) == 1


def test_multi_select_one_option_still_auto_resolved():
    """Single option AND min==max==1: still auto-resolve."""
    game = make_game_shell()
    iface_a = _CountingInterface(PlayerResponse(selected_option_ids=["unused"]))
    iface_b = _CountingInterface(PlayerResponse(selected_option_ids=["unused"]))
    game.interfaces = [iface_a, iface_b]

    decision = Decision(
        player_index=0,
        decision_type=DecisionType.PLAY_OR_PASS,
        prompt="Solo prompt",
        options=[_opt("only")],
        min_selections=1,
        max_selections=1,
    )
    response = game._ask(decision)
    assert response.first == "only"
    assert iface_a.calls == []


def test_multi_select_min_max_gt_1_not_auto_resolved():
    """Multi-select decisions with multiple options must reach the player
    even when every option must be chosen — order may carry weight
    (pitch_order, order_triggers).
    """
    game = make_game_shell()
    iface_a = _CountingInterface(PlayerResponse(selected_option_ids=["a", "b"]))
    iface_b = _CountingInterface(PlayerResponse(selected_option_ids=[]))
    game.interfaces = [iface_a, iface_b]

    decision = Decision(
        player_index=0,
        decision_type=DecisionType.PLAY_OR_PASS,
        prompt="Order your pitched cards",
        options=[_opt("a"), _opt("b")],
        min_selections=2,
        max_selections=2,
    )
    response = game._ask(decision)
    assert response.selected_option_ids == ["a", "b"]
    assert len(iface_a.calls) == 1
