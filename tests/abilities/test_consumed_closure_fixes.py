"""Tests for consumed-closure bug fixes and Overpower arsenal restriction.

Covers:
- Issue 1: Dagger attack power bonus survives multiple filter evaluations
  (Cut from the Same Cloth, Up Sticks and Run, Savor Bloodshed).
- Issue 2: Fealty Draconic grant survives multiple filter evaluations
  (supertype visible to cost reduction, Draconic tracking, etc.).
- Issue 3: Overpower blocks Ambush action cards from arsenal (not just hand).
"""

from __future__ import annotations

import unittest

from htc.cards.abilities._helpers import create_token
from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.abilities import AbilityContext
from htc.engine.actions import PlayerResponse
from htc.engine.events import EventType, GameEvent
from htc.enums import (
    CardType,
    Color,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from tests.conftest import make_card, make_game_shell
from tests.abilities.conftest import (
    make_dagger_attack,
    make_non_attack_action,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(game, card, link=None):
    """Build an AbilityContext for the given game and card."""
    return AbilityContext(
        state=game.state,
        source_card=card,
        controller_index=card.owner_index,
        chain_link=link,
        effect_engine=game.effect_engine,
        events=game.events,
        ask=lambda d: PlayerResponse(selected_option_ids=["pass"]),
        keyword_engine=game.keyword_engine,
        combat_mgr=game.combat_mgr,
    )


def _make_overpower_attack(instance_id=1, owner_index=0):
    """Create an attack with Overpower keyword."""
    defn = CardDefinition(
        unique_id=f"overpower-{instance_id}",
        name="Overpower Attack",
        color=Color.RED,
        pitch=1,
        cost=0,
        power=5,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset(),
        keywords=frozenset({Keyword.OVERPOWER}),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
    )


def _make_ambush_action(instance_id=40, owner_index=1):
    """Create an action card with Ambush keyword in arsenal."""
    defn = CardDefinition(
        unique_id=f"ambush-action-{instance_id}",
        name="Ambush Action",
        color=Color.RED,
        pitch=1,
        cost=0,
        power=None,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset(),
        supertypes=frozenset(),
        keywords=frozenset({Keyword.AMBUSH}),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.ARSENAL,
    )


def _make_ambush_equipment(instance_id=50, owner_index=1):
    """Create an equipment card with Ambush keyword in arsenal (non-action)."""
    defn = CardDefinition(
        unique_id=f"ambush-eq-{instance_id}",
        name="Ambush Equipment",
        color=None,
        pitch=None,
        cost=0,
        power=None,
        defense=2,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.EQUIPMENT}),
        subtypes=frozenset({SubType.ARMS}),
        supertypes=frozenset(),
        keywords=frozenset({Keyword.AMBUSH}),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.ARSENAL,
    )


# ===========================================================================
# Issue 1: Dagger attack bonus stable across multiple evaluations
# ===========================================================================


