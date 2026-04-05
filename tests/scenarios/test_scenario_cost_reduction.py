"""Scenario: Cost reduction stacking edge cases.

Tests:
7. Ignite + Fealty cost reduction stacking — Ignite reduces next Draconic card
   by 1. If Fealty grants Draconic, the cost reduction applies. Multiple cost
   reductions should stack.

Source: strategy-cindra-post-bnr.md
"""

from __future__ import annotations

import logging

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.cards.abilities.ninja import _ignite_on_attack, _art_of_the_dragon_blood_on_attack
from htc.cards.abilities.tokens import _fealty_instant
from htc.engine.continuous import EffectDuration, make_cost_modifier
from htc.engine.events import EventType, GameEvent
from htc.enums import (
    CardType,
    Color,
    EquipmentSlot,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from tests.conftest import make_game_shell
from tests.abilities.conftest import (
    make_ability_context,
    make_draconic_ninja_attack,
    make_ninja_attack,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared card factories
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


def _make_fealty_token(instance_id: int = 500, owner_index: int = 0) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"fealty-{instance_id}",
        name="Fealty",
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=None,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.TOKEN}),
        subtypes=frozenset({SubType.AURA}),
        supertypes=frozenset({SuperType.DRACONIC}),
        keywords=frozenset(),
        functional_text="Instant - Destroy this: The next card you play this turn is Draconic.",
        type_text="Draconic Token - Aura",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.PERMANENT,
    )


def _setup_base_game():
    """Create a game shell with heroes set up for Cindra (P0) vs Opponent (P1)."""
    game = make_game_shell()
    state = game.state

    hero = _make_hero(instance_id=900, owner_index=0)
    state.players[0].hero = hero
    state.players[0].life_total = 20

    opp_hero = _make_hero(name="Opponent", instance_id=901, owner_index=1)
    state.players[1].hero = opp_hero
    state.players[1].life_total = 20

    return game


# ---------------------------------------------------------------------------
# Test 7: Ignite + Fealty cost reduction stacking
# ---------------------------------------------------------------------------


