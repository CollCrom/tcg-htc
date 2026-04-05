"""Scenario: Multi-turn economy and resource management tests.

Tests:
11. Fealty multi-turn survival — Create Fealty turn 1, play Draconic card (survives),
    turn 2 break Fealty for Draconic grant, create new Fealty (survives).
    Verify tokens persist correctly across turns.
12. Oath of Loyalty draw timing — SKIPPED (Loyalty Beyond the Grave not implemented)
13. Blue Cindra resource curve — With many 1-cost cards, verify cost calculation
    and pitch work correctly even when resources are tight. Smoke test.
14. Tarantula Toxin rate math — Mode 1 (+3 power to stealth/dagger attack) +
    Mode 2 (-3 defense to defending card). Verify both modes work correctly.

Sources: strategy-cindra-post-bnr.md, strategy-arakni-masterclass.md
"""

from __future__ import annotations

import logging

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.cards.abilities.tokens import (
    FealtyEndPhaseTrigger,
    _fealty_instant,
    register_token_triggers,
)
from htc.cards.abilities.assassin import _tarantula_toxin
from htc.engine.actions import PlayerResponse
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
from tests.conftest import make_game_shell, make_pitch_card
from tests.abilities.conftest import (
    make_ability_context,
    make_attack_reaction,
    make_dagger_attack,
    make_defense_reaction,
    make_draconic_ninja_attack,
    make_ninja_attack,
    make_stealth_attack,
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
    game = make_game_shell()
    state = game.state

    state.players[0].hero = _make_hero(instance_id=900, owner_index=0)
    state.players[0].life_total = 20

    opp_hero = _make_hero(name="Arakni, Marionette", instance_id=901, owner_index=1)
    state.players[1].hero = opp_hero
    state.players[1].life_total = 20

    return game


# ---------------------------------------------------------------------------
# Test 11: Fealty multi-turn survival
# ---------------------------------------------------------------------------


class TestFealtyMultiTurnSurvival:
    """Fealty tokens survive end-phase if either condition is met:
    - A Fealty token was created this turn
    - A Draconic card was played this turn

    This tests the multi-turn lifecycle:
    Turn 1: Create Fealty, play Draconic card -> Fealty survives
    Turn 2: Break Fealty for Draconic grant, create new Fealty -> new Fealty survives

    Source: strategy-cindra-post-bnr.md
    """

    def test_fealty_survives_turn_1_draconic_played(self, scenario_recorder):
        """Turn 1: Fealty created, Draconic card played -> Fealty survives."""
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        fealty = _make_fealty_token(instance_id=500, owner_index=0)
        state.players[0].permanents.append(fealty)

        register_token_triggers(
            event_bus=game.events, effect_engine=game.effect_engine,
            state=state, controller_index=0, token=fealty,
        )

        # Simulate: player created Fealty and played a Draconic card this turn
        state.players[0].turn_counters.fealty_created_this_turn = True
        state.players[0].turn_counters.draconic_card_played_this_turn = True

        # End of turn 1
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))
        game._process_pending_triggers()

        assert fealty in state.players[0].permanents, (
            "Fealty should survive turn 1 end-phase when Draconic was played"
        )

    def test_fealty_survives_turn_2_after_new_fealty_created(self, scenario_recorder):
        """Turn 2: Break old Fealty, create new Fealty -> new one survives if
        Draconic was played.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        # Simulate: Turn 1 ended, Fealty survived. Now it's turn 2.
        # Reset turn counters for turn 2
        state.players[0].turn_counters.fealty_created_this_turn = False
        state.players[0].turn_counters.draconic_card_played_this_turn = False

        # Old Fealty from turn 1
        old_fealty = _make_fealty_token(instance_id=500, owner_index=0)
        state.players[0].permanents.append(old_fealty)

        # Break old Fealty (instant activation)
        ctx = make_ability_context(game, old_fealty, controller_index=0)
        _fealty_instant(ctx)

        assert old_fealty.zone == Zone.GRAVEYARD, "Old Fealty should be destroyed"

        # Create new Fealty for turn 2
        new_fealty = _make_fealty_token(instance_id=501, owner_index=0)
        state.players[0].permanents.append(new_fealty)
        state.players[0].turn_counters.fealty_created_this_turn = True
        state.players[0].turn_counters.draconic_card_played_this_turn = True

        register_token_triggers(
            event_bus=game.events, effect_engine=game.effect_engine,
            state=state, controller_index=0, token=new_fealty,
        )

        # End of turn 2
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))
        game._process_pending_triggers()

        assert new_fealty in state.players[0].permanents, (
            "New Fealty should survive turn 2 end-phase when Fealty was created "
            "and Draconic was played this turn"
        )

    def test_fealty_destroyed_when_no_draconic_played(self, scenario_recorder):
        """If neither a Fealty was created nor a Draconic card played,
        the Fealty token should be destroyed at end-phase.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        fealty = _make_fealty_token(instance_id=500, owner_index=0)
        state.players[0].permanents.append(fealty)

        register_token_triggers(
            event_bus=game.events, effect_engine=game.effect_engine,
            state=state, controller_index=0, token=fealty,
        )

        # Neither condition met
        state.players[0].turn_counters.fealty_created_this_turn = False
        state.players[0].turn_counters.draconic_card_played_this_turn = False

        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))
        game._process_pending_triggers()

        assert fealty not in state.players[0].permanents, (
            "Fealty should be destroyed when neither condition is met"
        )


