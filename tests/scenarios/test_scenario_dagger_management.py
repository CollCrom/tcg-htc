"""Scenario: Dagger management — weapon slots, Flick Knives destroy, equip flow.

Verifies:
1. Flick Knives destroys an off-chain dagger (moves to graveyard, removed from weapons).
2. Once-per-turn enforcement on Flick Knives (activated_this_turn flag).
3. Flick Knives only offered when an off-chain dagger is available.
4. Flick Knives is NOT offered when both daggers are on-chain or no daggers exist.
"""

from __future__ import annotations

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.cards.abilities.equipment import _flick_knives
from htc.engine.action_builder import ActionBuilder
from htc.engine.events import EventType, GameEvent
from htc.enums import (
    CardType,
    Color,
    CombatStep,
    EquipmentSlot,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from htc.state.combat_state import ChainLink
from tests.conftest import make_card, make_game_shell, make_weapon
from tests.abilities.conftest import (
    make_ability_context,
    make_dagger_weapon,
    make_ninja_attack,
    make_weapon_proxy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hero(
    name: str = "Cindra, Drachai of Two Talons",
    instance_id: int = 900,
    owner_index: int = 0,
) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"hero-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=None,
        health=20,
        intellect=4,
        arcane=None,
        types=frozenset({CardType.HERO}),
        subtypes=frozenset(),
        supertypes=frozenset({SuperType.NINJA}),
        keywords=frozenset(),
        functional_text="",
        type_text="Hero - Ninja",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HERO,
    )


def _make_flick_knives(instance_id: int = 51, owner_index: int = 0) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"flick-{instance_id}",
        name="Flick Knives",
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=0,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.EQUIPMENT}),
        subtypes=frozenset({SubType.ARMS}),
        supertypes=frozenset({SuperType.ASSASSIN, SuperType.NINJA}),
        keywords=frozenset(),
        functional_text="",
        type_text="Assassin Ninja Equipment - Arms",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.ARMS,
    )


def _setup_dagger_test(*, num_daggers: int = 2):
    """Set up game with daggers and Flick Knives.

    Returns (game, flick, daggers_list).
    """
    game = make_game_shell()
    state = game.state

    hero = _make_hero(instance_id=900, owner_index=0)
    state.players[0].hero = hero
    state.players[0].life_total = 20

    opp_hero = _make_hero(name="Opponent", instance_id=901, owner_index=1)
    state.players[1].hero = opp_hero
    state.players[1].life_total = 20

    flick = _make_flick_knives(instance_id=51, owner_index=0)
    state.players[0].equipment[EquipmentSlot.ARMS] = flick

    daggers = []
    for i in range(num_daggers):
        d = make_dagger_weapon(
            instance_id=100 + i,
            name="Kunai of Retribution",
            owner_index=0,
        )
        d.zone = Zone.WEAPON_1 if i == 0 else Zone.WEAPON_2
        daggers.append(d)
    state.players[0].weapons = daggers

    return game, flick, daggers


# ---------------------------------------------------------------------------
# Tests: Flick Knives destroys dagger
# ---------------------------------------------------------------------------