class TestIgniteFealtyStacking:
    """Multiple cost reductions should stack when applied to the same card.

    Scenario:
    - Ignite on-attack: next Draconic card costs 1 less (uses_remaining=1)
    - Fealty grants Draconic to next Ninja card played
    - That card should benefit from Ignite's cost reduction

    Source: strategy-cindra-post-bnr.md
    """

    def test_ignite_reduces_cost_of_draconic_card(self, scenario_recorder):
        """Basic: Ignite's -1 cost applies to an explicitly Draconic card."""
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)

        # Play Ignite (Draconic Ninja, on-attack registers cost reduction)
        ignite = make_draconic_ninja_attack(
            instance_id=1, name="Ignite", power=2, owner_index=0,
        )
        link = game.combat_mgr.add_chain_link(state, ignite, 1)

        ctx = make_ability_context(game, ignite, controller_index=0, chain_link=link)
        _ignite_on_attack(ctx)

        # Next Draconic card: cost=2, should become 1
        # Use "Dragon Power" (not "Blood Runs Deep") to avoid intrinsic cost modifiers
        next_card = make_draconic_ninja_attack(
            instance_id=2, name="Dragon Power", power=4, cost=2, owner_index=0,
        )
        next_card.zone = Zone.HAND  # Not yet played

        modified_cost = game.effect_engine.get_modified_cost(state, next_card)
        assert modified_cost == 1, (
            f"Ignite should reduce Draconic card cost by 1: 2 - 1 = 1. Got {modified_cost}"
        )

    def test_ignite_plus_fealty_stacks_cost_reduction(self, scenario_recorder):
        """Ignite + Fealty: next card is Draconic (via Fealty) and costs 1 less (via Ignite).

        Sequence:
        1. Attack with Ignite -> next Draconic costs 1 less
        2. Break Fealty -> next card played is Draconic
        3. Play a 2-cost Ninja card -> it's Draconic -> Ignite reduces to 1
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)

        # Step 1: Ignite on-attack
        ignite = make_draconic_ninja_attack(
            instance_id=1, name="Ignite", power=2, owner_index=0,
        )
        link = game.combat_mgr.add_chain_link(state, ignite, 1)

        ctx = make_ability_context(game, ignite, controller_index=0, chain_link=link)
        _ignite_on_attack(ctx)

        # Step 2: Break Fealty
        fealty = _make_fealty_token(instance_id=500, owner_index=0)
        state.players[0].permanents.append(fealty)
        fealty_ctx = make_ability_context(game, fealty, controller_index=0)
        _fealty_instant(fealty_ctx)

        # Step 3: Next card (Ninja, not inherently Draconic) -> should be Draconic via Fealty
        next_card = make_ninja_attack(
            instance_id=2, name="Dragon Power", power=4, cost=2, owner_index=0,
        )
        next_card.zone = Zone.COMBAT_CHAIN  # Simulating played

        # Verify Draconic is granted
        supertypes = game.effect_engine.get_modified_supertypes(state, next_card)
        assert SuperType.DRACONIC in supertypes, (
            "Fealty should grant Draconic to the next card played"
        )

        # Verify cost reduction
        modified_cost = game.effect_engine.get_modified_cost(state, next_card)
        assert modified_cost == 1, (
            f"Ignite cost reduction should apply to Fealty-granted Draconic card: "
            f"base 2 - 1 (Ignite) = 1. Got {modified_cost}"
        )

    def test_multiple_cost_reductions_stack(self, scenario_recorder):
        """If multiple cost reduction effects are active, they should all apply.

        Set up two separate -1 cost reductions targeting the same Draconic card.
        A 3-cost card should become 1-cost.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)

        # First cost reduction: from Ignite
        ignite = make_draconic_ninja_attack(
            instance_id=1, name="Ignite", power=2, owner_index=0,
        )
        link1 = game.combat_mgr.add_chain_link(state, ignite, 1)

        ctx1 = make_ability_context(game, ignite, controller_index=0, chain_link=link1)
        _ignite_on_attack(ctx1)

        # Second cost reduction: manual -1 for Draconic cards
        cost_effect = make_cost_modifier(
            -1,
            0,  # controller
            source_instance_id=999,
            duration=EffectDuration.END_OF_COMBAT,
            target_filter=lambda c: SuperType.DRACONIC in getattr(
                c, '_resolved_supertypes', c.definition.supertypes
            ),
        )
        cost_effect.uses_remaining = 1
        game.effect_engine.add_continuous_effect(state, cost_effect)

        # Target: 3-cost Draconic card (use "Dragon Power" to avoid intrinsic modifiers)
        target = make_draconic_ninja_attack(
            instance_id=2, name="Dragon Power", power=4, cost=3, owner_index=0,
        )
        target.zone = Zone.HAND

        modified_cost = game.effect_engine.get_modified_cost(state, target)
        assert modified_cost == 1, (
            f"Two -1 cost reductions should stack: 3 - 1 - 1 = 1. Got {modified_cost}"
        )

    def test_ignite_uses_remaining_consumed_on_first_draconic(self, scenario_recorder):
        """Ignite's cost reduction has uses_remaining=1. After the first Draconic
        card benefits, the reduction should be consumed.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)

        ignite = make_draconic_ninja_attack(
            instance_id=1, name="Ignite", power=2, owner_index=0,
        )
        link = game.combat_mgr.add_chain_link(state, ignite, 1)
        ctx = make_ability_context(game, ignite, controller_index=0, chain_link=link)
        _ignite_on_attack(ctx)

        # uses_remaining is only consumed by consume_limited_cost_effects() when
        # a card is actually played — get_modified_cost() is a read-only query.
        # So we simulate playing the first card by calling consume_limited_cost_effects.

        # First Draconic card: should get the reduction
        card1 = make_draconic_ninja_attack(
            instance_id=2, name="Dragon Power", power=4, cost=1, owner_index=0,
        )
        card1.zone = Zone.HAND
        cost1 = game.effect_engine.get_modified_cost(state, card1)
        assert cost1 == 0, f"First Draconic card should be reduced: 1 - 1 = 0. Got {cost1}"

        # Consume the uses_remaining (simulating the card being played)
        game.effect_engine.consume_limited_cost_effects(state, card1)

        # Second Draconic card: Ignite should be consumed now
        card2 = make_draconic_ninja_attack(
            instance_id=3, name="Display Loyalty", power=3, cost=2, owner_index=0,
        )
        card2.zone = Zone.HAND
        cost2 = game.effect_engine.get_modified_cost(state, card2)
        assert cost2 == 2, (
            f"After consuming Ignite's uses_remaining, second Draconic card "
            f"should not get the reduction. Cost 2 should remain 2. Got {cost2}"
        )
