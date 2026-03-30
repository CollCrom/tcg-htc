"""Tests for play restrictions: Command and Conquer, Exposed, Death Touch.

Covers:
- Command and Conquer: defense reactions can't be played this chain link
- Exposed: can't be played when controller is marked
- Death Touch: can only be played from arsenal
"""

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.actions import ActionOption
from htc.enums import (
    ActionType,
    CardType,
    Color,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from htc.state.player_state import BanishPlayability
from tests.conftest import make_card, make_game_shell
from tests.abilities.conftest import (
    make_attack_reaction,
    make_defense_reaction,
    make_ninja_attack,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_command_and_conquer(instance_id: int = 1, owner_index: int = 0) -> CardInstance:
    """Create a Command and Conquer attack action card."""
    defn = CardDefinition(
        unique_id=f"cnc-{instance_id}",
        name="Command and Conquer",
        color=Color.RED,
        pitch=1,
        cost=2,
        power=6,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="Defense reaction cards can't be played this chain link. When this hits a hero, destroy all cards in their arsenal.",
        type_text="Generic Action - Attack",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
    )


def _make_exposed(instance_id: int = 10, owner_index: int = 0) -> CardInstance:
    """Create an Exposed attack reaction card."""
    defn = CardDefinition(
        unique_id=f"exposed-{instance_id}",
        name="Exposed",
        color=Color.BLUE,
        pitch=3,
        cost=0,
        power=None,
        defense=None,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ATTACK_REACTION}),
        subtypes=frozenset(),
        supertypes=frozenset(),
        keywords=frozenset({Keyword.MARK}),
        functional_text='If you are marked, you can\'t play this.',
        type_text="Generic Attack Reaction",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HAND,
    )


def _make_death_touch(
    instance_id: int = 20,
    owner_index: int = 0,
    zone: Zone = Zone.HAND,
) -> CardInstance:
    """Create a Death Touch attack action card."""
    defn = CardDefinition(
        unique_id=f"dt-{instance_id}",
        name="Death Touch",
        color=Color.RED,
        pitch=1,
        cost=1,
        power=6,
        defense=2,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.ASSASSIN, SuperType.RANGER}),
        keywords=frozenset(),
        functional_text="Death Touch can't be played from hand.",
        type_text="Assassin Ranger Action - Attack",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=zone,
    )


def _option_ids(options: list[ActionOption]) -> list[str]:
    """Extract action_ids from a list of ActionOption."""
    return [o.action_id for o in options]


def _card_names_in_options(options: list[ActionOption]) -> list[str]:
    """Extract card names (from description) that are play-card actions."""
    return [
        o.description
        for o in options
        if o.action_type == ActionType.PLAY_CARD
    ]


# ---------------------------------------------------------------------------
# Command and Conquer — defense reactions blocked
# ---------------------------------------------------------------------------


def test_cnc_on_attack_sets_defense_reactions_blocked():
    """Command and Conquer on_attack sets defense_reactions_blocked on the chain link."""
    game = make_game_shell(action_points={0: 1, 1: 0})
    attack = _make_command_and_conquer(instance_id=1, owner_index=0)

    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    # Before on_attack, flag should be False
    assert link.defense_reactions_blocked is False

    # Fire on_attack handler
    from htc.cards.abilities.ninja import _command_and_conquer_on_attack
    from tests.abilities.conftest import make_ability_context

    ctx = make_ability_context(game, attack, 0, chain_link=link)
    _command_and_conquer_on_attack(ctx)

    assert link.defense_reactions_blocked is True


def test_cnc_blocks_defense_reactions_in_hand():
    """When defense_reactions_blocked is True, defender can't play defense reactions from hand."""
    game = make_game_shell()

    # Give defender (player 1) a defense reaction in hand
    dr = make_defense_reaction(name="Sink Below", instance_id=30, owner_index=1)
    game.state.players[1].hand.append(dr)

    # Set up combat with defense_reactions_blocked
    attack = _make_command_and_conquer(instance_id=1, owner_index=0)
    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)
    link.defense_reactions_blocked = True

    # Build reaction decision for defender
    decision = game.action_builder.build_reaction_decision(
        game.state,
        priority_player=1,
        attacker_index=0,
        defender_index=1,
    )

    # Defense reaction should NOT be offered
    card_ids = [o.card_instance_id for o in decision.options if o.action_type == ActionType.PLAY_CARD]
    assert dr.instance_id not in card_ids


