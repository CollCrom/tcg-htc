"""Shared helpers for card ability implementations.

Extracts common patterns used across assassin, ninja, generic, and hero
ability files to reduce duplication.
"""

from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING

from htc.engine.continuous import EffectDuration, make_keyword_grant, make_power_modifier
from htc.enums import CardType, Keyword, SubType, Zone

if TYPE_CHECKING:
    from collections.abc import Callable

    from htc.cards.instance import CardInstance
    from htc.engine.abilities import AbilityContext
    from htc.state.game_state import GameState

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Player name helper
# ---------------------------------------------------------------------------


def get_player_name(state: GameState, player_index: int) -> str:
    """Short hero name for logging (e.g. 'Cindra' from 'Cindra, Dracai of Retribution').

    Falls back to 'Player N' when hero is not set (test scaffolding).
    """
    player = state.players[player_index]
    if player.hero:
        return player.hero.definition.name.split(",")[0]
    return f"Player {player_index}"


# ---------------------------------------------------------------------------
# Zone transition helper
# ---------------------------------------------------------------------------


def move_card(card: CardInstance, from_list: list, to_list: list, new_zone: Zone) -> None:
    """Move a card between zone lists, updating its zone attribute.

    Performs the standard 3-step zone transition:
      1. Remove from source list
      2. Set card.zone
      3. Append to destination list
    """
    from_list.remove(card)
    card.zone = new_zone
    to_list.append(card)


# ---------------------------------------------------------------------------
# Instance ID filter factory
# ---------------------------------------------------------------------------


def make_instance_id_filter(target_id: int) -> Callable[[CardInstance], bool]:
    """Create a target_filter that matches a specific card by instance_id.

    Replaces the repeated pattern: ``lambda c, _id=target_id: c.instance_id == _id``
    """
    return lambda c, _id=target_id: c.instance_id == _id


# ---------------------------------------------------------------------------
# Once-filter factory
# ---------------------------------------------------------------------------


def make_once_filter(condition_fn: Callable[[CardInstance], bool]) -> Callable[[CardInstance], bool]:
    """Create a target_filter that matches at most one card.

    On the first call where *condition_fn* returns True, the card's
    ``instance_id`` is recorded.  All subsequent calls return True only
    for that same card (idempotent across repeated effect-engine queries).
    """
    applied_to: set[int] = set()

    def filter_fn(card: CardInstance) -> bool:
        if card.instance_id in applied_to:
            return True
        if applied_to:
            return False
        if condition_fn(card):
            applied_to.add(card.instance_id)
            return True
        return False

    return filter_fn


# ---------------------------------------------------------------------------
# Color bonus
# ---------------------------------------------------------------------------


def color_bonus(ctx: AbilityContext, *, plus_one: bool = False) -> int:
    """Determine bonus amount from the source card's color.

    Standard scale: Red=3, Yellow=2, Blue=1.
    If *plus_one* is True: Red=4, Yellow=3, Blue=2.
    """
    color = ctx.source_card.definition.color
    offset = 1 if plus_one else 0
    if color is not None:
        base = {"Red": 3, "Yellow": 2, "Blue": 1}.get(color.value, 2)
        return base + offset
    return 2 + offset


# ---------------------------------------------------------------------------
# Power modifier
# ---------------------------------------------------------------------------


def grant_power_bonus(
    ctx: AbilityContext,
    target_card: CardInstance,
    bonus: int,
    ability_name: str,
    duration: EffectDuration = EffectDuration.END_OF_COMBAT,
) -> None:
    """Grant +N power to a target card via continuous effect."""
    effect = make_power_modifier(
        bonus,
        ctx.controller_index,
        source_instance_id=ctx.source_card.instance_id,
        duration=duration,
        target_filter=make_instance_id_filter(target_card.instance_id),
    )
    ctx.effect_engine.add_continuous_effect(ctx.state, effect)
    log.info(f"  {ability_name}: {target_card.name} gets +{bonus} power")


# ---------------------------------------------------------------------------
# Keyword grant
# ---------------------------------------------------------------------------


def grant_keyword(
    ctx: AbilityContext,
    target_card: CardInstance,
    keyword: Keyword,
    ability_name: str,
    duration: EffectDuration = EffectDuration.END_OF_COMBAT,
) -> None:
    """Grant a keyword to a target card via continuous effect."""
    effect = make_keyword_grant(
        frozenset({keyword}),
        ctx.controller_index,
        source_instance_id=ctx.source_card.instance_id,
        duration=duration,
        target_filter=make_instance_id_filter(target_card.instance_id),
    )
    ctx.effect_engine.add_continuous_effect(ctx.state, effect)
    log.info(f"  {ability_name}: {target_card.name} gets {keyword.value}")


