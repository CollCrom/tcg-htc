"""Tests for Phase 6 token abilities.

Tests all 7 tokens used by the Cindra and Arakni decks:
- Ponder: end-phase draw
- Frailty: -1 power continuous + end-phase destroy
- Inertia: end-phase hand/arsenal to deck bottom
- Bloodrot Pox: end-phase 2 damage or pay 3
- Fealty: instant Draconic grant + conditional end-phase destroy
- Silver: action activation (pay 3, draw, go again)
- Graphene Chelicera: weapon token (1 power, 1 cost, go again)
"""

from __future__ import annotations

import unittest

from htc.cards.abilities._helpers import create_token
from htc.cards.abilities.tokens import (
    BloodrotPoxEndPhaseTrigger,
    FealtyEndPhaseTrigger,
    FrailtyEndPhaseTrigger,
    InertiaEndPhaseTrigger,
    PonderEndPhaseTrigger,
    register_frailty_continuous_effect,
    register_token_triggers,
)
from htc.engine.actions import PlayerResponse
from htc.engine.events import EventType, GameEvent
from htc.enums import CardType, Keyword, SubType, SuperType, Zone
from tests.abilities.conftest import make_dagger_weapon, make_weapon_proxy
from tests.conftest import make_card, make_game_shell, make_mock_ask, make_pitch_card


def _emit_end_of_turn(game, player_index: int) -> None:
    """Emit END_OF_TURN for the given player and process triggers."""
    game.events.emit(GameEvent(
        event_type=EventType.END_OF_TURN,
        target_player=player_index,
    ))
    game._process_pending_triggers()


# ---------------------------------------------------------------------------
# Ponder
# ---------------------------------------------------------------------------


class TestPonderToken(unittest.TestCase):
    """Ponder: At end of turn, destroy and draw a card."""

    def test_end_phase_draw(self):
        """Ponder draws a card at end of turn."""
        game = make_game_shell()
        p0 = game.state.players[0]
        p0.deck.append(make_card(instance_id=300, name="Top Card"))

        token = create_token(
            game.state, 0, "Ponder", SubType.AURA,
            functional_text="At the beginning of your end phase, destroy Ponder and draw a card.",
            type_text="Token - Aura",
            event_bus=game.events, effect_engine=game.effect_engine,
        )

        assert len(p0.permanents) == 1
        hand_before = len(p0.hand)
        _emit_end_of_turn(game, 0)

        # Token should be destroyed and card drawn
        assert len(p0.permanents) == 0
        assert len(p0.hand) == hand_before + 1

    def test_no_trigger_for_other_player(self):
        """Ponder only triggers on its controller's end of turn."""
        game = make_game_shell()
        p0 = game.state.players[0]
        p0.deck.append(make_card(instance_id=300, name="Top Card"))

        create_token(
            game.state, 0, "Ponder", SubType.AURA,
            event_bus=game.events, effect_engine=game.effect_engine,
        )

        hand_before = len(p0.hand)
        _emit_end_of_turn(game, 1)  # Other player's end of turn

        # Token should still exist, no draw
        assert len(p0.permanents) == 1
        assert len(p0.hand) == hand_before

    def test_empty_deck_no_crash(self):
        """Ponder with empty deck: token destroyed, no draw."""
        game = make_game_shell()
        p0 = game.state.players[0]
        p0.deck.clear()

        create_token(
            game.state, 0, "Ponder", SubType.AURA,
            event_bus=game.events, effect_engine=game.effect_engine,
        )

        _emit_end_of_turn(game, 0)
        assert len(p0.permanents) == 0


# ---------------------------------------------------------------------------
# Frailty
# ---------------------------------------------------------------------------