class TestDaggerBonusMultipleEvaluations(unittest.TestCase):
    """The dagger attack power bonus must survive multiple filter evaluations.

    Before the fix, the consumed-closure pattern set consumed=True on the
    first filter call (e.g. during defend prompt display), so subsequent
    calls (damage calculation) returned False and the bonus was lost.
    """

    def test_cut_from_same_cloth_bonus_survives_multiple_queries(self):
        """Cut from the Same Cloth: bonus visible on every power query."""
        game = make_game_shell()
        state = game.state

        # Put an attack reaction in opponent's hand so mark triggers
        ar = make_card(
            instance_id=99, name="AR Card", power=None, defense=2,
            is_attack=False, owner_index=1, zone=Zone.HAND,
        )
        ar.definition = CardDefinition(
            unique_id="ar-99", name="AR Card", color=Color.RED,
            pitch=1, cost=0, power=None, defense=2, health=None,
            intellect=None, arcane=None,
            types=frozenset({CardType.ATTACK_REACTION}),
            subtypes=frozenset(), supertypes=frozenset(),
            keywords=frozenset(), functional_text="", type_text="",
        )
        state.players[1].hand.append(ar)

        # Set up a dagger attack on the chain
        dagger = make_dagger_attack(instance_id=1, power=1, owner_index=0)
        game.combat_mgr.open_chain(state)
        link = game.combat_mgr.add_chain_link(state, dagger, 1)

        # Play Cut from the Same Cloth
        naa = make_non_attack_action("Cut from the Same Cloth", instance_id=30, color=Color.RED)
        game._apply_card_ability(naa, 0, "on_play")

        # Query power multiple times — must be stable
        power1 = game.effect_engine.get_modified_power(state, dagger)
        power2 = game.effect_engine.get_modified_power(state, dagger)
        power3 = game.effect_engine.get_modified_power(state, dagger)

        assert power1 == 5, f"Expected 1+4=5, got {power1}"
        assert power2 == 5, f"Second query should still be 5, got {power2}"
        assert power3 == 5, f"Third query should still be 5, got {power3}"

    def test_up_sticks_and_run_bonus_survives_multiple_queries(self):
        """Up Sticks and Run: dagger bonus stable across evaluations."""
        game = make_game_shell()
        state = game.state

        dagger = make_dagger_attack(instance_id=1, power=2, owner_index=0)
        game.combat_mgr.open_chain(state)
        link = game.combat_mgr.add_chain_link(state, dagger, 1)

        naa = make_non_attack_action("Up Sticks and Run", instance_id=30, color=Color.RED)
        game._apply_card_ability(naa, 0, "on_play")

        power1 = game.effect_engine.get_modified_power(state, dagger)
        power2 = game.effect_engine.get_modified_power(state, dagger)

        # Red Up Sticks and Run gives +4 to next dagger
        assert power1 == 6, f"Expected 2+4=6, got {power1}"
        assert power2 == 6, f"Second query should still be 6, got {power2}"

    def test_savor_bloodshed_bonus_survives_multiple_queries(self):
        """Savor Bloodshed: dagger bonus stable across evaluations."""
        game = make_game_shell()
        state = game.state

        dagger = make_dagger_attack(instance_id=1, power=1, owner_index=0)
        game.combat_mgr.open_chain(state)
        link = game.combat_mgr.add_chain_link(state, dagger, 1)

        naa = make_non_attack_action("Savor Bloodshed", instance_id=30, color=Color.RED)
        game._apply_card_ability(naa, 0, "on_play")

        power1 = game.effect_engine.get_modified_power(state, dagger)
        power2 = game.effect_engine.get_modified_power(state, dagger)

        # Red Savor Bloodshed gives +4 to next dagger
        assert power1 == 5, f"Expected 1+4=5, got {power1}"
        assert power2 == 5, f"Second query should still be 5, got {power2}"

    def test_bonus_only_applies_to_first_dagger(self):
        """The bonus should only apply to the first dagger, not subsequent ones."""
        game = make_game_shell()
        state = game.state

        dagger1 = make_dagger_attack(instance_id=1, power=1, owner_index=0)
        dagger2 = make_dagger_attack(instance_id=2, power=1, owner_index=0)

        game.combat_mgr.open_chain(state)
        link = game.combat_mgr.add_chain_link(state, dagger1, 1)

        naa = make_non_attack_action("Up Sticks and Run", instance_id=30, color=Color.RED)
        game._apply_card_ability(naa, 0, "on_play")

        # First dagger gets the bonus
        assert game.effect_engine.get_modified_power(state, dagger1) == 5

        # Put second dagger on chain too
        dagger2.zone = Zone.COMBAT_CHAIN
        link2 = game.combat_mgr.add_chain_link(state, dagger2, 1)

        # Second dagger should NOT get the bonus
        assert game.effect_engine.get_modified_power(state, dagger2) == 1


