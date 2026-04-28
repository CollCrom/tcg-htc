"""Scenario: Fealty token economy — creation, activation, Draconic grant, survival.

Verifies:
1. Activating Fealty (destroy) grants Draconic supertype to next card played.
2. Draconic tracking sees effect-granted supertypes (not just definition).
3. Fealty tokens survive end-phase if a Fealty was created this turn.
4. Fealty tokens survive end-phase if a Draconic card was played this turn.
5. Fealty tokens are destroyed at end-phase if neither condition is met.
"""

from __future__ import annotations

from engine.cards.card import CardDefinition
from engine.cards.instance import CardInstance
from engine.cards.abilities.tokens import (
    FealtyEndPhaseTrigger,
    _fealty_instant,
    register_token_triggers,
)
from engine.rules.continuous import EffectDuration, make_supertype_grant
from engine.rules.events import EventType, GameEvent
from engine.enums import (
    CardType,
    Color,
    EquipmentSlot,
    SubType,
    SuperType,
    Zone,
)
from tests.conftest import make_game_shell
from tests.abilities.conftest import (
    make_ability_context,
    make_ninja_attack,
    make_draconic_ninja_attack,
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

def _make_fealty_token(instance_id: int = 500, owner_index: int = 0) -> CardInstance:
    """Create a Fealty token on the battlefield."""
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
        functional_text=(
            "Instant - Destroy this: The next card you play this turn is Draconic. "
            "At the beginning of your end phase, if you haven't created a Fealty "
            "token or played a Draconic card this turn, destroy this."
        ),
        type_text="Draconic Aura Token",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.PERMANENT,
    )

def _setup_fealty_test():
    """Set up game with Fealty token on the battlefield.

    Returns (game, fealty_token).
    """
    game = make_game_shell()
    state = game.state

    hero = _make_hero(instance_id=900, owner_index=0)
    state.players[0].hero = hero
    state.players[0].life_total = 20

    opp_hero = _make_hero(name="Opponent", instance_id=901, owner_index=1)
    state.players[1].hero = opp_hero
    state.players[1].life_total = 20

    fealty = _make_fealty_token(instance_id=500, owner_index=0)
    state.players[0].permanents.append(fealty)

    # Register Fealty end-phase trigger
    register_token_triggers(
        event_bus=game.events,
        effect_engine=game.effect_engine,
        state=state,
        controller_index=0,
        token=fealty,
    )

    return game, fealty

# ---------------------------------------------------------------------------
# Tests: Fealty activation grants Draconic
# ---------------------------------------------------------------------------

class TestFealtyActivation:
    """Activating Fealty destroys the token and grants Draconic to next card."""

    def test_fealty_instant_destroys_token(self, scenario_recorder):
        """Activating Fealty should remove it from permanents."""
        game, fealty = _setup_fealty_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        assert fealty in state.players[0].permanents

        ctx = make_ability_context(game, fealty, controller_index=0)
        _fealty_instant(ctx)

        assert fealty not in state.players[0].permanents, (
            "Fealty should be removed from permanents after activation"
        )
        assert fealty.zone == Zone.GRAVEYARD, (
            "Fealty should move to graveyard after activation"
        )

    def test_fealty_instant_grants_draconic_supertype(self, scenario_recorder):
        """After Fealty activation, the next card played should gain Draconic supertype.

        The Draconic grant is a continuous effect. We verify the effect engine
        sees the granted supertype on a non-Draconic attack card.
        """
        game, fealty = _setup_fealty_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        ctx = make_ability_context(game, fealty, controller_index=0)
        _fealty_instant(ctx)

        # Create a plain Ninja attack (not Draconic by definition)
        atk = make_ninja_attack(instance_id=10, name="Plain Strike", owner_index=0)
        atk.zone = Zone.COMBAT_CHAIN  # simulate being played

        # The effect engine should now see Draconic on this card
        modified_supertypes = game.effect_engine.get_modified_supertypes(state, atk)

        assert SuperType.DRACONIC in modified_supertypes, (
            "Fealty activation should grant Draconic supertype to next card on chain"
        )

    def test_fealty_draconic_grant_is_once_only(self, scenario_recorder):
        """Fealty's Draconic grant should only apply to the first matching card.

        After the first card gets Draconic, a second card should not.
        """
        game, fealty = _setup_fealty_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        ctx = make_ability_context(game, fealty, controller_index=0)
        _fealty_instant(ctx)

        # First card — should get Draconic
        atk1 = make_ninja_attack(instance_id=10, name="First Strike", owner_index=0)
        atk1.zone = Zone.COMBAT_CHAIN

        supertypes1 = game.effect_engine.get_modified_supertypes(state, atk1)
        assert SuperType.DRACONIC in supertypes1

        # Second card — should NOT get Draconic (once filter consumed)
        atk2 = make_ninja_attack(instance_id=11, name="Second Strike", owner_index=0)
        atk2.zone = Zone.COMBAT_CHAIN

        supertypes2 = game.effect_engine.get_modified_supertypes(state, atk2)

        assert SuperType.DRACONIC not in supertypes2, (
            "Fealty's Draconic grant should only apply once"
        )