class TestFrailtyToken(unittest.TestCase):
    """Frailty: -1 power to attack actions and weapon attacks. Destroy at end of turn."""

    def test_continuous_debuff_on_attack_action_from_arsenal(self):
        """Frailty gives -1 power to attack action cards played from arsenal."""
        game = make_game_shell()

        token = create_token(
            game.state, 0, "Frailty", SubType.AURA,
            functional_text="Your attack action cards played from arsenal and weapon attacks have -1{p}.",
            event_bus=game.events, effect_engine=game.effect_engine,
        )

        # Create an attack action card played from arsenal
        attack = make_card(instance_id=1, name="Test Attack", power=3, is_attack=True)
        attack.owner_index = 0
        attack.played_from_zone = Zone.ARSENAL

        # Check modified power
        modified_power = game.effect_engine.get_modified_power(game.state, attack)
        assert modified_power == 2  # 3 - 1

    def test_no_debuff_on_attack_from_hand(self):
        """Frailty does NOT debuff attack action cards played from hand."""
        game = make_game_shell()

        create_token(
            game.state, 0, "Frailty", SubType.AURA,
            functional_text="Your attack action cards played from arsenal and weapon attacks have -1{p}.",
            event_bus=game.events, effect_engine=game.effect_engine,
        )

        attack = make_card(instance_id=1, name="Test Attack", power=3, is_attack=True)
        attack.owner_index = 0
        attack.played_from_zone = Zone.HAND

        modified_power = game.effect_engine.get_modified_power(game.state, attack)
        assert modified_power == 3  # No debuff from hand

    def test_continuous_debuff_on_weapon_proxy(self):
        """Frailty gives -1 power to weapon proxy attacks."""
        game = make_game_shell()

        create_token(
            game.state, 0, "Frailty", SubType.AURA,
            event_bus=game.events, effect_engine=game.effect_engine,
        )

        # Create a weapon proxy (simulates weapon attack)
        dagger = make_dagger_weapon(instance_id=49)
        proxy = make_weapon_proxy(dagger, instance_id=50)

        modified_power = game.effect_engine.get_modified_power(game.state, proxy)
        assert modified_power == 0  # 1 - 1

    def test_no_debuff_on_opponent(self):
        """Frailty does not affect opponent's attacks."""
        game = make_game_shell()

        create_token(
            game.state, 0, "Frailty", SubType.AURA,
            event_bus=game.events, effect_engine=game.effect_engine,
        )

        attack = make_card(instance_id=1, power=3, is_attack=True, owner_index=1)
        modified_power = game.effect_engine.get_modified_power(game.state, attack)
        assert modified_power == 3  # No debuff

    def test_end_phase_destroy(self):
        """Frailty is destroyed at end of turn."""
        game = make_game_shell()

        create_token(
            game.state, 0, "Frailty", SubType.AURA,
            event_bus=game.events, effect_engine=game.effect_engine,
        )
        assert len(game.state.players[0].permanents) == 1

        _emit_end_of_turn(game, 0)
        assert len(game.state.players[0].permanents) == 0

    def test_debuff_removed_after_destroy(self):
        """After Frailty is destroyed, debuff no longer applies."""
        game = make_game_shell()

        create_token(
            game.state, 0, "Frailty", SubType.AURA,
            event_bus=game.events, effect_engine=game.effect_engine,
        )

        attack = make_card(instance_id=1, power=3, is_attack=True, owner_index=0)
        attack.played_from_zone = Zone.ARSENAL
        assert game.effect_engine.get_modified_power(game.state, attack) == 2

        _emit_end_of_turn(game, 0)

        # After zone cleanup, the WHILE_SOURCE_IN_ZONE effect should be removed
        game.effect_engine.cleanup_zone_effects(game.state)
        assert game.effect_engine.get_modified_power(game.state, attack) == 3


# ---------------------------------------------------------------------------
# Inertia
# ---------------------------------------------------------------------------