# ===========================================================================
# Issue 2: Fealty Draconic grant stable across multiple evaluations
# ===========================================================================


class TestFealtyDraconicGrantMultipleEvaluations(unittest.TestCase):
    """The Fealty Draconic grant must survive multiple filter evaluations.

    Before the fix, the consumed-closure pattern set consumed=True on the
    first filter call (e.g. during cost reduction pre-resolution), so
    subsequent calls (get_modified_supertypes for Draconic tracking) returned
    False and the card was not seen as Draconic.
    """

    def test_fealty_grant_survives_multiple_supertype_queries(self):
        """Draconic grant visible on every supertype query for the same card."""
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

        # Create a non-Draconic card and put it on the stack
        card = make_card(
            instance_id=50, name="Test Action", power=3, defense=2,
            cost=1, owner_index=0, zone=Zone.STACK,
        )

        # Query supertypes multiple times — must consistently show Draconic
        supers1 = game.effect_engine.get_modified_supertypes(game.state, card)
        supers2 = game.effect_engine.get_modified_supertypes(game.state, card)
        supers3 = game.effect_engine.get_modified_supertypes(game.state, card)

        assert SuperType.DRACONIC in supers1, f"First query: Draconic missing from {supers1}"
        assert SuperType.DRACONIC in supers2, f"Second query: Draconic missing from {supers2}"
        assert SuperType.DRACONIC in supers3, f"Third query: Draconic missing from {supers3}"

    def test_fealty_grant_only_applies_to_first_card(self):
        """The Draconic grant should only apply to the first card played."""
        game = make_game_shell()

        token = create_token(
            game.state, 0, "Fealty", SubType.AURA,
            supertypes=frozenset({SuperType.DRACONIC}),
            event_bus=game.events, effect_engine=game.effect_engine,
        )

        handler = game.ability_registry.lookup("permanent_instant_effect", "Fealty")
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

        # First card on the stack gets Draconic
        card1 = make_card(instance_id=50, name="First Card", owner_index=0, zone=Zone.STACK)
        card2 = make_card(instance_id=51, name="Second Card", owner_index=0, zone=Zone.STACK)

        supers1 = game.effect_engine.get_modified_supertypes(game.state, card1)
        assert SuperType.DRACONIC in supers1

        # Second card should NOT get Draconic (grant already locked to first)
        supers2 = game.effect_engine.get_modified_supertypes(game.state, card2)
        assert SuperType.DRACONIC not in supers2

    def test_fealty_grant_ignores_opponent_cards(self):
        """The Draconic grant should not apply to opponent's cards."""
        game = make_game_shell()

        token = create_token(
            game.state, 0, "Fealty", SubType.AURA,
            supertypes=frozenset({SuperType.DRACONIC}),
            event_bus=game.events, effect_engine=game.effect_engine,
        )

        handler = game.ability_registry.lookup("permanent_instant_effect", "Fealty")
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

        # Opponent's card on the stack should not get Draconic
        opponent_card = make_card(
            instance_id=60, name="Opponent Card", owner_index=1, zone=Zone.STACK,
        )
        supers = game.effect_engine.get_modified_supertypes(game.state, opponent_card)
        assert SuperType.DRACONIC not in supers


# ===========================================================================
# Issue 3: Overpower restricts Ambush action cards from arsenal
# ===========================================================================