# ---------------------------------------------------------------------------
# Mark attacker
# ---------------------------------------------------------------------------


def mark_attacker(ctx: AbilityContext, link, ability_name: str) -> None:
    """Mark the attacking hero (the player who controls the active attack)."""
    attacker_index = 1 - link.attack_target_index
    ctx.state.players[attacker_index].is_marked = True
    log.info(f"  {ability_name}: Marked {ctx.player_name(attacker_index)}")


# ---------------------------------------------------------------------------
# Draw card
# ---------------------------------------------------------------------------


def draw_card(ctx: AbilityContext, ability_name: str) -> None:
    """Draw a card for the controller via the event system."""
    from htc.engine.events import EventType, GameEvent

    player = ctx.state.players[ctx.controller_index]
    if player.deck:
        ctx.events.emit(GameEvent(
            event_type=EventType.DRAW_CARD,
            target_player=ctx.controller_index,
        ))
        log.info(f"  {ability_name}: {ctx.player_name(ctx.controller_index)} draws a card")


def gain_life(ctx: AbilityContext, player_index: int, amount: int, ability_name: str) -> None:
    """Gain life for a player via the event system."""
    from htc.engine.events import EventType, GameEvent

    ctx.events.emit(GameEvent(
        event_type=EventType.GAIN_LIFE,
        target_player=player_index,
        amount=amount,
    ))
    log.info(f"  {ability_name}: {ctx.player_name(player_index)} gains {amount} life")


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------


def create_token(
    state: GameState,
    controller_index: int,
    name: str,
    subtype: SubType,
    functional_text: str = "",
    type_text: str = "",
    supertypes: frozenset = frozenset(),
    *,
    event_bus: object = None,
    effect_engine: object = None,
    ask: object = None,
) -> CardInstance:
    """Create a token permanent for the given player.

    If *event_bus* and *effect_engine* are provided, token abilities (triggers
    and continuous effects) are registered automatically.
    """
    from htc.cards.card import CardDefinition
    from htc.cards.instance import CardInstance

    token_def = CardDefinition(
        unique_id=f"{name.lower().replace(' ', '-')}-token",
        name=name,
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=None,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.TOKEN}),
        subtypes=frozenset({subtype}),
        supertypes=supertypes,
        keywords=frozenset(),
        functional_text=functional_text,
        type_text=type_text,
    )
    token = CardInstance(
        instance_id=state.next_instance_id(),
        definition=token_def,
        owner_index=controller_index,
        zone=Zone.PERMANENT,
    )
    state.players[controller_index].permanents.append(token)
    # Track Fealty creation for end-phase condition
    if name == "Fealty":
        state.players[controller_index].turn_counters.fealty_created_this_turn = True
    log.info(f"  Created {name} token for {get_player_name(state, controller_index)}")

    # Register token abilities if the event bus is provided
    if event_bus is not None and effect_engine is not None:
        from htc.cards.abilities.tokens import register_token_triggers
        register_token_triggers(
            event_bus, effect_engine, state, controller_index, token, ask=ask,
        )

    return token


# ---------------------------------------------------------------------------
# Guard decorators
# ---------------------------------------------------------------------------


def require_active_attack(fn: Callable[[AbilityContext], None]) -> Callable[[AbilityContext], None]:
    """Decorator: return early if there is no active chain link or attack."""

    @functools.wraps(fn)
    def wrapper(ctx: AbilityContext) -> None:
        if ctx.chain_link is None or ctx.chain_link.active_attack is None:
            return
        return fn(ctx)

    return wrapper


def require_chain_link(fn: Callable[[AbilityContext], None]) -> Callable[[AbilityContext], None]:
    """Decorator: return early if there is no active chain link."""

    @functools.wraps(fn)
    def wrapper(ctx: AbilityContext) -> None:
        if ctx.chain_link is None:
            return
        return fn(ctx)

    return wrapper


# ---------------------------------------------------------------------------
# Dagger helpers
# ---------------------------------------------------------------------------


def is_dagger_attack(attack: CardInstance | None, link=None) -> bool:
    """Check if an attack is a dagger attack (card subtype or weapon proxy of dagger)."""
    if attack is None:
        return False
    if SubType.DAGGER in attack.definition.subtypes:
        return True
    if attack.is_proxy and link and link.attack_source:
        if SubType.DAGGER in link.attack_source.definition.subtypes:
            return True
    return False