class TestInertiaToken(unittest.TestCase):
    """Inertia: Destroy, then hand + arsenal to bottom of deck."""

    def test_end_phase_moves_hand_and_arsenal(self):
        """Inertia puts all hand and arsenal cards on deck bottom."""
        game = make_game_shell()
        p0 = game.state.players[0]

        # Add cards to hand and arsenal
        for i in range(3):
            p0.hand.append(make_card(instance_id=100 + i, name=f"Hand Card {i}"))
        arsenal_card = make_card(instance_id=200, name="Arsenal Card", zone=Zone.ARSENAL)
        p0.arsenal.append(arsenal_card)

        create_token(
            game.state, 0, "Inertia", SubType.AURA,
            event_bus=game.events, effect_engine=game.effect_engine,
        )

        deck_before = len(p0.deck)
        _emit_end_of_turn(game, 0)

        # Token destroyed, hand and arsenal empty, deck grew
        assert len(p0.permanents) == 0
        assert len(p0.hand) == 0
        assert len(p0.arsenal) == 0
        assert len(p0.deck) == deck_before + 4

    def test_empty_hand_no_crash(self):
        """Inertia with empty hand and arsenal: just destroy token."""
        game = make_game_shell()
        p0 = game.state.players[0]
        p0.hand.clear()
        p0.arsenal.clear()

        create_token(
            game.state, 0, "Inertia", SubType.AURA,
            event_bus=game.events, effect_engine=game.effect_engine,
        )

        _emit_end_of_turn(game, 0)
        assert len(p0.permanents) == 0


# ---------------------------------------------------------------------------
# Bloodrot Pox
# ---------------------------------------------------------------------------


class TestBloodrotPoxToken(unittest.TestCase):
    """Bloodrot Pox: Destroy, deal 2 damage unless pay 3."""

    def test_takes_damage_when_cant_pay(self):
        """Bloodrot Pox deals 2 damage when player can't pay 3 resources."""
        game = make_game_shell()
        p0 = game.state.players[0]
        p0.hand.clear()  # No cards to pitch

        life_before = p0.life_total
        create_token(
            game.state, 0, "Bloodrot Pox", SubType.AURA,
            event_bus=game.events, effect_engine=game.effect_engine,
            ask=lambda d: PlayerResponse(selected_option_ids=["take_damage"]),
        )

        _emit_end_of_turn(game, 0)
        assert len(p0.permanents) == 0
        assert p0.life_total == life_before - 2

    def test_pays_to_prevent_damage(self):
        """Bloodrot Pox: player can pay 3 to prevent damage."""
        game = make_game_shell()
        p0 = game.state.players[0]
        # Give player resources
        game.state.resource_points[0] = 3

        life_before = p0.life_total
        create_token(
            game.state, 0, "Bloodrot Pox", SubType.AURA,
            event_bus=game.events, effect_engine=game.effect_engine,
            ask=lambda d: PlayerResponse(selected_option_ids=["pay"]),
        )

        _emit_end_of_turn(game, 0)
        assert len(p0.permanents) == 0
        assert p0.life_total == life_before  # No damage taken

    def test_pays_by_pitching(self):
        """Bloodrot Pox: player pitches cards to pay 3."""
        game = make_game_shell()
        p0 = game.state.players[0]
        p0.hand.clear()
        # Give one blue pitch card (pitch 3)
        pitch = make_pitch_card(instance_id=300, owner_index=0, pitch=3)
        p0.hand.append(pitch)

        life_before = p0.life_total
        create_token(
            game.state, 0, "Bloodrot Pox", SubType.AURA,
            event_bus=game.events, effect_engine=game.effect_engine,
            ask=lambda d: PlayerResponse(selected_option_ids=["pay"]),
        )

        _emit_end_of_turn(game, 0)
        assert p0.life_total == life_before  # No damage taken
        assert len(p0.permanents) == 0


# ---------------------------------------------------------------------------
# Fealty — end-phase conditional destroy
# ---------------------------------------------------------------------------


