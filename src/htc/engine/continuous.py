"""Continuous effects and the staging system (rules 6.2-6.3).

This module defines the data model for continuous effects and the staging
resolver that applies them in correct order per the FaB Comprehensive Rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Callable

from htc.enums import Keyword, SuperType, Zone

if TYPE_CHECKING:
    from htc.cards.instance import CardInstance
    from htc.state.game_state import GameState


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EffectDuration(Enum):
    """How long a continuous effect lasts."""

    END_OF_TURN = "end_of_turn"
    END_OF_COMBAT = "end_of_combat"
    WHILE_SOURCE_IN_ZONE = "while_source_in_zone"
    PERMANENT = "permanent"


class ModStage(IntEnum):
    """8 stages for applying continuous effects (rules 6.3.2).

    Stages 7-8 are fully implemented. Stages 1-6 are placeholders.
    """

    COPYABLE = 1
    CONTROLLER = 2
    TEXT = 3
    TYPES = 4
    SUPERTYPES = 5
    ABILITIES = 6
    BASE_NUMERIC = 7
    NUMERIC = 8


class ModSubstage(IntEnum):
    """Substages for stages 7-8 (rules 6.3.3)."""

    ADD_REMOVE = 1
    SET = 2
    MULTIPLY = 3
    DIVIDE = 4
    ADD_TO = 5
    SUBTRACT_FROM = 6
    DEPENDENT = 7


class NumericProperty(Enum):
    """Which numeric property an effect modifies."""

    POWER = "power"
    DEFENSE = "defense"
    COST = "cost"


# ---------------------------------------------------------------------------
# ContinuousEffect
# ---------------------------------------------------------------------------


@dataclass
class ContinuousEffect:
    """A single continuous effect that modifies card properties.

    For numeric modifications (stages 7-8), the ``modify_numeric`` callable
    receives the current value and returns the new value. The ``substage``
    determines ordering only — the callable contains the actual logic.

    For keyword modifications (stage 6), use ``keywords_to_add`` and
    ``keywords_to_remove``.
    """

    # Identity
    effect_id: int = 0  # assigned by EffectEngine
    source_instance_id: int | None = None
    source_zone: Zone | None = None
    controller_index: int = 0

    # Ordering
    stage: ModStage = ModStage.NUMERIC
    substage: ModSubstage = ModSubstage.ADD_TO
    timestamp: int = 0  # assigned by EffectEngine

    # Duration
    duration: EffectDuration = EffectDuration.END_OF_TURN

    # Targeting — which cards this effect applies to
    target_filter: Callable[[CardInstance], bool] = field(
        default_factory=lambda: (lambda _c: True)
    )

    # Numeric modification (stages 7-8)
    numeric_property: NumericProperty | None = None
    modify_numeric: Callable[[int], int] | None = None

    # Keyword modification (stage 6)
    keywords_to_add: frozenset[Keyword] = frozenset()
    keywords_to_remove: frozenset[Keyword] = frozenset()

    # Supertype modification (stage 5)
    supertypes_to_add: frozenset[SuperType] = frozenset()

    # Optional condition — effect only active when this returns True
    condition: Callable[[GameState], bool] | None = None


# ---------------------------------------------------------------------------
# StagingResolver
# ---------------------------------------------------------------------------


class StagingResolver:
    """Applies continuous effects in staging order per rules 6.3."""

    def resolve_numeric(
        self,
        effects: list[ContinuousEffect],
        card: CardInstance,
        state: GameState,
        base_value: int,
        prop: NumericProperty,
        stage: ModStage,
    ) -> int:
        """Apply numeric effects for *prop* at *stage* in correct order.

        Filters to effects matching ``prop`` and ``stage``, targeting this
        card, then applies them sorted by ``(substage, timestamp)``.
        """
        matching = [
            e
            for e in effects
            if (
                e.stage == stage
                and e.numeric_property == prop
                and e.modify_numeric is not None
                and e.target_filter(card)
            )
        ]
        matching.sort(key=lambda e: (e.substage, e.timestamp))

        value = base_value
        for effect in matching:
            assert effect.modify_numeric is not None
            value = effect.modify_numeric(value)
        return value

    def resolve_supertypes(
        self,
        effects: list[ContinuousEffect],
        card: CardInstance,
        state: GameState,
        base_supertypes: frozenset[SuperType],
    ) -> frozenset[SuperType]:
        """Apply supertype grant effects in timestamp order."""
        matching = [
            e
            for e in effects
            if (
                e.stage == ModStage.SUPERTYPES
                and e.supertypes_to_add
                and e.target_filter(card)
            )
        ]
        matching.sort(key=lambda e: e.timestamp)

        supertypes = set(base_supertypes)
        for effect in matching:
            supertypes |= effect.supertypes_to_add
        return frozenset(supertypes)

    def resolve_keywords(
        self,
        effects: list[ContinuousEffect],
        card: CardInstance,
        state: GameState,
        base_keywords: frozenset[Keyword],
    ) -> frozenset[Keyword]:
        """Apply keyword grant/removal effects in timestamp order."""
        matching = [
            e
            for e in effects
            if (
                e.stage == ModStage.ABILITIES
                and (e.keywords_to_add or e.keywords_to_remove)
                and e.target_filter(card)
            )
        ]
        matching.sort(key=lambda e: e.timestamp)

        keywords = set(base_keywords)
        for effect in matching:
            keywords |= effect.keywords_to_add
            keywords -= effect.keywords_to_remove
        return frozenset(keywords)


# ---------------------------------------------------------------------------
# Factory functions — convenient constructors for common effects
# ---------------------------------------------------------------------------


def _make_numeric_modifier(
    amount: int,
    controller_index: int,
    prop: NumericProperty,
    *,
    source_instance_id: int | None = None,
    duration: EffectDuration = EffectDuration.END_OF_TURN,
    target_filter: Callable[[CardInstance], bool] | None = None,
    condition: Callable[[GameState], bool] | None = None,
) -> ContinuousEffect:
    """Create a +N/-N numeric modification effect for the given property."""
    substage = ModSubstage.ADD_TO if amount >= 0 else ModSubstage.SUBTRACT_FROM
    return ContinuousEffect(
        source_instance_id=source_instance_id,
        controller_index=controller_index,
        stage=ModStage.NUMERIC,
        substage=substage,
        duration=duration,
        target_filter=target_filter or (lambda _c: True),
        numeric_property=prop,
        modify_numeric=lambda v, _a=amount: v + _a,
        condition=condition,
    )


def make_power_modifier(amount: int, controller_index: int, **kwargs) -> ContinuousEffect:
    """Create a +N/-N power modification effect."""
    return _make_numeric_modifier(amount, controller_index, NumericProperty.POWER, **kwargs)


def make_defense_modifier(amount: int, controller_index: int, **kwargs) -> ContinuousEffect:
    """Create a +N/-N defense modification effect."""
    return _make_numeric_modifier(amount, controller_index, NumericProperty.DEFENSE, **kwargs)


def make_cost_modifier(amount: int, controller_index: int, **kwargs) -> ContinuousEffect:
    """Create a +N/-N cost modification effect."""
    return _make_numeric_modifier(amount, controller_index, NumericProperty.COST, **kwargs)


def make_supertype_grant(
    supertypes: frozenset[SuperType],
    controller_index: int,
    *,
    source_instance_id: int | None = None,
    duration: EffectDuration = EffectDuration.END_OF_TURN,
    target_filter: Callable[[CardInstance], bool] | None = None,
    condition: Callable[[GameState], bool] | None = None,
) -> ContinuousEffect:
    """Create an effect that grants supertypes to matching cards."""
    return ContinuousEffect(
        source_instance_id=source_instance_id,
        controller_index=controller_index,
        stage=ModStage.SUPERTYPES,
        substage=ModSubstage.ADD_TO,
        duration=duration,
        target_filter=target_filter or (lambda _c: True),
        supertypes_to_add=supertypes,
        condition=condition,
    )


def make_keyword_grant(
    keywords: frozenset[Keyword],
    controller_index: int,
    *,
    source_instance_id: int | None = None,
    duration: EffectDuration = EffectDuration.END_OF_TURN,
    target_filter: Callable[[CardInstance], bool] | None = None,
    condition: Callable[[GameState], bool] | None = None,
) -> ContinuousEffect:
    """Create an effect that grants keywords to matching cards."""
    return ContinuousEffect(
        source_instance_id=source_instance_id,
        controller_index=controller_index,
        stage=ModStage.ABILITIES,
        substage=ModSubstage.ADD_TO,
        duration=duration,
        target_filter=target_filter or (lambda _c: True),
        keywords_to_add=keywords,
        condition=condition,
    )
