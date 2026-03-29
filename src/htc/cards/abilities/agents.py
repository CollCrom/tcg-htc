"""Agent of Chaos Demi-Hero ability implementations.

All 6 Agent of Chaos forms share "At the beginning of your end phase,
return to the brood" (revert to original hero). Each has unique abilities:

1. Arakni, Redback — AR: discard Assassin, +3 power; stealth => go again
2. Arakni, Black Widow — AR: discard Assassin, +3 power; stealth => on-hit banish from hand
3. Arakni, Funnel Web — AR: discard Assassin, +3 power; stealth => on-hit banish arsenal
4. Arakni, Tarantula — Passive: dagger hit => lose 1 life. AR: discard Assassin, dagger +3 power
5. Arakni, Orb-Weaver — Instant: discard Assassin, create Graphene Chelicera token,
   next stealth attack +3 power. (Cost reduction deferred.)
6. Arakni, Trap-Door — On-become: search deck for card, banish face-down.
   (Play-trap part deferred.)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from htc.cards.abilities._helpers import grant_power_bonus, grant_keyword
from htc.engine.abilities import AbilityContext, AbilityRegistry
from htc.engine.continuous import EffectDuration, make_keyword_grant, make_power_modifier
from htc.engine.events import EventType, GameEvent, TriggeredEffect

from htc.enums import (
    ActionType,
    CardType,
    DecisionType,
    Keyword,
    SubType,
    SuperType,
    Zone,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from htc.cards.instance import CardInstance
    from htc.engine.effects import EffectEngine
    from htc.engine.events import EventBus
    from htc.state.game_state import GameState

log = logging.getLogger(__name__)

# Tag used to identify agent-specific triggers for deregistration
AGENT_TRIGGER_TAG = "_agent_trigger_controller"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_assassin_card(card: CardInstance) -> bool:
    """Check if a card has the Assassin supertype."""
    return SuperType.ASSASSIN in card.definition.supertypes


def _is_dagger_attack(attack: CardInstance | None, link=None) -> bool:
    """Check if an attack is a dagger attack."""
    if attack is None:
        return False
    if SubType.DAGGER in attack.definition.subtypes:
        return True
    if attack.is_proxy and link and link.attack_source:
        if SubType.DAGGER in link.attack_source.definition.subtypes:
            return True
    return False


def _has_stealth(attack: CardInstance, effect_engine, state) -> bool:
    """Check if an attack has Stealth via effect engine."""
    kws = effect_engine.get_modified_keywords(state, attack)
    return Keyword.STEALTH in kws


def _discard_assassin_card(ctx: AbilityContext) -> CardInstance | None:
    """Prompt controller to discard an Assassin card from hand.

    Returns the discarded card, or None if no valid discard available.
    """
    from htc.engine.actions import ActionOption, Decision

    player = ctx.state.players[ctx.controller_index]
    assassin_cards = [c for c in player.hand if _is_assassin_card(c)]
    if not assassin_cards:
        return None

    options = [
        ActionOption(
            action_id=f"discard_{c.instance_id}",
            description=f"Discard {c.name}",
            action_type=ActionType.DISCARD,
            card_instance_id=c.instance_id,
        )
        for c in assassin_cards
    ]

    decision = Decision(
        player_index=ctx.controller_index,
        decision_type=DecisionType.CHOOSE_DISCARD,
        prompt="Choose an Assassin card to discard",
        options=options,
        min_selections=1,
        max_selections=1,
    )
    response = ctx.ask(decision)

    if response.first:
        chosen_id = int(response.first.replace("discard_", ""))
        for c in assassin_cards:
            if c.instance_id == chosen_id:
                player.hand.remove(c)
                c.zone = Zone.GRAVEYARD
                player.graveyard.append(c)
                log.info(
                    f"  Agent ability: Player {ctx.controller_index} "
                    f"discards {c.name}"
                )
                return c

    # Fallback: discard first available
    card = assassin_cards[0]
    player.hand.remove(card)
    card.zone = Zone.GRAVEYARD
    player.graveyard.append(card)
    log.info(
        f"  Agent ability: Player {ctx.controller_index} "
        f"discards {card.name} (fallback)"
    )
    return card


# ---------------------------------------------------------------------------
# Return to the Brood — shared by all 6 agents
# ---------------------------------------------------------------------------


@dataclass
class ReturnToBroodTrigger(TriggeredEffect):
    """At the beginning of your end phase, return to the brood.

    Reverts the player's hero to original_hero and deregisters agent triggers.
    """

    controller_index: int = 0
    one_shot: bool = False  # NOT one-shot; deregister_agent_triggers handles cleanup
    _game: object = None  # Game reference
    _fired: bool = False

    def condition(self, event: GameEvent) -> bool:
        if self._fired:
            return False
        if event.event_type != EventType.START_OF_END_PHASE:
            return False
        return event.target_player == self.controller_index

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        self._fired = True
        if self._game is not None:
            self._game._return_to_brood(self.controller_index)
        return None


# ---------------------------------------------------------------------------
# 1. Arakni, Redback — AR: +3 power, stealth => go again
# ---------------------------------------------------------------------------


def _redback_ar(ctx: AbilityContext) -> None:
    """Arakni, Redback attack reaction."""
    link = ctx.chain_link
    if link is None or link.active_attack is None:
        return

    attack = link.active_attack
    # Must be an Assassin attack
    if not _is_assassin_card(attack):
        return

    # Cost: discard an Assassin card
    discarded = _discard_assassin_card(ctx)
    if discarded is None:
        log.info("  Arakni, Redback: No Assassin card to discard")
        return

    # +3 power
    grant_power_bonus(ctx, attack, 3, "Arakni, Redback")

    # If stealth: grant Go Again
    if _has_stealth(attack, ctx.effect_engine, ctx.state):
        grant_keyword(ctx, attack, Keyword.GO_AGAIN, "Arakni, Redback")


# ---------------------------------------------------------------------------
# 2. Arakni, Black Widow — AR: +3 power, stealth => on-hit banish from hand
# ---------------------------------------------------------------------------


@dataclass
class _BlackWidowOnHitBanishHand(TriggeredEffect):
    """One-shot: when the attack hits, defender banishes a card from hand."""

    controller_index: int = 0
    attack_instance_id: int = 0
    one_shot: bool = True
    _state_getter: object = None

    def condition(self, event: GameEvent) -> bool:
        if event.event_type != EventType.HIT:
            return False
        if event.source is None:
            return False
        return event.source.instance_id == self.attack_instance_id

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        state = self._get_state()
        if state is None:
            return None

        target_index = triggering_event.target_player
        if target_index is None:
            return None

        target = state.players[target_index]
        if not target.hand:
            log.info("  Arakni, Black Widow on-hit: Defender has no cards in hand")
            return None

        # Banish a random card from defender's hand
        card = state.rng.choice(target.hand)
        target.hand.remove(card)
        card.zone = Zone.BANISHED
        target.banished.append(card)
        log.info(
            f"  Arakni, Black Widow on-hit: Player {target_index} "
            f"banishes {card.name} from hand"
        )
        return None

    def _get_state(self):
        if self._state_getter and callable(self._state_getter):
            return self._state_getter()
        return None


def _black_widow_ar(ctx: AbilityContext) -> None:
    """Arakni, Black Widow attack reaction."""
    link = ctx.chain_link
    if link is None or link.active_attack is None:
        return

    attack = link.active_attack
    if not _is_assassin_card(attack):
        return

    discarded = _discard_assassin_card(ctx)
    if discarded is None:
        log.info("  Arakni, Black Widow: No Assassin card to discard")
        return

    grant_power_bonus(ctx, attack, 3, "Arakni, Black Widow")

    if _has_stealth(attack, ctx.effect_engine, ctx.state):
        # Register on-hit trigger to banish from hand
        trigger = _BlackWidowOnHitBanishHand(
            controller_index=ctx.controller_index,
            attack_instance_id=attack.instance_id,
            _state_getter=lambda: ctx.state,
            one_shot=True,
        )
        ctx.events.register_trigger(trigger)
        log.info(
            f"  Arakni, Black Widow: {attack.name} gains "
            f"'when this hits, banish a card from hand'"
        )


# ---------------------------------------------------------------------------
# 3. Arakni, Funnel Web — AR: +3 power, stealth => on-hit banish arsenal
# ---------------------------------------------------------------------------


@dataclass
class _FunnelWebOnHitBanishArsenal(TriggeredEffect):
    """One-shot: when the attack hits, banish a card from defender's arsenal."""

    controller_index: int = 0
    attack_instance_id: int = 0
    one_shot: bool = True
    _state_getter: object = None

    def condition(self, event: GameEvent) -> bool:
        if event.event_type != EventType.HIT:
            return False
        if event.source is None:
            return False
        return event.source.instance_id == self.attack_instance_id

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        state = self._get_state()
        if state is None:
            return None

        target_index = triggering_event.target_player
        if target_index is None:
            return None

        target = state.players[target_index]
        if not target.arsenal:
            log.info("  Arakni, Funnel Web on-hit: Defender has no cards in arsenal")
            return None

        # Banish the card in arsenal (typically only 1)
        card = target.arsenal.pop(0)
        card.zone = Zone.BANISHED
        target.banished.append(card)
        log.info(
            f"  Arakni, Funnel Web on-hit: Player {target_index} "
            f"banishes {card.name} from arsenal"
        )
        return None

    def _get_state(self):
        if self._state_getter and callable(self._state_getter):
            return self._state_getter()
        return None