class TestFealtyToken(unittest.TestCase):
    """Fealty: Instant destroy for Draconic grant, conditional end-phase destroy."""

    def test_end_phase_destroy_when_no_fealty_or_draconic(self):
        """Fealty self-destructs if no Fealty created and no Draconic played."""
        game = make_game_shell()
        p0 = game.state.players[0]

        create_token(
            game.state, 0, "Fealty", SubType.AURA,
            type_text="Draconic Token - Aura",
            supertypes=frozenset({SuperType.DRACONIC}),
            event_bus=game.events, effect_engine=game.effect_engine,
        )
        # Reset the fealty_created flag (simulate a prior turn's Fealty)
        p0.turn_counters.fealty_created_this_turn = False
        p0.turn_counters.draconic_card_played_this_turn = False

        assert len(p0.permanents) == 1
        _emit_end_of_turn(game, 0)
        assert len(p0.permanents) == 0

    def test_survives_when_fealty_created_this_turn(self):
        """Fealty survives if a Fealty was created this turn."""
        game = make_game_shell()
        p0 = game.state.players[0]

        create_token(
            game.state, 0, "Fealty", SubType.AURA,
            supertypes=frozenset({SuperType.DRACONIC}),
            event_bus=game.events, effect_engine=game.effect_engine,
        )
        # fealty_created_this_turn should be True from create_token
        assert p0.turn_counters.fealty_created_this_turn is True

        _emit_end_of_turn(game, 0)
        # Token should survive
        assert len(p0.permanents) == 1

    def test_survives_when_draconic_card_played(self):
        """Fealty survives if a Draconic card was played this turn."""
        game = make_game_shell()
        p0 = game.state.players[0]

        create_token(
            game.state, 0, "Fealty", SubType.AURA,
            supertypes=frozenset({SuperType.DRACONIC}),
            event_bus=game.events, effect_engine=game.effect_engine,
        )
        p0.turn_counters.fealty_created_this_turn = False
        p0.turn_counters.draconic_card_played_this_turn = True

        _emit_end_of_turn(game, 0)
        assert len(p0.permanents) == 1

    def test_instant_activation_grants_draconic(self):
        """Fealty instant: destroy to grant Draconic to next card."""
        game = make_game_shell()
        p0 = game.state.players[0]

        token = create_token(
            game.state, 0, "Fealty", SubType.AURA,
            supertypes=frozenset({SuperType.DRACONIC}),
            event_bus=game.events, effect_engine=game.effect_engine,
        )

        # Activate Fealty instant
        handler = game.ability_registry.lookup("permanent_instant_effect", "Fealty")
        assert handler is not None

        from htc.engine.abilities import AbilityContext
        ctx = AbilityContext(
            state=game.state,
            source_card=token,
            controller_index=0,
            chain_link=None,
            effect_engine=game.effect_engine,
            events=game.events,
            ask=lambda d: PlayerResponse(selected_option_ids=["pass"]),
            keyword_engine=game.keyword_engine,
            combat_mgr=game.combat_mgr,
        )
        handler(ctx)

        # Token should be destroyed
        assert token not in p0.permanents

        # The continuous effect should exist, granting Draconic to next card
        draconic_effects = [
            e for e in game.state.continuous_effects
            if e.supertypes_to_add and SuperType.DRACONIC in e.supertypes_to_add
        ]
        assert len(draconic_effects) == 1

    def test_fealty_registered_as_permanent_instant(self):
        """Fealty is registered as a permanent_instant_effect."""
        game = make_game_shell()
        handler = game.ability_registry.lookup("permanent_instant_effect", "Fealty")
        assert handler is not None


# ---------------------------------------------------------------------------
# Silver — action activation
# ---------------------------------------------------------------------------


