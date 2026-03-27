"""Tests for Overpower keyword (8.3.9): limits defense to 1 action card from hand."""

from htc.engine.actions import PlayerResponse
from htc.enums import EquipmentSlot, Keyword, SubType, Zone
from tests.conftest import make_card, make_equipment, make_game_shell, make_mock_ask_once


def test_overpower_limits_action_card_defense():
    """With Overpower, only 1 action card should be accepted for defense."""
    game = make_game_shell()
    state = game.state

    attack = make_card(instance_id=1, power=8, keywords=frozenset({Keyword.OVERPOWER}))
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, 1)

    card_a = make_card(instance_id=10, name="Card A", defense=3, owner_index=1, zone=Zone.HAND)
    card_b = make_card(instance_id=11, name="Card B", defense=3, owner_index=1, zone=Zone.HAND)
    card_c = make_card(instance_id=12, name="Card C", defense=2, owner_index=1, zone=Zone.HAND)
    state.players[1].hand = [card_a, card_b, card_c]

    game._ask = make_mock_ask_once(PlayerResponse(selected_option_ids=[
        f"defend_{card_a.instance_id}",
        f"defend_{card_b.instance_id}",
        f"defend_{card_c.instance_id}",
    ]))

    game._defend_step()

    # Only 1 action card should have been accepted
    assert len(link.defending_cards) == 1
    assert link.defending_cards[0] is card_a


def test_overpower_does_not_limit_equipment():
    """Overpower should not limit equipment defense."""
    game = make_game_shell()
    state = game.state

    attack = make_card(instance_id=1, power=6, keywords=frozenset({Keyword.OVERPOWER}))
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, 1)

    hand_card = make_card(instance_id=10, name="Hand Card", defense=3, owner_index=1, zone=Zone.HAND)
    state.players[1].hand = [hand_card]

    eq = make_equipment(instance_id=50, name="Chest Plate", defense=2, subtype=SubType.CHEST)
    state.players[1].equipment[EquipmentSlot.CHEST] = eq

    game._ask = make_mock_ask_once(PlayerResponse(selected_option_ids=[
        f"defend_{hand_card.instance_id}",
        f"defend_{eq.instance_id}",
    ]))

    game._defend_step()

    # Both accepted: 1 action card from hand + 1 equipment
    assert len(link.defending_cards) == 2


def test_no_overpower_allows_multiple_action_cards():
    """Without Overpower, multiple action cards can defend."""
    game = make_game_shell()
    state = game.state

    attack = make_card(instance_id=1, power=8)
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, 1)

    card_a = make_card(instance_id=10, name="Card A", defense=3, owner_index=1, zone=Zone.HAND)
    card_b = make_card(instance_id=11, name="Card B", defense=3, owner_index=1, zone=Zone.HAND)
    state.players[1].hand = [card_a, card_b]

    game._ask = make_mock_ask_once(PlayerResponse(selected_option_ids=[
        f"defend_{card_a.instance_id}",
        f"defend_{card_b.instance_id}",
    ]))

    game._defend_step()

    assert len(link.defending_cards) == 2