# ---------------------------------------------------------------------------
# Tests: Fealty end-phase survival
# ---------------------------------------------------------------------------

class TestFealtyEndPhaseSurvival:
    """Fealty token end-phase conditional self-destruct."""

    def test_fealty_survives_if_fealty_created_this_turn(self, scenario_recorder):
        """Fealty should NOT be destroyed if a Fealty token was created this turn."""
        game, fealty = _setup_fealty_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        # Mark that a Fealty was created this turn
        state.players[0].turn_counters.fealty_created_this_turn = True

        # Emit END_OF_TURN for player 0
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))

        assert fealty in state.players[0].permanents, (
            "Fealty should survive end-phase when fealty_created_this_turn is True"
        )
        assert fealty.zone == Zone.PERMANENT, (
            "Fealty should remain in PERMANENT zone"
        )

    def test_fealty_survives_if_draconic_card_played_this_turn(self, scenario_recorder):
        """Fealty should NOT be destroyed if a Draconic card was played this turn."""
        game, fealty = _setup_fealty_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        state.players[0].turn_counters.draconic_card_played_this_turn = True

        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))

        assert fealty in state.players[0].permanents, (
            "Fealty should survive end-phase when draconic_card_played_this_turn is True"
        )

    def test_fealty_destroyed_if_neither_condition_met(self, scenario_recorder):
        """Fealty should be destroyed if no Fealty created AND no Draconic played."""
        game, fealty = _setup_fealty_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        # Neither condition set (defaults are False)
        assert not state.players[0].turn_counters.fealty_created_this_turn
        assert not state.players[0].turn_counters.draconic_card_played_this_turn

        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))

        assert fealty not in state.players[0].permanents, (
            "Fealty should be destroyed at end-phase when neither condition is met"
        )
        assert fealty.zone == Zone.GRAVEYARD, (
            "Destroyed Fealty should be in graveyard"
        )

    def test_fealty_not_destroyed_on_opponents_end_of_turn(self, scenario_recorder):
        """Fealty end-phase trigger should only fire on controller's end of turn."""
        game, fealty = _setup_fealty_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        # Neither condition met, but it's the OPPONENT's end of turn
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=1,  # opponent
        ))

        assert fealty in state.players[0].permanents, (
            "Fealty should not self-destruct on opponent's end of turn"
        )

    def test_multiple_fealty_tokens_all_survive_if_condition_met(self, scenario_recorder):
        """Multiple Fealty tokens should all survive if condition is met."""
        game, fealty1 = _setup_fealty_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        # Add a second Fealty token
        fealty2 = _make_fealty_token(instance_id=501, owner_index=0)
        state.players[0].permanents.append(fealty2)
        register_token_triggers(
            event_bus=game.events,
            effect_engine=game.effect_engine,
            state=state,
            controller_index=0,
            token=fealty2,
        )

        state.players[0].turn_counters.fealty_created_this_turn = True

        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))

        assert fealty1 in state.players[0].permanents
        assert fealty2 in state.players[0].permanents

    def test_multiple_fealty_tokens_all_destroyed_if_no_condition(self, scenario_recorder):
        """Multiple Fealty tokens should all be destroyed when neither condition met."""
        game, fealty1 = _setup_fealty_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        fealty2 = _make_fealty_token(instance_id=501, owner_index=0)
        state.players[0].permanents.append(fealty2)
        register_token_triggers(
            event_bus=game.events,
            effect_engine=game.effect_engine,
            state=state,
            controller_index=0,
            token=fealty2,
        )

        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))

        assert fealty1 not in state.players[0].permanents
        assert fealty2 not in state.players[0].permanents
