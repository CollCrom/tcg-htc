"""Agent of Chaos (Demi-Hero) ability implementations.

Registers on_become handlers for Arakni's six Demi-Hero forms.
These fire when a player transforms into a Demi-Hero via
Mask of Deceit or other Agent of Chaos effects.

Implemented:
- Trap-Door — search deck for card, banish face-down, shuffle;
              if Trap subtype, playable from banish until start of next turn
- Orb-Weaver — Graphene Chelicera cost reduction is handled by
               the action builder / weapon activation cost logic

Card texts verified against data/cards.tsv functional_text field.
"""

from __future__ import annotations

import logging

from htc.engine.abilities import AbilityContext, AbilityRegistry
from htc.engine.actions import ActionOption, Decision, PlayerResponse
from htc.enums import ActionType, DecisionType, SubType, Zone

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trap-Door
# ---------------------------------------------------------------------------
# "When you become this, you may search your deck for a card, banish it
#  face-down, then shuffle. If it's a trap, you may play it until the
#  start of your next turn."
#
# "At the beginning of your end phase, return to the brood."


def _trap_door_on_become(ctx: AbilityContext) -> None:
    """Arakni, Trap-Door on-become ability.

    Search deck for a card (player chooses), banish it face-down, shuffle.
    If it has the Trap subtype, mark it as playable from banish until
    start of next turn.
    """
    player = ctx.state.players[ctx.controller_index]

    if not player.deck:
        log.info("  Trap-Door: deck is empty, no card to search for")
        return

    # Player may choose not to search (optional "you may")
    options = []
    for card in player.deck:
        options.append(ActionOption(
            action_id=f"trap_door_{card.instance_id}",
            description=f"{card.name} ({card.definition.color_label})",
            action_type=ActionType.ACTIVATE_ABILITY,
            card_instance_id=card.instance_id,
        ))
    options.append(ActionOption(
        action_id="pass",
        description="Don't search",
        action_type=ActionType.PASS,
    ))

    decision = Decision(
        player_index=ctx.controller_index,
        decision_type=DecisionType.CHOOSE_TARGET,
        prompt="Trap-Door: Search your deck for a card to banish face-down",
        options=options,
    )
    response = ctx.ask(decision)
    choice = response.first

    if choice is None or choice == "pass":
        log.info("  Trap-Door: chose not to search")
        return

    instance_id = int(choice.replace("trap_door_", ""))
    target = next((c for c in player.deck if c.instance_id == instance_id), None)
    if target is None:
        log.warning("  Trap-Door: chosen card not found in deck")
        return

    # Banish face-down (uses AbilityContext helper to emit BANISH event)
    ctx.banish_card(target, ctx.controller_index, face_down=True)
    log.info(f"  Trap-Door: banished {target.name} face-down")

    # Shuffle deck
    ctx.state.rng.shuffle(player.deck)

    # If it's a Trap, mark as playable from banish until start of next turn
    if SubType.TRAP in target.definition.subtypes:
        player.playable_from_banish.append(
            (target.instance_id, "start_of_next_turn"),
        )
        log.info(f"  Trap-Door: {target.name} is a Trap, playable until start of next turn")


# ---------------------------------------------------------------------------
# Orb-Weaver
# ---------------------------------------------------------------------------
# "Graphene Chelicerae cost you {r} less to activate."
#
# "Once per Turn Instant - Discard an Assassin card: Equip a Graphene
#  Chelicera token. Your next attack with stealth this turn gets +3{p}."
#
# The cost reduction is handled by the action builder and weapon activation
# cost calculation (checking if current hero is Orb-Weaver).
#
# The instant ability to create Graphene Chelicera tokens is a future TODO —
# it requires token weapon creation infrastructure.


def _orb_weaver_on_become(ctx: AbilityContext) -> None:
    """Arakni, Orb-Weaver on-become ability.

    The passive cost reduction is handled elsewhere. The on-become
    itself has no immediate effect — the abilities are ongoing.
    """
    log.info("  Orb-Weaver: active — Graphene Chelicera activation costs reduced by 1")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_agent_abilities(registry: AbilityRegistry) -> None:
    """Register all Agent of Chaos demi-hero on_become abilities."""
    registry.register("on_become", "Arakni, Trap-Door", _trap_door_on_become)
    registry.register("on_become", "Arakni, Orb-Weaver", _orb_weaver_on_become)
