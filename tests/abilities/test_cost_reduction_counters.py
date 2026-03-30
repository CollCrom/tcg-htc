"""Tests for usage-limited cost reduction counters.

Verifies that Art of the Dragon: Blood (next 3 Draconic cards cost 1 less)
and Ignite (next 1 Draconic card costs 1 less) correctly track and
decrement their usage counters instead of applying blanket reductions.
"""

from htc.engine.continuous import (
    ContinuousEffect,
    EffectDuration,
    NumericProperty,
    make_cost_modifier,
)
from htc.engine.effects import EffectEngine
from htc.enums import SuperType
from tests.conftest import make_card, make_game_shell, make_state
from tests.abilities.conftest import (
    make_ability_context,
    make_draconic_ninja_attack,
    make_draconic_attack,
    make_ninja_attack,
)


# ---------------------------------------------------------------------------
# Helper: create a limited-use Draconic cost reduction effect
# ---------------------------------------------------------------------------


def _make_draconic_cost_reduction(
    effect_engine: EffectEngine,
    state,
    *,
    amount: int = -1,
    uses: int = 3,
    controller_index: int = 0,
    duration: EffectDuration = EffectDuration.END_OF_TURN,
) -> ContinuousEffect:
    """Create and register a Draconic cost reduction with limited uses."""
    effect = make_cost_modifier(
        amount,
        controller_index,
        duration=duration,
        target_filter=lambda c: SuperType.DRACONIC in getattr(
            c, '_resolved_supertypes', c.definition.supertypes
        ),
    )
    effect.uses_remaining = uses
    effect_engine.add_continuous_effect(state, effect)
    return effect


# ---------------------------------------------------------------------------
# EffectEngine.consume_limited_cost_effects — unit tests
# ---------------------------------------------------------------------------


class TestConsumeLimitedCostEffects:
    """Unit tests for consume_limited_cost_effects on EffectEngine."""

    def test_decrement_on_matching_card(self):
        """A Draconic card should decrement uses_remaining by 1."""
        state = make_state()
        ee = EffectEngine()
        effect = _make_draconic_cost_reduction(ee, state, uses=3)

        draconic = make_draconic_attack(instance_id=1, cost=2)
        ee.consume_limited_cost_effects(state, draconic)

        assert effect.uses_remaining == 2
        assert len(state.continuous_effects) == 1

    def test_non_draconic_does_not_consume(self):
        """A non-Draconic card should NOT decrement uses_remaining."""
        state = make_state()
        ee = EffectEngine()
        effect = _make_draconic_cost_reduction(ee, state, uses=3)

        ninja = make_ninja_attack(instance_id=2, cost=1)
        ee.consume_limited_cost_effects(state, ninja)

        assert effect.uses_remaining == 3
        assert len(state.continuous_effects) == 1

    def test_removed_when_uses_reach_zero(self):
        """Effect should be removed when uses_remaining reaches 0."""
        state = make_state()
        ee = EffectEngine()
        _make_draconic_cost_reduction(ee, state, uses=1)

        draconic = make_draconic_attack(instance_id=1, cost=2)
        ee.consume_limited_cost_effects(state, draconic)

        assert len(state.continuous_effects) == 0

    def test_unlimited_effect_not_consumed(self):
        """Effects with uses_remaining=None should not be consumed."""
        state = make_state()
        ee = EffectEngine()
        effect = make_cost_modifier(
            -1, 0,
            target_filter=lambda c: SuperType.DRACONIC in getattr(
                c, '_resolved_supertypes', c.definition.supertypes
            ),
        )
        # uses_remaining defaults to None (unlimited)
        ee.add_continuous_effect(state, effect)

        draconic = make_draconic_attack(instance_id=1, cost=2)
        ee.consume_limited_cost_effects(state, draconic)

        # Should still be there — unlimited
        assert len(state.continuous_effects) == 1
        assert effect.uses_remaining is None

    def test_cost_still_reduced_on_last_use(self):
        """The Nth card (last use) should still get the cost reduction."""
        state = make_state()
        ee = EffectEngine()
        _make_draconic_cost_reduction(ee, state, uses=1)

        draconic = make_draconic_attack(instance_id=1, cost=3)
        # Cost should be reduced BEFORE consume is called
        modified_cost = ee.get_modified_cost(state, draconic)
        assert modified_cost == 2  # 3 - 1

        # Now consume — effect removed
        ee.consume_limited_cost_effects(state, draconic)
        assert len(state.continuous_effects) == 0

        # Next draconic card should NOT get reduction
        draconic2 = make_draconic_attack(instance_id=2, cost=3)
        assert ee.get_modified_cost(state, draconic2) == 3


# ---------------------------------------------------------------------------
# Art of the Dragon: Blood — integration with ability handler
# ---------------------------------------------------------------------------