class TestSilverToken(unittest.TestCase):
    """Silver: Action — {r}{r}{r}, destroy: Draw a card. Go again."""

    def test_handler_registered(self):
        """Silver is registered as a permanent_action_effect."""
        game = make_game_shell()
        handler = game.ability_registry.lookup("permanent_action_effect", "Silver")
        assert handler is not None

    def test_action_activation_draws_and_go_again(self):
        """Silver activation: pay 3, destroy, draw a card, gain AP."""
        game = make_game_shell()
        p0 = game.state.players[0]
        p0.deck.append(make_card(instance_id=300, name="Drawn Card"))

        from htc.cards.abilities.assassin import _create_silver_token
        token = _create_silver_token(game.state, 0)

        handler = game.ability_registry.lookup("permanent_action_effect", "Silver")
        from htc.engine.abilities import AbilityContext
        ctx = AbilityContext(
            state=game.state,
            source_card=token,
            controller_index=0,
            chain_link=None,
            effect_engine=game.effect_engine,
            events=game.events,
            ask=lambda d: PlayerResponse(selected_option_ids=["pass"]),
            keyword_engine=game.keyword_engine,
            combat_mgr=game.combat_mgr,
        )

        hand_before = len(p0.hand)
        ap_before = game.state.action_points.get(0, 0)

        handler(ctx)

        # Token destroyed
        assert token not in p0.permanents
        # Card drawn
        assert len(p0.hand) == hand_before + 1
        # Go again (AP gained)
        assert game.state.action_points[0] == ap_before + 1

    def test_offered_as_action_option(self):
        """Silver is offered in action decisions when player has AP and 3 resources."""
        game = make_game_shell(action_points={0: 1, 1: 0})
        game.state.turn_player_index = 0
        p0 = game.state.players[0]

        from htc.cards.abilities.assassin import _create_silver_token
        _create_silver_token(game.state, 0)

        # Player needs resources (3 from pitching or pool)
        game.state.resource_points[0] = 3

        decision = game.action_builder.build_action_decision(
            game.state, 0, stack_is_empty=True,
        )
        activate_ids = [
            o.action_id for o in decision.options
            if "Silver" in o.description and o.action_id.startswith("activate_")
        ]
        assert len(activate_ids) == 1

    def test_not_offered_without_resources(self):
        """Silver is NOT offered when player can't afford 3 resources."""
        game = make_game_shell(action_points={0: 1, 1: 0})
        game.state.turn_player_index = 0
        p0 = game.state.players[0]
        p0.hand.clear()  # No cards to pitch

        from htc.cards.abilities.assassin import _create_silver_token
        _create_silver_token(game.state, 0)

        decision = game.action_builder.build_action_decision(
            game.state, 0, stack_is_empty=True,
        )
        activate_ids = [
            o.action_id for o in decision.options
            if "Silver" in o.description
        ]
        assert len(activate_ids) == 0


# ---------------------------------------------------------------------------
# Graphene Chelicera — weapon token
# ---------------------------------------------------------------------------


class TestGrapheneCheliceraToken(unittest.TestCase):
    """Graphene Chelicera: Once per Turn Action — {r}: Attack for 1, go again."""

    def test_created_as_weapon(self):
        """Graphene Chelicera is created as a weapon, not a permanent."""
        game = make_game_shell()
        from htc.cards.abilities.assassin import _create_graphene_chelicera
        _create_graphene_chelicera(game.state, 0)

        weapons = [w for w in game.state.players[0].weapons if w.name == "Graphene Chelicera"]
        assert len(weapons) == 1
        assert len(game.state.players[0].permanents) == 0

    def test_weapon_properties(self):
        """Graphene Chelicera has correct weapon properties."""
        game = make_game_shell()
        from htc.cards.abilities.assassin import _create_graphene_chelicera
        _create_graphene_chelicera(game.state, 0)

        weapon = game.state.players[0].weapons[-1]
        assert weapon.name == "Graphene Chelicera"
        assert weapon.definition.power == 1
        assert CardType.WEAPON in weapon.definition.types
        assert SubType.DAGGER in weapon.definition.subtypes
        assert Keyword.GO_AGAIN in weapon.definition.keywords

    def test_activation_cost_is_one(self):
        """Graphene Chelicera costs 1 resource to activate."""
        game = make_game_shell()
        from htc.cards.abilities.assassin import _create_graphene_chelicera
        _create_graphene_chelicera(game.state, 0)

        weapon = game.state.players[0].weapons[-1]
        cost = game._base_weapon_activation_cost(weapon)
        assert cost == 1

    def test_offered_as_weapon_activation(self):
        """Graphene Chelicera appears in weapon activation options."""
        game = make_game_shell(action_points={0: 1, 1: 0})
        game.state.turn_player_index = 0
        p0 = game.state.players[0]

        from htc.cards.abilities.assassin import _create_graphene_chelicera
        _create_graphene_chelicera(game.state, 0)

        # Player needs 1 resource to activate
        game.state.resource_points[0] = 1

        decision = game.action_builder.build_action_decision(
            game.state, 0, stack_is_empty=True,
        )
        weapon_opts = [
            o for o in decision.options
            if "Graphene Chelicera" in o.description
        ]
        assert len(weapon_opts) == 1


# ---------------------------------------------------------------------------
# Token functional text
# ---------------------------------------------------------------------------


