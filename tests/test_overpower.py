"""Tests for Overpower keyword (8.3.9): limits defense to 1 action card from hand."""

from htc.engine.actions import PlayerResponse
from htc.engine.combat import CombatManager
from htc.engine.effects import EffectEngine
from htc.engine.events import EventBus
from htc.engine.game import Game
from htc.engine.stack import StackManager
from htc.enums import Keyword, Zone
from htc.state.game_state import GameState
from htc.state.player_state import PlayerState
from tests.conftest import make_card


def _make_game_shell() -> Game:
    game = Game.__new__(Game)
    game.state = GameState()
    game.state.players = [
        PlayerState(index=0, life_total=20),
        PlayerState(index=1, life_total=20),
    ]
    game.effect_engine = EffectEngine()
    game.events = EventBus()
    game.stack_mgr = StackManager()
    game.combat_mgr = CombatManager(game.effect_engine)
    game._register_event_handlers()
    game.state.action_points = {0: 0, 1: 0}
    game.state.resource_points = {0: 0, 1: 0}
    game.state.turn_player_index = 0
    return game


def _mock_ask(first_response: PlayerResponse):
    """Return first_response once, then always pass."""
    called = [False]

    def _ask(decision):
        if not called[0]:
            called[0] = True
            return first_response
        return PlayerResponse(selected_option_ids=["pass"])

    return _ask


def test_overpower_limits_action_card_defense():
    """With Overpower, only 1 action card should be accepted for defense."""
    game = _make_game_shell()
    state = game.state

    attack = make_card(instance_id=1, power=8, keywords=frozenset({Keyword.OVERPOWER}))
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, 1)

    card_a = make_card(instance_id=10, name="Card A", defense=3, owner_index=1, zone=Zone.HAND)
    card_b = make_card(instance_id=11, name="Card B", defense=3, owner_index=1, zone=Zone.HAND)
    card_c = make_card(instance_id=12, name="Card C", defense=2, owner_index=1, zone=Zone.HAND)
    state.players[1].hand = [card_a, card_b, card_c]

    game._ask = _mock_ask(PlayerResponse(selected_option_ids=[
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
    game = _make_game_shell()
    state = game.state

    from htc.cards.card import CardDefinition
    from htc.cards.instance import CardInstance
    from htc.enums import CardType, EquipmentSlot, SubType

    attack = make_card(instance_id=1, power=6, keywords=frozenset({Keyword.OVERPOWER}))
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, 1)

    hand_card = make_card(instance_id=10, name="Hand Card", defense=3, owner_index=1, zone=Zone.HAND)
    state.players[1].hand = [hand_card]

    eq_def = CardDefinition(
        unique_id="eq-1", name="Chest Plate", color=None, pitch=None,
        cost=0, power=None, defense=2, health=None, intellect=None,
        arcane=None, types=frozenset({CardType.EQUIPMENT}),
        subtypes=frozenset({SubType.CHEST}), supertypes=frozenset(),
        keywords=frozenset(), functional_text="", type_text="",
    )
    eq = CardInstance(instance_id=50, definition=eq_def, owner_index=1, zone=Zone.CHEST)
    state.players[1].equipment[EquipmentSlot.CHEST] = eq

    game._ask = _mock_ask(PlayerResponse(selected_option_ids=[
        f"defend_{hand_card.instance_id}",
        f"defend_{eq.instance_id}",
    ]))

    game._defend_step()

    # Both accepted: 1 action card from hand + 1 equipment
    assert len(link.defending_cards) == 2


def test_no_overpower_allows_multiple_action_cards():
    """Without Overpower, multiple action cards can defend."""
    game = _make_game_shell()
    state = game.state

    attack = make_card(instance_id=1, power=8)
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, 1)

    card_a = make_card(instance_id=10, name="Card A", defense=3, owner_index=1, zone=Zone.HAND)
    card_b = make_card(instance_id=11, name="Card B", defense=3, owner_index=1, zone=Zone.HAND)
    state.players[1].hand = [card_a, card_b]

    game._ask = _mock_ask(PlayerResponse(selected_option_ids=[
        f"defend_{card_a.instance_id}",
        f"defend_{card_b.instance_id}",
    ]))

    game._defend_step()

    assert len(link.defending_cards) == 2
