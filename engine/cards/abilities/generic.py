"""Generic card ability implementations.

Registers ability handlers for commonly-used attack and defense reactions.
Each handler receives an AbilityContext and applies its effect.

Card texts verified against data/cards.tsv functional_text field.
"""

from __future__ import annotations

import logging

from engine.cards.abilities._helpers import (
    color_bonus,
    draw_card,
    grant_power_bonus,
    make_instance_id_filter,
    move_card,
    require_active_attack,
)
from engine.rules.abilities import AbilityContext, AbilityRegistry
from engine.rules.actions import ActionOption, Decision, PlayerResponse
from engine.rules.continuous import EffectDuration, make_keyword_grant, make_power_modifier
from engine.rules.events import EventType, GameEvent, TriggeredEffect
from engine.enums import ActionType, DecisionType, Keyword, SubType, SuperType, Zone

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Attack Reactions
# ---------------------------------------------------------------------------


@require_active_attack
def _ancestral_empowerment(ctx: AbilityContext) -> None:
    """Ancestral Empowerment (Red, Attack Reaction):

    'Target Ninja attack action card gains +1{p}. Draw a card.'

    Only applies if the active attack is a Ninja attack action card.
    """
    link = ctx.chain_link

    attack = link.active_attack
    # Check: must be a Ninja attack action card (use effect engine for supertypes)
    is_ninja = SuperType.NINJA in ctx.effect_engine.get_modified_supertypes(ctx.state, attack)
    is_attack_action = attack.definition.is_attack_action
    if not (is_ninja and is_attack_action):
        log.info(
            f"  Ancestral Empowerment: no effect — {attack.name} is not a "
            f"Ninja attack action card"
        )
        return

    # +1 power via continuous effect on the active attack
    grant_power_bonus(ctx, attack, 1, "Ancestral Empowerment")

    # Draw a card
    draw_card(ctx, "Ancestral Empowerment")


