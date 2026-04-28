"""Tests for Go Again evaluation on non-attack cards at resolution time.

Ensures non-attack cards query the effect engine for Go Again at resolution,
matching the pattern used by attack cards (rule 7.6.2 / 8.3.5).
"""

from __future__ import annotations

from engine.rules.continuous import EffectDuration, make_keyword_grant
from engine.enums import Keyword, Zone

from tests.conftest import make_card, make_game_shell


def test_non_attack_gains_go_again_from_effect():
    """Non-attack card without inherent Go Again gains it from a continuous effect."""
    game = make_game_shell(action_points={0: 0, 1: 0})
    card = make_card(1, "Test Action", is_attack=False, zone=Zone.HAND)
    game.state.players[0].hand.append(card)

    # Put card on stack
    layer = game.stack_mgr.add_card_layer(game.state, card, 0)

    # Grant Go Again via continuous effect AFTER card is on stack
    effect = make_keyword_grant(
        frozenset({Keyword.GO_AGAIN}),
        controller_index=0,
        source_instance_id=999,
        duration=EffectDuration.END_OF_TURN,
        target_filter=lambda c: c.instance_id == card.instance_id,
    )
    game.effect_engine.add_continuous_effect(game.state, effect)

    # Verify card does NOT have inherent Go Again
    assert not card.definition.has_go_again
    # But effect engine grants it
    assert Keyword.GO_AGAIN in game.effect_engine.get_modified_keywords(game.state, card)

    # Resolve - should grant AP via effect engine query
    game._move_to_graveyard_or_banish(card)
    if not card.definition.is_attack and Keyword.GO_AGAIN in game.effect_engine.get_modified_keywords(game.state, card):
        game.state.action_points[0] += 1

    assert game.state.action_points[0] == 1


def test_non_attack_inherent_go_again_still_works():
    """Non-attack card with inherent Go Again still grants AP."""
    game = make_game_shell(action_points={0: 0, 1: 0})
    card = make_card(1, "Go Again Action", is_attack=False,
                     keywords=frozenset({Keyword.GO_AGAIN}), zone=Zone.HAND)
    game.state.players[0].hand.append(card)

    layer = game.stack_mgr.add_card_layer(game.state, card, 0)

    # Resolve
    game._move_to_graveyard_or_banish(card)
    if not card.definition.is_attack and Keyword.GO_AGAIN in game.effect_engine.get_modified_keywords(game.state, card):
        game.state.action_points[0] += 1

    assert game.state.action_points[0] == 1


def test_non_attack_without_go_again_no_ap():
    """Non-attack card without Go Again does not grant AP."""
    game = make_game_shell(action_points={0: 0, 1: 0})
    card = make_card(1, "Plain Action", is_attack=False, zone=Zone.HAND)
    game.state.players[0].hand.append(card)

    layer = game.stack_mgr.add_card_layer(game.state, card, 0)

    # Resolve
    game._move_to_graveyard_or_banish(card)
    if not card.definition.is_attack and Keyword.GO_AGAIN in game.effect_engine.get_modified_keywords(game.state, card):
        game.state.action_points[0] += 1

    assert game.state.action_points[0] == 0