class TestTokenFunctionalText(unittest.TestCase):
    """Verify authoritative functional_text for each token."""

    def test_ponder_text(self):
        game = make_game_shell()
        token = create_token(
            game.state, 0, "Ponder", SubType.AURA,
            functional_text="At the beginning of your end phase, destroy Ponder and draw a card.",
            event_bus=game.events, effect_engine=game.effect_engine,
        )
        assert "end phase" in token.definition.functional_text
        assert "draw a card" in token.definition.functional_text

    def test_frailty_text(self):
        game = make_game_shell()
        token = create_token(
            game.state, 0, "Frailty", SubType.AURA,
            functional_text="Your attack action cards played from arsenal and weapon attacks have -1{p}. At the beginning of your end phase destroy Frailty.",
            event_bus=game.events, effect_engine=game.effect_engine,
        )
        assert "-1{p}" in token.definition.functional_text
        assert "end phase" in token.definition.functional_text

    def test_inertia_text(self):
        game = make_game_shell()
        token = create_token(
            game.state, 0, "Inertia", SubType.AURA,
            functional_text="At the beginning of your end phase, destroy Inertia, then put all cards from your hand and arsenal on the bottom of your deck.",
            event_bus=game.events, effect_engine=game.effect_engine,
        )
        assert "hand and arsenal" in token.definition.functional_text

    def test_bloodrot_pox_text(self):
        game = make_game_shell()
        token = create_token(
            game.state, 0, "Bloodrot Pox", SubType.AURA,
            functional_text="At the beginning of your end phase, destroy Bloodrot Pox, then it deals 2 damage to you unless you pay {r}{r}{r}.",
            event_bus=game.events, effect_engine=game.effect_engine,
            ask=lambda d: PlayerResponse(selected_option_ids=["pass"]),
        )
        assert "2 damage" in token.definition.functional_text
        assert "{r}{r}{r}" in token.definition.functional_text


# ---------------------------------------------------------------------------
# End-phase trigger processing integration
# ---------------------------------------------------------------------------


class TestEndPhaseTriggerProcessing(unittest.TestCase):
    """Verify END_OF_TURN triggers are processed in _run_end_phase."""

    def test_process_pending_triggers_called(self):
        """_run_end_phase processes pending triggers from END_OF_TURN event.

        Uses the direct emit+process pattern since make_game_shell doesn't
        have player interfaces needed for _run_end_phase's arsenal decision.
        """
        game = make_game_shell()
        p0 = game.state.players[0]
        p0.deck.append(make_card(instance_id=300, name="Draw Target"))
        game.state.turn_player_index = 0

        create_token(
            game.state, 0, "Ponder", SubType.AURA,
            event_bus=game.events, effect_engine=game.effect_engine,
        )

        # Verify token exists
        assert len(p0.permanents) == 1

        # Emit END_OF_TURN + process triggers (same as _run_end_phase does)
        _emit_end_of_turn(game, 0)

        # Ponder should have triggered: token destroyed, card drawn
        assert len(p0.permanents) == 0


# ---------------------------------------------------------------------------
# Turn counter tracking
# ---------------------------------------------------------------------------


class TestTurnCounterTracking(unittest.TestCase):
    """Verify Fealty/Draconic tracking on TurnCounters."""

    def test_fealty_created_flag_set_by_create_token(self):
        """Creating a Fealty token sets fealty_created_this_turn."""
        game = make_game_shell()
        p0 = game.state.players[0]
        assert p0.turn_counters.fealty_created_this_turn is False

        create_token(game.state, 0, "Fealty", SubType.AURA)
        assert p0.turn_counters.fealty_created_this_turn is True

    def test_draconic_tracking_on_turn_counters(self):
        """draconic_card_played_this_turn defaults to False."""
        game = make_game_shell()
        p0 = game.state.players[0]
        assert p0.turn_counters.draconic_card_played_this_turn is False

    def test_turn_counters_reset(self):
        """TurnCounters.reset() clears Fealty/Draconic flags."""
        game = make_game_shell()
        p0 = game.state.players[0]
        p0.turn_counters.fealty_created_this_turn = True
        p0.turn_counters.draconic_card_played_this_turn = True
        p0.turn_counters.reset()
        assert p0.turn_counters.fealty_created_this_turn is False
        assert p0.turn_counters.draconic_card_played_this_turn is False


if __name__ == "__main__":
    unittest.main()