def test_cnc_blocks_defense_reactions_from_banish():
    """When defense_reactions_blocked is True, defense reactions from banish are also blocked."""
    game = make_game_shell()

    # Give defender a defense reaction in banish marked as playable
    dr = make_defense_reaction(name="Frailty Trap", instance_id=31, owner_index=1)
    dr.zone = Zone.BANISHED
    game.state.players[1].banished.append(dr)
    game.state.players[1].playable_from_banish.append(
        BanishPlayability(dr.instance_id, "end_of_turn", False)
    )

    # Set up combat with defense_reactions_blocked
    attack = _make_command_and_conquer(instance_id=1, owner_index=0)
    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)
    link.defense_reactions_blocked = True

    decision = game.action_builder.build_reaction_decision(
        game.state,
        priority_player=1,
        attacker_index=0,
        defender_index=1,
    )

    card_ids = [o.card_instance_id for o in decision.options if o.action_type == ActionType.PLAY_CARD]
    assert dr.instance_id not in card_ids


def test_cnc_does_not_block_attack_reactions():
    """Command and Conquer's defense_reactions_blocked does NOT affect attack reactions."""
    game = make_game_shell()

    # Give attacker (player 0) an attack reaction in hand
    ar = make_attack_reaction(name="Razor Reflex", instance_id=40, owner_index=0)
    game.state.players[0].hand.append(ar)

    attack = _make_command_and_conquer(instance_id=1, owner_index=0)
    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)
    link.defense_reactions_blocked = True

    decision = game.action_builder.build_reaction_decision(
        game.state,
        priority_player=0,
        attacker_index=0,
        defender_index=1,
    )

    card_ids = [o.card_instance_id for o in decision.options if o.action_type == ActionType.PLAY_CARD]
    assert ar.instance_id in card_ids


def test_cnc_without_flag_allows_defense_reactions():
    """Without defense_reactions_blocked, defense reactions are offered normally."""
    game = make_game_shell()

    dr = make_defense_reaction(name="Sink Below", instance_id=30, owner_index=1)
    game.state.players[1].hand.append(dr)

    attack = make_ninja_attack(instance_id=1, owner_index=0)
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    decision = game.action_builder.build_reaction_decision(
        game.state,
        priority_player=1,
        attacker_index=0,
        defender_index=1,
    )

    card_ids = [o.card_instance_id for o in decision.options if o.action_type == ActionType.PLAY_CARD]
    assert dr.instance_id in card_ids


# ---------------------------------------------------------------------------
# Exposed — can't play when marked
# ---------------------------------------------------------------------------


def test_exposed_blocked_when_marked():
    """Exposed can't be played when the controller is marked."""
    game = make_game_shell()

    exposed = _make_exposed(instance_id=10, owner_index=0)
    game.state.players[0].hand.append(exposed)
    game.state.players[0].is_marked = True

    # Set up combat: player 0 is the attacker
    attack = make_ninja_attack(instance_id=1, owner_index=0)
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    decision = game.action_builder.build_reaction_decision(
        game.state,
        priority_player=0,
        attacker_index=0,
        defender_index=1,
    )

    card_ids = [o.card_instance_id for o in decision.options if o.action_type == ActionType.PLAY_CARD]
    assert exposed.instance_id not in card_ids


