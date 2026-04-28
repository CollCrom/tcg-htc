"""CostManager — resource and action point payment logic.

Wraps the stateless cost functions from cost.py and adds the
interactive pitch-to-pay loop that requires player decisions.
Extracted from Game to keep payment logic separate from game-loop
orchestration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from engine.rules.actions import Decision, PlayerResponse
from engine.rules.cost import (
    build_pitch_decision,
    calculate_play_cost,
    can_pay_action_cost,
    can_pay_resource_cost,
    pay_action_cost,
    pay_resource_cost,
    pitch_card,
)

if TYPE_CHECKING:
    from engine.cards.instance import CardInstance
    from engine.rules.effects import EffectEngine
    from engine.rules.events import EventBus
    from engine.state.game_state import GameState

log = logging.getLogger(__name__)

# Type alias for the ask callback (routes decisions to player interfaces)
AskFn = Callable[[Decision], PlayerResponse]


class CostManager:
    """Handles resource/action point payment and pitching.

    Wraps the free functions in ``cost.py`` with an ask callback so the
    interactive pitch loop can query players.
    """

    def __init__(
        self,
        effect_engine: EffectEngine,
        ask_fn: AskFn,
        event_bus: EventBus | None = None,
    ) -> None:
        self.effect_engine = effect_engine
        self._ask = ask_fn
        self.event_bus = event_bus

    # --- Delegations to cost.py free functions ---

    @staticmethod
    def can_pay_action_cost(state: GameState, player_index: int, card: CardInstance) -> bool:
        """Check if the player can pay the action point cost."""
        return can_pay_action_cost(state, player_index, card)

    def can_pay_resource_cost(
        self, state: GameState, player_index: int, card: CardInstance
    ) -> bool:
        """Check if the player can pay the resource cost."""
        return can_pay_resource_cost(state, player_index, card, self.effect_engine)

    @staticmethod
    def pay_action_cost(state: GameState, player_index: int, card: CardInstance) -> None:
        """Deduct the action point cost for playing an action card."""
        pay_action_cost(state, player_index, card)

    @staticmethod
    def pay_resource_cost(state: GameState, player_index: int, amount: int) -> None:
        """Deduct resource points from a player."""
        pay_resource_cost(state, player_index, amount)

    def calculate_play_cost(self, state: GameState, card: CardInstance) -> int:
        """Calculate the total resource cost to play a card."""
        return calculate_play_cost(state, card, self.effect_engine)

    # --- Interactive pitch-to-pay loop ---

    def pitch_to_pay(self, state: GameState, player_index: int, cost: int) -> None:
        """Pitch cards from hand to generate resources, then pay the cost."""
        player = state.players[player_index]
        while state.resource_points[player_index] < cost:
            pitch_decision = build_pitch_decision(
                state, player_index,
                cost - state.resource_points[player_index],
            )
            if pitch_decision is None:
                break
            response = self._ask(pitch_decision)
            if response.first:
                pitch_id = int(response.first.replace("pitch_", ""))
                pitch_target = player.find_card(pitch_id)
                if pitch_target:
                    pitch_card(state, player_index, pitch_target, self.event_bus)
        pay_resource_cost(state, player_index, cost)
