"""Generic card ability implementations.

Registers ability handlers for commonly-used attack and defense reactions.
Each handler receives an AbilityContext and applies its effect.

Card texts verified against data/cards.csv functional_text field.
"""

from __future__ import annotations

import logging

from htc.engine.abilities import AbilityContext, AbilityRegistry
from htc.engine.actions import ActionOption, Decision, PlayerResponse
from htc.engine.continuous import EffectDuration, make_keyword_grant, make_power_modifier
from htc.enums import ActionType, DecisionType, Keyword, SubType, SuperType

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Attack Reactions
# ---------------------------------------------------------------------------


def _ancestral_empowerment(ctx: AbilityContext) -> None:
    """Ancestral Empowerment (Red, Attack Reaction):

    'Target Ninja attack action card gains +1{p}. Draw a card.'

    Only applies if the active attack is a Ninja attack action card.
    """
    link = ctx.chain_link
    if link is None or link.active_attack is None:
        return

    attack = link.active_attack
    # Check: must be a Ninja attack action card
    is_ninja = SuperType.NINJA in attack.definition.supertypes
    is_attack_action = attack.definition.is_attack_action
    if not (is_ninja and is_attack_action):
        log.info(
            f"  Ancestral Empowerment: no effect — {attack.name} is not a "
            f"Ninja attack action card"
        )
        return

    # +1 power via continuous effect on the active attack
    atk_id = attack.instance_id
    effect = make_power_modifier(
        1,
        ctx.controller_index,
        source_instance_id=ctx.source_card.instance_id,
        duration=EffectDuration.END_OF_COMBAT,
        target_filter=lambda c, _id=atk_id: c.instance_id == _id,
    )
    ctx.effect_engine.add_continuous_effect(ctx.state, effect)
    log.info(
        f"  Ancestral Empowerment: {attack.name} gets +1 power"
    )

    # Draw a card
    player = ctx.state.players[ctx.controller_index]
    if player.deck:
        drawn = player.deck.pop(0)
        drawn.zone = _zone_hand()
        player.hand.append(drawn)
        player.turn_counters.num_cards_drawn += 1
        log.info(f"  Ancestral Empowerment: Player {ctx.controller_index} draws a card")


def _razor_reflex(ctx: AbilityContext) -> None:
    """Razor Reflex (Generic, Attack Reaction):

    'Choose 1:
     - Target dagger or sword weapon attack gets +N{p}.
     - Target attack action card with cost 1 or less gets +N{p} and
       "When this hits, it gets go again."'

    N = 3 (Red), 2 (Yellow), 1 (Blue). We determine N from the source card's
    color: Red=3, Yellow=2, Blue=1.

    Simplified: we always target the current active attack and check
    eligibility for each mode. If only one mode is valid, pick it
    automatically. If neither is valid, no effect.
    """
    link = ctx.chain_link
    if link is None or link.active_attack is None:
        return

    attack = link.active_attack

    # Determine +N from color
    color = ctx.source_card.definition.color
    if color is not None:
        color_val = color.value  # "Red", "Yellow", "Blue"
        bonus = {"Red": 3, "Yellow": 2, "Blue": 1}.get(color_val, 2)
    else:
        bonus = 2  # fallback

    # Check mode eligibility
    # Mode 1: dagger or sword weapon attack
    is_weapon_attack = attack.is_proxy  # weapon attacks are proxies
    has_dagger_or_sword = False
    if is_weapon_attack and attack.definition.subtypes:
        has_dagger_or_sword = bool(
            attack.definition.subtypes & {SubType.DAGGER, SubType.SWORD}
        )
    # Also check the attack source (the weapon itself) if available
    if is_weapon_attack and link.attack_source:
        has_dagger_or_sword = has_dagger_or_sword or bool(
            link.attack_source.definition.subtypes & {SubType.DAGGER, SubType.SWORD}
        )
    mode1_valid = is_weapon_attack and has_dagger_or_sword

    # Mode 2: attack action card with cost 1 or less
    is_attack_action = attack.definition.is_attack_action
    cost = ctx.effect_engine.get_modified_cost(ctx.state, attack)
    mode2_valid = is_attack_action and cost <= 1

    if not mode1_valid and not mode2_valid:
        log.info(f"  Razor Reflex: no valid mode for {attack.name}")
        return

    chosen_mode: int | None = None
    if mode1_valid and not mode2_valid:
        chosen_mode = 1
    elif mode2_valid and not mode1_valid:
        chosen_mode = 2
    else:
        # Both valid — ask player
        options = [
            ActionOption(
                action_id="mode_1",
                description=f"Target weapon attack gets +{bonus} power",
                action_type=ActionType.ACTIVATE_ABILITY,
            ),
            ActionOption(
                action_id="mode_2",
                description=f"Target attack action gets +{bonus} power and go again on hit",
                action_type=ActionType.ACTIVATE_ABILITY,
            ),
        ]
        decision = Decision(
            player_index=ctx.controller_index,
            decision_type=DecisionType.CHOOSE_MODE,
            prompt=f"Razor Reflex: Choose a mode",
            options=options,
        )
        response = ctx.ask(decision)
        if response.first == "mode_1":
            chosen_mode = 1
        else:
            chosen_mode = 2

    atk_id = attack.instance_id
    if chosen_mode == 1:
        # +N power to weapon attack
        effect = make_power_modifier(
            bonus,
            ctx.controller_index,
            source_instance_id=ctx.source_card.instance_id,
            duration=EffectDuration.END_OF_COMBAT,
            target_filter=lambda c, _id=atk_id: c.instance_id == _id,
        )
        ctx.effect_engine.add_continuous_effect(ctx.state, effect)
        log.info(f"  Razor Reflex: {attack.name} gets +{bonus} power (weapon mode)")
    elif chosen_mode == 2:
        # +N power and grant go again on hit
        power_effect = make_power_modifier(
            bonus,
            ctx.controller_index,
            source_instance_id=ctx.source_card.instance_id,
            duration=EffectDuration.END_OF_COMBAT,
            target_filter=lambda c, _id=atk_id: c.instance_id == _id,
        )
        ctx.effect_engine.add_continuous_effect(ctx.state, power_effect)

        # Grant "go again" (simplified — the real card says "when this hits,
        # it gets go again", but implementing hit-triggered go again requires
        # event-driven ability triggers. For now, grant go again directly.)
        # TODO: implement "when this hits, it gets go again" properly via
        # on_hit triggered ability instead of granting go again immediately.
        go_again_effect = make_keyword_grant(
            frozenset({Keyword.GO_AGAIN}),
            ctx.controller_index,
            source_instance_id=ctx.source_card.instance_id,
            duration=EffectDuration.END_OF_COMBAT,
            target_filter=lambda c, _id=atk_id: c.instance_id == _id,
        )
        ctx.effect_engine.add_continuous_effect(ctx.state, go_again_effect)
        log.info(
            f"  Razor Reflex: {attack.name} gets +{bonus} power and go again "
            f"(attack action mode)"
        )


