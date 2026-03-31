"""Ninja/Draconic card ability implementations for the Cindra deck.

Registers ability handlers for Ninja and Draconic attack actions,
attack reactions, and non-attack actions used in the Cindra Blue decklist.

Card texts verified against data/cards.tsv functional_text field.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from htc.cards.abilities._helpers import (
    choose_dagger,
    create_token,
    deal_dagger_damage,
    destroy_arsenal,
    draw_card,
    get_mark_on_hit_trigger_class,
    grant_keyword,
    grant_power_bonus,
    require_active_attack,
    require_chain_link,
)
from htc.engine.abilities import AbilityContext, AbilityRegistry
from htc.engine.actions import ActionOption, Decision, PlayerResponse
from htc.engine.continuous import (
    EffectDuration,
    make_cost_modifier,
    make_keyword_grant,
    make_power_modifier,
    make_supertype_grant,
)
from htc.engine.events import EventType, GameEvent, TriggeredEffect
from htc.enums import (
    ActionType,
    CardType,
    Color,
    DecisionType,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from htc.state.player_state import BanishPlayability, EXPIRY_END_OF_TURN

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def count_draconic_chain_links(ctx: AbilityContext) -> int:
    """Count the number of Draconic chain links the controller has on the combat chain.

    A chain link is "Draconic" if its active_attack has the Draconic supertype
    (including supertypes granted by continuous effects) and is owned by the
    controller.
    """
    chain = ctx.state.combat_chain
    controller = ctx.controller_index
    count = 0
    for link in chain.chain_links:
        if link.active_attack is None:
            continue
        if link.active_attack.owner_index != controller:
            continue
        supertypes = ctx.effect_engine.get_modified_supertypes(
            ctx.state, link.active_attack,
        )
        if SuperType.DRACONIC in supertypes:
            count += 1
    return count


def _is_draconic(card, ctx: AbilityContext | None = None) -> bool:
    """Check if a card has the Draconic supertype (including granted supertypes).

    When *ctx* is provided, uses the effect engine for modified supertypes.
    Otherwise falls back to the card definition (for backward compatibility).
    """
    if ctx is not None:
        supertypes = ctx.effect_engine.get_modified_supertypes(ctx.state, card)
        return SuperType.DRACONIC in supertypes
    return SuperType.DRACONIC in card.definition.supertypes


def _create_fealty_token(ctx: AbilityContext) -> None:
    """Create a Fealty token for the controller."""
    create_token(
        ctx.state, ctx.controller_index, "Fealty", SubType.AURA,
        functional_text="Instant - Destroy this: The next card you play this turn is Draconic. At the beginning of your end phase, if you haven't created a Fealty token or played a Draconic card this turn, destroy this.",
        type_text="Draconic Token - Aura",
        supertypes=frozenset({SuperType.DRACONIC}),
        event_bus=ctx.events, effect_engine=ctx.effect_engine,
    )


# ---------------------------------------------------------------------------
# Attack Reactions
# ---------------------------------------------------------------------------


@require_chain_link
def _throw_dagger(ctx: AbilityContext) -> None:
    """Throw Dagger (Assassin/Ninja, Attack Reaction, Blue):

    'Target dagger you control that isn't on the active chain link deals
     1 damage to the defending hero. If damage is dealt this way, the dagger
     has hit and you draw a card. Destroy the dagger.'
    """
    link = ctx.chain_link
    player = ctx.state.players[ctx.controller_index]
    defender_index = link.attack_target_index

    # Find daggers the player controls that are NOT the active attack
    active_atk_id = link.active_attack.instance_id if link.active_attack else None
    # Also exclude the attack source (the weapon being swung this chain link)
    attack_source_id = link.attack_source.instance_id if link.attack_source else None
    daggers = []
    for weapon in player.weapons:
        if SubType.DAGGER in weapon.definition.subtypes:
            if weapon.instance_id != active_atk_id and weapon.instance_id != attack_source_id:
                daggers.append(weapon)

    if not daggers:
        log.info("  Throw Dagger: no eligible dagger found")
        return

    chosen_dagger = choose_dagger(
        ctx, daggers, "Throw Dagger: Choose a dagger to throw",
    )

    actual_damage = deal_dagger_damage(ctx, chosen_dagger, defender_index, link)
    if actual_damage > 0:
        log.info(
            f"  Throw Dagger: {chosen_dagger.name} deals {actual_damage} damage to {ctx.player_name(defender_index)}"
        )
        draw_card(ctx, "Throw Dagger")
    else:
        log.info("  Throw Dagger: Damage was prevented")

    # Destroy the dagger
    if chosen_dagger in player.weapons:
        player.weapons.remove(chosen_dagger)
    chosen_dagger.zone = Zone.GRAVEYARD
    player.graveyard.append(chosen_dagger)
    log.info(f"  Throw Dagger: {chosen_dagger.name} destroyed")


@require_active_attack
def _exposed(ctx: AbilityContext) -> None:
    """Exposed (Generic, Attack Reaction, Blue):

    'If you are marked, you can't play this.
     Target attack gets +1{p}.
     Mark the defending hero.'

    NOTE: The "can't play if marked" restriction should be enforced at
    the action-building level (legality check). Here we just apply the effect.
    """
    link = ctx.chain_link

    # +1 power to the active attack
    attack = link.active_attack
    grant_power_bonus(ctx, attack, 1, "Exposed")

    # Mark the defending hero
    defender = ctx.state.players[link.attack_target_index]
    defender.is_marked = True
    log.info(f"  Exposed: {ctx.player_name(link.attack_target_index)} is now marked")


# ---------------------------------------------------------------------------
# Non-Attack Actions (on_play)
# ---------------------------------------------------------------------------


def _warmongers_diplomacy(ctx: AbilityContext) -> None:
    """Warmonger's Diplomacy (Generic, Action, Blue):

    'Starting with the hero to your left, each hero chooses war or peace.
     War: only weapon and attack actions next turn.
     Peace: only non-weapon non-attack actions next turn.'

    Stores the choice on the opponent's PlayerState. ActionBuilder enforces
    the restriction during their next turn. Cleared at end of their turn.
    """
    opponent_index = 1 - ctx.controller_index
    options = [
        ActionOption(
            action_id="war",
            description="War: only weapon and attack actions next turn",
            action_type=ActionType.PASS,
        ),
        ActionOption(
            action_id="peace",
            description="Peace: only non-weapon non-attack actions next turn",
            action_type=ActionType.PASS,
        ),
    ]
    decision = Decision(
        player_index=opponent_index,
        decision_type=DecisionType.CHOOSE_MODE,
        prompt="Warmonger's Diplomacy: Choose war or peace",
        options=options,
    )
    response = ctx.ask(decision)
    choice = response.first if response.first in ("war", "peace") else "peace"

    # Store restriction on the opponent — enforced by ActionBuilder next turn
    ctx.state.players[opponent_index].diplomacy_restriction = choice
    log.info(
        f"  Warmonger's Diplomacy: {ctx.player_name(opponent_index)} chose {choice} "
        "(restriction active next turn)"
    )


def _authority_of_ataya(ctx: AbilityContext) -> None:
    """Authority of Ataya (Generic, Resource, Gem, Blue):

    'Legendary. When this is pitched, defense reaction cards cost opponents
     an additional {r} to play this turn.'

    Creates a continuous effect that increases the cost of defense reaction
    cards for all opponents by 1 resource until end of turn.
    """
    from htc.engine.continuous import EffectDuration, make_cost_modifier

    controller = ctx.controller_index
    # "opponents" = all other players
    opponent_indices = [i for i in range(len(ctx.state.players)) if i != controller]

    for opp_idx in opponent_indices:
        effect = make_cost_modifier(
            +1,
            controller,
            source_instance_id=ctx.source_card.instance_id,
            duration=EffectDuration.END_OF_TURN,
            target_filter=lambda c, _oi=opp_idx: (
                c.definition.is_defense_reaction and c.owner_index == _oi
            ),
        )
        ctx.effect_engine.add_continuous_effect(ctx.state, effect)

    log.info(
        f"  Authority of Ataya: defense reactions cost opponents +1{{r}} "
        f"this turn (controller P{controller})"
    )


# ---------------------------------------------------------------------------
# Attack Actions — on_attack
# ---------------------------------------------------------------------------


@require_active_attack
def _dragon_power_on_attack(ctx: AbilityContext) -> None:
    """Dragon Power (Ninja, Attack Action):

    'When this attacks, if it is Draconic, it gets +3{p}.'

    Dragon Power is a Ninja card. It is "Draconic" only if it has gained
    the Draconic supertype (e.g. from being on a Draconic chain or from
    an effect). By default it is NOT Draconic — it's just Ninja.
    """
    link = ctx.chain_link

    attack = link.active_attack
    if not _is_draconic(attack, ctx):
        log.info("  Dragon Power: not Draconic, no bonus")
        return

    grant_power_bonus(ctx, attack, 3, "Dragon Power")


@require_active_attack
def _art_of_the_dragon_blood_on_attack(ctx: AbilityContext) -> None:
    """Art of the Dragon: Blood (Ninja, Attack Action):

    'When this attacks, if it is Draconic, it gets go again and the next
     3 Draconic cards you play this turn cost {r} less to play.'

    The card itself is Ninja (not Draconic). It only gains the Draconic
    bonus if it has become Draconic through game effects.
    """
    link = ctx.chain_link

    attack = link.active_attack
    if not _is_draconic(attack, ctx):
        log.info("  Art of the Dragon: Blood: not Draconic, no bonus")
        return

    # Grant Go Again via continuous effect
    grant_keyword(ctx, attack, Keyword.GO_AGAIN, "Art of the Dragon: Blood")

    # Next 3 Draconic cards cost {r} less
    cost_effect = make_cost_modifier(
        -1,
        ctx.controller_index,
        source_instance_id=ctx.source_card.instance_id,
        duration=EffectDuration.END_OF_TURN,
        target_filter=lambda c: SuperType.DRACONIC in getattr(
            c, '_resolved_supertypes', c.definition.supertypes
        ),
    )
    cost_effect.uses_remaining = 3
    ctx.effect_engine.add_continuous_effect(ctx.state, cost_effect)
    log.info(
        "  Art of the Dragon: Blood: next 3 Draconic cards cost 1 less"
    )


@require_active_attack
def _art_of_the_dragon_fire_on_attack(ctx: AbilityContext) -> None:
    """Art of the Dragon: Fire (Ninja, Attack Action):

    'When this attacks, if it is Draconic, deal 2 damage to any target.'

    In 1v1, "any target" means the defending hero or your own hero.
    """
    link = ctx.chain_link

    attack = link.active_attack
    if not _is_draconic(attack, ctx):
        log.info("  Art of the Dragon: Fire: not Draconic, no effect")
        return

    # Ask the player which hero to target (opponent or self)
    defender_index = link.attack_target_index
    options = [
        ActionOption(
            action_id=f"target_{defender_index}",
            description=f"Deal 2 damage to opponent ({ctx.player_name(defender_index)})",
            action_type=ActionType.ACTIVATE_ABILITY,
        ),
        ActionOption(
            action_id=f"target_{ctx.controller_index}",
            description=f"Deal 2 damage to yourself ({ctx.player_name(ctx.controller_index)})",
            action_type=ActionType.ACTIVATE_ABILITY,
        ),
    ]
    decision = Decision(
        player_index=ctx.controller_index,
        decision_type=DecisionType.CHOOSE_TARGET,
        prompt="Art of the Dragon: Fire: Choose a target for 2 damage",
        options=options,
    )
    response = ctx.ask(decision)

    # Default to opponent if no valid response
    target_index = defender_index
    if response.first and response.first.startswith("target_"):
        try:
            chosen = int(response.first.replace("target_", ""))
            if chosen in (0, 1):
                target_index = chosen
        except ValueError:
            pass

    # Deal 2 damage via DEAL_DAMAGE event (so prevention/replacement can apply)
    damage_event = ctx.events.emit(GameEvent(
        event_type=EventType.DEAL_DAMAGE,
        source=attack,
        target_player=target_index,
        amount=2,
        data={"chain_link": link, "is_combat": False},
    ))

    actual_damage = damage_event.amount if not damage_event.cancelled else 0
    if actual_damage > 0:
        log.info(
            f"  Art of the Dragon: Fire: deals {actual_damage} damage to {ctx.player_name(target_index)}"
        )
    else:
        log.info("  Art of the Dragon: Fire: Damage was prevented")


@require_active_attack
def _art_of_the_dragon_scale_on_attack(ctx: AbilityContext) -> None:
    """Art of the Dragon: Scale (Ninja, Attack Action):

    'When this attacks, if it is Draconic, it gets "When this hits a hero,
     put a -1{d} counter on an equipment they control. Then if it has 0{d},
     destroy it."'
    """
    link = ctx.chain_link

    attack = link.active_attack
    if not _is_draconic(attack, ctx):
        log.info("  Art of the Dragon: Scale: not Draconic, no effect")
        return

    # Register a one-shot HIT trigger for the equipment destruction effect
    hit_trigger = _ArtOfDragonScaleHitTrigger(
        attack_instance_id=attack.instance_id,
        controller_index=ctx.controller_index,
        target_player_index=link.attack_target_index,
        _state=ctx.state,
        _ask=ctx.ask,
        one_shot=True,
    )
    ctx.events.register_trigger(hit_trigger)
    log.info(
        "  Art of the Dragon: Scale: registered on-hit equipment counter trigger"
    )


@dataclass
class _ArtOfDragonScaleHitTrigger(TriggeredEffect):
    """One-shot: on hit, put -1{d} counter on target equipment, destroy if 0{d}."""

    attack_instance_id: int = 0
    controller_index: int = 0
    target_player_index: int = 0
    one_shot: bool = True
    _state: object = None
    _ask: object = None

    def condition(self, event: GameEvent) -> bool:
        if event.event_type != EventType.HIT:
            return False
        if event.source is None:
            return False
        return event.source.instance_id == self.attack_instance_id

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        if self._state is None:
            return None
        state = self._state
        target = state.players[self.target_player_index]

        # Find equipment the target controls
        from htc.enums import EquipmentSlot

        equipment = []
        for slot, eq in target.equipment.items():
            if eq is not None:
                equipment.append((slot, eq))

        if not equipment:
            log.info("  Art of the Dragon: Scale hit: no equipment to target")
            return None

        # Choose equipment (auto-pick if only one)
        if len(equipment) == 1:
            chosen_slot, chosen = equipment[0]
        elif self._ask:
            options = [
                ActionOption(
                    action_id=f"eq_{eq.instance_id}",
                    description=f"{eq.name} (defense {eq.definition.defense})",
                    action_type=ActionType.PASS,
                    card_instance_id=eq.instance_id,
                )
                for _slot, eq in equipment
            ]
            decision = Decision(
                player_index=self.controller_index,
                decision_type=DecisionType.CHOOSE_MODE,
                prompt="Art of the Dragon: Scale: Choose equipment to put -1 defense counter on",
                options=options,
            )
            response = self._ask(decision)
            chosen_id = (
                int(response.first.replace("eq_", ""))
                if response.first
                else equipment[0][1].instance_id
            )
            chosen_slot, chosen = next(
                ((s, eq) for s, eq in equipment if eq.instance_id == chosen_id),
                equipment[0],
            )
        else:
            chosen_slot, chosen = equipment[0]

        # Put -1 defense counter using card.counters dict (visible to effect engine)
        chosen.counters["defense"] = chosen.counters.get("defense", 0) - 1
        effective_defense = (chosen.definition.defense or 0) + chosen.counters["defense"]
        log.info(
            f"  Art of the Dragon: Scale: {chosen.name} gets -1 defense counter "
            f"(now {effective_defense} defense)"
        )

        # If defense is 0 or less, destroy it
        if effective_defense <= 0:
            target.equipment[chosen_slot] = None
            chosen.zone = Zone.GRAVEYARD
            target.graveyard.append(chosen)
            log.info(
                f"  Art of the Dragon: Scale: {chosen.name} destroyed (0 defense)"
            )

        return None


@require_active_attack
def _blood_runs_deep_on_attack(ctx: AbilityContext) -> None:
    """Blood Runs Deep (Draconic/Ninja, Attack Action):

    'This costs {r} less to play for each Draconic chain link you control.
     When this attacks a hero, each dagger you control deals 1 damage to them.
     If damage is dealt this way, the dagger has hit. Destroy the daggers.
     Go again'

    Cost reduction is implemented via an intrinsic cost modifier registered
    in register_ninja_cost_modifiers(). The on_attack handler deals the dagger damage.
    """
    link = ctx.chain_link

    player = ctx.state.players[ctx.controller_index]
    defender_index = link.attack_target_index

    # Find all daggers the player controls
    daggers = [w for w in player.weapons if SubType.DAGGER in w.definition.subtypes]

    if not daggers:
        log.info("  Blood Runs Deep: no daggers to deal damage")
        return

    for dagger in daggers:
        actual_damage = deal_dagger_damage(ctx, dagger, defender_index, link)
        if actual_damage > 0:
            log.info(
                f"  Blood Runs Deep: {dagger.name} deals {actual_damage} damage to {ctx.player_name(defender_index)}"
            )
        else:
            log.info(f"  Blood Runs Deep: {dagger.name} damage was prevented")
        # Destroy the dagger
        if dagger in player.weapons:
            player.weapons.remove(dagger)
        dagger.zone = Zone.GRAVEYARD
        player.graveyard.append(dagger)
        log.info(f"  Blood Runs Deep: {dagger.name} destroyed")


@require_active_attack
def _breaking_point_on_hit(ctx: AbilityContext) -> None:
    """Breaking Point (Draconic, Attack Action):

    'Rupture - If Breaking Point is played as chain link 4 or higher,
     it has "When this hits a hero, destroy all cards in their arsenal."'

    Rupture check: only fires if current chain link number >= 4.
    """
    link = ctx.chain_link

    # Check Rupture condition (chain link 4 or higher)
    if link.link_number < 4:
        log.info(
            f"  Breaking Point: Rupture not active (chain link {link.link_number})"
        )
        return

    destroy_arsenal(ctx, link.attack_target_index, "Breaking Point (Rupture)")


@require_chain_link
def _command_and_conquer_on_attack(ctx: AbilityContext) -> None:
    """Command and Conquer on_attack: block defense reactions this chain link.

    Sets defense_reactions_blocked on the active chain link so that
    build_reaction_decision() won't offer defense reactions to the defender.
    """
    ctx.chain_link.defense_reactions_blocked = True
    log.info("  Command and Conquer: defense reactions blocked this chain link")


@require_chain_link
def _command_and_conquer_on_hit(ctx: AbilityContext) -> None:
    """Command and Conquer (Generic, Attack Action):

    'Defense reaction cards can't be played this chain link.
     When this hits a hero, destroy all cards in their arsenal.'
    """
    destroy_arsenal(ctx, ctx.chain_link.attack_target_index, "Command and Conquer")


def _draconic_devotion_handler(ability_name: str):
    """Factory for Demonstrate Devotion / Display Loyalty (identical behavior).

    'If you control 2 or more Draconic chain links, this gets go again
     and "When this attacks a hero, create a Fealty token."'
    """

    @require_active_attack
    def handler(ctx: AbilityContext) -> None:
        draconic_count = count_draconic_chain_links(ctx)
        if draconic_count < 2:
            log.info(
                f"  {ability_name}: only {draconic_count} Draconic chain link(s), "
                f"need 2+"
            )
            return

        attack = ctx.chain_link.active_attack
        grant_keyword(ctx, attack, Keyword.GO_AGAIN, ability_name)
        _create_fealty_token(ctx)
        log.info(f"  {ability_name}: created Fealty token")

    handler.__name__ = f"_{ability_name.lower().replace(' ', '_')}_on_attack"
    return handler


_demonstrate_devotion_on_attack = _draconic_devotion_handler("Demonstrate Devotion")
_display_loyalty_on_attack = _draconic_devotion_handler("Display Loyalty")


@require_active_attack
def _devotion_never_dies_on_hit(ctx: AbilityContext) -> None:
    """Devotion Never Dies (Ninja, Attack Action):

    'When this hits, if a Draconic attack was the last attack this combat
     chain, banish this. If you do, you may play it this turn.
     Go again'
    """
    link = ctx.chain_link

    chain = ctx.state.combat_chain
    # Check if the previous chain link was a Draconic attack
    current_idx = chain.chain_links.index(link) if link in chain.chain_links else -1
    if current_idx <= 0:
        log.info("  Devotion Never Dies: no previous chain link")
        return

    prev_link = chain.chain_links[current_idx - 1]
    if prev_link.active_attack is None or not _is_draconic(prev_link.active_attack, ctx):
        log.info("  Devotion Never Dies: previous attack was not Draconic")
        return

    # Banish the attack card via ctx.banish_card (emits BANISH event)
    attack = link.active_attack
    ctx.banish_card(attack, ctx.controller_index)
    # Clear the chain link reference so close_chain won't try to move it again
    link.active_attack = None

    # Mark as playable from banish this turn (goes to graveyard normally)
    player = ctx.state.players[ctx.controller_index]
    player.playable_from_banish.append(BanishPlayability(attack.instance_id, EXPIRY_END_OF_TURN, False))
    log.info(
        f"  Devotion Never Dies: banished {attack.name}, "
        "may play it this turn from banish"
    )


@require_active_attack
def _hot_on_their_heels_on_attack(ctx: AbilityContext) -> None:
    """Hot on Their Heels (Draconic/Ninja, Attack Action):

    'If you control 2 or more Draconic chain links, this gets go again
     and "When this hits a hero, mark them."'
    """
    link = ctx.chain_link

    draconic_count = count_draconic_chain_links(ctx)
    if draconic_count < 2:
        log.info(
            f"  Hot on Their Heels: only {draconic_count} Draconic chain link(s), "
            f"need 2+"
        )
        return

    # Grant Go Again
    attack = link.active_attack
    grant_keyword(ctx, attack, Keyword.GO_AGAIN, "Hot on Their Heels")

    # Register on-hit trigger to mark the defending hero
    hit_trigger = get_mark_on_hit_trigger_class()(
        attack_instance_id=attack.instance_id,
        target_player_index=link.attack_target_index,
        _state=ctx.state,
        card_name="Hot on Their Heels",
        one_shot=True,
    )
    ctx.events.register_trigger(hit_trigger)
    log.info("  Hot on Their Heels: registered mark-on-hit trigger")


@require_active_attack
def _mark_with_magma_on_attack(ctx: AbilityContext) -> None:
    """Mark with Magma (Draconic/Ninja, Attack Action):

    'If you control 2 or more Draconic chain links, this gets go again
     and "When this hits a hero, mark them."'

    Same conditional effect as Hot on Their Heels.
    """
    link = ctx.chain_link

    draconic_count = count_draconic_chain_links(ctx)
    if draconic_count < 2:
        log.info(
            f"  Mark with Magma: only {draconic_count} Draconic chain link(s), "
            f"need 2+"
        )
        return

    attack = link.active_attack
    grant_keyword(ctx, attack, Keyword.GO_AGAIN, "Mark with Magma")

    hit_trigger = get_mark_on_hit_trigger_class()(
        attack_instance_id=attack.instance_id,
        target_player_index=link.attack_target_index,
        _state=ctx.state,
        card_name="Mark with Magma",
        one_shot=True,
    )
    ctx.events.register_trigger(hit_trigger)
    log.info("  Mark with Magma: registered mark-on-hit trigger")


@require_active_attack
def _hunt_to_the_ends_on_attack(ctx: AbilityContext) -> None:
    """Hunt to the Ends of Rathe (Draconic, Attack Action):

    'When this attacks Arakni, mark them.
     If this is attacking a marked hero, this gets +2{p}.
     Go again'
    """
    link = ctx.chain_link

    defender_index = link.attack_target_index
    defender = ctx.state.players[defender_index]

    # "When this attacks Arakni, mark them"
    # Check if the defender's hero is named Arakni
    hero = getattr(defender, "hero", None)
    if hero is not None and "Arakni" in hero.name:
        defender.is_marked = True
        log.info(
            f"  Hunt to the Ends of Rathe: marked {ctx.player_name(defender_index)} (Arakni)"
        )

    # "If attacking a marked hero, +2 power"
    if defender.is_marked:
        grant_power_bonus(ctx, link.active_attack, 2, "Hunt to the Ends of Rathe")


@require_active_attack
def _ignite_on_attack(ctx: AbilityContext) -> None:
    """Ignite (Draconic/Ninja, Attack Action):

    'When this attacks, the next Draconic card you play or activate this
     combat chain costs {r} less to play or activate.
     Go again'

    Simplified: apply a cost reduction to Draconic cards for the combat chain.
    Counter-limited via uses_remaining on the ContinuousEffect.
    """
    link = ctx.chain_link

    cost_effect = make_cost_modifier(
        -1,
        ctx.controller_index,
        source_instance_id=ctx.source_card.instance_id,
        duration=EffectDuration.END_OF_COMBAT,
        target_filter=lambda c: SuperType.DRACONIC in getattr(
            c, '_resolved_supertypes', c.definition.supertypes
        ),
    )
    cost_effect.uses_remaining = 1
    ctx.effect_engine.add_continuous_effect(ctx.state, cost_effect)
    log.info(
        "  Ignite: next 1 Draconic card costs 1 less"
    )


@require_active_attack
def _enlightened_strike_on_attack(ctx: AbilityContext) -> None:
    """Enlightened Strike (Generic, Attack Action):

    'As an additional cost to play Enlightened Strike, put a card from your
     hand on the bottom of your deck.
     Choose 1:
     - When you attack with Enlightened Strike, draw a card.
     - Enlightened Strike gains +2{p}.
     - Enlightened Strike gains go again.'

    NOTE: The additional cost (put card on bottom) should ideally be enforced
    at play-time. For now we enforce it in the on_attack handler.
    """
    link = ctx.chain_link

    player = ctx.state.players[ctx.controller_index]
    attack = link.active_attack
    atk_id = attack.instance_id

    # Additional cost: put a card from hand on bottom of deck
    if player.hand:
        options = [
            ActionOption(
                action_id=f"bottom_{c.instance_id}",
                description=f"Put {c.name} on bottom of deck",
                action_type=ActionType.PASS,
                card_instance_id=c.instance_id,
            )
            for c in player.hand
        ]
        decision = Decision(
            player_index=ctx.controller_index,
            decision_type=DecisionType.CHOOSE_MODE,
            prompt="Enlightened Strike: Put a card from your hand on the bottom of your deck",
            options=options,
        )
        response = ctx.ask(decision)
        if response.first and response.first.startswith("bottom_"):
            card_id = int(response.first.replace("bottom_", ""))
            card = next(
                (c for c in player.hand if c.instance_id == card_id), None
            )
            if card:
                player.hand.remove(card)
                card.zone = Zone.DECK
                player.deck.append(card)
                log.info(
                    f"  Enlightened Strike: put {card.name} on bottom of deck "
                    "(additional cost)"
                )

    # Choose a mode
    mode_options = [
        ActionOption(
            action_id="draw",
            description="Draw a card",
            action_type=ActionType.ACTIVATE_ABILITY,
        ),
        ActionOption(
            action_id="power",
            description="+2 power",
            action_type=ActionType.ACTIVATE_ABILITY,
        ),
        ActionOption(
            action_id="go_again",
            description="Gain go again",
            action_type=ActionType.ACTIVATE_ABILITY,
        ),
    ]
    mode_decision = Decision(
        player_index=ctx.controller_index,
        decision_type=DecisionType.CHOOSE_MODE,
        prompt="Enlightened Strike: Choose a mode",
        options=mode_options,
    )
    mode_response = ctx.ask(mode_decision)
    chosen = mode_response.first if mode_response.first else "draw"

    if chosen == "draw":
        draw_card(ctx, "Enlightened Strike")
    elif chosen == "power":
        grant_power_bonus(ctx, attack, 2, "Enlightened Strike")
    elif chosen == "go_again":
        grant_keyword(ctx, attack, Keyword.GO_AGAIN, "Enlightened Strike")


@require_active_attack
def _rising_resentment_on_hit(ctx: AbilityContext) -> None:
    """Rising Resentment (Draconic/Ninja, Attack Action):

    'When Rising Resentment hits, you may banish an attack action card from
     your hand with cost less than the number of Draconic chain links you
     control. If you do, it costs {r} less to play and you may play it this
     turn.
     Go again'
    """
    link = ctx.chain_link

    player = ctx.state.players[ctx.controller_index]
    draconic_count = count_draconic_chain_links(ctx)

    # Find attack action cards in hand with cost < draconic chain link count
    eligible = []
    for card in player.hand:
        if card.definition.is_attack_action:
            card_cost = card.definition.cost
            if card_cost is not None and card_cost < draconic_count:
                eligible.append(card)

    if not eligible:
        log.info(
            f"  Rising Resentment: no eligible attack actions in hand "
            f"(need cost < {draconic_count})"
        )
        return

    # Ask player to choose (or pass)
    options = [
        ActionOption(
            action_id=f"banish_{c.instance_id}",
            description=f"Banish {c.name} (cost {c.definition.cost})",
            action_type=ActionType.ACTIVATE_ABILITY,
            card_instance_id=c.instance_id,
        )
        for c in eligible
    ]
    options.append(
        ActionOption(
            action_id="pass",
            description="Don't banish a card",
            action_type=ActionType.PASS,
        )
    )

    decision = Decision(
        player_index=ctx.controller_index,
        decision_type=DecisionType.CHOOSE_MODE,
        prompt="Rising Resentment: You may banish an attack action card from your hand",
        options=options,
    )
    response = ctx.ask(decision)

    if response.first and response.first.startswith("banish_"):
        card_id = int(response.first.replace("banish_", ""))
        card = next((c for c in eligible if c.instance_id == card_id), None)
        if card:
            ctx.banish_card(card, ctx.controller_index)

            # Mark as playable from banish this turn (goes to graveyard normally)
            player.playable_from_banish.append(BanishPlayability(card.instance_id, EXPIRY_END_OF_TURN, False))

            # "it costs {r} less to play" — continuous cost reduction for this card
            cost_effect = make_cost_modifier(
                -1,
                ctx.controller_index,
                source_instance_id=ctx.source_card.instance_id,
                duration=EffectDuration.END_OF_TURN,
                target_filter=lambda c, _id=card.instance_id: c.instance_id == _id,
            )
            ctx.effect_engine.add_continuous_effect(ctx.state, cost_effect)

            log.info(
                f"  Rising Resentment: banished {card.name}, "
                "may play it this turn for 1 less"
            )


@require_active_attack
def _spreading_flames_on_attack(ctx: AbilityContext) -> None:
    """Spreading Flames (Draconic/Ninja, Attack Action):

    'Draconic attacks you control have +1{p} while their base {p} is less
     than the number of Draconic chain links you control.
     Go again'

    This is a static/continuous effect that applies to all Draconic attacks.
    We apply it as a continuous effect for the combat chain duration.
    """
    link = ctx.chain_link

    state = ctx.state
    controller = ctx.controller_index
    effect_engine = ctx.effect_engine

    def _spreading_filter(card):
        """Match Draconic attacks with base power < draconic chain link count (dynamic)."""
        card_supertypes = getattr(
            card, '_resolved_supertypes', card.definition.supertypes
        )
        if SuperType.DRACONIC not in card_supertypes:
            return False
        base_power = card.definition.power
        if base_power is None:
            return False
        # Recount dynamically each evaluation — chain grows as more attacks are played.
        # Use the effect engine to check supertypes so effect-granted Draconic
        # (e.g. from Enflame tier 3) is visible.
        dcount = sum(
            1 for lnk in state.combat_chain.chain_links
            if lnk.active_attack
            and lnk.active_attack.owner_index == controller
            and SuperType.DRACONIC in effect_engine.get_modified_supertypes(
                state, lnk.active_attack
            )
        )
        return base_power < dcount

    effect = make_power_modifier(
        1,
        ctx.controller_index,
        source_instance_id=ctx.source_card.instance_id,
        duration=EffectDuration.END_OF_COMBAT,
        target_filter=_spreading_filter,
    )
    ctx.effect_engine.add_continuous_effect(ctx.state, effect)
    log.info(
        f"  Spreading Flames: Draconic attacks with base power < dynamic draconic count "
        "get +1 power"
    )


# ---------------------------------------------------------------------------
# Enflame the Firebrand (Draconic Ninja Attack Action)
# ---------------------------------------------------------------------------
# "When this attacks, if you control 2 or more Draconic chain links,
#  this gets go again, 3 or more, your attacks are Draconic this combat
#  chain, 4 or more, this gets +2{p}."
#
# NOTE: Fabrary data lists Go Again in Card Keywords, but it's conditional
# (only at 2+ Draconic chain links). The _is_keyword_inherent() heuristic
# in card_db.py correctly detects this and strips it from the parsed keywords.
# ---------------------------------------------------------------------------


@require_active_attack
def _enflame_the_firebrand_on_attack(ctx: AbilityContext) -> None:
    """Enflame the Firebrand on_attack: tiered bonuses based on Draconic chain links."""
    link = ctx.chain_link

    attack = link.active_attack
    draconic_count = count_draconic_chain_links(ctx)
    log.info(f"  Enflame the Firebrand: {draconic_count} Draconic chain link(s)")

    if draconic_count >= 2:
        # This gets go again (conditional — not an inherent keyword)
        grant_keyword(ctx, attack, Keyword.GO_AGAIN, "Enflame the Firebrand (2+)")

    if draconic_count >= 3:
        # Your attacks are Draconic this combat chain — grant Draconic supertype
        # to all future attacks by this controller for the rest of combat
        controller = ctx.controller_index
        effect = make_supertype_grant(
            frozenset({SuperType.DRACONIC}),
            controller,
            source_instance_id=ctx.source_card.instance_id,
            duration=EffectDuration.END_OF_COMBAT,
            target_filter=lambda c, _ctrl=controller: c.owner_index == _ctrl,
        )
        ctx.effect_engine.add_continuous_effect(ctx.state, effect)
        log.info("  Enflame the Firebrand (3+): your attacks are Draconic this combat chain")

    if draconic_count >= 4:
        # This gets +2 power
        grant_power_bonus(ctx, attack, 2, "Enflame the Firebrand (4+)")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_ninja_abilities(registry: AbilityRegistry) -> None:
    """Register all Ninja/Draconic card abilities with the given registry."""

    # Attack reactions
    registry.register("attack_reaction_effect", "Throw Dagger", _throw_dagger)
    registry.register("attack_reaction_effect", "Exposed", _exposed)

    # Non-attack actions (on_play)
    registry.register("on_play", "Warmonger's Diplomacy", _warmongers_diplomacy)
    registry.register("on_pitch", "Authority of Ataya", _authority_of_ataya)

    # Attack actions — on_attack
    registry.register("on_attack", "Dragon Power", _dragon_power_on_attack)
    registry.register(
        "on_attack", "Art of the Dragon: Blood", _art_of_the_dragon_blood_on_attack
    )
    registry.register(
        "on_attack", "Art of the Dragon: Fire", _art_of_the_dragon_fire_on_attack
    )
    registry.register(
        "on_attack", "Art of the Dragon: Scale", _art_of_the_dragon_scale_on_attack
    )
    registry.register("on_attack", "Blood Runs Deep", _blood_runs_deep_on_attack)
    registry.register(
        "on_attack", "Demonstrate Devotion", _demonstrate_devotion_on_attack
    )
    registry.register("on_attack", "Display Loyalty", _display_loyalty_on_attack)
    registry.register(
        "on_attack", "Hot on Their Heels", _hot_on_their_heels_on_attack
    )
    registry.register(
        "on_attack", "Mark with Magma", _mark_with_magma_on_attack
    )
    registry.register(
        "on_attack", "Hunt to the Ends of Rathe", _hunt_to_the_ends_on_attack
    )
    registry.register("on_attack", "Ignite", _ignite_on_attack)
    registry.register(
        "on_attack", "Enlightened Strike", _enlightened_strike_on_attack
    )
    registry.register(
        "on_attack", "Spreading Flames", _spreading_flames_on_attack
    )
    registry.register(
        "on_attack", "Enflame the Firebrand", _enflame_the_firebrand_on_attack
    )

    registry.register(
        "on_attack", "Command and Conquer", _command_and_conquer_on_attack
    )

    # Attack actions — on_hit
    registry.register("on_hit", "Breaking Point", _breaking_point_on_hit)
    registry.register("on_hit", "Command and Conquer", _command_and_conquer_on_hit)
    registry.register("on_hit", "Devotion Never Dies", _devotion_never_dies_on_hit)
    registry.register("on_hit", "Rising Resentment", _rising_resentment_on_hit)


def _make_blood_runs_deep_cost_modifier(effect_engine):
    """Create a cost modifier for Blood Runs Deep that captures the effect engine.

    Blood Runs Deep costs {r} less for each Draconic chain link you control.
    The effect engine is needed to check supertypes (including effect-granted
    Draconic from e.g. Enflame tier 3).
    """

    def _blood_runs_deep_cost_modifier(state, card, current_cost: int) -> int:
        chain = state.combat_chain
        controller = card.owner_index
        draconic_count = 0
        for link in chain.chain_links:
            if link.active_attack is None:
                continue
            if link.active_attack.owner_index != controller:
                continue
            supertypes = effect_engine.get_modified_supertypes(
                state, link.active_attack,
            )
            if SuperType.DRACONIC in supertypes:
                draconic_count += 1
        return current_cost - draconic_count

    return _blood_runs_deep_cost_modifier


def register_ninja_cost_modifiers(effect_engine) -> None:
    """Register intrinsic cost modifiers for Ninja/Draconic cards."""
    effect_engine.register_intrinsic_cost_modifier(
        "Blood Runs Deep", _make_blood_runs_deep_cost_modifier(effect_engine)
    )
