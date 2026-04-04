"""Assassin card ability implementations for Arakni Marionette deck.

Registers ability handlers for Assassin attack reactions, defense reactions,
non-attack actions, and attack action on-attack/on-hit effects.

Card texts verified against data/cards.tsv functional_text field.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from htc.cards.abilities._helpers import (
    choose_dagger,
    color_bonus,
    create_token,
    deal_dagger_damage,
    draw_card,
    gain_life,
    get_mark_on_hit_trigger_class,
    get_player_name,
    grant_keyword,
    grant_power_bonus,
    make_once_filter,
    mark_attacker,
    move_card,
    require_active_attack,
    require_chain_link,
)
from htc.engine.abilities import AbilityContext, AbilityRegistry
from htc.engine.actions import ActionOption, Decision, PlayerResponse
from htc.engine.continuous import EffectDuration, make_defense_modifier, make_keyword_grant, make_power_modifier
from htc.engine.events import EventType, GameEvent, TriggeredEffect
from htc.enums import ActionType, CardType, Color, DecisionType, Keyword, SubType, SuperType, Zone
from htc.state.player_state import BanishPlayability, EXPIRY_END_OF_TURN

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



def _count_weapon_hand_slots(player) -> int:
    """Count how many 1H weapon hand slots are occupied."""
    count = 0
    for w in player.weapons:
        if SubType.TWO_HAND in w.definition.subtypes:
            count += 2
        else:
            count += 1
    return count


MAX_WEAPON_HAND_SLOTS = 2  # Two 1H weapons or one 2H weapon


def _create_graphene_chelicera(state, controller_index: int) -> bool:
    """Create a Graphene Chelicera token as a weapon.

    "Once per Turn Action - {r}: Attack with this for 1, with go again."
    Created as a weapon (not a permanent) so the weapon activation system handles it.

    Returns True if the token was created, False if no weapon slot available.
    """
    from htc.cards.card import CardDefinition
    from htc.cards.instance import CardInstance

    player = state.players[controller_index]
    pname = get_player_name(state, controller_index)

    # Check weapon slot availability (max 2 hand slots: two 1H or one 2H)
    if _count_weapon_hand_slots(player) >= MAX_WEAPON_HAND_SLOTS:
        log.info(f"  {pname}: No open weapon slot for Graphene Chelicera")
        return False

    token_def = CardDefinition(
        unique_id="graphene-chelicera-token",
        name="Graphene Chelicera",
        color=None,
        pitch=None,
        cost=None,
        power=1,
        defense=None,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.TOKEN, CardType.WEAPON}),
        subtypes=frozenset({SubType.ARMS, SubType.DAGGER, SubType.ONE_HAND}),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset({Keyword.GO_AGAIN}),
        functional_text="Once per Turn Action - {r}: Attack with this for 1, with go again.",
        type_text="Assassin Arms Equipment Token",
    )
    token = CardInstance(
        instance_id=state.next_instance_id(),
        definition=token_def,
        owner_index=controller_index,
        zone=Zone.WEAPON_1,
    )
    player.weapons.append(token)
    log.info(f"  Equipped Graphene Chelicera token for {pname}")
    return True


def _is_dagger_attack(attack, link=None) -> bool:
    """Check if an attack is a dagger attack (card subtype or weapon proxy of dagger)."""
    if attack is None:
        return False
    if SubType.DAGGER in attack.definition.subtypes:
        return True
    if attack.is_proxy and link and link.attack_source:
        if SubType.DAGGER in link.attack_source.definition.subtypes:
            return True
    return False


def _is_assassin_attack(attack, ctx: AbilityContext | None = None) -> bool:
    """Check if an attack is an Assassin attack (supertype).

    When *ctx* is provided, uses the effect engine for modified supertypes.
    Otherwise falls back to the card definition (for backward compatibility).
    """
    if attack is None:
        return False
    if ctx is not None:
        supertypes = ctx.effect_engine.get_modified_supertypes(ctx.state, attack)
        return SuperType.ASSASSIN in supertypes
    return SuperType.ASSASSIN in attack.definition.supertypes


def _has_stealth(attack, ctx: AbilityContext) -> bool:
    """Check if an attack has the Stealth keyword (via effect engine)."""
    if attack is None:
        return False
    kws = ctx.effect_engine.get_modified_keywords(ctx.state, attack)
    return Keyword.STEALTH in kws






# ---------------------------------------------------------------------------
# Attack Reactions
# ---------------------------------------------------------------------------


@require_active_attack
def _incision(ctx: AbilityContext) -> None:
    """Incision (Assassin/Warrior, Attack Reaction):

    'Target dagger attack gets +N{p}.'
    Red=+3, Yellow=+2, Blue=+1.
    """
    link = ctx.chain_link

    attack = link.active_attack
    if not _is_dagger_attack(attack, link):
        log.info(f"  Incision: no effect -- {attack.name} is not a dagger attack")
        return

    bonus = color_bonus(ctx)
    grant_power_bonus(ctx, attack, bonus, "Incision")


@require_active_attack
def _to_the_point(ctx: AbilityContext) -> None:
    """To the Point (Assassin/Warrior, Attack Reaction):

    'Target dagger attack gets +N{p}. If the defending hero is marked,
     instead it gets +(N+1){p}.'
    Red: +3/+4, Yellow: +2/+3, Blue: +1/+2.
    """
    link = ctx.chain_link

    attack = link.active_attack
    if not _is_dagger_attack(attack, link):
        log.info(f"  To the Point: no effect -- {attack.name} is not a dagger attack")
        return

    base_bonus = color_bonus(ctx)
    # Check if defending hero is marked
    defender = ctx.state.players[link.attack_target_index]
    bonus = base_bonus + 1 if defender.is_marked else base_bonus

    grant_power_bonus(ctx, attack, bonus, f"To the Point (marked={defender.is_marked})")


@require_active_attack
def _stains_of_the_redback(ctx: AbilityContext) -> None:
    """Stains of the Redback (Assassin, Attack Reaction):

    'If the defending hero is marked, this costs {r} less to play.
     Target attack with stealth gets +N{p} and go again.'
    Red=+3, Yellow=+2, Blue=+1.

    Cost reduction handled in EffectEngine.get_modified_cost() as a static
    card-specific modifier (costs {r} less when opponent is marked).
    """
    link = ctx.chain_link

    attack = link.active_attack
    if not _has_stealth(attack, ctx):
        log.info(f"  Stains of the Redback: no effect -- {attack.name} does not have Stealth")
        return

    bonus = color_bonus(ctx)
    grant_power_bonus(ctx, attack, bonus, "Stains of the Redback")
    grant_keyword(ctx, attack, Keyword.GO_AGAIN, "Stains of the Redback")


@require_active_attack
def _shred(ctx: AbilityContext) -> None:
    """Shred (Assassin, Attack Reaction):

    'Target card defending an Assassin attack gets -N{d} this combat chain.'
    Red=-4, Yellow=-3, Blue=-2.

    NOTE: We target a defending card. If multiple defenders, the player
    chooses which one gets the defense reduction.
    """
    link = ctx.chain_link

    attack = link.active_attack
    if not _is_assassin_attack(attack, ctx):
        log.info(f"  Shred: no effect -- {attack.name} is not an Assassin attack")
        return

    if not link.defending_cards:
        log.info(f"  Shred: no defending cards to target")
        return

    # Determine penalty from color: Red=-4, Yellow=-3, Blue=-2
    color = ctx.source_card.definition.color
    if color is not None:
        penalty = {"Red": -4, "Yellow": -3, "Blue": -2}.get(color.value, -3)
    else:
        penalty = -3

    # Choose target defender
    if len(link.defending_cards) == 1:
        target = link.defending_cards[0]
    else:
        options = []
        for card in link.defending_cards:
            mod_def = ctx.effect_engine.get_modified_defense(ctx.state, card)
            options.append(ActionOption(
                action_id=f"shred_{card.instance_id}",
                description=f"{card.name} (defense={mod_def})",
                action_type=ActionType.ACTIVATE_ABILITY,
                card_instance_id=card.instance_id,
            ))
        decision = Decision(
            player_index=ctx.controller_index,
            decision_type=DecisionType.CHOOSE_MODE,
            prompt=f"Shred: Choose a defending card to get {penalty} defense",
            options=options,
        )
        response = ctx.ask(decision)
        target_id = int(response.first.replace("shred_", "")) if response.first else link.defending_cards[0].instance_id
        target = next((c for c in link.defending_cards if c.instance_id == target_id), link.defending_cards[0])

    target_id = target.instance_id
    effect = make_defense_modifier(
        penalty,
        ctx.controller_index,
        source_instance_id=ctx.source_card.instance_id,
        duration=EffectDuration.END_OF_COMBAT,
        target_filter=lambda c, _id=target_id: c.instance_id == _id,
    )
    ctx.effect_engine.add_continuous_effect(ctx.state, effect)
    log.info(f"  Shred: {target.name} gets {penalty} defense")


@require_active_attack
def _take_up_the_mantle(ctx: AbilityContext) -> None:
    """Take Up the Mantle (Assassin, Attack Reaction):

    'Target attack action card with stealth gets +2{p}. If it's attacking a
     marked hero, instead it gets +3{p} and you may banish an attack action
     card with stealth from your graveyard. If you do, the target becomes a
     copy of the banished card.'

    The "becomes a copy" effect sets definition_override on the active
    attack so it takes on the banished card's name, power, defense, cost,
    keywords, types, subtypes, and supertypes — while keeping its current
    zone, counters, and continuous effects already on it.
    """
    link = ctx.chain_link

    attack = link.active_attack
    if not attack.definition.is_attack_action:
        log.info(f"  Take Up the Mantle: no effect -- {attack.name} is not an attack action")
        return

    if not _has_stealth(attack, ctx):
        log.info(f"  Take Up the Mantle: no effect -- {attack.name} does not have Stealth")
        return

    # Check if attacking a marked hero
    defender = ctx.state.players[link.attack_target_index]
    if defender.is_marked:
        bonus = 3
        log.info(f"  Take Up the Mantle: {attack.name} gets +{bonus} power (marked target)")
        grant_power_bonus(ctx, attack, bonus, "Take Up the Mantle")

        # Find eligible stealth attack actions in graveyard
        controller = ctx.state.players[ctx.controller_index]
        stealth_in_gy = [
            c for c in controller.graveyard
            if c.definition.is_attack_action
            and Keyword.STEALTH in c.definition.keywords
        ]

        if stealth_in_gy:
            # "you may" — offer the choice
            options = [
                ActionOption(
                    action_id=f"banish_{c.instance_id}",
                    description=f"Banish {c.name} — target becomes a copy",
                    action_type=ActionType.ACTIVATE_ABILITY,
                    card_instance_id=c.instance_id,
                )
                for c in stealth_in_gy
            ]
            options.append(ActionOption(
                action_id="pass",
                description="Do not banish a card",
                action_type=ActionType.PASS,
            ))
            decision = Decision(
                player_index=ctx.controller_index,
                decision_type=DecisionType.CHOOSE_TARGET,
                prompt="Take Up the Mantle: banish a stealth attack from graveyard?",
                options=options,
            )
            response = ctx.ask(decision)

            if response.first and response.first != "pass":
                banish_id = int(response.first.replace("banish_", ""))
                banish_card = next(
                    (c for c in stealth_in_gy if c.instance_id == banish_id),
                    None,
                )
                if banish_card is not None:
                    # Banish the chosen card from graveyard
                    ctx.banish_card(banish_card, ctx.controller_index)

                    # Target becomes a copy of the banished card
                    old_name = attack.name
                    attack.definition_override = banish_card.definition
                    log.info(
                        f"  Take Up the Mantle: {old_name} becomes a copy of "
                        f"{banish_card.definition.name}"
                    )
    else:
        bonus = 2
        log.info(f"  Take Up the Mantle: {attack.name} gets +{bonus} power")
        grant_power_bonus(ctx, attack, bonus, "Take Up the Mantle")


@require_active_attack
def _tarantula_toxin(ctx: AbilityContext) -> None:
    """Tarantula Toxin (Assassin, Attack Reaction):

    'Choose 1 or both;
     * Target dagger attack gets +3{p}.
     * Target card defending an attack with stealth gets -3{d} this turn.'

    NOTE: Only Red variant in the deck. The CSV only shows Red with +3/-3.
    """
    link = ctx.chain_link

    attack = link.active_attack
    bonus = 3  # Red only in this deck

    mode1_valid = _is_dagger_attack(attack, link)
    mode2_valid = _has_stealth(attack, ctx) and bool(link.defending_cards)

    if not mode1_valid and not mode2_valid:
        log.info(f"  Tarantula Toxin: no valid mode")
        return

    # If both valid, choose
    apply_mode1 = False
    apply_mode2 = False

    if mode1_valid and mode2_valid:
        options = [
            ActionOption(action_id="mode_1", description=f"Dagger attack gets +{bonus} power",
                         action_type=ActionType.ACTIVATE_ABILITY),
            ActionOption(action_id="mode_2", description=f"Defending card gets -{bonus} defense",
                         action_type=ActionType.ACTIVATE_ABILITY),
            ActionOption(action_id="mode_both", description=f"Both: +{bonus} power and -{bonus} defense",
                         action_type=ActionType.ACTIVATE_ABILITY),
        ]
        decision = Decision(
            player_index=ctx.controller_index,
            decision_type=DecisionType.CHOOSE_MODE,
            prompt="Tarantula Toxin: Choose 1 or both",
            options=options,
        )
        response = ctx.ask(decision)
        choice = response.first or "mode_both"
        apply_mode1 = choice in ("mode_1", "mode_both")
        apply_mode2 = choice in ("mode_2", "mode_both")
    elif mode1_valid:
        apply_mode1 = True
    elif mode2_valid:
        apply_mode2 = True

    atk_id = attack.instance_id
    if apply_mode1:
        effect = make_power_modifier(
            bonus,
            ctx.controller_index,
            source_instance_id=ctx.source_card.instance_id,
            duration=EffectDuration.END_OF_COMBAT,
            target_filter=lambda c, _id=atk_id: c.instance_id == _id,
        )
        ctx.effect_engine.add_continuous_effect(ctx.state, effect)
        log.info(f"  Tarantula Toxin: {attack.name} gets +{bonus} power")

    if apply_mode2 and link.defending_cards:
        # Target the first defending card (simplified)
        defender_card = link.defending_cards[0]
        def_id = defender_card.instance_id
        effect = make_defense_modifier(
            -bonus,
            ctx.controller_index,
            source_instance_id=ctx.source_card.instance_id,
            duration=EffectDuration.END_OF_COMBAT,
            target_filter=lambda c, _id=def_id: c.instance_id == _id,
        )
        ctx.effect_engine.add_continuous_effect(ctx.state, effect)
        log.info(f"  Tarantula Toxin: {defender_card.name} gets -{bonus} defense")


# ---------------------------------------------------------------------------
# Defense Reactions / Traps
# ---------------------------------------------------------------------------


@require_active_attack
def _den_of_the_spider(ctx: AbilityContext) -> None:
    """Den of the Spider (Assassin/Warrior, Defense Reaction, Trap):

    'When this defends an attack with {p} greater than its base, mark the
     attacking hero.'

    The trap condition is checked at resolution: if the active attack's
    modified power is greater than its base power, mark the attacker.
    """
    link = ctx.chain_link

    attack = link.active_attack
    base_power = attack.definition.power or 0
    modified_power = ctx.effect_engine.get_modified_power(ctx.state, attack)

    if modified_power > base_power:
        mark_attacker(ctx, link, "Den of the Spider")
    else:
        log.info(f"  Den of the Spider: no effect (power {modified_power} <= base {base_power})")


@require_active_attack
def _lair_of_the_spider(ctx: AbilityContext) -> None:
    """Lair of the Spider (Assassin/Ninja, Defense Reaction, Trap):

    'When this defends an attack with go again, mark the attacking hero.'
    """
    link = ctx.chain_link

    attack = link.active_attack
    kws = ctx.effect_engine.get_modified_keywords(ctx.state, attack)

    if Keyword.GO_AGAIN in kws:
        mark_attacker(ctx, link, "Lair of the Spider")
    else:
        log.info(f"  Lair of the Spider: no effect (attack has no Go Again)")


@require_active_attack
def _frailty_trap(ctx: AbilityContext) -> None:
    """Frailty Trap (Assassin/Ranger, Defense Reaction, Trap):

    'When this defends an attack with go again, create a Frailty token under
     the attacking hero's control.'
    """
    link = ctx.chain_link

    attack = link.active_attack
    kws = ctx.effect_engine.get_modified_keywords(ctx.state, attack)

    if Keyword.GO_AGAIN in kws:
        attacker_index = 1 - link.attack_target_index
        create_token(
            ctx.state, attacker_index, "Frailty", SubType.AURA,
            functional_text="Your attack action cards played from arsenal and weapon attacks have -1{p}. At the beginning of your end phase destroy Frailty.",
            type_text="Token - Aura",
            event_bus=ctx.events, effect_engine=ctx.effect_engine,
        )
        log.info(f"  Frailty Trap: Created Frailty token for {ctx.player_name(attacker_index)}")
    else:
        log.info(f"  Frailty Trap: no effect (attack has no Go Again)")


@require_active_attack
def _inertia_trap(ctx: AbilityContext) -> None:
    """Inertia Trap (Assassin/Ranger, Defense Reaction, Trap):

    'When this defends an attack with {p} greater than its base, create an
     Inertia token under the attacking hero's control.'
    """
    link = ctx.chain_link

    attack = link.active_attack
    base_power = attack.definition.power or 0
    modified_power = ctx.effect_engine.get_modified_power(ctx.state, attack)

    if modified_power > base_power:
        attacker_index = 1 - link.attack_target_index
        create_token(
            ctx.state, attacker_index, "Inertia", SubType.AURA,
            functional_text="At the beginning of your end phase, destroy Inertia, then put all cards from your hand and arsenal on the bottom of your deck.",
            type_text="Token - Aura",
            event_bus=ctx.events, effect_engine=ctx.effect_engine,
        )
        log.info(
            f"  Inertia Trap: Created Inertia token for {ctx.player_name(attacker_index)} "
            f"(power {modified_power} > base {base_power})"
        )
    else:
        log.info(f"  Inertia Trap: no effect (power {modified_power} <= base {base_power})")


# ---------------------------------------------------------------------------
# Non-Attack Actions (on_play)
# ---------------------------------------------------------------------------


def _cut_from_the_same_cloth(ctx: AbilityContext) -> None:
    """Cut from the Same Cloth (Assassin/Warrior, Non-Attack Action):

    'Target opposing hero reveals their hand. If an attack reaction card is
     revealed this way, mark them.

     Your next dagger attack this turn gets +N{p}.'
    Red=+4, Yellow=+3, Blue=+2. Go again (keyword, handled by engine).
    """
    opponent_index = 1 - ctx.controller_index
    opponent = ctx.state.players[opponent_index]

    # Reveal hand and check for attack reaction
    has_ar = any(c.definition.is_attack_reaction for c in opponent.hand)
    if has_ar:
        opponent.is_marked = True
        log.info(f"  Cut from the Same Cloth: Marked {ctx.player_name(opponent_index)} (has attack reaction)")
    else:
        log.info(f"  Cut from the Same Cloth: No attack reaction found in opponent's hand")

    # Next dagger attack this turn gets +N power
    bonus = color_bonus(ctx, plus_one=True)
    _grant_next_dagger_attack_bonus(ctx, bonus, "Cut from the Same Cloth")


def _grant_next_dagger_attack_bonus(ctx: AbilityContext, bonus: int, source_name: str) -> None:
    """Grant +N power to the controller's next dagger attack this turn.

    Uses :func:`make_once_filter` so the bonus sticks to the first matching
    dagger and remains stable across repeated effect-engine queries.
    """
    controller = ctx.controller_index
    source_id = ctx.source_card.instance_id

    target_filter = make_once_filter(lambda card: (
        card.zone == Zone.COMBAT_CHAIN
        and card.owner_index == controller
        and (SubType.DAGGER in card.definition.subtypes or card.is_proxy)
    ))

    effect = make_power_modifier(
        bonus,
        controller,
        source_instance_id=source_id,
        duration=EffectDuration.END_OF_TURN,
        target_filter=target_filter,
    )
    ctx.effect_engine.add_continuous_effect(ctx.state, effect)
    log.info(f"  {source_name}: Next dagger attack gets +{bonus} power")


def _codex_template(
    ctx: AbilityContext,
    codex_name: str,
    arsenal_fn,
    debuff_token_name: str,
    debuff_token_text: str,
) -> None:
    """Shared template for Codex of Frailty / Codex of Inertia.

    Both follow the same structure:
    1. Each hero arsenals a card via *arsenal_fn* and discards if they do.
    2. Create a Ponder token for controller.
    3. Create a debuff token for the opponent.
    """
    for i, player in enumerate(ctx.state.players):
        arsenalled = arsenal_fn(player, i, codex_name)
        if arsenalled and player.hand:
            pname = ctx.player_name(i)
            if len(player.hand) == 1:
                discarded = player.hand[0]
            else:
                options = [
                    ActionOption(
                        action_id=f"discard_{c.instance_id}",
                        description=f"Discard {c.name}{c.definition.color_label}",
                        action_type=ActionType.PASS,
                        card_instance_id=c.instance_id,
                    )
                    for c in player.hand
                ]
                decision = Decision(
                    player_index=i,
                    decision_type=DecisionType.CHOOSE_MODE,
                    prompt=f"{codex_name}: Choose a card to discard",
                    options=options,
                    min_selections=1,
                    max_selections=1,
                )
                response = ctx.ask(decision)
                chosen_id = int(response.first.replace("discard_", "")) if response.first else player.hand[0].instance_id
                discarded = next((c for c in player.hand if c.instance_id == chosen_id), player.hand[0])
            move_card(discarded, player.hand, player.graveyard, Zone.GRAVEYARD)
            log.info(f"  {codex_name}: {pname} discards {discarded.name}")

    create_token(
        ctx.state, ctx.controller_index, "Ponder", SubType.AURA,
        functional_text="At the beginning of your end phase, destroy Ponder and draw a card.",
        type_text="Token - Aura",
        event_bus=ctx.events, effect_engine=ctx.effect_engine,
    )
    opponent_index = 1 - ctx.controller_index
    create_token(
        ctx.state, opponent_index, debuff_token_name, SubType.AURA,
        functional_text=debuff_token_text,
        type_text="Token - Aura",
        event_bus=ctx.events, effect_engine=ctx.effect_engine, ask=ctx.ask,
    )
    log.info(f"  {codex_name}: Created Ponder for {ctx.player_name(ctx.controller_index)}, {debuff_token_name} for {ctx.player_name(opponent_index)}")


def _codex_of_frailty(ctx: AbilityContext) -> None:
    """Codex of Frailty (Assassin/Ranger, Non-Attack Action):

    'Each hero puts an attack action card from their graveyard face down
     into their arsenal. Each hero that does, discards a card.

     Create a Ponder token under your control and a Frailty token under
     each opponent's control.'

    Go again (keyword, handled by engine).
    """
    def _arsenal_from_graveyard(player, i, name):
        attack_actions = [c for c in player.graveyard if c.definition.is_attack_action]
        if attack_actions and len(player.arsenal) < 1:
            chosen = attack_actions[0]
            player.graveyard.remove(chosen)
            chosen.zone = Zone.ARSENAL
            chosen.face_up = False
            player.arsenal.append(chosen)
            pn = player.hero.definition.name.split(",")[0] if player.hero else f"Player {i}"
            log.info(f"  {name}: {pn} arsenals {chosen.name} from graveyard")
            return True
        return False

    _codex_template(
        ctx, "Codex of Frailty", _arsenal_from_graveyard,
        "Frailty",
        "Your attack action cards played from arsenal and weapon attacks have -1{p}. At the beginning of your end phase destroy Frailty.",
    )


def _codex_of_inertia(ctx: AbilityContext) -> None:
    """Codex of Inertia (Assassin/Ranger, Non-Attack Action):

    'Each hero puts the top card of their deck face down into their arsenal.
     Each hero that does, discards a card.

     Create a Ponder token under your control and an Inertia token under
     each opponent's control.'

    Go again (keyword, handled by engine).
    """
    def _arsenal_from_deck(player, i, name):
        if player.deck and len(player.arsenal) < 1:
            top = player.deck.pop(0)
            top.zone = Zone.ARSENAL
            top.face_up = False
            player.arsenal.append(top)
            pn = player.hero.definition.name.split(",")[0] if player.hero else f"Player {i}"
            log.info(f"  {name}: {pn} arsenals top card face down")
            return True
        return False

    _codex_template(
        ctx, "Codex of Inertia", _arsenal_from_deck,
        "Inertia",
        "At the beginning of your end phase, destroy Inertia, then put all cards from your hand and arsenal on the bottom of your deck.",
    )


def _relentless_pursuit(ctx: AbilityContext) -> None:
    """Relentless Pursuit (Generic, Non-Attack Action):

    'Mark target opposing hero.
     If you've attacked them this turn, put this on the bottom of its
     owner's deck.'

    Go again (keyword, handled by engine).
    """
    opponent_index = 1 - ctx.controller_index
    ctx.state.players[opponent_index].is_marked = True
    log.info(f"  Relentless Pursuit: Marked {ctx.player_name(opponent_index)}")

    # If we've attacked this turn, put this on the bottom of the deck
    player = ctx.state.players[ctx.controller_index]
    if player.turn_counters.has_attacked:
        # The card is about to go to graveyard from _resolve_stack.
        # We need to intercept: move it to the bottom of the deck instead.
        # Since on_play fires BEFORE graveyard in _resolve_stack, we set
        # a flag on the card to redirect it.
        # Simplified approach: move it now and mark zone so graveyard move is skipped
        # Actually, the card is still on the stack at this point. After on_play
        # returns, _resolve_stack will move it to graveyard. We can't prevent that
        # from inside the handler easily.
        # Best approach: move it from graveyard to deck bottom after the fact.
        # We'll use a one-shot trigger on the next event.
        # For now, simplified: just move it to bottom of deck directly and hope
        # the graveyard move finds it gone.
        # Actually the card is on the STACK, _resolve_stack will try move_card
        # which calls remove_card + append to graveyard. If we put it in deck
        # first, remove_card won't find it in the stack.
        # Let's set a marker so we know to redirect.
        ctx.source_card._redirect_to_deck_bottom = True  # type: ignore[attr-defined]
        log.info(f"  Relentless Pursuit: Will return to bottom of deck (attacked this turn)")


def _up_sticks_and_run(ctx: AbilityContext) -> None:
    """Up Sticks and Run (Assassin/Ninja, Non-Attack Action):

    'You may retrieve a dagger from your graveyard.
     Your next dagger attack this turn gets +N{p}.'
    Red=+4, Yellow=+3, Blue=+2. Go again (keyword).
    """
    # Retrieve a dagger from graveyard
    def dagger_filter(card):
        return SubType.DAGGER in card.definition.subtypes

    ctx.keyword_engine.perform_retrieve(ctx.state, ctx.controller_index, dagger_filter)

    # Next dagger attack bonus
    bonus = color_bonus(ctx, plus_one=True)
    _grant_next_dagger_attack_bonus(ctx, bonus, "Up Sticks and Run")


def _orb_weaver_spinneret(ctx: AbilityContext) -> None:
    """Orb-Weaver Spinneret (Assassin, Non-Attack Action):

    'Equip a Graphene Chelicera token.
     Your next attack with stealth this turn gets +N{p}.'
    Red=+3, Yellow=+2, Blue=+1. Go again (keyword).

    Graphene Chelicera is created as a weapon token (Arms, Dagger, 1H)
    with power 1 and Go Again.  Once-per-turn is enforced by the
    weapon activation system (activated_this_turn flag).
    """
    # Create Graphene Chelicera as a weapon token
    _create_graphene_chelicera(ctx.state, ctx.controller_index)

    # Next stealth attack bonus — use make_once_filter so the bonus only
    # applies to the first matching stealth attack (not all of them).
    bonus = color_bonus(ctx)
    controller = ctx.controller_index
    source_id = ctx.source_card.instance_id

    # Note: ideally check Stealth via effect engine, but target_filter
    target_filter = make_once_filter(lambda card: (
        card.zone == Zone.COMBAT_CHAIN
        and card.owner_index == controller
        and Keyword.STEALTH in card._effective_definition.keywords
    ))

    effect = make_power_modifier(
        bonus,
        controller,
        source_instance_id=source_id,
        duration=EffectDuration.END_OF_TURN,
        target_filter=target_filter,
    )
    ctx.effect_engine.add_continuous_effect(ctx.state, effect)
    log.info(f"  Orb-Weaver Spinneret: Equipped Graphene Chelicera, next Stealth attack gets +{bonus} power")


def _savor_bloodshed(ctx: AbilityContext) -> None:
    """Savor Bloodshed (Assassin/Warrior, Non-Attack Action):

    'Your next dagger attack this turn gets +4{p}.
     The next time you hit a marked hero with a dagger this turn, draw a card.'

    Go again (keyword).
    NOTE: Only Red variant exists. +4 power.
    """
    bonus = 4  # Red only
    _grant_next_dagger_attack_bonus(ctx, bonus, "Savor Bloodshed")

    # Register one-shot trigger: next dagger hit on marked hero -> draw
    trigger = _SavorBloodshedDrawOnHit(
        controller_index=ctx.controller_index,
        _state_getter=lambda _s=ctx.state: _s,
        one_shot=True,
    )
    ctx.events.register_trigger(trigger)
    log.info(f"  Savor Bloodshed: Next dagger attack gets +{bonus} power, draw on hit if marked")


@dataclass
class _SavorBloodshedDrawOnHit(TriggeredEffect):
    """One-shot: next dagger hit on a marked hero this turn -> draw a card."""
    controller_index: int = 0
    _state_getter: object = None
    one_shot: bool = True

    def _get_state(self):
        if self._state_getter and callable(self._state_getter):
            return self._state_getter()
        return None

    def condition(self, event: GameEvent) -> bool:
        if event.event_type != EventType.HIT:
            return False
        if event.source is None:
            return False
        # Must be a dagger attack by controller
        if event.source.owner_index != self.controller_index:
            return False
        if SubType.DAGGER not in event.source.definition.subtypes:
            return False
        # Target must have been marked at the time of the hit.
        # Check pre-recorded state from event data first (set by _damage_step
        # before the HIT handler clears is_marked), then fall back to live
        # state for unit tests that emit HIT events directly.
        if event.target_player is None:
            return False
        was_marked = event.data.get("target_was_marked")
        if was_marked is not None:
            return was_marked
        # Fallback: check live state (only reached in unit tests)
        state = self._get_state()
        if state is None:
            return False
        return state.players[event.target_player].is_marked

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        state = self._get_state()
        if state is None:
            return None
        player = state.players[self.controller_index]
        if player.deck:
            log.info(f"  Savor Bloodshed: {get_player_name(state, self.controller_index)} draws a card (dagger hit marked hero)")
            return GameEvent(
                event_type=EventType.DRAW_CARD,
                target_player=self.controller_index,
            )
        return None


# ---------------------------------------------------------------------------
# Attack Actions — on_attack
# ---------------------------------------------------------------------------


def _pick_up_the_point_on_attack(ctx: AbilityContext) -> None:
    """Pick Up the Point (Assassin/Ninja, Attack Action):

    'When this attacks, you may retrieve a dagger from your graveyard.'
    Go again (keyword).
    """
    def dagger_filter(card):
        return SubType.DAGGER in card.definition.subtypes

    ctx.keyword_engine.perform_retrieve(ctx.state, ctx.controller_index, dagger_filter)
    log.info(f"  Pick Up the Point: Retrieved dagger (if available)")


@require_chain_link
def _whittle_from_bone_on_attack(ctx: AbilityContext) -> None:
    """Whittle from Bone (Assassin, Attack Action):

    'When this attacks a marked hero, equip a Graphene Chelicera token.'
    Stealth (keyword).
    """
    link = ctx.chain_link

    defender = ctx.state.players[link.attack_target_index]
    if defender.is_marked:
        _create_graphene_chelicera(ctx.state, ctx.controller_index)
        log.info(f"  Whittle from Bone: Equipped Graphene Chelicera (attacking marked hero)")
    else:
        log.info(f"  Whittle from Bone: no effect (target not marked)")


# ---------------------------------------------------------------------------
# Attack Actions — on_hit
# ---------------------------------------------------------------------------


@require_chain_link
def _kiss_of_death_on_hit(ctx: AbilityContext) -> None:
    """Kiss of Death (Assassin, Dagger Attack Action):

    'When this hits a hero, they lose 1{h}.'
    Stealth (keyword).
    """
    link = ctx.chain_link

    # Card text: "they lose 1 life" — life loss, not damage (bypasses prevention)
    ctx.events.emit(GameEvent(
        event_type=EventType.LOSE_LIFE,
        source=ctx.source_card,
        target_player=link.attack_target_index,
        amount=1,
    ))
    log.info(f"  Kiss of Death: {ctx.player_name(link.attack_target_index)} loses 1 life (now {ctx.state.players[link.attack_target_index].life_total})")


@require_chain_link
def _mark_of_the_black_widow_on_hit(ctx: AbilityContext) -> None:
    """Mark of the Black Widow (Assassin, Attack Action):

    'When this hits a marked hero, they banish a card from their hand.'
    Stealth (keyword).
    """
    link = ctx.chain_link

    target = ctx.state.players[link.attack_target_index]
    # Use pre-hit mark state: the HIT handler clears is_marked before
    # on_hit abilities run.  Fall back to live state for unit tests that
    # call _apply_card_ability directly without emitting a HIT event.
    was_marked = ctx.target_was_marked or target.is_marked
    if not was_marked:
        log.info(f"  Mark of the Black Widow: no effect (target not marked)")
        return

    if not target.hand:
        log.info(f"  Mark of the Black Widow: target has no cards in hand")
        return

    # Opponent chooses a card to banish (simplified: first card)
    banished_card = target.hand[0]
    ctx.banish_card(banished_card, link.attack_target_index)
    log.info(f"  Mark of the Black Widow: {ctx.player_name(link.attack_target_index)} banishes {banished_card.name}")


@require_chain_link
def _meet_madness_on_hit(ctx: AbilityContext) -> None:
    """Meet Madness (Chaos/Assassin, Attack Action):

    'When this hits a hero, choose 1 at random;
     - They choose a card in their hand. Banish it.
     - They choose a card in their arsenal. Banish it.
     - Banish the top card of their deck.'
    Stealth (keyword, in functional_text but not card keywords in CSV).
    """
    link = ctx.chain_link

    target_index = link.attack_target_index
    target = ctx.state.players[target_index]

    # Choose 1 at random from 3 options (use state RNG for reproducibility)
    modes = [1, 2, 3]
    chosen = ctx.state.rng.choice(modes)

    if chosen == 1 and target.hand:
        # They choose a card in hand to banish (simplified: first card)
        card = target.hand[0]
        ctx.banish_card(card, target_index)
        log.info(f"  Meet Madness: {ctx.player_name(target_index)} banishes {card.name} from hand")
    elif chosen == 2 and target.arsenal:
        card = target.arsenal[0]
        ctx.banish_card(card, target_index)
        log.info(f"  Meet Madness: {ctx.player_name(target_index)} banishes {card.name} from arsenal")
    elif chosen == 3 and target.deck:
        card = target.deck[0]
        ctx.banish_card(card, target_index)
        log.info(f"  Meet Madness: {ctx.player_name(target_index)} banishes {card.name} from top of deck")
    else:
        log.info(f"  Meet Madness: chosen mode {chosen} has no valid target")


def _under_the_trap_door_on_hit(ctx: AbilityContext) -> None:
    """Under the Trap-Door (Assassin, Attack Action):

    On-hit: No on-hit effect. The card's main ability is an Instant discard
    activation that banishes a trap from graveyard and lets you play it.
    The instant discard is implemented in _under_the_trap_door_instant().
    """
    # No on-hit effect for this card.
    pass


@require_chain_link
def _pain_in_the_backside_on_hit(ctx: AbilityContext) -> None:
    """Pain in the Backside (Assassin/Ninja, Attack Action):

    'When this hits a hero, target dagger you control deals 1 damage to them.
     If damage is dealt this way, the dagger has hit.'
    Go again (keyword).

    Implementation: player chooses a dagger, DEAL_DAMAGE event is emitted
    through the event pipeline (so prevention/replacement effects apply),
    and if damage is dealt, a HIT event is emitted for the dagger.
    """
    link = ctx.chain_link
    target_index = link.attack_target_index
    controller = ctx.state.players[ctx.controller_index]

    # Find daggers the controller owns
    daggers = [w for w in controller.weapons if SubType.DAGGER in w.definition.subtypes]

    if not daggers:
        log.info("  Pain in the Backside: No dagger found — no damage dealt")
        return

    dagger = choose_dagger(
        ctx, daggers, "Pain in the Backside: Choose a dagger to deal damage",
        decision_type="CHOOSE_TARGET",
    )

    actual_damage = deal_dagger_damage(ctx, dagger, target_index, link)
    if actual_damage > 0:
        log.info(
            f"  Pain in the Backside: {dagger.name} deals {actual_damage} damage "
            f"to {ctx.player_name(target_index)} (now {ctx.state.players[target_index].life_total})"
        )
    else:
        log.info(f"  Pain in the Backside: {dagger.name} damage was prevented")


@dataclass
class _LeaveNoWitnessesContractTrigger(TriggeredEffect):
    """Contract trigger: whenever an opponent's red card is banished, create a Silver.

    This is a persistent (not one-shot) trigger that lasts as long as Leave No
    Witnesses is relevant (registered on attack, not one-shot so it fires for
    every qualifying banish).  We make it one_shot=False so it fires for the
    on-hit banishes AND any future banishes this game.
    """

    controller_index: int = 0
    opponent_index: int = 0
    one_shot: bool = False
    _state_getter: object = None
    _event_bus_getter: object = None
    _effect_engine_getter: object = None

    def condition(self, event: GameEvent) -> bool:
        if event.event_type != EventType.BANISH:
            return False
        card = event.card
        if card is None:
            return False
        # Must be an opponent's card that is red
        if card.owner_index != self.opponent_index:
            return False
        return card.definition.color == Color.RED

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        if self._state_getter is None or not callable(self._state_getter):
            return None
        state = self._state_getter()
        event_bus = self._event_bus_getter() if self._event_bus_getter and callable(self._event_bus_getter) else None
        effect_engine = self._effect_engine_getter() if self._effect_engine_getter and callable(self._effect_engine_getter) else None
        _create_silver_token(state, self.controller_index, event_bus=event_bus, effect_engine=effect_engine)
        card_name = triggering_event.card.name if triggering_event.card else "unknown"
        log.info(
            f"  Leave No Witnesses: Contract completed — {card_name} is red, "
            f"created Silver token for P{self.controller_index}"
        )
        return None


def _leave_no_witnesses_on_attack(ctx: AbilityContext) -> None:
    """Leave No Witnesses (Assassin, Attack Action):

    'Contract - You are contracted to banish opponents' red cards.
     Whenever you complete this contract, create a Silver token.'

    Register the contract trigger when the card attacks.  The trigger
    persists for the rest of the game (Contract is a global ability).
    """
    link = ctx.chain_link
    if link is None:
        return

    opponent_index = link.attack_target_index
    trigger = _LeaveNoWitnessesContractTrigger(
        controller_index=ctx.controller_index,
        opponent_index=opponent_index,
        _state_getter=lambda _s=ctx.state: _s,
        _event_bus_getter=lambda _eb=ctx.events: _eb,
        _effect_engine_getter=lambda _ee=ctx.effect_engine: _ee,
    )
    ctx.events.register_trigger(trigger)
    log.info(f"  Leave No Witnesses: Contract registered — Silver on opponent red banish")


@require_chain_link
def _leave_no_witnesses_on_hit(ctx: AbilityContext) -> None:
    """Leave No Witnesses (Assassin, Attack Action):

    'When this hits a hero, banish the top card of their deck and up to 1
     card in their arsenal.'

    The Contract trigger is registered separately on_attack so it fires
    for ALL banishes of opponent red cards, not just on-hit banishes.
    """
    link = ctx.chain_link

    target_index = link.attack_target_index
    target = ctx.state.players[target_index]

    # Banish top card of deck
    if target.deck:
        card = target.deck[0]
        ctx.banish_card(card, target_index)
        log.info(f"  Leave No Witnesses: Banished {card.name} from top of P{target_index}'s deck")

    # Banish up to 1 card in their arsenal
    if target.arsenal:
        card = target.arsenal[0]
        ctx.banish_card(card, target_index)
        log.info(f"  Leave No Witnesses: Banished {card.name} from P{target_index}'s arsenal")


def _create_silver_token(
    state, controller_index: int, *, event_bus=None, effect_engine=None,
) -> CardInstance:
    """Create a Silver token as a permanent for the given player.

    Silver tokens are item tokens with:
    "Action - {r}{r}{r}, destroy Silver: Draw a card. Go again."
    """
    token = create_token(
        state,
        controller_index,
        name="Silver",
        subtype=SubType.ITEM,
        functional_text="Action - {r}{r}{r}, destroy Silver: Draw a card. Go again.",
        type_text="Token - Item",
        event_bus=event_bus,
        effect_engine=effect_engine,
    )
    return token


@require_chain_link
def _death_touch_on_hit(ctx: AbilityContext) -> None:
    """Death Touch (Assassin/Ranger, Attack Action):

    'Death Touch can't be played from hand.
     When this hits a hero, create a Frailty, Inertia, or Bloodrot Pox token
     under their control.'

    NOTE: "can't be played from hand" is enforced in ActionBuilder.can_play_card()
    (arsenal-only restriction).
    The controller chooses which token to create.
    """
    link = ctx.chain_link

    target_index = link.attack_target_index

    options = [
        ActionOption(action_id="frailty", description="Create Frailty token",
                     action_type=ActionType.ACTIVATE_ABILITY),
        ActionOption(action_id="inertia", description="Create Inertia token",
                     action_type=ActionType.ACTIVATE_ABILITY),
        ActionOption(action_id="bloodrot_pox", description="Create Bloodrot Pox token",
                     action_type=ActionType.ACTIVATE_ABILITY),
    ]
    decision = Decision(
        player_index=ctx.controller_index,
        decision_type=DecisionType.CHOOSE_MODE,
        prompt="Death Touch: Choose a token to create",
        options=options,
    )
    response = ctx.ask(decision)
    choice = response.first or "frailty"
    token_name = {"frailty": "Frailty", "inertia": "Inertia", "bloodrot_pox": "Bloodrot Pox"}.get(choice, "Frailty")

    # Map token names to their authoritative functional text
    _token_texts = {
        "Frailty": "Your attack action cards played from arsenal and weapon attacks have -1{p}. At the beginning of your end phase destroy Frailty.",
        "Inertia": "At the beginning of your end phase, destroy Inertia, then put all cards from your hand and arsenal on the bottom of your deck.",
        "Bloodrot Pox": "At the beginning of your end phase, destroy Bloodrot Pox, then it deals 2 damage to you unless you pay {r}{r}{r}.",
    }
    create_token(
        ctx.state, target_index, token_name, SubType.AURA,
        functional_text=_token_texts.get(token_name, ""),
        type_text="Token - Aura",
        event_bus=ctx.events, effect_engine=ctx.effect_engine, ask=ctx.ask,
    )
    log.info(f"  Death Touch: Created {token_name} token for {ctx.player_name(target_index)}")


@require_chain_link
def _persuasive_prognosis_on_hit(ctx: AbilityContext) -> None:
    """Persuasive Prognosis (Assassin, Attack Action):

    'When this hits a hero, banish the top card of their deck. Then look at
     their hand and banish a card with the same color as the banished card.
     Whenever this banishes an action card, gain 1{h}.'
    Stealth (keyword).
    """
    link = ctx.chain_link

    target_index = link.attack_target_index
    target = ctx.state.players[target_index]

    # Banish top card of deck
    if not target.deck:
        log.info(f"  Persuasive Prognosis: no cards in deck to banish")
        return

    top_card = target.deck[0]
    ctx.banish_card(top_card, target_index)
    banished_color = top_card.definition.color
    log.info(f"  Persuasive Prognosis: Banished {top_card.name} ({banished_color}) from deck")

    # If banished an action card, gain 1 life
    if top_card.definition.is_action:
        gain_life(ctx, ctx.controller_index, 1, "Persuasive Prognosis")

    # Look at hand, banish a card with same color
    if banished_color is not None:
        matching = [c for c in target.hand if c.definition.color == banished_color]
        if matching:
            card = matching[0]  # Simplified: first matching card
            ctx.banish_card(card, target_index)
            log.info(f"  Persuasive Prognosis: Banished {card.name} from hand (same color: {banished_color})")

            if card.definition.is_action:
                gain_life(ctx, ctx.controller_index, 1, "Persuasive Prognosis")


def _reapers_call_on_hit(ctx: AbilityContext) -> None:
    """Reaper's Call (Assassin, Attack Action):

    No on-hit effect. Main body is Stealth (keyword).
    The Instant discard activation is registered separately.
    """
    pass


def _reapers_call_instant(ctx: AbilityContext) -> None:
    """Reaper's Call (Assassin, Attack Action):

    'Instant - Discard this: Mark target opposing hero.'

    The card is already discarded (moved to graveyard) before this handler
    runs. We just need to mark the opposing hero.
    """
    opponent_index = 1 - ctx.controller_index
    ctx.state.players[opponent_index].is_marked = True
    log.info(
        f"  Reaper's Call: Marked {ctx.player_name(opponent_index)} (instant discard)"
    )


def _amulet_of_echoes_on_play(ctx: AbilityContext) -> None:
    """Amulet of Echoes (Generic, Item Action):

    'Go again' (keyword, handled by engine).
    'Instant - Destroy Amulet of Echoes: Target hero discards 2 cards.
     Activate this ability only if they have played 2 or more cards with
     the same name this turn.'

    The Go Again is a keyword handled by the stack layer.
    The Instant destroy ability is registered as a permanent_instant_effect.
    """
    # Item enters as a permanent (handled by _resolve_stack).
    # No on-play effect beyond Go Again (keyword).
    log.info(f"  Amulet of Echoes: Enters the arena")


def _amulet_of_echoes_instant(ctx: AbilityContext) -> None:
    """Amulet of Echoes instant activation:

    'Instant - Destroy Amulet of Echoes: Target hero discards 2 cards.
     Activate this ability only if they have played 2 or more cards with
     the same name this turn.'

    Preconditions are checked by ActionBuilder._can_use_permanent_instant().
    This handler destroys the Amulet and forces the target to discard 2 cards.
    """
    player = ctx.state.players[ctx.controller_index]
    # Choose target hero (opponent by default for competitive play)
    opponent_index = 1 - ctx.controller_index

    # Destroy the Amulet
    amulet = ctx.source_card
    if amulet in player.permanents:
        player.permanents.remove(amulet)
        amulet.zone = Zone.GRAVEYARD
        player.graveyard.append(amulet)
        log.info(f"  Amulet of Echoes: Destroyed")

    # Target hero discards 2 cards
    target = ctx.state.players[opponent_index]
    cards_to_discard = min(2, len(target.hand))
    if cards_to_discard == 0:
        log.info(f"  Amulet of Echoes: P{opponent_index} has no cards to discard")
        return

    for _ in range(cards_to_discard):
        if not target.hand:
            break
        # Let the opponent choose which card to discard
        if len(target.hand) == 1:
            chosen = target.hand[0]
        else:
            discard_options = [
                ActionOption(
                    action_id=f"discard_{c.instance_id}",
                    description=f"Discard {c.name}",
                    action_type=ActionType.PLAY_CARD,
                    card_instance_id=c.instance_id,
                )
                for c in target.hand
            ]
            decision = Decision(
                player_index=opponent_index,
                decision_type=DecisionType.CHOOSE_TARGET,
                prompt="Amulet of Echoes: Choose a card to discard",
                options=discard_options,
            )
            response = ctx.ask(decision)
            chosen_id_str = response.selected_option_ids[0] if response.selected_option_ids else None
            chosen = None
            if chosen_id_str and chosen_id_str.startswith("discard_"):
                try:
                    chosen_id = int(chosen_id_str.split("_", 1)[1])
                    chosen = next((c for c in target.hand if c.instance_id == chosen_id), None)
                except (ValueError, StopIteration):
                    pass
            if chosen is None:
                chosen = target.hand[0]

        move_card(chosen, target.hand, target.graveyard, Zone.GRAVEYARD)
        log.info(f"  Amulet of Echoes: P{opponent_index} discards {chosen.name}")


@require_active_attack
def _overcrowded_on_attack(ctx: AbilityContext) -> None:
    """Overcrowded (Generic, Attack Action):

    'Ambush. When this attacks or defends, it gets +1{p} +1{d} for each
     different name among aura tokens in the arena.'
    """
    link = ctx.chain_link

    # Count unique aura token names in the entire arena
    aura_token_names: set[str] = set()
    for player in ctx.state.players:
        for perm in player.permanents:
            if (CardType.TOKEN in perm.definition.types and
                    SubType.AURA in perm.definition.subtypes):
                aura_token_names.add(perm.name)

    bonus = len(aura_token_names)
    if bonus == 0:
        log.info(f"  Overcrowded: no aura tokens in arena")
        return

    grant_power_bonus(ctx, link.active_attack, bonus, "Overcrowded")

    # +N defense
    atk_id = link.active_attack.instance_id
    def_effect = make_defense_modifier(
        bonus,
        ctx.controller_index,
        source_instance_id=ctx.source_card.instance_id,
        duration=EffectDuration.END_OF_COMBAT,
        target_filter=lambda c, _id=atk_id: c.instance_id == _id,
    )
    ctx.effect_engine.add_continuous_effect(ctx.state, def_effect)
    log.info(f"  Overcrowded: gets +{bonus}/+{bonus} ({bonus} aura token names)")


# ---------------------------------------------------------------------------
# Scar Tissue — on-hit trigger to mark the defending hero
# ---------------------------------------------------------------------------


@require_active_attack
def _scar_tissue(ctx: AbilityContext) -> None:
    """Scar Tissue (Assassin/Warrior, Attack Reaction):

    'Target dagger attack gets +N{p} and "When this hits a hero, mark them."'
    Red=+3, Yellow=+2, Blue=+1.
    """
    link = ctx.chain_link

    attack = link.active_attack
    if not _is_dagger_attack(attack, link):
        log.info(f"  Scar Tissue: no effect -- {attack.name} is not a dagger attack")
        return

    bonus = color_bonus(ctx)
    grant_power_bonus(ctx, attack, bonus, "Scar Tissue")

    hit_trigger = get_mark_on_hit_trigger_class()(
        attack_instance_id=attack.instance_id,
        target_player_index=link.attack_target_index,
        card_name="Scar Tissue",
        _state_getter=lambda _s=ctx.state: _s,
        one_shot=True,
    )
    ctx.events.register_trigger(hit_trigger)
    log.info(f"  Scar Tissue: {attack.name} gets +{bonus} power and mark on hit")


# ---------------------------------------------------------------------------
# Instant-from-hand (discard to activate)
# ---------------------------------------------------------------------------


def _under_the_trap_door_instant(ctx: AbilityContext) -> None:
    """Under the Trap-Door (Assassin, Attack Action):

    'Instant - Discard this: Banish target trap from your graveyard.
     If you do, you may play it this turn and if it would be put into
     the graveyard this turn, instead banish it.'

    This is the instant-discard ability. The card is already discarded
    (moved to graveyard) before this handler runs.
    """
    player = ctx.state.players[ctx.controller_index]

    # Find traps in graveyard
    traps = [c for c in player.graveyard if SubType.TRAP in c.definition.subtypes]
    if not traps:
        log.info("  Under the Trap-Door: no traps in graveyard")
        return

    # Player chooses which trap to banish
    options = []
    for card in traps:
        options.append(ActionOption(
            action_id=f"banish_trap_{card.instance_id}",
            description=f"{card.name} ({card.definition.color_label})",
            action_type=ActionType.ACTIVATE_ABILITY,
            card_instance_id=card.instance_id,
        ))
    options.append(ActionOption(
        action_id="pass",
        description="Don't banish a trap",
        action_type=ActionType.PASS,
    ))

    decision = Decision(
        player_index=ctx.controller_index,
        decision_type=DecisionType.CHOOSE_TARGET,
        prompt="Under the Trap-Door: Choose a trap from your graveyard to banish",
        options=options,
    )
    response = ctx.ask(decision)
    choice = response.first

    if choice is None or choice == "pass":
        log.info("  Under the Trap-Door: chose not to banish a trap")
        return

    instance_id = int(choice.replace("banish_trap_", ""))
    target = next((c for c in traps if c.instance_id == instance_id), None)
    if target is None:
        log.warning("  Under the Trap-Door: chosen trap not found")
        return

    # Banish the trap from graveyard (face-up, uses context helper for BANISH event)
    ctx.banish_card(target, ctx.controller_index, face_down=False)
    log.info(f"  Under the Trap-Door: banished {target.name} from graveyard")

    # Mark as playable from banish this turn
    player.playable_from_banish.append(BanishPlayability(target.instance_id, EXPIRY_END_OF_TURN, True))
    log.info(f"  Under the Trap-Door: {target.name} playable from banish this turn")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_assassin_abilities(registry: AbilityRegistry) -> None:
    """Register all Assassin card abilities with the given registry."""

    # Attack reactions
    registry.register("attack_reaction_effect", "Incision", _incision)
    registry.register("attack_reaction_effect", "To the Point", _to_the_point)
    registry.register("attack_reaction_effect", "Scar Tissue", _scar_tissue)
    registry.register("attack_reaction_effect", "Stains of the Redback", _stains_of_the_redback)
    registry.register("attack_reaction_effect", "Shred", _shred)
    registry.register("attack_reaction_effect", "Take Up the Mantle", _take_up_the_mantle)
    registry.register("attack_reaction_effect", "Tarantula Toxin", _tarantula_toxin)

    # Defense reactions / traps
    registry.register("defense_reaction_effect", "Den of the Spider", _den_of_the_spider)
    registry.register("defense_reaction_effect", "Lair of the Spider", _lair_of_the_spider)
    registry.register("defense_reaction_effect", "Frailty Trap", _frailty_trap)
    registry.register("defense_reaction_effect", "Inertia Trap", _inertia_trap)

    # Non-attack actions (on_play)
    registry.register("on_play", "Cut from the Same Cloth", _cut_from_the_same_cloth)
    registry.register("on_play", "Codex of Frailty", _codex_of_frailty)
    registry.register("on_play", "Codex of Inertia", _codex_of_inertia)
    registry.register("on_play", "Relentless Pursuit", _relentless_pursuit)
    registry.register("on_play", "Up Sticks and Run", _up_sticks_and_run)
    registry.register("on_play", "Orb-Weaver Spinneret", _orb_weaver_spinneret)
    registry.register("on_play", "Savor Bloodshed", _savor_bloodshed)

    # Item permanent (on_play for logging)
    registry.register("on_play", "Amulet of Echoes", _amulet_of_echoes_on_play)

    # Attack actions — on_attack
    registry.register("on_attack", "Pick Up the Point", _pick_up_the_point_on_attack)
    registry.register("on_attack", "Whittle from Bone", _whittle_from_bone_on_attack)
    registry.register("on_attack", "Overcrowded", _overcrowded_on_attack)
    registry.register("on_attack", "Leave No Witnesses", _leave_no_witnesses_on_attack)

    # Attack actions — on_hit
    registry.register("on_hit", "Kiss of Death", _kiss_of_death_on_hit)
    registry.register("on_hit", "Mark of the Black Widow", _mark_of_the_black_widow_on_hit)
    registry.register("on_hit", "Meet Madness", _meet_madness_on_hit)
    registry.register("on_hit", "Pain in the Backside", _pain_in_the_backside_on_hit)
    registry.register("on_hit", "Leave No Witnesses", _leave_no_witnesses_on_hit)
    registry.register("on_hit", "Death Touch", _death_touch_on_hit)
    registry.register("on_hit", "Persuasive Prognosis", _persuasive_prognosis_on_hit)

    # Instant-from-hand (discard to activate)
    registry.register("instant_discard_effect", "Reaper's Call", _reapers_call_instant)
    registry.register("instant_discard_effect", "Under the Trap-Door", _under_the_trap_door_instant)

    # Permanent instants (destroy to activate)
    registry.register("permanent_instant_effect", "Amulet of Echoes", _amulet_of_echoes_instant)


def _stains_of_the_redback_cost_modifier(state, card, current_cost: int) -> int:
    """Stains of the Redback costs {r} less if the defending hero is marked."""
    opponent_index = 1 - card.owner_index
    if (
        0 <= opponent_index < len(state.players)
        and state.players[opponent_index].is_marked
    ):
        return current_cost - 1
    return current_cost


def register_assassin_cost_modifiers(effect_engine) -> None:
    """Register intrinsic cost modifiers for Assassin cards."""
    effect_engine.register_intrinsic_cost_modifier(
        "Stains of the Redback", _stains_of_the_redback_cost_modifier
    )
