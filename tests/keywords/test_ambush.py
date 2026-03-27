"""Tests for Ambush keyword (8.3).

Ambush: While in your arsenal, you may defend with this card.
"""
from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.actions import PlayerResponse
from htc.enums import CardType, Keyword, SubType, Zone
from tests.conftest import make_card, make_game_shell, make_mock_ask_once


def _make_ambush_card(
    instance_id: int = 20, defense: int = 3, name: str = "Ambush Card"
) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"ambush-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=1,
        power=4,
        defense=defense,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset(),
        keywords=frozenset({Keyword.AMBUSH}),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id, definition=defn, owner_index=1, zone=Zone.ARSENAL,
    )


def test_ambush_card_in_arsenal_can_defend():
    """Card with Ambush in arsenal should appear in defender options and work."""
    game = make_game_shell()
    state = game.state

    attack = make_card(instance_id=1, power=6)
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, 1)

    ambush_card = _make_ambush_card(instance_id=20, defense=3)
    state.players[1].arsenal = [ambush_card]
    state.players[1].hand = []

    game._ask = make_mock_ask_once(PlayerResponse(selected_option_ids=[
        f"defend_{ambush_card.instance_id}",
    ]))

    game._defend_step()

    assert len(link.defending_cards) == 1
    assert link.defending_cards[0] is ambush_card
    assert ambush_card not in state.players[1].arsenal


def test_non_ambush_arsenal_cannot_defend():
    """Card without Ambush in arsenal should NOT be a defender option."""
    game = make_game_shell()
    state = game.state

    attack = make_card(instance_id=1, power=6)
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, 1)

    normal_card = make_card(instance_id=20, defense=3, owner_index=1, zone=Zone.ARSENAL)
    state.players[1].arsenal = [normal_card]
    state.players[1].hand = []

    game._ask = make_mock_ask_once(PlayerResponse(selected_option_ids=[
        f"defend_{normal_card.instance_id}",
    ]))

    game._defend_step()

    # Normal arsenal card should not be in defenders (no option was generated)
    # The defend_step won't find the card in hand so it won't add it
    assert len(link.defending_cards) == 0


def test_ambush_with_hand_cards():
    """Ambush card from arsenal can defend alongside hand cards."""
    game = make_game_shell()
    state = game.state

    attack = make_card(instance_id=1, power=8)
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, 1)

    hand_card = make_card(instance_id=10, name="Hand Card", defense=3, owner_index=1, zone=Zone.HAND)
    ambush_card = _make_ambush_card(instance_id=20, defense=3)

    state.players[1].hand = [hand_card]
    state.players[1].arsenal = [ambush_card]

    game._ask = make_mock_ask_once(PlayerResponse(selected_option_ids=[
        f"defend_{hand_card.instance_id}",
        f"defend_{ambush_card.instance_id}",
    ]))

    game._defend_step()

    assert len(link.defending_cards) == 2