class TestOverpowerAmbushArsenal(unittest.TestCase):
    """Overpower restricts action cards regardless of source zone.

    Overpower says "can't be defended by more than 1 action card" — no
    "from hand" qualifier. Arsenal Ambush action cards must be counted.
    """

    def test_sole_ambush_action_from_arsenal_allowed(self):
        """A single Ambush action from arsenal should be allowed by Overpower."""
        game = make_game_shell(life=20)
        state = game.state

        game.combat_mgr.open_chain(state)
        attack = _make_overpower_attack(instance_id=1)
        link = game.combat_mgr.add_chain_link(state, attack, 1)

        ambush = _make_ambush_action(instance_id=40, owner_index=1)
        state.players[1].arsenal.append(ambush)

        def mock_ask(decision):
            return PlayerResponse(
                selected_option_ids=[f"defend_{ambush.instance_id}"]
            )

        game._ask = mock_ask
        game._defend_step()

        assert ambush in link.defending_cards, "Sole Ambush action should defend"

    def test_ambush_action_blocked_after_hand_action(self):
        """Ambush action from arsenal blocked if hand action already defended."""
        game = make_game_shell(life=20)
        state = game.state

        game.combat_mgr.open_chain(state)
        attack = _make_overpower_attack(instance_id=1)
        link = game.combat_mgr.add_chain_link(state, attack, 1)

        hand_action = make_card(
            instance_id=30, name="Hand Action", power=None, defense=2,
            is_attack=False, owner_index=1, zone=Zone.HAND,
        )
        state.players[1].hand.append(hand_action)

        ambush = _make_ambush_action(instance_id=40, owner_index=1)
        state.players[1].arsenal.append(ambush)

        def mock_ask(decision):
            return PlayerResponse(
                selected_option_ids=[
                    f"defend_{hand_action.instance_id}",
                    f"defend_{ambush.instance_id}",
                ]
            )

        game._ask = mock_ask
        game._defend_step()

        assert hand_action in link.defending_cards
        assert ambush not in link.defending_cards, (
            "Ambush action should be blocked by Overpower after hand action"
        )

    def test_hand_action_blocked_after_ambush_action(self):
        """Hand action blocked if Ambush action from arsenal already defended."""
        game = make_game_shell(life=20)
        state = game.state

        game.combat_mgr.open_chain(state)
        attack = _make_overpower_attack(instance_id=1)
        link = game.combat_mgr.add_chain_link(state, attack, 1)

        ambush = _make_ambush_action(instance_id=40, owner_index=1)
        state.players[1].arsenal.append(ambush)

        hand_action = make_card(
            instance_id=30, name="Hand Action", power=None, defense=2,
            is_attack=False, owner_index=1, zone=Zone.HAND,
        )
        state.players[1].hand.append(hand_action)

        def mock_ask(decision):
            # Arsenal card processed after hand cards in the response loop,
            # but we put ambush first to test ordering
            return PlayerResponse(
                selected_option_ids=[
                    f"defend_{ambush.instance_id}",
                    f"defend_{hand_action.instance_id}",
                ]
            )

        game._ask = mock_ask
        game._defend_step()

        # One of them defends, the other is blocked
        action_defenders = [c for c in link.defending_cards if c.definition.is_action]
        assert len(action_defenders) == 1, (
            f"Overpower should allow only 1 action card, got {len(action_defenders)}"
        )

    def test_non_action_ambush_from_arsenal_not_restricted(self):
        """Non-action Ambush cards from arsenal are not restricted by Overpower."""
        game = make_game_shell(life=20)
        state = game.state

        game.combat_mgr.open_chain(state)
        attack = _make_overpower_attack(instance_id=1)
        link = game.combat_mgr.add_chain_link(state, attack, 1)

        # Hand action card
        hand_action = make_card(
            instance_id=30, name="Hand Action", power=None, defense=2,
            is_attack=False, owner_index=1, zone=Zone.HAND,
        )
        state.players[1].hand.append(hand_action)

        # Non-action Ambush card (equipment type) in arsenal
        ambush_eq = _make_ambush_equipment(instance_id=50, owner_index=1)
        state.players[1].arsenal.append(ambush_eq)

        def mock_ask(decision):
            return PlayerResponse(
                selected_option_ids=[
                    f"defend_{hand_action.instance_id}",
                    f"defend_{ambush_eq.instance_id}",
                ]
            )

        game._ask = mock_ask
        game._defend_step()

        # Both should defend: equipment is not an action card
        assert hand_action in link.defending_cards
        assert ambush_eq in link.defending_cards
