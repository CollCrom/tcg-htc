"""Token ability implementations.

Registers triggered effects and activation handlers for all 7 tokens
used by the Cindra and Arakni decks:
  - Fealty (Draconic Aura): instant destroy for Draconic grant + end-phase self-destruct
  - Frailty (Generic Aura): -1 power debuff + end-phase self-destruct
  - Inertia (Generic Aura): end-phase devastation (hand + arsenal to deck bottom)
  - Bloodrot Pox (Generic Aura): end-phase 2 damage unless pay 3 resources
  - Ponder (Generic Aura): end-phase draw a card
  - Silver (Generic Item): action activation to draw a card with go again
  - Graphene Chelicera (Arms Equipment Token): weapon with 1 power, go again
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from htc.cards.abilities._helpers import make_once_filter
from htc.engine.abilities import AbilityContext, AbilityRegistry
from htc.engine.continuous import (
    EffectDuration,
    make_power_modifier,
    make_supertype_grant,
)
from htc.engine.events import EventType, GameEvent, TriggeredEffect
from htc.enums import CardType, SubType, SuperType, Zone

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from htc.cards.instance import CardInstance
    from htc.engine.effects import EffectEngine
    from htc.engine.events import EventBus
    from htc.state.game_state import GameState

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _destroy_token(state: GameState, controller_index: int, token: CardInstance) -> None:
    """Remove a token from permanents and mark as destroyed.

    Tokens cease to exist when they leave the arena (rules), but we move them
    to graveyard for tracking purposes.
    """
    player = state.players[controller_index]
    if token in player.permanents:
        player.permanents.remove(token)
        token.zone = Zone.GRAVEYARD
        player.graveyard.append(token)
        log.info(f"  Token destroyed: {token.name} (Player {controller_index})")


# ---------------------------------------------------------------------------
# Base class for end-phase token triggers
# ---------------------------------------------------------------------------


@dataclass
class TokenEndPhaseTrigger(TriggeredEffect):
    """Base class for token triggers that fire at the beginning of end phase.

    Provides shared fields (controller_index, token_instance_id, one_shot,
    _state_getter), the standard ``condition()`` check (END_OF_TURN event,
    correct controller, token still on the battlefield), and helpers
    ``_get_state()`` / ``_get_token()``.

    Subclasses only need to override ``create_triggered_event()``.
    """

    controller_index: int = 0
    token_instance_id: int = 0
    one_shot: bool = True
    _state_getter: object = None

    def condition(self, event: GameEvent) -> bool:
        if event.event_type != EventType.END_OF_TURN:
            return False
        if event.target_player != self.controller_index:
            return False
        state = self._get_state()
        if state is None:
            return False
        player = state.players[self.controller_index]
        return any(p.instance_id == self.token_instance_id for p in player.permanents)

    def _get_state(self) -> GameState | None:
        if self._state_getter and callable(self._state_getter):
            return self._state_getter()
        return None

    def _get_token(self) -> CardInstance | None:
        """Return the token CardInstance if it still exists, else None."""
        state = self._get_state()
        if state is None:
            return None
        player = state.players[self.controller_index]
        return next(
            (p for p in player.permanents if p.instance_id == self.token_instance_id),
            None,
        )


# ---------------------------------------------------------------------------
# Ponder — end-phase trigger
# ---------------------------------------------------------------------------
# "At the beginning of your end phase, destroy Ponder and draw a card."
# ---------------------------------------------------------------------------


@dataclass
class PonderEndPhaseTrigger(TokenEndPhaseTrigger):
    """Ponder token: destroy and draw a card at end of turn."""

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        token = self._get_token()
        if token is None:
            return None
        state = self._get_state()
        _destroy_token(state, self.controller_index, token)
        log.info(f"  Ponder: Player {self.controller_index} draws a card")
        return GameEvent(
            event_type=EventType.DRAW_CARD,
            target_player=self.controller_index,
        )


# ---------------------------------------------------------------------------
# Frailty — continuous debuff + end-phase self-destruct
# ---------------------------------------------------------------------------
# "Your attack action cards played from arsenal and weapon attacks have -1{p}.
#  At the beginning of your end phase destroy Frailty."
# ---------------------------------------------------------------------------


@dataclass
class FrailtyEndPhaseTrigger(TokenEndPhaseTrigger):
    """Frailty token: destroy at end of turn (continuous effect is removed by
    cleanup_zone_effects when the source token leaves the arena)."""

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        token = self._get_token()
        if token is None:
            return None
        state = self._get_state()
        _destroy_token(state, self.controller_index, token)
        log.info(f"  Frailty: Destroyed at end of turn (Player {self.controller_index})")
        return None


def register_frailty_continuous_effect(
    effect_engine: EffectEngine,
    state: GameState,
    controller_index: int,
    token: CardInstance,
) -> None:
    """Register -1 power continuous effect for Frailty token.

    Targets the controller's attack action cards (from any zone on the combat
    chain, which includes cards played from arsenal) and weapon proxy attacks.
    Duration is WHILE_SOURCE_IN_ZONE — automatically cleaned up when the token
    is destroyed.
    """
    token_id = token.instance_id
    ctrl = controller_index

    def frailty_filter(card: CardInstance) -> bool:
        if card.owner_index != ctrl:
            return False
        # Weapon proxy attack
        if card.is_proxy:
            return True
        # Attack action card on the combat chain
        if (
            CardType.ACTION in card.definition.types
            and SubType.ATTACK in card.definition.subtypes
        ):
            return True
        return False

    effect = make_power_modifier(
        -1,
        controller_index,
        source_instance_id=token_id,
        duration=EffectDuration.WHILE_SOURCE_IN_ZONE,
        target_filter=frailty_filter,
    )
    effect.source_zone = Zone.PERMANENT
    effect_engine.add_continuous_effect(state, effect)
    log.info(f"  Frailty: Registered -1 power debuff for Player {controller_index}")


# ---------------------------------------------------------------------------
# Inertia — end-phase devastation
# ---------------------------------------------------------------------------
# "At the beginning of your end phase, destroy Inertia, then put all cards
#  from your hand and arsenal on the bottom of your deck."
# ---------------------------------------------------------------------------


@dataclass
class InertiaEndPhaseTrigger(TokenEndPhaseTrigger):
    """Inertia token: destroy, then move hand + arsenal to bottom of deck."""

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        token = self._get_token()
        if token is None:
            return None
        state = self._get_state()

        _destroy_token(state, self.controller_index, token)

        player = state.players[self.controller_index]
        # Move all cards from hand to bottom of deck
        cards_moved = 0
        for card in list(player.hand):
            player.hand.remove(card)
            card.zone = Zone.DECK
            player.deck.append(card)
            cards_moved += 1

        # Move all cards from arsenal to bottom of deck
        for card in list(player.arsenal):
            player.arsenal.remove(card)
            card.zone = Zone.DECK
            player.deck.append(card)
            cards_moved += 1

        log.info(
            f"  Inertia: Player {self.controller_index} puts {cards_moved} cards "
            f"from hand and arsenal to bottom of deck"
        )
        return None


# ---------------------------------------------------------------------------
# Bloodrot Pox — end-phase damage unless pay 3
# ---------------------------------------------------------------------------
# "At the beginning of your end phase, destroy Bloodrot Pox, then it deals
#  2 damage to you unless you pay {r}{r}{r}."
# ---------------------------------------------------------------------------


@dataclass
class BloodrotPoxEndPhaseTrigger(TokenEndPhaseTrigger):
    """Bloodrot Pox: destroy, then deal 2 damage unless controller pays 3 resources."""

    _ask: object = None  # ask callback

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        token = self._get_token()
        if token is None:
            return None
        state = self._get_state()

        _destroy_token(state, self.controller_index, token)

        player = state.players[self.controller_index]
        # Check if player can pay 3 resources (from existing resources + pitchable cards)
        available = state.resource_points.get(self.controller_index, 0)
        for c in player.hand:
            if c.pitch is not None:
                available += c.pitch
        can_pay = available >= 3

        if can_pay and self._ask is not None:
            from htc.engine.actions import ActionOption, Decision
            from htc.enums import ActionType, DecisionType

            options = [
                ActionOption(
                    action_id="pay",
                    description="Pay {r}{r}{r} to prevent 2 damage",
                    action_type=ActionType.ACTIVATE_ABILITY,
                ),
                ActionOption(
                    action_id="take_damage",
                    description="Take 2 damage",
                    action_type=ActionType.ACTIVATE_ABILITY,
                ),
            ]
            decision = Decision(
                player_index=self.controller_index,
                decision_type=DecisionType.CHOOSE_MODE,
                prompt="Bloodrot Pox: Pay {r}{r}{r} or take 2 damage?",
                options=options,
            )
            response = self._ask(decision)
            choice = response.first if response.first else "take_damage"

            if choice == "pay":
                # Pay 3 resources - use existing resource points first, then pitch
                cost_remaining = 3
                current_rp = state.resource_points.get(self.controller_index, 0)
                rp_used = min(cost_remaining, current_rp)
                state.resource_points[self.controller_index] = current_rp - rp_used
                cost_remaining -= rp_used

                # Pitch cards to cover remaining cost
                while cost_remaining > 0 and player.hand:
                    pitch_card = None
                    for c in player.hand:
                        if c.pitch is not None and c.pitch > 0:
                            pitch_card = c
                            break
                    if pitch_card is None:
                        break
                    pitched_value = pitch_card.pitch or 0
                    player.hand.remove(pitch_card)
                    pitch_card.zone = Zone.PITCH
                    player.pitch.append(pitch_card)
                    state.resource_points[self.controller_index] = (
                        state.resource_points.get(self.controller_index, 0) + pitched_value
                    )
                    rp_now = state.resource_points[self.controller_index]
                    rp_used = min(cost_remaining, rp_now)
                    state.resource_points[self.controller_index] = rp_now - rp_used
                    cost_remaining -= rp_used

                log.info(
                    f"  Bloodrot Pox: Player {self.controller_index} pays 3 resources"
                )
                return None

        # Take 2 damage
        log.info(
            f"  Bloodrot Pox: Player {self.controller_index} takes 2 damage"
        )
        return GameEvent(
            event_type=EventType.DEAL_DAMAGE,
            source=token,
            target_player=self.controller_index,
            amount=2,
            data={"is_combat": False},
        )


# ---------------------------------------------------------------------------
# Fealty — instant activation + end-phase conditional self-destruct
# ---------------------------------------------------------------------------
# "Instant - Destroy this: The next card you play this turn is Draconic.
#  At the beginning of your end phase, if you haven't created a Fealty token
#  or played a Draconic card this turn, destroy this."
# ---------------------------------------------------------------------------


@dataclass
class FealtyEndPhaseTrigger(TokenEndPhaseTrigger):
    """Fealty token: conditionally self-destruct at end of turn.

    Destroyed if the controller hasn't created a Fealty token OR played a
    Draconic card this turn.
    """

    def condition(self, event: GameEvent) -> bool:
        if not super().condition(event):
            return False
        # Extra check: hasn't created a Fealty OR played a Draconic card
        state = self._get_state()
        player = state.players[self.controller_index]
        tc = player.turn_counters
        if tc.fealty_created_this_turn or tc.draconic_card_played_this_turn:
            return False  # condition NOT met, don't destroy
        return True  # condition met, destroy

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        token = self._get_token()
        if token is None:
            return None
        state = self._get_state()

        _destroy_token(state, self.controller_index, token)
        log.info(
            f"  Fealty: Self-destructed at end of turn — no Fealty created "
            f"and no Draconic card played (Player {self.controller_index})"
        )
        return None


def _fealty_instant(ctx: AbilityContext) -> None:
    """Fealty instant activation: destroy to grant Draconic supertype to next card played.

    "Instant - Destroy this: The next card you play this turn is Draconic."
    """
    player = ctx.state.players[ctx.controller_index]

    # Destroy the Fealty token
    token = ctx.source_card
    if token in player.permanents:
        player.permanents.remove(token)
        token.zone = Zone.GRAVEYARD
        player.graveyard.append(token)
        log.info(f"  Fealty: Destroyed (instant activation)")

    # Grant Draconic supertype to the next card played this turn
    controller = ctx.controller_index

    next_card_filter = make_once_filter(lambda card: (
        card.owner_index == controller
        and card.zone in (Zone.COMBAT_CHAIN, Zone.STACK)
    ))

    effect = make_supertype_grant(
        frozenset({SuperType.DRACONIC}),
        controller,
        source_instance_id=token.instance_id,
        duration=EffectDuration.END_OF_TURN,
        target_filter=next_card_filter,
    )
    ctx.effect_engine.add_continuous_effect(ctx.state, effect)
    log.info(f"  Fealty: Next card played this turn is Draconic")


# ---------------------------------------------------------------------------
# Silver — action activation
# ---------------------------------------------------------------------------
# "Action - {r}{r}{r}, destroy Silver: Draw a card. Go again."
# ---------------------------------------------------------------------------


def _silver_action(ctx: AbilityContext) -> None:
    """Silver token action activation: pay 3 resources, destroy, draw a card.

    Go again is granted by adding an action point after the draw.
    Cost payment is handled by the engine before this handler is called.
    """
    player = ctx.state.players[ctx.controller_index]

    # Destroy the Silver token
    token = ctx.source_card
    if token in player.permanents:
        player.permanents.remove(token)
        token.zone = Zone.GRAVEYARD
        player.graveyard.append(token)
        log.info(f"  Silver: Destroyed (action activation)")

    # Draw a card
    if player.deck:
        ctx.events.emit(GameEvent(
            event_type=EventType.DRAW_CARD,
            target_player=ctx.controller_index,
        ))
        log.info(f"  Silver: Player {ctx.controller_index} draws a card")

    # Go again — gain an action point
    ctx.state.action_points[ctx.controller_index] = (
        ctx.state.action_points.get(ctx.controller_index, 0) + 1
    )
    log.info(f"  Silver: Player {ctx.controller_index} gains an action point (go again)")


# ---------------------------------------------------------------------------
# Token trigger registration
# ---------------------------------------------------------------------------


def register_token_triggers(
    event_bus: EventBus,
    effect_engine: EffectEngine,
    state: GameState,
    controller_index: int,
    token: CardInstance,
    *,
    ask: object = None,
) -> None:
    """Register triggered effects for a newly created token.

    Called whenever a token is created via create_token(). Checks the token
    name and registers appropriate end-phase triggers and continuous effects.
    """
    state_getter = lambda _state=state: _state
    token_id = token.instance_id

    if token.name == "Ponder":
        trigger = PonderEndPhaseTrigger(
            controller_index=controller_index,
            token_instance_id=token_id,
            _state_getter=state_getter,
            one_shot=True,
        )
        event_bus.register_trigger(trigger)
        log.info(f"  Registered Ponder end-phase trigger for Player {controller_index}")

    elif token.name == "Frailty":
        trigger = FrailtyEndPhaseTrigger(
            controller_index=controller_index,
            token_instance_id=token_id,
            _state_getter=state_getter,
            one_shot=True,
        )
        event_bus.register_trigger(trigger)
        register_frailty_continuous_effect(effect_engine, state, controller_index, token)
        log.info(f"  Registered Frailty triggers for Player {controller_index}")

    elif token.name == "Inertia":
        trigger = InertiaEndPhaseTrigger(
            controller_index=controller_index,
            token_instance_id=token_id,
            _state_getter=state_getter,
            one_shot=True,
        )
        event_bus.register_trigger(trigger)
        log.info(f"  Registered Inertia end-phase trigger for Player {controller_index}")

    elif token.name == "Bloodrot Pox":
        trigger = BloodrotPoxEndPhaseTrigger(
            controller_index=controller_index,
            token_instance_id=token_id,
            _state_getter=state_getter,
            _ask=ask,
            one_shot=True,
        )
        event_bus.register_trigger(trigger)
        log.info(f"  Registered Bloodrot Pox end-phase trigger for Player {controller_index}")

    elif token.name == "Fealty":
        trigger = FealtyEndPhaseTrigger(
            controller_index=controller_index,
            token_instance_id=token_id,
            _state_getter=state_getter,
            one_shot=True,
        )
        event_bus.register_trigger(trigger)
        log.info(f"  Registered Fealty end-phase trigger for Player {controller_index}")


# ---------------------------------------------------------------------------
# Registration — Ability Registry
# ---------------------------------------------------------------------------


def register_token_abilities(registry: AbilityRegistry) -> None:
    """Register token card abilities with the given registry."""
    # Fealty: instant activation (destroy to grant Draconic)
    registry.register("permanent_instant_effect", "Fealty", _fealty_instant)

    # Silver: action activation (pay 3 resources, destroy, draw, go again)
    registry.register("permanent_action_effect", "Silver", _silver_action)
