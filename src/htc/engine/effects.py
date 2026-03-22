from __future__ import annotations

from htc.cards.instance import CardInstance
from htc.state.game_state import GameState


class EffectEngine:
    """Minimal effect engine for Phase 1.

    Currently just provides modified power/defense lookups.
    Will be expanded to handle continuous effects, replacement effects,
    triggered effects, prevention effects, and the staging system.
    """

    def get_modified_power(self, state: GameState, card: CardInstance) -> int:
        base = card.base_power or 0
        # TODO: apply continuous effects from state.active_effects
        return max(0, base)

    def get_modified_defense(self, state: GameState, card: CardInstance) -> int:
        base = card.base_defense or 0
        # TODO: apply continuous effects
        return max(0, base)

    def get_modified_cost(self, state: GameState, card: CardInstance) -> int:
        base = card.cost or 0
        # TODO: apply cost modification effects
        return max(0, base)