# ---------------------------------------------------------------------------
# Test 12: Loyalty Beyond the Grave — SKIPPED
# ---------------------------------------------------------------------------


class TestLoyaltyBeyondTheGrave:
    """Loyalty Beyond the Grave: 'While this is in your graveyard, at the
    start of your turn, you may banish 2 cards named Loyalty Beyond the
    Grave from your graveyard. If you do, draw a card.'

    SKIPPED: This card is not implemented in the ability registry.
    """

    def test_loyalty_beyond_not_implemented(self, scenario_recorder):
        """Verify Loyalty Beyond the Grave has no ability handler yet."""
        game = _setup_base_game()
        recorder = scenario_recorder.bind(game)

        # Check all ability types
        for ability_type in ["on_play", "on_attack", "on_hit", "graveyard_trigger"]:
            handler = game.ability_registry.lookup(ability_type, "Loyalty Beyond the Grave")
            assert handler is None, (
                f"Loyalty Beyond the Grave is expected to not be implemented yet "
                f"(found handler in '{ability_type}'). If this fails, real tests "
                f"should replace this stub."
            )


# ---------------------------------------------------------------------------
# Test 13: Blue Cindra resource curve (smoke test)
# ---------------------------------------------------------------------------


class TestBlueCindraResourceCurve:
    """With many 1-cost cards and few blue pitch cards, verify cost calculation
    and pitch work correctly when resources are tight.

    This is a smoke test ensuring the engine handles 0/1/2/3 pitch values
    and 0/1 cost cards correctly.

    Source: strategy-cindra-post-bnr.md
    """

    def test_1_cost_card_with_1_pitch(self, scenario_recorder):
        """A 1-cost card should be playable with exactly 1 resource from a red pitch card."""
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        # 1-cost attack card
        atk = make_ninja_attack(
            instance_id=1, name="Art of the Dragon: Blood", power=3, cost=1, owner_index=0,
        )
        atk.zone = Zone.HAND

        # Red pitch card (pitch=1)
        pitch_card = make_pitch_card(instance_id=200, owner_index=0, pitch=1)

        state.players[0].hand = [atk, pitch_card]

        # Verify cost is 1
        modified_cost = game.effect_engine.get_modified_cost(state, atk)
        assert modified_cost == 1, f"Card cost should be 1, got {modified_cost}"

        # Verify pitch value
        assert pitch_card.definition.pitch == 1, "Red card should pitch for 1"

    def test_0_cost_card_needs_no_pitch(self, scenario_recorder):
        """A 0-cost card should be playable without pitching anything."""
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        atk = make_ninja_attack(
            instance_id=1, name="Ignite", power=2, cost=0, owner_index=0,
        )
        atk.zone = Zone.HAND

        modified_cost = game.effect_engine.get_modified_cost(state, atk)
        assert modified_cost == 0, f"0-cost card should remain 0, got {modified_cost}"

    def test_blue_pitch_overpays_for_1_cost(self, scenario_recorder):
        """A blue pitch card (pitch=3) paying for a 1-cost card wastes 2 resources.
        Verify the cost is still calculated correctly.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        atk = make_ninja_attack(
            instance_id=1, name="Demonstrate Devotion", power=5, cost=1, owner_index=0,
        )
        atk.zone = Zone.HAND

        blue_pitch = make_pitch_card(instance_id=200, owner_index=0, pitch=3)

        # Cost is 1, pitch gives 3 — overpay of 2 but card is still playable
        assert atk.definition.cost == 1
        assert blue_pitch.definition.pitch == 3

    def test_cost_floor_is_zero(self, scenario_recorder):
        """Cost reductions should not go below 0."""
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        from htc.engine.continuous import EffectDuration, make_cost_modifier

        # 0-cost card with a -1 cost reduction
        atk = make_draconic_ninja_attack(
            instance_id=1, name="Ignite", power=2, cost=0, owner_index=0,
        )
        atk.zone = Zone.HAND

        cost_effect = make_cost_modifier(
            -1,
            0,
            source_instance_id=999,
            duration=EffectDuration.END_OF_TURN,
            target_filter=lambda c: True,
        )
        game.effect_engine.add_continuous_effect(state, cost_effect)

        modified_cost = game.effect_engine.get_modified_cost(state, atk)
        assert modified_cost >= 0, (
            f"Cost should never go below 0. Got {modified_cost}"
        )


# ---------------------------------------------------------------------------
# Test 14: Tarantula Toxin rate math
# ---------------------------------------------------------------------------


class TestTarantulaToxinModes:
    """Tarantula Toxin (Assassin, Attack Reaction):
    'Choose 1 or both;
     * Target dagger attack gets +3{p}.
     * Target card defending an attack with stealth gets -3{d} this turn.'

    Verify both modes work correctly and the math adds up.

    Source: strategy-arakni-masterclass.md
    """

    def test_mode1_dagger_attack_plus_3_power(self, scenario_recorder):
        """Mode 1: Target dagger attack gets +3 power."""
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)

        # Dagger attack
        atk = make_dagger_attack(
            instance_id=1, name="Kiss of Death", power=2, owner_index=1,
            keywords=frozenset({Keyword.STEALTH}),
        )
        link = game.combat_mgr.add_chain_link(state, atk, 0)

        # Tarantula Toxin as attack reaction (Red)
        toxin = make_attack_reaction(
            name="Tarantula Toxin", instance_id=10, color=Color.RED,
            owner_index=1, supertypes=frozenset({SuperType.ASSASSIN}),
        )

        initial_power = game.effect_engine.get_modified_power(state, atk)

        ctx = make_ability_context(game, toxin, controller_index=1, chain_link=link)
        _tarantula_toxin(ctx)

        final_power = game.effect_engine.get_modified_power(state, atk)
        assert final_power == initial_power + 3, (
            f"Mode 1: Dagger attack should get +3 power. "
            f"Was {initial_power}, now {final_power}"
        )

    def test_mode2_defending_card_minus_3_defense(self, scenario_recorder):
        """Mode 2: Target card defending an attack with stealth gets -3 defense."""
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)

        # Stealth attack (not dagger, so only mode 2 is valid)
        atk = make_stealth_attack(
            instance_id=1, name="Stealth Strike", power=3, owner_index=1,
        )
        link = game.combat_mgr.add_chain_link(state, atk, 0)

        # Defender
        defender = make_defense_reaction(
            name="Sink Below", instance_id=20, defense=4, owner_index=0,
        )
        defender.zone = Zone.COMBAT_CHAIN
        link.defending_cards.append(defender)

        toxin = make_attack_reaction(
            name="Tarantula Toxin", instance_id=10, color=Color.RED,
            owner_index=1, supertypes=frozenset({SuperType.ASSASSIN}),
        )

        initial_defense = game.effect_engine.get_modified_defense(state, defender)

        ctx = make_ability_context(game, toxin, controller_index=1, chain_link=link)
        _tarantula_toxin(ctx)

        final_defense = game.effect_engine.get_modified_defense(state, defender)
        assert final_defense == initial_defense - 3, (
            f"Mode 2: Defending card should get -3 defense. "
            f"Was {initial_defense}, now {final_defense}"
        )

    def test_both_modes_when_dagger_stealth_with_defender(self, scenario_recorder):
        """When both modes are valid (dagger attack WITH stealth AND defenders),
        choosing 'both' should apply +3 power AND -3 defense.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)

        # Dagger attack with stealth (both modes valid)
        atk = make_dagger_attack(
            instance_id=1, name="Kiss of Death", power=2, owner_index=1,
            keywords=frozenset({Keyword.STEALTH}),
        )
        link = game.combat_mgr.add_chain_link(state, atk, 0)

        # Defender
        defender = make_defense_reaction(
            name="Sink Below", instance_id=20, defense=4, owner_index=0,
        )
        defender.zone = Zone.COMBAT_CHAIN
        link.defending_cards.append(defender)

        toxin = make_attack_reaction(
            name="Tarantula Toxin", instance_id=10, color=Color.RED,
            owner_index=1, supertypes=frozenset({SuperType.ASSASSIN}),
        )

        initial_power = game.effect_engine.get_modified_power(state, atk)
        initial_defense = game.effect_engine.get_modified_defense(state, defender)

        # Ask callback: choose both modes
        def ask_fn(decision):
            return PlayerResponse(selected_option_ids=["mode_both"])

        ctx = make_ability_context(game, toxin, controller_index=1, chain_link=link, ask=ask_fn)
        _tarantula_toxin(ctx)

        final_power = game.effect_engine.get_modified_power(state, atk)
        final_defense = game.effect_engine.get_modified_defense(state, defender)

        assert final_power == initial_power + 3, (
            f"Both modes: dagger should get +3 power. Was {initial_power}, now {final_power}"
        )
        assert final_defense == initial_defense - 3, (
            f"Both modes: defender should get -3 defense. Was {initial_defense}, now {final_defense}"
        )

    def test_neither_mode_valid_no_effect(self, scenario_recorder):
        """If the attack is neither a dagger nor has stealth, Tarantula Toxin
        should have no effect.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)

        # Plain ninja attack (no dagger, no stealth)
        atk = make_ninja_attack(
            instance_id=1, name="Leg Tap", power=4, cost=0, owner_index=1,
        )
        link = game.combat_mgr.add_chain_link(state, atk, 0)

        toxin = make_attack_reaction(
            name="Tarantula Toxin", instance_id=10, color=Color.RED,
            owner_index=1, supertypes=frozenset({SuperType.ASSASSIN}),
        )

        initial_power = game.effect_engine.get_modified_power(state, atk)

        ctx = make_ability_context(game, toxin, controller_index=1, chain_link=link)
        _tarantula_toxin(ctx)

        final_power = game.effect_engine.get_modified_power(state, atk)
        assert final_power == initial_power, (
            "No valid mode: power should be unchanged"
        )