@require_active_attack
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

    attack = link.active_attack

    # Determine +N from color
    bonus = color_bonus(ctx)

    # Check mode eligibility
    # Mode 1: dagger or sword weapon attack
    is_weapon_attack = attack.is_proxy  # weapon attacks are proxies
    has_dagger_or_sword = False
    if is_weapon_attack:
        atk_subtypes = ctx.effect_engine.get_modified_subtypes(ctx.state, attack)
        has_dagger_or_sword = bool(
            atk_subtypes & {SubType.DAGGER, SubType.SWORD}
        )
    # Also check the attack source (the weapon itself) if available
    if is_weapon_attack and link.attack_source:
        src_subtypes = ctx.effect_engine.get_modified_subtypes(ctx.state, link.attack_source)
        has_dagger_or_sword = has_dagger_or_sword or bool(
            src_subtypes & {SubType.DAGGER, SubType.SWORD}
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
        grant_power_bonus(ctx, attack, bonus, "Razor Reflex (weapon mode)")
    elif chosen_mode == 2:
        # +N power and "when this hits, it gets go again"
        grant_power_bonus(ctx, attack, bonus, "Razor Reflex (attack action mode)")

        # Register a one-shot HIT trigger that grants Go Again when this
        # attack hits. This is the correct "when this hits, it gets go again"
        # timing per the card text.
        hit_trigger = _RazorReflexGoAgainOnHit(
            attack_instance_id=atk_id,
            controller_index=ctx.controller_index,
            source_instance_id=ctx.source_card.instance_id,
            _effect_engine=ctx.effect_engine,
            _state_getter=lambda _s=ctx.state: _s,
            one_shot=True,
        )
        ctx.events.register_trigger(hit_trigger)


# ---------------------------------------------------------------------------
# On-Hit Triggers (registered by attack reactions)
# ---------------------------------------------------------------------------


from dataclasses import dataclass


@dataclass
class _RazorReflexGoAgainOnHit(TriggeredEffect):
    """One-shot trigger: when the specific attack hits, grant Go Again.

    Registered by Razor Reflex mode 2 to implement "when this hits,
    it gets go again" correctly at hit timing rather than immediately.
    """

    attack_instance_id: int = 0
    controller_index: int = 0
    source_instance_id: int | None = None
    one_shot: bool = True

    _effect_engine: object = None  # EffectEngine
    _state_getter: object = None  # callable returning GameState

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
        """Grant Go Again to the attack via continuous effect."""
        state = self._get_state()
        if self._effect_engine is None or state is None:
            return None

        go_again_effect = make_keyword_grant(
            frozenset({Keyword.GO_AGAIN}),
            self.controller_index,
            source_instance_id=self.source_instance_id,
            duration=EffectDuration.END_OF_COMBAT,
            target_filter=make_instance_id_filter(self.attack_instance_id),
        )
        self._effect_engine.add_continuous_effect(state, go_again_effect)
        log.info(f"  Razor Reflex: attack gets Go Again on hit")
        return None


# ---------------------------------------------------------------------------
# Defense Reactions
# ---------------------------------------------------------------------------


def _fate_foreseen(ctx: AbilityContext) -> None:
    """Fate Foreseen (Generic, Defense Reaction):

    'Opt 1'

    Triggers Opt 1 when played as a defense reaction.
    """
    ctx.keyword_engine.perform_opt(ctx.state, ctx.controller_index, 1)
    log.info(f"  Fate Foreseen: {ctx.player_name(ctx.controller_index)} performs Opt 1")


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
            move_card(card, player.hand, player.deck, Zone.DECK)
            log.info(
                f"  Sink Below: {ctx.player_name(ctx.controller_index)} puts "
                f"{card.name} on bottom of deck"
            )

            # Draw a card
            draw_card(ctx, "Sink Below")


def _shelter_from_the_storm_instant(ctx: AbilityContext) -> None:
    """Shelter from the Storm (Generic, Defense Reaction):

    'Instant — Discard Shelter from the Storm: The next 3 times you would
     be dealt damage this turn, prevent 1 of that damage.'

    Creates a ReplacementEffect that intercepts DEAL_DAMAGE events targeting
    this hero, reducing damage by 1 each time, for up to 3 instances.
    """
    from engine.rules.events import ReplacementEffect

    controller = ctx.controller_index

    class ShelterPrevention(ReplacementEffect):
        """Prevents 1 damage up to 3 times this turn."""

        def __init__(self, target_player: int, source_card):
            super().__init__(source=source_card, one_shot=False)
            self.target_player = target_player
            self.uses_remaining = 3

        def condition(self, event: GameEvent) -> bool:
            return (
                event.event_type == EventType.DEAL_DAMAGE
                and event.target_player == self.target_player
                and event.amount > 0
                and self.uses_remaining > 0
            )

        def replace(self, event: GameEvent) -> GameEvent:
            source_name = event.source.name if event.source else "unknown"
            event.amount = max(0, event.amount - 1)
            event.modified = True
            self.uses_remaining -= 1
            pname = ctx.player_name(self.target_player)
            if self.uses_remaining > 0:
                log.info(
                    f"  Shelter from the Storm: prevented 1 damage from {source_name} "
                    f"({self.uses_remaining} use(s) remaining for {pname})"
                )
            else:
                log.info(
                    f"  Shelter from the Storm: prevented 1 damage from {source_name} "
                    f"(expired for {pname})"
                )
                ctx.events.unregister_replacement(self)
            return event

    prevention = ShelterPrevention(controller, ctx.source_card)
    ctx.events.register_replacement(prevention)

    # Remove at end of turn — card says "this turn".
    # The prevention expires on the FIRST END_OF_TURN after registration,
    # regardless of which player's turn it is.  Shelter is played during the
    # opponent's turn as a defense reaction, so the turn player is the
    # opponent — not the controller.  Checking target_player == controller
    # would cause the prevention to persist incorrectly.
    expired = [False]

    def _expire_shelter(event: GameEvent) -> None:
        if not expired[0]:
            expired[0] = True
            ctx.events.unregister_replacement(prevention)

    ctx.events.register_handler(EventType.END_OF_TURN, _expire_shelter)

    log.info(
        f"  Shelter from the Storm: damage prevention active "
        f"(3 uses, {ctx.player_name(controller)})"
    )


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

    # Instant discard effects
    registry.register("instant_discard_effect", "Shelter from the Storm", _shelter_from_the_storm_instant)