def choose_card(
    ctx: AbilityContext,
    candidates: list[CardInstance],
    prompt: str,
    *,
    id_prefix: str = "card",
    decision_type: str = "CHOOSE_MODE",
    describe: Callable[[CardInstance], str] | None = None,
) -> CardInstance:
    """Auto-select if one candidate, else ask the player to choose.

    *id_prefix* is used for action_id formatting (e.g. ``"dagger"`` ->
    ``"dagger_123"``).  *describe* optionally customizes the description
    shown for each card; defaults to ``card.name (ID N)``.

    Returns the chosen CardInstance.
    """
    from htc.engine.actions import ActionOption, Decision
    from htc.enums import ActionType, DecisionType

    if len(candidates) == 1:
        return candidates[0]

    desc_fn = describe or (lambda c: f"{c.name} (ID {c.instance_id})")
    dtype = getattr(DecisionType, decision_type)
    options = [
        ActionOption(
            action_id=f"{id_prefix}_{c.instance_id}",
            description=desc_fn(c),
            action_type=ActionType.ACTIVATE_ABILITY,
            card_instance_id=c.instance_id,
        )
        for c in candidates
    ]
    decision = Decision(
        player_index=ctx.controller_index,
        decision_type=dtype,
        prompt=prompt,
        options=options,
    )
    response = ctx.ask(decision)
    chosen_id = (
        int(response.first.replace(f"{id_prefix}_", ""))
        if response.first
        else candidates[0].instance_id
    )
    return next(
        (c for c in candidates if c.instance_id == chosen_id), candidates[0]
    )


def choose_dagger(
    ctx: AbilityContext,
    daggers: list[CardInstance],
    prompt: str,
    *,
    decision_type: str = "CHOOSE_MODE",
) -> CardInstance:
    """Pick a dagger: auto-pick if only one, else ask the player.

    Returns the chosen dagger CardInstance. Delegates to choose_card().
    """
    return choose_card(ctx, daggers, prompt, id_prefix="dagger", decision_type=decision_type)


def deal_dagger_damage(
    ctx: AbilityContext,
    dagger: CardInstance,
    target_index: int,
    link: object,
) -> int:
    """Deal 1 damage from a dagger, emit HIT if damage dealt. Returns actual damage."""
    from htc.engine.events import EventType, GameEvent

    damage_event = ctx.events.emit(GameEvent(
        event_type=EventType.DEAL_DAMAGE,
        source=dagger,
        target_player=target_index,
        amount=1,
        data={"chain_link": link, "is_combat": False},
    ))

    actual_damage = damage_event.amount if not damage_event.cancelled else 0
    if actual_damage > 0:
        ctx.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=dagger,
            target_player=target_index,
            amount=actual_damage,
            data={"chain_link": link},
        ))
    return actual_damage


def destroy_arsenal(
    ctx: AbilityContext,
    player_index: int,
    ability_name: str,
) -> int:
    """Destroy all cards in a player's arsenal. Returns count destroyed."""
    player = ctx.state.players[player_index]
    if not player.arsenal:
        log.info(f"  {ability_name}: {ctx.player_name(player_index)}'s arsenal is empty")
        return 0

    count = len(player.arsenal)
    for card in list(player.arsenal):
        card.zone = Zone.GRAVEYARD
        player.graveyard.append(card)
    player.arsenal.clear()
    log.info(
        f"  {ability_name}: destroyed {count} card(s) "
        f"in {ctx.player_name(player_index)}'s arsenal"
    )
    return count


# ---------------------------------------------------------------------------
# Shared triggered effects
# ---------------------------------------------------------------------------


def _make_mark_on_hit_trigger_class():
    """Create MarkOnHitTrigger class (deferred import to avoid circular deps)."""
    from dataclasses import dataclass
    from htc.engine.events import EventType, GameEvent, TriggeredEffect

    @dataclass
    class MarkOnHitTrigger(TriggeredEffect):
        """One-shot trigger: on hit, mark the target hero.

        Shared by Scar Tissue (assassin), Mark with Magma (ninja), etc.
        """

        attack_instance_id: int = 0
        target_player_index: int = 0
        card_name: str = ""
        one_shot: bool = True
        _state_getter: object = None

        def condition(self, event: GameEvent) -> bool:
            if event.event_type != EventType.HIT:
                return False
            if event.source is None:
                return False
            return event.source.instance_id == self.attack_instance_id

        def _get_state(self):
            if self._state_getter and callable(self._state_getter):
                return self._state_getter()
            return None

        def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
            state = self._get_state()
            if state is None:
                return None
            state.players[self.target_player_index].is_marked = True
            log.info(
                f"  {self.card_name}: {get_player_name(state, self.target_player_index)} is now marked"
            )
            return None

    return MarkOnHitTrigger


# Lazy singleton to avoid circular import at module load time
_MarkOnHitTriggerCls = None


def get_mark_on_hit_trigger_class():
    """Return the shared MarkOnHitTrigger class (created once on first call)."""
    global _MarkOnHitTriggerCls
    if _MarkOnHitTriggerCls is None:
        _MarkOnHitTriggerCls = _make_mark_on_hit_trigger_class()
    return _MarkOnHitTriggerCls
