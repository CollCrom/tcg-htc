"""Effect engine — central API for querying modified card properties.

All game code should ask EffectEngine for a card's effective power, defense,
cost, and keywords rather than reading base values directly.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from engine.rules.continuous import (
    ContinuousEffect,
    EffectDuration,
    ModStage,
    NumericProperty,
    StagingResolver,
)

if TYPE_CHECKING:
    from engine.cards.instance import CardInstance
    from engine.enums import Keyword, SuperType
    from engine.state.game_state import GameState

# Signature: (state, card, current_cost) -> adjusted_cost
IntrinsicCostModifier = Callable[["GameState", "CardInstance", int], int]


class EffectEngine:
    """Central query point for modified card properties.

    Owns ID/timestamp counters and delegates to :class:`StagingResolver`
    for the actual staging-order application of effects.
    """

    def __init__(self) -> None:
        self._resolver = StagingResolver()
        self._next_effect_id: int = 0
        self._next_timestamp: int = 0
        # Intrinsic cost modifiers keyed by card name.  Each callable
        # receives (state, card, current_cost) and returns the adjusted cost.
        self._intrinsic_cost_modifiers: dict[str, IntrinsicCostModifier] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_intrinsic_cost_modifier(
        self, card_name: str, modifier: IntrinsicCostModifier
    ) -> None:
        """Register an intrinsic cost modifier for cards with *card_name*.

        Intrinsic cost modifiers represent card-text cost adjustments that
        depend on game state (e.g. "costs {r} less if the defending hero
        is marked").  They are applied after continuous-effect cost
        modifiers and before the floor clamp.
        """
        self._intrinsic_cost_modifiers[card_name] = modifier

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
        return self._resolve_numeric_property(state, card, base, NumericProperty.POWER)

    def get_modified_defense(self, state: GameState, card: CardInstance) -> int:
        base = card.base_defense or 0
        # Include defense counters (from Battleworn/Temper degradation)
        base += card.counters.get("defense", 0)
        return self._resolve_numeric_property(state, card, base, NumericProperty.DEFENSE)

    def get_modified_cost(self, state: GameState, card: CardInstance) -> int:
        base = card.cost if card.cost is not None else 0
        result = self._resolve_numeric_property(state, card, base, NumericProperty.COST)

        # Apply intrinsic cost modifiers (card-text cost adjustments)
        modifier = self._intrinsic_cost_modifiers.get(card.name)
        if modifier is not None:
            result = modifier(state, card, result)

        return max(0, result)

    def get_modified_supertypes(
        self, state: GameState, card: CardInstance
    ) -> frozenset[SuperType]:
        """Get the effective supertypes for a card (base + continuous effects)."""
        base = card._effective_definition.supertypes
        active = self._active_effects(state)
        return self._resolver.resolve_supertypes(active, card, state, base)

    def get_modified_subtypes(
        self, state: GameState, card: CardInstance
    ) -> frozenset:
        """Get the effective subtypes for a card (base + continuous effects)."""
        base = card._effective_definition.subtypes
        active = self._active_effects(state)
        return self._resolver.resolve_subtypes(active, card, state, base)

    def get_modified_keywords(
        self, state: GameState, card: CardInstance
    ) -> frozenset[Keyword]:
        base = card._effective_definition.keywords
        active = self._active_effects(state)
        # Pre-resolve supertypes so target_filter lambdas can see
        # effect-granted supertypes.
        card._resolved_supertypes = self._resolver.resolve_supertypes(
            active, card, state, card._effective_definition.supertypes
        )
        try:
            return self._resolver.resolve_keywords(active, card, state, base)
        finally:
            del card._resolved_supertypes

    def get_keyword_value(
        self, state: GameState, card: CardInstance, keyword: Keyword
    ) -> int:
        """Get the effective numeric value for a keyword (e.g. Arcane Barrier 2).

        Currently returns the base value from the card definition. When
        continuous effects that modify keyword values are added, this method
        will incorporate them.
        """
        return card._effective_definition.keyword_value(keyword)

    # ------------------------------------------------------------------
    # Usage-limited cost effects
    # ------------------------------------------------------------------

    def consume_limited_cost_effects(
        self, state: GameState, card: CardInstance
    ) -> None:
        """Decrement ``uses_remaining`` on cost effects that matched *card*.

        Called after a card is successfully played and its cost paid.
        Only cost-modifying effects (``numeric_property == COST``) with a
        non-None ``uses_remaining`` are considered.  Effects whose counter
        reaches 0 are removed.
        """
        active = self._active_effects(state)
        # Pre-resolve supertypes so target_filter sees granted supertypes
        card._resolved_supertypes = self._resolver.resolve_supertypes(
            active, card, state, card._effective_definition.supertypes
        )
        try:
            to_remove: list[int] = []
            for effect in active:
                if (
                    effect.numeric_property == NumericProperty.COST
                    and effect.uses_remaining is not None
                    and effect.target_filter(card)
                ):
                    effect.uses_remaining -= 1
                    if effect.uses_remaining <= 0:
                        to_remove.append(effect.effect_id)
            for eid in to_remove:
                self.remove_continuous_effect(state, eid)
        finally:
            if hasattr(card, "_resolved_supertypes"):
                del card._resolved_supertypes

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

    def _resolve_numeric_property(
        self, state: GameState, card: CardInstance, base: int, prop: NumericProperty
    ) -> int:
        """Apply staging resolution for a numeric property and clamp >= 0."""
        active = self._active_effects(state)
        # Pre-resolve supertypes so target_filter lambdas can see
        # effect-granted supertypes (e.g. Enflame's Draconic grant).
        card._resolved_supertypes = self._resolver.resolve_supertypes(
            active, card, state, card._effective_definition.supertypes
        )
        try:
            value = self._resolver.resolve_numeric(
                active, card, state, base, prop, ModStage.BASE_NUMERIC
            )
            value = self._resolver.resolve_numeric(
                active, card, state, value, prop, ModStage.NUMERIC
            )
            return max(0, value)
        finally:
            del card._resolved_supertypes

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
