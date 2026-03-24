"""Effect engine — central API for querying modified card properties.

All game code should ask EffectEngine for a card's effective power, defense,
cost, and keywords rather than reading base values directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from htc.engine.continuous import (
    ContinuousEffect,
    EffectDuration,
    ModStage,
    NumericProperty,
    StagingResolver,
)

if TYPE_CHECKING:
    from htc.cards.instance import CardInstance
    from htc.enums import Keyword
    from htc.state.game_state import GameState


class EffectEngine:
    """Central query point for modified card properties.

    Owns ID/timestamp counters and delegates to :class:`StagingResolver`
    for the actual staging-order application of effects.
    """

    def __init__(self) -> None:
        self._resolver = StagingResolver()
        self._next_effect_id: int = 0
        self._next_timestamp: int = 0

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def add_continuous_effect(
        self,
        state: GameState,
        effect: ContinuousEffect,
    ) -> ContinuousEffect:
        """Register a continuous effect. Assigns ``effect_id`` and ``timestamp``."""
        self._next_effect_id += 1
        effect.effect_id = self._next_effect_id
        self._next_timestamp += 1
        effect.timestamp = self._next_timestamp
        state.continuous_effects.append(effect)
        return effect

    def remove_continuous_effect(self, state: GameState, effect_id: int) -> None:
        """Remove a specific effect by its ID."""
        state.continuous_effects = [
            e for e in state.continuous_effects if e.effect_id != effect_id
        ]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_modified_power(self, state: GameState, card: CardInstance) -> int:
        base = card.base_power or 0
        active = self._active_effects(state)
        value = self._resolver.resolve_numeric(
            active, card, state, base, NumericProperty.POWER, ModStage.BASE_NUMERIC
        )
        value = self._resolver.resolve_numeric(
            active, card, state, value, NumericProperty.POWER, ModStage.NUMERIC
        )
        return max(0, value)

    def get_modified_defense(self, state: GameState, card: CardInstance) -> int:
        base = card.base_defense or 0
        active = self._active_effects(state)
        value = self._resolver.resolve_numeric(
            active, card, state, base, NumericProperty.DEFENSE, ModStage.BASE_NUMERIC
        )
        value = self._resolver.resolve_numeric(
            active, card, state, value, NumericProperty.DEFENSE, ModStage.NUMERIC
        )
        return max(0, value)

    def get_modified_cost(self, state: GameState, card: CardInstance) -> int:
        base = card.cost if card.cost is not None else 0
        active = self._active_effects(state)
        value = self._resolver.resolve_numeric(
            active, card, state, base, NumericProperty.COST, ModStage.BASE_NUMERIC
        )
        value = self._resolver.resolve_numeric(
            active, card, state, value, NumericProperty.COST, ModStage.NUMERIC
        )
        return max(0, value)

    def get_modified_keywords(
        self, state: GameState, card: CardInstance
    ) -> frozenset[Keyword]:
        base = card.definition.keywords
        active = self._active_effects(state)
        return self._resolver.resolve_keywords(active, card, state, base)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_expired_effects(
        self, state: GameState, duration: EffectDuration
    ) -> None:
        """Remove all effects with the given duration."""
        state.continuous_effects = [
            e for e in state.continuous_effects if e.duration != duration
        ]

    def cleanup_zone_effects(self, state: GameState) -> None:
        """Remove WHILE_SOURCE_IN_ZONE effects whose source left its zone."""
        state.continuous_effects = [
            e for e in state.continuous_effects if not self._zone_effect_expired(state, e)
        ]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _active_effects(self, state: GameState) -> list[ContinuousEffect]:
        """Return currently active effects (condition met)."""
        return [
            e
            for e in state.continuous_effects
            if e.condition is None or e.condition(state)
        ]

    def _zone_effect_expired(
        self, state: GameState, effect: ContinuousEffect
    ) -> bool:
        if effect.duration != EffectDuration.WHILE_SOURCE_IN_ZONE:
            return False
        if effect.source_instance_id is None:
            return False
        card = state.find_card(effect.source_instance_id)
        if card is None:
            return True
        return card.zone != effect.source_zone