def _funnel_web_ar(ctx: AbilityContext) -> None:
    """Arakni, Funnel Web attack reaction."""
    link = ctx.chain_link
    if link is None or link.active_attack is None:
        return

    attack = link.active_attack
    if not _is_assassin_card(attack):
        return

    discarded = _discard_assassin_card(ctx)
    if discarded is None:
        log.info("  Arakni, Funnel Web: No Assassin card to discard")
        return

    grant_power_bonus(ctx, attack, 3, "Arakni, Funnel Web")

    if _has_stealth(attack, ctx.effect_engine, ctx.state):
        trigger = _FunnelWebOnHitBanishArsenal(
            controller_index=ctx.controller_index,
            attack_instance_id=attack.instance_id,
            _state_getter=lambda: ctx.state,
            one_shot=True,
        )
        ctx.events.register_trigger(trigger)
        log.info(
            f"  Arakni, Funnel Web: {attack.name} gains "
            f"'when this hits, banish a card from arsenal'"
        )


# ---------------------------------------------------------------------------
# 4. Arakni, Tarantula — Passive: dagger hit => 1 life loss.
#    AR: discard Assassin, dagger +3 power.
# ---------------------------------------------------------------------------


@dataclass
class TarantulaDaggerHitTrigger(TriggeredEffect):
    """Whenever a dagger you own hits a hero, they lose 1 life."""

    controller_index: int = 0
    one_shot: bool = False  # persists while agent form is active
    _state_getter: object = None
    _event_bus: object = None

    def condition(self, event: GameEvent) -> bool:
        if event.event_type != EventType.HIT:
            return False
        if event.source is None:
            return False
        if event.source.owner_index != self.controller_index:
            return False

        state = self._get_state()
        if state is None:
            return False

        # Check it's a dagger attack
        chain = state.combat_chain
        link = chain.chain_links[-1] if chain.chain_links else None
        return _is_dagger_attack(event.source, link)

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        """Cause the hit hero to lose 1 life (LOSE_LIFE, not DEAL_DAMAGE)."""
        target_index = triggering_event.target_player
        if target_index is None:
            return None

        log.info(
            f"  Arakni, Tarantula: Dagger hit — Player {target_index} loses 1 life"
        )
        # Return a LOSE_LIFE event to be emitted through the pipeline
        return GameEvent(
            event_type=EventType.LOSE_LIFE,
            source=triggering_event.source,
            target_player=target_index,
            amount=1,
        )

    def _get_state(self):
        if self._state_getter and callable(self._state_getter):
            return self._state_getter()
        return None


