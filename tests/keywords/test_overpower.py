"""Tests for Overpower keyword (8.3.9): limits defense to 1 action card from hand."""

from engine.cards.card import CardDefinition
from engine.cards.instance import CardInstance
from engine.rules.actions import PlayerResponse
from engine.enums import CardType, EquipmentSlot, Keyword, SubType, Zone
from tests.conftest import make_card, make_equipment, make_game_shell, make_mock_ask_once


def _make_defense_reaction(
    instance_id: int,
    name: str = "Defense Reaction",
    *,
    defense: int = 3,
    cost: int = 0,
    owner_index: int = 1,
) -> CardInstance:
    """Create a defense reaction card for testing."""
    defn = CardDefinition(
        unique_id=f"dr-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=cost,
        power=None,
        defense=defense,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.DEFENSE_REACTION}),
        subtypes=frozenset(),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HAND,
    )


def _make_attack_reaction(
    instance_id: int,
    name: str = "Attack Reaction",
    *,
    power: int = 3,
    cost: int = 0,
    owner_index: int = 0,
) -> CardInstance:
    """Create an attack reaction card for testing."""
    defn = CardDefinition(
        unique_id=f"ar-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=cost,
        power=power,
        defense=None,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ATTACK_REACTION}),
        subtypes=frozenset(),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HAND,
    )


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


def test_overpower_allows_multiple_defense_reactions():
    """With Overpower, defender can still play 2+ defense reactions during reaction step.

    Overpower only restricts action cards from hand during the defend step (7.3).
    Defense reactions played during the reaction step (7.4) go through the stack
    and are not subject to the Overpower limit.
    """
    game = make_game_shell()
    state = game.state

    attack = make_card(instance_id=1, power=8, keywords=frozenset({Keyword.OVERPOWER}))
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, 1)

    # Two defense reactions in defender's hand (player 1)
    dr_a = _make_defense_reaction(instance_id=20, name="DR Alpha", defense=2)
    dr_b = _make_defense_reaction(instance_id=21, name="DR Beta", defense=3)
    state.players[1].hand = [dr_a, dr_b]

    # Mock: player 0 (attacker/turn player) always passes.
    # Player 1 (defender) plays each defense reaction one at a time, then passes.
    play_queue = [f"play_{dr_a.instance_id}", f"play_{dr_b.instance_id}"]

    def _ask(decision):
        if decision.player_index == 1 and play_queue:
            action_id = play_queue.pop(0)
            return PlayerResponse(selected_option_ids=[action_id])
        return PlayerResponse(selected_option_ids=["pass"])

    game._ask = _ask

    game._reaction_step()

    # Both defense reactions should have been added as defending cards
    assert len(link.defending_cards) == 2
    assert dr_a in link.defending_cards
    assert dr_b in link.defending_cards


def test_overpower_allows_blocking_with_attack_reactions():
    """With Overpower, attack reactions in hand should not be limited by the action card cap.

    Overpower (8.3.9) restricts the defender to 1 *action card* from hand.
    Attack reactions (CardType.ATTACK_REACTION) are not action cards, so they
    should all be accepted as defenders alongside the single allowed action card.
    """
    game = make_game_shell()
    state = game.state

    attack = make_card(instance_id=1, power=8, keywords=frozenset({Keyword.OVERPOWER}))
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, 1)

    # 1 action card + 2 attack reactions in defender's hand (player 1)
    action_card = make_card(instance_id=10, name="Action Card", defense=3, owner_index=1, zone=Zone.HAND)
    ar_a = _make_attack_reaction(instance_id=20, name="AR Alpha", power=3, owner_index=1)
    ar_a.definition = CardDefinition(
        unique_id="ar-20",
        name="AR Alpha",
        color=None,
        pitch=None,
        cost=0,
        power=3,
        defense=2,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ATTACK_REACTION}),
        subtypes=frozenset(),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    ar_b = _make_attack_reaction(instance_id=21, name="AR Beta", power=3, owner_index=1)
    ar_b.definition = CardDefinition(
        unique_id="ar-21",
        name="AR Beta",
        color=None,
        pitch=None,
        cost=0,
        power=3,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ATTACK_REACTION}),
        subtypes=frozenset(),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    state.players[1].hand = [action_card, ar_a, ar_b]

    game._ask = make_mock_ask_once(PlayerResponse(selected_option_ids=[
        f"defend_{action_card.instance_id}",
        f"defend_{ar_a.instance_id}",
        f"defend_{ar_b.instance_id}",
    ]))

    game._defend_step()

    # All 3 cards should be accepted: 1 action card (at the Overpower limit)
    # plus 2 attack reactions (not subject to Overpower's action card cap)
    assert len(link.defending_cards) == 3
    assert action_card in link.defending_cards
    assert ar_a in link.defending_cards
    assert ar_b in link.defending_cards
