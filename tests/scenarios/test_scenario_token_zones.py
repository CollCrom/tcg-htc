"""Scenario: Token and zone interaction tests.

Tests:
8. Inertia token end-phase — Inertia forces the controller to put all cards
   from hand and arsenal to the bottom of their deck at end of turn.
   Verify arsenal face-down cards are correctly moved.

Source: strategy-arakni-masterclass.md
"""

from __future__ import annotations

import logging

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.cards.abilities.tokens import InertiaEndPhaseTrigger, register_token_triggers
from htc.engine.events import EventType, GameEvent
from htc.enums import (
    CardType,
    Color,
    SubType,
    SuperType,
    Zone,
)
from tests.conftest import make_game_shell

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared card factories
# ---------------------------------------------------------------------------

def _make_hero(
    name: str = "Arakni, Marionette",
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
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset(),
        functional_text="",
        type_text="Hero - Assassin",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HERO,
    )


def _make_generic_card(
    instance_id: int,
    name: str = "Filler Card",
    owner_index: int = 1,
    zone: Zone = Zone.HAND,
    color: Color = Color.BLUE,
) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"generic-{instance_id}",
        name=name,
        color=color,
        pitch=3,
        cost=0,
        power=None,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset(),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="",
        type_text="Generic Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=zone,
    )


def _make_inertia_token(instance_id: int = 600, owner_index: int = 1) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"inertia-{instance_id}",
        name="Inertia",
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
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="At the beginning of your end phase, destroy Inertia, then put all cards from your hand and arsenal on the bottom of your deck.",
        type_text="Generic Token - Aura",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.PERMANENT,
    )


def _setup_base_game():
    """Create a game shell with heroes."""
    game = make_game_shell()
    state = game.state

    state.players[0].hero = _make_hero(name="Cindra", instance_id=900, owner_index=0)
    state.players[0].life_total = 20

    state.players[1].hero = _make_hero(name="Arakni, Marionette", instance_id=901, owner_index=1)
    state.players[1].life_total = 20

    return game


# ---------------------------------------------------------------------------
# Test 8: Inertia token end-phase
# ---------------------------------------------------------------------------


class TestInertiaEndPhase:
    """Inertia token end-phase forces controller to put all cards from hand
    and arsenal to the bottom of their deck.

    Source: strategy-arakni-masterclass.md
    """

    def test_inertia_moves_hand_to_deck_bottom(self, scenario_recorder):
        """Inertia end-phase should move all cards from hand to bottom of deck."""
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        player = state.players[1]  # Opponent has inertia on them
        inertia = _make_inertia_token(instance_id=600, owner_index=1)
        player.permanents.append(inertia)

        # Give them some cards in hand
        hand_cards = []
        for i in range(3):
            card = _make_generic_card(instance_id=700 + i, name=f"Hand Card {i}", owner_index=1)
            player.hand.append(card)
            hand_cards.append(card)

        initial_deck_size = len(player.deck)

        # Set up trigger
        trigger = InertiaEndPhaseTrigger(
            controller_index=1,
            token_instance_id=inertia.instance_id,
            _state_getter=lambda: state,
        )
        game.events.register_trigger(trigger)

        # Emit END_OF_TURN for player 1
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=1,
        ))
        game._process_pending_triggers()

        # Hand should be empty
        assert len(player.hand) == 0, (
            f"Inertia should empty the hand. Hand still has {len(player.hand)} cards"
        )

        # Cards should be on bottom of deck
        assert len(player.deck) == initial_deck_size + 3, (
            f"Deck should have 3 more cards. Was {initial_deck_size}, now {len(player.deck)}"
        )

        # Inertia token should be destroyed
        assert inertia not in player.permanents, (
            "Inertia token should be destroyed after triggering"
        )

    def test_inertia_moves_arsenal_to_deck_bottom(self, scenario_recorder):
        """Inertia end-phase should also move arsenal cards to deck bottom."""
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        player = state.players[1]
        inertia = _make_inertia_token(instance_id=600, owner_index=1)
        player.permanents.append(inertia)

        # Put a card in arsenal
        arsenal_card = _make_generic_card(
            instance_id=800, name="Arsenal Card", owner_index=1, zone=Zone.ARSENAL,
        )
        player.arsenal.append(arsenal_card)

        initial_deck_size = len(player.deck)

        trigger = InertiaEndPhaseTrigger(
            controller_index=1,
            token_instance_id=inertia.instance_id,
            _state_getter=lambda: state,
        )
        game.events.register_trigger(trigger)

        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=1,
        ))
        game._process_pending_triggers()

        assert len(player.arsenal) == 0, (
            f"Inertia should empty the arsenal. Arsenal still has {len(player.arsenal)} cards"
        )
        assert len(player.deck) == initial_deck_size + 1, (
            f"Deck should have 1 more card from arsenal"
        )

    def test_inertia_moves_both_hand_and_arsenal(self, scenario_recorder):
        """Inertia should move all cards from BOTH hand and arsenal at once."""
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        player = state.players[1]
        inertia = _make_inertia_token(instance_id=600, owner_index=1)
        player.permanents.append(inertia)

        # 2 cards in hand, 1 in arsenal
        for i in range(2):
            card = _make_generic_card(instance_id=700 + i, name=f"Hand Card {i}", owner_index=1)
            player.hand.append(card)
        arsenal_card = _make_generic_card(
            instance_id=800, name="Arsenal Card", owner_index=1, zone=Zone.ARSENAL,
        )
        player.arsenal.append(arsenal_card)

        initial_deck_size = len(player.deck)

        trigger = InertiaEndPhaseTrigger(
            controller_index=1,
            token_instance_id=inertia.instance_id,
            _state_getter=lambda: state,
        )
        game.events.register_trigger(trigger)

        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=1,
        ))
        game._process_pending_triggers()

        assert len(player.hand) == 0, "Hand should be empty after Inertia"
        assert len(player.arsenal) == 0, "Arsenal should be empty after Inertia"
        assert len(player.deck) == initial_deck_size + 3, (
            f"Deck should have 3 more cards (2 from hand + 1 from arsenal)"
        )

    def test_inertia_only_triggers_for_controller(self, scenario_recorder):
        """Inertia should only trigger on the controller's end-of-turn,
        not the opponent's.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        player = state.players[1]
        inertia = _make_inertia_token(instance_id=600, owner_index=1)
        player.permanents.append(inertia)

        card = _make_generic_card(instance_id=700, name="Hand Card", owner_index=1)
        player.hand.append(card)

        trigger = InertiaEndPhaseTrigger(
            controller_index=1,
            token_instance_id=inertia.instance_id,
            _state_getter=lambda: state,
        )
        game.events.register_trigger(trigger)

        # Emit END_OF_TURN for player 0 (opponent) — should NOT trigger
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))
        game._process_pending_triggers()

        assert len(player.hand) == 1, (
            "Inertia should NOT trigger on opponent's end-of-turn"
        )
        assert inertia in player.permanents, (
            "Inertia token should still be on the battlefield"
        )