def _tarantula_ar(ctx: AbilityContext) -> None:
    """Arakni, Tarantula attack reaction: dagger +3 power."""
    link = ctx.chain_link
    if link is None or link.active_attack is None:
        return

    attack = link.active_attack
    # Must be a dagger attack (not Assassin — specifically daggers)
    if not _is_dagger_attack(attack, link):
        return

    discarded = _discard_assassin_card(ctx)
    if discarded is None:
        log.info("  Arakni, Tarantula: No Assassin card to discard")
        return

    grant_power_bonus(ctx, attack, 3, "Arakni, Tarantula")


# ---------------------------------------------------------------------------
# 5. Arakni, Orb-Weaver — Instant: discard Assassin, equip Graphene
#    Chelicera token, next stealth attack gets +3 power.
#    (Cost reduction deferred — requires cost modification infrastructure.)
# ---------------------------------------------------------------------------


@dataclass
class _OrbWeaverStealthBuff(TriggeredEffect):
    """One-shot: next stealth attack this turn gets +3 power."""

    controller_index: int = 0
    one_shot: bool = True
    _effect_engine: object = None
    _state_getter: object = None

    def condition(self, event: GameEvent) -> bool:
        if event.event_type != EventType.ATTACK_DECLARED:
            return False
        if event.source is None:
            return False
        if event.source.owner_index != self.controller_index:
            return False

        state = self._get_state()
        if state is None:
            return False

        # Must have Stealth
        kws = self._effect_engine.get_modified_keywords(state, event.source)
        return Keyword.STEALTH in kws

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        state = self._get_state()
        if state is None or self._effect_engine is None:
            return None

        atk = triggering_event.source
        if atk is None:
            return None

        atk_id = atk.instance_id
        effect = make_power_modifier(
            3,
            self.controller_index,
            source_instance_id=None,
            duration=EffectDuration.END_OF_COMBAT,
            target_filter=lambda c, _id=atk_id: c.instance_id == _id,
        )
        self._effect_engine.add_continuous_effect(state, effect)
        log.info(
            f"  Arakni, Orb-Weaver: Stealth attack {atk.name} gets +3 power"
        )
        return None

    def _get_state(self):
        if self._state_getter and callable(self._state_getter):
            return self._state_getter()
        return None