def test_exposed_allowed_when_not_marked():
    """Exposed can be played when the controller is NOT marked."""
    game = make_game_shell()

    exposed = _make_exposed(instance_id=10, owner_index=0)
    game.state.players[0].hand.append(exposed)
    game.state.players[0].is_marked = False

    attack = make_ninja_attack(instance_id=1, owner_index=0)
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    decision = game.action_builder.build_reaction_decision(
        game.state,
        priority_player=0,
        attacker_index=0,
        defender_index=1,
    )

    card_ids = [o.card_instance_id for o in decision.options if o.action_type == ActionType.PLAY_CARD]
    assert exposed.instance_id in card_ids


# ---------------------------------------------------------------------------
# Death Touch — can only be played from arsenal
# ---------------------------------------------------------------------------


def test_death_touch_blocked_from_hand():
    """Death Touch can't be played from hand."""
    game = make_game_shell(action_points={0: 1, 1: 0})

    dt = _make_death_touch(instance_id=20, owner_index=0, zone=Zone.HAND)
    game.state.players[0].hand.append(dt)

    # Give player a pitch card so cost isn't the issue
    from tests.conftest import make_pitch_card
    pitch = make_pitch_card(instance_id=200, owner_index=0, pitch=3)
    game.state.players[0].hand.append(pitch)

    decision = game.action_builder.build_action_decision(
        game.state, player_index=0, stack_is_empty=True
    )

    card_ids = [o.card_instance_id for o in decision.options if o.action_type == ActionType.PLAY_CARD]
    assert dt.instance_id not in card_ids


def test_death_touch_allowed_from_arsenal():
    """Death Touch CAN be played from arsenal."""
    game = make_game_shell(action_points={0: 1, 1: 0})

    dt = _make_death_touch(instance_id=20, owner_index=0, zone=Zone.ARSENAL)
    game.state.players[0].arsenal.append(dt)

    # Give player a pitch card so cost isn't the issue
    from tests.conftest import make_pitch_card
    pitch = make_pitch_card(instance_id=200, owner_index=0, pitch=3)
    game.state.players[0].hand.append(pitch)

    decision = game.action_builder.build_action_decision(
        game.state, player_index=0, stack_is_empty=True
    )

    card_ids = [o.card_instance_id for o in decision.options if o.action_type == ActionType.PLAY_CARD]
    assert dt.instance_id in card_ids


def test_death_touch_blocked_from_banish():
    """Death Touch can NOT be played from banish — only from arsenal."""
    game = make_game_shell(action_points={0: 1, 1: 0})

    dt = _make_death_touch(instance_id=20, owner_index=0, zone=Zone.BANISHED)
    game.state.players[0].banished.append(dt)
    game.state.players[0].playable_from_banish.append(
        BanishPlayability(dt.instance_id, "end_of_turn", False)
    )

    # Give player a pitch card so cost isn't the issue
    from tests.conftest import make_pitch_card
    pitch = make_pitch_card(instance_id=200, owner_index=0, pitch=3)
    game.state.players[0].hand.append(pitch)

    decision = game.action_builder.build_action_decision(
        game.state, player_index=0, stack_is_empty=True
    )

    card_ids = [o.card_instance_id for o in decision.options if o.action_type == ActionType.PLAY_CARD]
    assert dt.instance_id not in card_ids


def test_death_touch_can_play_card_returns_false_for_hand():
    """ActionBuilder.can_play_card returns False for Death Touch in hand zone."""
    game = make_game_shell(action_points={0: 1, 1: 0})
    dt = _make_death_touch(instance_id=20, owner_index=0, zone=Zone.HAND)
    assert game.action_builder.can_play_card(game.state, 0, dt) is False


def test_death_touch_can_play_card_returns_true_for_arsenal():
    """ActionBuilder.can_play_card returns True for Death Touch in arsenal zone."""
    game = make_game_shell(action_points={0: 1, 1: 0})

    from tests.conftest import make_pitch_card
    pitch = make_pitch_card(instance_id=200, owner_index=0, pitch=3)
    game.state.players[0].hand.append(pitch)

    dt = _make_death_touch(instance_id=20, owner_index=0, zone=Zone.ARSENAL)
    assert game.action_builder.can_play_card(game.state, 0, dt) is True