# ---------------------------------------------------------------------------
# Defense Reactions
# ---------------------------------------------------------------------------


def _fate_foreseen(ctx: AbilityContext) -> None:
    """Fate Foreseen (Generic, Defense Reaction):

    'Opt 1'

    Triggers Opt 1 when played as a defense reaction.
    """
    ctx.keyword_engine.perform_opt(ctx.state, ctx.controller_index, 1)
    log.info(f"  Fate Foreseen: Player {ctx.controller_index} performs Opt 1")


def _sink_below(ctx: AbilityContext) -> None:
    """Sink Below (Generic, Defense Reaction):

    'You may put a card from your hand on the bottom of your deck.
     If you do, draw a card.'
    """
    player = ctx.state.players[ctx.controller_index]

    if not player.hand:
        return

    # Ask player to choose a card from hand to put on bottom (or pass)
    options: list[ActionOption] = []
    for card in player.hand:
        options.append(ActionOption(
            action_id=f"bottom_{card.instance_id}",
            description=f"Put {card.name}{card.definition.color_label} on bottom of deck",
            action_type=ActionType.PASS,
            card_instance_id=card.instance_id,
        ))
    options.append(ActionOption(
        action_id="pass",
        description="Don't put a card on bottom",
        action_type=ActionType.PASS,
    ))

    decision = Decision(
        player_index=ctx.controller_index,
        decision_type=DecisionType.CHOOSE_MODE,
        prompt="Sink Below: You may put a card from your hand on the bottom of your deck",
        options=options,
    )
    response = ctx.ask(decision)

    if response.first and response.first.startswith("bottom_"):
        instance_id = int(response.first.replace("bottom_", ""))
        card = next(
            (c for c in player.hand if c.instance_id == instance_id), None
        )
        if card:
            player.hand.remove(card)
            card.zone = _zone_deck()
            player.deck.append(card)
            log.info(
                f"  Sink Below: Player {ctx.controller_index} puts "
                f"{card.name} on bottom of deck"
            )

            # Draw a card
            if player.deck:
                drawn = player.deck.pop(0)
                drawn.zone = _zone_hand()
                player.hand.append(drawn)
                player.turn_counters.num_cards_drawn += 1
                log.info(
                    f"  Sink Below: Player {ctx.controller_index} draws a card"
                )


# NOTE: Shelter from the Storm has an Instant discard activation ability that
# creates a damage prevention effect. This is a complex triggered/replacement
# effect that needs Phase 5 infrastructure (damage prevention layer). The card
# still contributes its defense value when played as a defense reaction.
# TODO: implement Shelter from the Storm's instant discard prevention effect.


# ---------------------------------------------------------------------------
# Zone helpers (avoid circular imports)
# ---------------------------------------------------------------------------

def _zone_hand():
    from htc.enums import Zone
    return Zone.HAND


def _zone_deck():
    from htc.enums import Zone
    return Zone.DECK


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_generic_abilities(registry: AbilityRegistry) -> None:
    """Register all generic card abilities with the given registry."""
    # Attack reactions
    registry.register("attack_reaction_effect", "Ancestral Empowerment", _ancestral_empowerment)
    registry.register("attack_reaction_effect", "Razor Reflex", _razor_reflex)

    # Defense reactions
    registry.register("defense_reaction_effect", "Fate Foreseen", _fate_foreseen)
    registry.register("defense_reaction_effect", "Sink Below", _sink_below)