def _orb_weaver_instant(ctx: AbilityContext) -> None:
    """Arakni, Orb-Weaver instant: create Graphene Chelicera + stealth buff."""
    # Cost: discard an Assassin card
    discarded = _discard_assassin_card(ctx)
    if discarded is None:
        log.info("  Arakni, Orb-Weaver: No Assassin card to discard")
        return

    # Create Graphene Chelicera equipment token
    from htc.cards.abilities._helpers import create_token
    # TODO: Graphene Chelicerae is actually an equipment token that goes into
    # an equipment slot. For now we create it as a permanent token. Full
    # equipment-token support would need slot assignment and weapon activation.
    token = create_token(
        ctx.state,
        ctx.controller_index,
        "Graphene Chelicera",
        SubType.ARMS,
        functional_text="(Equipment token)",
        supertypes=frozenset({SuperType.ASSASSIN}),
    )
    log.info(
        f"  Arakni, Orb-Weaver: Created Graphene Chelicera token "
        f"for Player {ctx.controller_index}"
    )

    # Register one-shot trigger: next stealth attack this turn gets +3 power
    trigger = _OrbWeaverStealthBuff(
        controller_index=ctx.controller_index,
        one_shot=True,
        _effect_engine=ctx.effect_engine,
        _state_getter=lambda: ctx.state,
    )
    setattr(trigger, AGENT_TRIGGER_TAG, ctx.controller_index)
    ctx.events.register_trigger(trigger)
    log.info(
        f"  Arakni, Orb-Weaver: Next stealth attack this turn gets +3 power"
    )


# ---------------------------------------------------------------------------
# 6. Arakni, Trap-Door — On-become: search deck for card, banish face-down.
#    (Play-trap-until-start-of-next-turn deferred.)
# ---------------------------------------------------------------------------


@dataclass
class TrapDoorOnBecomeTrigger(TriggeredEffect):
    """When you become Arakni, Trap-Door, search deck for a card and banish it face-down."""

    controller_index: int = 0
    one_shot: bool = True  # fires once on transformation
    _state_getter: object = None
    _game: object = None

    def condition(self, event: GameEvent) -> bool:
        if event.event_type != EventType.BECOME_AGENT:
            return False
        if event.target_player != self.controller_index:
            return False
        # Only fire for Arakni, Trap-Door specifically
        return event.source is not None and event.source.name == "Arakni, Trap-Door"

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        state = self._get_state()
        if state is None or self._game is None:
            return None

        player = state.players[self.controller_index]
        if not player.deck:
            log.info("  Arakni, Trap-Door: Deck is empty, nothing to search")
            return None

        from htc.engine.actions import ActionOption, Decision

        # Let player choose any card from their deck
        options = [
            ActionOption(
                action_id=f"banish_{c.instance_id}",
                description=f"Banish {c.name}",
                action_type=ActionType.BANISH,
                card_instance_id=c.instance_id,
            )
            for c in player.deck
        ]

        decision = Decision(
            player_index=self.controller_index,
            decision_type=DecisionType.CHOOSE_CARD,
            prompt="Search your deck: choose a card to banish face-down",
            options=options,
            min_selections=1,
            max_selections=1,
        )
        response = self._game._ask(decision)

        chosen = None
        if response.first:
            chosen_id = int(response.first.replace("banish_", ""))
            for c in player.deck:
                if c.instance_id == chosen_id:
                    chosen = c
                    break

        if chosen is None:
            # Fallback: first card in deck
            chosen = player.deck[0]

        # Banish face-down
        player.deck.remove(chosen)
        chosen.zone = Zone.BANISHED
        chosen.face_up = False
        player.banished.append(chosen)

        # Shuffle deck after search
        state.rng.shuffle(player.deck)

        is_trap = SubType.TRAP in chosen.definition.subtypes
        log.info(
            f"  Arakni, Trap-Door: Banished {chosen.name} face-down"
            f"{' (Trap!)' if is_trap else ''}"
        )

        # TODO: If it's a Trap, allow playing it until start of next turn.
        # This requires infrastructure for "play from banish zone" permissions
        # and a duration that expires at START_OF_TURN.

        return None

    def _get_state(self):
        if self._state_getter and callable(self._state_getter):
            return self._state_getter()
        return None


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

