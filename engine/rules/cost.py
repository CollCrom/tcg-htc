from __future__ import annotations

import logging
from typing import TYPE_CHECKING

log = logging.getLogger(__name__)

from engine.cards.instance import CardInstance
from engine.enums import ActionType, DecisionType, Zone
from engine.rules.actions import ActionOption, Decision
from engine.state.game_state import GameState

if TYPE_CHECKING:
    from engine.rules.effects import EffectEngine
    from engine.rules.events import EventBus


def calculate_play_cost(
    state: GameState, card: CardInstance, effect_engine: EffectEngine
) -> int:
    """Calculate the total resource cost to play a card.

    Rules 5.1.6: base cost, modified by effects. Action cards also
    cost 1 action point (handled separately).
    """
    return effect_engine.get_modified_cost(state, card)


def _requires_action_point(card: CardInstance) -> bool:
    """Check if playing this card costs an action point (actions that aren't instants)."""
    return card.definition.is_action and not card.definition.is_instant


def can_pay_action_cost(state: GameState, player_index: int, card: CardInstance) -> bool:
    """Check if the player can pay the action point cost to play a card."""
    if _requires_action_point(card):
        return state.action_points[player_index] >= 1
    return True


def pay_action_cost(state: GameState, player_index: int, card: CardInstance) -> None:
    """Deduct the action point cost for playing an action card."""
    if _requires_action_point(card):
        state.action_points[player_index] -= 1


def can_pay_resource_cost(
    state: GameState, player_index: int, card: CardInstance, effect_engine: EffectEngine
) -> bool:
    """Check if the player CAN pay the resource cost (has enough pitchable cards + existing resources)."""
    cost = calculate_play_cost(state, card, effect_engine)
    if cost <= 0:
        return True
    available = state.resource_points[player_index]
    player = state.players[player_index]
    for c in player.hand:
        if c.instance_id != card.instance_id and c.pitch is not None:
            available += c.pitch
    return available >= cost


def build_pitch_decision(
    state: GameState,
    player_index: int,
    cost_remaining: int,
) -> Decision | None:
    """Build a decision asking which card to pitch next, or None if cost is paid."""
    if cost_remaining <= 0:
        return None

    player = state.players[player_index]
    options = []
    for card in player.hand:
        if card.pitch is not None and card.pitch > 0:
            options.append(ActionOption(
                action_id=f"pitch_{card.instance_id}",
                description=f"Pitch {card.name} ({card.definition.color.value if card.definition.color else '?'}) for {card.pitch} resource(s)",
                action_type=ActionType.PLAY_CARD,
                card_instance_id=card.instance_id,
            ))

    if not options:
        return None

    return Decision(
        player_index=player_index,
        decision_type=DecisionType.CHOOSE_CARDS_TO_PITCH,
        prompt=f"Pitch a card to pay {cost_remaining} remaining resource cost",
        options=options,
    )


def pitch_card(
    state: GameState,
    player_index: int,
    card: CardInstance,
    event_bus: EventBus | None = None,
) -> int:
    """Pitch a card: move from hand to pitch zone, gain resources. Returns resources gained.

    If *event_bus* is provided, emits a ``PITCH_CARD`` event so that
    pitch-triggered abilities (e.g. Authority of Ataya) can fire.
    """
    player = state.players[player_index]
    if card in player.hand:
        player.hand.remove(card)
    card.zone = Zone.PITCH
    player.pitch.append(card)
    gained = card.pitch or 0
    state.resource_points[player_index] += gained
    player.turn_counters.num_cards_pitched += 1
    log.info(f"  Pitched {card.name}{card.definition.color_label} for {gained} resource(s)")

    if event_bus is not None:
        from engine.rules.events import EventType, GameEvent

        event_bus.emit(GameEvent(
            event_type=EventType.PITCH_CARD,
            source=card,
            target_player=player_index,
            card=card,
            amount=gained,
        ))

    return gained


def pay_resource_cost(state: GameState, player_index: int, amount: int) -> None:
    """Deduct resource points from a player."""
    state.resource_points[player_index] -= amount
