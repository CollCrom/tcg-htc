"""Shared helpers for card ability implementations.

Extracts common patterns used across assassin, ninja, generic, and hero
ability files to reduce duplication.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from htc.engine.continuous import EffectDuration, make_keyword_grant, make_power_modifier
from htc.enums import CardType, Keyword, SubType, Zone

if TYPE_CHECKING:
    from htc.cards.instance import CardInstance
    from htc.engine.abilities import AbilityContext
    from htc.state.game_state import GameState

log = logging.getLogger(__name__)


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
    target_id = target_card.instance_id
    effect = make_power_modifier(
        bonus,
        ctx.controller_index,
        source_instance_id=ctx.source_card.instance_id,
        duration=duration,
        target_filter=lambda c, _id=target_id: c.instance_id == _id,
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
    target_id = target_card.instance_id
    effect = make_keyword_grant(
        frozenset({keyword}),
        ctx.controller_index,
        source_instance_id=ctx.source_card.instance_id,
        duration=duration,
        target_filter=lambda c, _id=target_id: c.instance_id == _id,
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
    log.info(f"  {ability_name}: Marked Player {attacker_index}")


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
        log.info(f"  {ability_name}: Player {ctx.controller_index} draws a card")


def gain_life(ctx: AbilityContext, player_index: int, amount: int, ability_name: str) -> None:
    """Gain life for a player via the event system."""
    from htc.engine.events import EventType, GameEvent

    ctx.events.emit(GameEvent(
        event_type=EventType.GAIN_LIFE,
        target_player=player_index,
        amount=amount,
    ))
    log.info(f"  {ability_name}: Player {player_index} gains {amount} life")


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
) -> CardInstance:
    """Create a token permanent for the given player."""
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
    log.info(f"  Created {name} token for Player {controller_index}")
    return token