# Maps agent name -> (AR handler name, AR handler function)
# AR handlers are registered in the AbilityRegistry; triggers go on EventBus.
_AGENT_AR_MAP: dict[str, tuple[str, object]] = {
    "Arakni, Redback": ("attack_reaction_effect", _redback_ar),
    "Arakni, Black Widow": ("attack_reaction_effect", _black_widow_ar),
    "Arakni, Funnel Web": ("attack_reaction_effect", _funnel_web_ar),
    "Arakni, Tarantula": ("attack_reaction_effect", _tarantula_ar),
    "Arakni, Orb-Weaver": ("equipment_instant_effect", _orb_weaver_instant),
}


def register_agent_abilities(
    agent_name: str,
    controller_index: int,
    event_bus: EventBus,
    effect_engine: EffectEngine,
    state_getter: object,
    ability_registry: AbilityRegistry,
    game: object = None,
) -> None:
    """Register abilities for a specific Agent of Chaos form.

    Called when a player transforms into an agent. Registers:
    - Return to brood trigger (all agents)
    - Agent-specific attack reactions or instants (via AbilityRegistry)
    - Agent-specific triggered effects (EventBus triggers)
    """
    # 1. Return to the brood (shared by all)
    brood_trigger = ReturnToBroodTrigger(
        controller_index=controller_index,
        _game=game,
    )
    setattr(brood_trigger, AGENT_TRIGGER_TAG, controller_index)
    event_bus.register_trigger(brood_trigger)

    # 2. Agent-specific abilities
    if agent_name in _AGENT_AR_MAP:
        timing, handler = _AGENT_AR_MAP[agent_name]
        # Register under the agent's hero name so ActionBuilder can find it
        ability_registry.register(timing, agent_name, handler)

    # 3. Agent-specific EventBus triggers
    if agent_name == "Arakni, Tarantula":
        trigger = TarantulaDaggerHitTrigger(
            controller_index=controller_index,
            one_shot=False,
            _state_getter=state_getter,
            _event_bus=event_bus,
        )
        setattr(trigger, AGENT_TRIGGER_TAG, controller_index)
        event_bus.register_trigger(trigger)
        log.info(
            f"  Registered Tarantula dagger-hit trigger for Player {controller_index}"
        )

    if agent_name == "Arakni, Trap-Door":
        trigger = TrapDoorOnBecomeTrigger(
            controller_index=controller_index,
            one_shot=True,
            _state_getter=state_getter,
            _game=game,
        )
        setattr(trigger, AGENT_TRIGGER_TAG, controller_index)
        event_bus.register_trigger(trigger)
        log.info(
            f"  Registered Trap-Door on-become trigger for Player {controller_index}"
        )

    log.info(f"  Registered {agent_name} abilities for Player {controller_index}")


def deregister_agent_triggers(event_bus: EventBus, controller_index: int) -> None:
    """Remove all agent-specific triggered effects for a player.

    Called during return-to-brood when the player reverts to original hero.
    Identifies triggers by the AGENT_TRIGGER_TAG attribute.
    """
    to_remove = [
        t for t in event_bus._triggered_effects
        if getattr(t, AGENT_TRIGGER_TAG, None) == controller_index
    ]
    for t in to_remove:
        event_bus.unregister_trigger(t)

    if to_remove:
        log.info(
            f"  Deregistered {len(to_remove)} agent trigger(s) "
            f"for Player {controller_index}"
        )