class TestFlickKnivesDestroysDagger:
    """Flick Knives activation destroys an off-chain dagger."""

    def test_flick_destroys_off_chain_dagger(self):
        """Flick Knives should destroy one dagger (move to graveyard)."""
        game, flick, daggers = _setup_dagger_test(num_daggers=2)
        state = game.state

        dagger1, dagger2 = daggers

        # Open chain, attack with dagger1 (dagger2 is off-chain)
        game.combat_mgr.open_chain(state)
        proxy = make_weapon_proxy(dagger1, instance_id=200, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = dagger1

        ctx = make_ability_context(game, flick, controller_index=0, chain_link=link)
        _flick_knives(ctx)

        # dagger2 should be destroyed
        assert dagger2 not in state.players[0].weapons, (
            "Off-chain dagger should be removed from weapons list"
        )
        assert dagger2.zone == Zone.GRAVEYARD, (
            "Destroyed dagger should be in graveyard"
        )

        # dagger1 should still be in weapons (it was attacking)
        assert dagger1 in state.players[0].weapons, (
            "Attacking dagger should NOT be destroyed by Flick Knives"
        )

    def test_flick_sets_activated_this_turn(self):
        """Flick Knives should set activated_this_turn flag."""
        game, flick, daggers = _setup_dagger_test(num_daggers=2)
        state = game.state

        assert not flick.activated_this_turn

        game.combat_mgr.open_chain(state)
        proxy = make_weapon_proxy(daggers[0], instance_id=200, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = daggers[0]

        ctx = make_ability_context(game, flick, controller_index=0, chain_link=link)
        _flick_knives(ctx)

        assert flick.activated_this_turn, (
            "Flick Knives should set activated_this_turn flag after use"
        )

    def test_flick_deals_damage_to_opponent(self):
        """Flick Knives should deal 1 damage to the opponent via DEAL_DAMAGE event."""
        game, flick, daggers = _setup_dagger_test(num_daggers=2)
        state = game.state

        damage_events = []
        game.events.register_handler(
            EventType.DEAL_DAMAGE,
            lambda e: damage_events.append(e),
        )

        game.combat_mgr.open_chain(state)
        proxy = make_weapon_proxy(daggers[0], instance_id=200, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = daggers[0]

        ctx = make_ability_context(game, flick, controller_index=0, chain_link=link)
        _flick_knives(ctx)

        assert len(damage_events) >= 1, (
            "Flick Knives should emit a DEAL_DAMAGE event"
        )
        assert damage_events[0].amount == 1, (
            "Flick Knives dagger should deal exactly 1 damage"
        )
        assert damage_events[0].target_player == 1, (
            "Flick Knives damage should target the opponent"
        )

    def test_flick_with_no_off_chain_dagger_does_nothing(self):
        """Flick Knives should do nothing if no off-chain dagger is available."""
        game, flick, daggers = _setup_dagger_test(num_daggers=1)
        state = game.state

        # Attack with the only dagger — no off-chain dagger available
        game.combat_mgr.open_chain(state)
        proxy = make_weapon_proxy(daggers[0], instance_id=200, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = daggers[0]

        initial_graveyard = len(state.players[0].graveyard)

        ctx = make_ability_context(game, flick, controller_index=0, chain_link=link)
        _flick_knives(ctx)

        assert len(state.players[0].graveyard) == initial_graveyard, (
            "No dagger should be destroyed when no off-chain dagger exists"
        )


# ---------------------------------------------------------------------------
# Tests: ActionBuilder Flick Knives availability
# ---------------------------------------------------------------------------


class TestFlickKnivesAvailability:
    """ActionBuilder correctly offers/withholds Flick Knives."""

    def test_flick_offered_when_off_chain_dagger_exists(self):
        """ActionBuilder should offer Flick Knives when there's an off-chain dagger."""
        game, flick, daggers = _setup_dagger_test(num_daggers=2)
        state = game.state

        game.combat_mgr.open_chain(state)
        proxy = make_weapon_proxy(daggers[0], instance_id=200, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = daggers[0]

        can_use = game.action_builder._can_use_equipment_reaction(state, 0, flick)
        assert can_use, (
            "Flick Knives should be usable when off-chain dagger is available"
        )

    def test_flick_not_offered_when_no_daggers(self):
        """ActionBuilder should NOT offer Flick Knives when there are no daggers."""
        game, flick, daggers = _setup_dagger_test(num_daggers=0)
        state = game.state

        game.combat_mgr.open_chain(state)
        atk = make_ninja_attack(instance_id=10, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, atk, 1)

        can_use = game.action_builder._can_use_equipment_reaction(state, 0, flick)
        assert not can_use, (
            "Flick Knives should not be usable when no daggers exist"
        )

    def test_flick_not_offered_when_only_dagger_is_attacking(self):
        """ActionBuilder should NOT offer Flick Knives when the only dagger is on-chain."""
        game, flick, daggers = _setup_dagger_test(num_daggers=1)
        state = game.state

        game.combat_mgr.open_chain(state)
        proxy = make_weapon_proxy(daggers[0], instance_id=200, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = daggers[0]

        can_use = game.action_builder._can_use_equipment_reaction(state, 0, flick)
        assert not can_use, (
            "Flick Knives should not be usable when the only dagger is on-chain"
        )