class TestArtOfTheDragonBloodCounter:
    """Art of the Dragon: Blood sets uses_remaining=3 on its cost effect."""

    def _setup_blood_effect(self):
        """Trigger Art of the Dragon: Blood and return (game, effect)."""
        game = make_game_shell()
        state = game.state

        # Create a Draconic Ninja attack as Art of the Dragon: Blood
        blood = make_draconic_ninja_attack(
            instance_id=1, name="Art of the Dragon: Blood", cost=0
        )
        blood.zone = game.state.players[0].hand[0].zone if state.players[0].hand else None

        # Open combat chain and set up a chain link with a Draconic attack
        game.combat_mgr.open_chain(state)
        from htc.state.combat_state import ChainLink
        link = ChainLink(
            link_number=1,
            attack_target_index=1,
            active_attack=blood,
        )
        state.combat_chain.chain_links.append(link)

        # Build ability context and call the handler
        from tests.abilities.conftest import make_ability_context
        ctx = make_ability_context(game, blood, 0, chain_link=link, ask=lambda d: None)

        from htc.cards.abilities.ninja import _art_of_the_dragon_blood_on_attack
        _art_of_the_dragon_blood_on_attack(ctx)

        # Find the cost effect (not the Go Again keyword effect)
        cost_effects = [
            e for e in state.continuous_effects
            if e.numeric_property == NumericProperty.COST
        ]
        assert len(cost_effects) == 1
        return game, cost_effects[0]

    def test_blood_sets_uses_remaining_3(self):
        """Art of the Dragon: Blood should set uses_remaining=3."""
        _, effect = self._setup_blood_effect()
        assert effect.uses_remaining == 3

    def test_blood_exhausted_after_3_draconic_cards(self):
        """After 3 Draconic cards, the cost reduction should be gone."""
        game, _ = self._setup_blood_effect()
        state = game.state
        ee = game.effect_engine

        for i in range(3):
            card = make_draconic_attack(instance_id=100 + i, cost=2)
            ee.consume_limited_cost_effects(state, card)

        cost_effects = [
            e for e in state.continuous_effects
            if e.numeric_property == NumericProperty.COST
        ]
        assert len(cost_effects) == 0

    def test_blood_still_active_after_2_draconic_cards(self):
        """After 2 Draconic cards, 1 use should remain."""
        game, effect = self._setup_blood_effect()
        state = game.state
        ee = game.effect_engine

        for i in range(2):
            card = make_draconic_attack(instance_id=100 + i, cost=2)
            ee.consume_limited_cost_effects(state, card)

        assert effect.uses_remaining == 1
        # Verify the reduction still applies
        next_card = make_draconic_attack(instance_id=200, cost=3)
        assert ee.get_modified_cost(state, next_card) == 2

    def test_blood_non_draconic_doesnt_consume(self):
        """Non-Draconic cards should not consume Blood uses."""
        game, effect = self._setup_blood_effect()
        state = game.state
        ee = game.effect_engine

        ninja = make_ninja_attack(instance_id=100, cost=2)
        ee.consume_limited_cost_effects(state, ninja)

        assert effect.uses_remaining == 3

    def test_blood_4th_draconic_card_no_reduction(self):
        """The 4th Draconic card should NOT get a cost reduction."""
        game, _ = self._setup_blood_effect()
        state = game.state
        ee = game.effect_engine

        # Consume all 3 uses
        for i in range(3):
            card = make_draconic_attack(instance_id=100 + i, cost=2)
            ee.consume_limited_cost_effects(state, card)

        # 4th card: no reduction
        fourth = make_draconic_attack(instance_id=200, cost=3)
        assert ee.get_modified_cost(state, fourth) == 3


# ---------------------------------------------------------------------------
# Ignite — integration with ability handler
# ---------------------------------------------------------------------------


class TestIgniteCounter:
    """Ignite sets uses_remaining=1 on its cost effect."""

    def _setup_ignite_effect(self):
        """Trigger Ignite and return (game, effect)."""
        game = make_game_shell()
        state = game.state

        ignite = make_draconic_ninja_attack(
            instance_id=1, name="Ignite", cost=0
        )

        game.combat_mgr.open_chain(state)
        from htc.state.combat_state import ChainLink
        link = ChainLink(
            link_number=1,
            attack_target_index=1,
            active_attack=ignite,
        )
        state.combat_chain.chain_links.append(link)

        ctx = make_ability_context(game, ignite, 0, chain_link=link, ask=lambda d: None)

        from htc.cards.abilities.ninja import _ignite_on_attack
        _ignite_on_attack(ctx)

        cost_effects = [
            e for e in state.continuous_effects
            if e.numeric_property == NumericProperty.COST
        ]
        assert len(cost_effects) == 1
        return game, cost_effects[0]

    def test_ignite_sets_uses_remaining_1(self):
        """Ignite should set uses_remaining=1."""
        _, effect = self._setup_ignite_effect()
        assert effect.uses_remaining == 1

    def test_ignite_exhausted_after_1_draconic_card(self):
        """After 1 Draconic card, the cost reduction should be gone."""
        game, _ = self._setup_ignite_effect()
        state = game.state
        ee = game.effect_engine

        card = make_draconic_attack(instance_id=100, cost=2)
        ee.consume_limited_cost_effects(state, card)

        cost_effects = [
            e for e in state.continuous_effects
            if e.numeric_property == NumericProperty.COST
        ]
        assert len(cost_effects) == 0

    def test_ignite_2nd_draconic_card_no_reduction(self):
        """After consuming, the 2nd Draconic card should NOT get reduction."""
        game, _ = self._setup_ignite_effect()
        state = game.state
        ee = game.effect_engine

        first = make_draconic_attack(instance_id=100, cost=2)
        ee.consume_limited_cost_effects(state, first)

        second = make_draconic_attack(instance_id=101, cost=3)
        assert ee.get_modified_cost(state, second) == 3

    def test_ignite_non_draconic_doesnt_consume(self):
        """Non-Draconic cards should not consume Ignite uses."""
        game, effect = self._setup_ignite_effect()
        state = game.state
        ee = game.effect_engine

        ninja = make_ninja_attack(instance_id=100, cost=2)
        ee.consume_limited_cost_effects(state, ninja)

        assert effect.uses_remaining == 1
        # Draconic card should still get reduction
        draconic = make_draconic_attack(instance_id=101, cost=3)
        assert ee.get_modified_cost(state, draconic) == 2
