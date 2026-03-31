"""Hero ability implementations as triggered effects.

Hero abilities are registered on the EventBus as TriggeredEffects during
game setup. They persist for the entire game (not one-shot).

Implemented heroes:
- Arakni, Marionette — stealth attacks vs marked heroes get +1 power
  and "when this hits, this gets go again"
- Cindra, Dracai of Retribution — whenever you hit a marked hero,
  create a Fealty token
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from htc.engine.continuous import EffectDuration, make_keyword_grant, make_power_modifier
from htc.engine.events import EventType, GameEvent, TriggeredEffect
from htc.enums import Keyword

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from htc.cards.instance import CardInstance
    from htc.engine.effects import EffectEngine
    from htc.engine.events import EventBus
    from htc.state.game_state import GameState

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Arakni, Marionette
# ---------------------------------------------------------------------------
# "Your attacks with stealth that are attacking a marked hero get +1{p}
#  and 'When this hits, this gets go again.'"
#
# Implementation:
# 1. Register an ATTACK_DECLARED trigger that checks stealth + marked.
# 2. When triggered, apply +1 power continuous effect AND register a
#    one-shot HIT trigger that grants Go Again on hit.


@dataclass
class ArakniMarionetteTrigger(TriggeredEffect):
    """Arakni, Marionette hero ability — fires on ATTACK_DECLARED.

    Checks if the attack has Stealth and the target hero is marked.
    If both, grants +1 power and registers a one-shot hit trigger
    for Go Again.
    """

    controller_index: int = 0
    one_shot: bool = False  # persists all game

    # These are injected at registration time
    _effect_engine: EffectEngine | None = None
    _event_bus: EventBus | None = None
    _state_getter: object = None  # callable returning GameState

    def condition(self, event: GameEvent) -> bool:
        if event.event_type != EventType.ATTACK_DECLARED:
            return False

        attacker_index = event.data.get("attacker_index")
        if attacker_index != self.controller_index:
            return False

        # Check: does the attack have Stealth?
        attack_card = event.source
        if attack_card is None or self._effect_engine is None:
            return False

        state = self._get_state()
        if state is None:
            return False

        attack_keywords = self._effect_engine.get_modified_keywords(state, attack_card)
        if Keyword.STEALTH not in attack_keywords:
            return False

        # Check: is the target hero marked?
        target_index = event.target_player
        if target_index is None:
            return False
        target_player = state.players[target_index]
        if not target_player.is_marked:
            return False

        return True

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        """Apply +1 power and register the on-hit Go Again trigger."""
        attack_card = triggering_event.source
        if attack_card is None or self._effect_engine is None:
            return None

        state = self._get_state()
        if state is None or self._event_bus is None:
            return None

        atk_id = attack_card.instance_id

        # +1 power continuous effect
        power_effect = make_power_modifier(
            1,
            self.controller_index,
            source_instance_id=None,  # hero ability, no specific source card
            duration=EffectDuration.END_OF_COMBAT,
            target_filter=lambda c, _id=atk_id: c.instance_id == _id,
        )
        self._effect_engine.add_continuous_effect(state, power_effect)
        log.info(
            f"  Arakni ability: {attack_card.name} gets +1 power "
            f"(stealth vs marked)"
        )

        # Register one-shot HIT trigger for Go Again
        hit_trigger = ArakniGoAgainOnHit(
            controller_index=self.controller_index,
            attack_instance_id=atk_id,
            _effect_engine=self._effect_engine,
            _state_getter=self._state_getter,
            one_shot=True,
        )
        self._event_bus.register_trigger(hit_trigger)

        # Return None — we applied effects directly, no event to re-emit
        return None

    def _get_state(self) -> GameState | None:
        if self._state_getter and callable(self._state_getter):
            return self._state_getter()
        return None


@dataclass
class ArakniGoAgainOnHit(TriggeredEffect):
    """One-shot trigger: when the specific attack hits, grant Go Again."""

    controller_index: int = 0
    attack_instance_id: int = 0
    one_shot: bool = True

    _effect_engine: EffectEngine | None = None
    _state_getter: object = None

    def condition(self, event: GameEvent) -> bool:
        if event.event_type != EventType.HIT:
            return False
        if event.source is None:
            return False
        return event.source.instance_id == self.attack_instance_id

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        """Grant Go Again to the attack via continuous effect."""
        if self._effect_engine is None:
            return None

        state = self._get_state()
        if state is None:
            return None

        atk_id = self.attack_instance_id
        go_again_effect = make_keyword_grant(
            frozenset({Keyword.GO_AGAIN}),
            self.controller_index,
            source_instance_id=None,
            duration=EffectDuration.END_OF_COMBAT,
            target_filter=lambda c, _id=atk_id: c.instance_id == _id,
        )
        self._effect_engine.add_continuous_effect(state, go_again_effect)
        log.info(
            f"  Arakni ability: attack gets Go Again on hit"
        )
        return None

    def _get_state(self) -> GameState | None:
        if self._state_getter and callable(self._state_getter):
            return self._state_getter()
        return None


# ---------------------------------------------------------------------------
# Cindra, Dracai of Retribution
# ---------------------------------------------------------------------------
# "Whenever you hit a marked hero, create a Fealty token."
#
# Implementation:
# Register a HIT trigger that checks if the target hero is marked
# (at the time of the hit). If so, create a Fealty token for the
# controller. Note: mark removal happens via _handle_hit_mark_removal
# which is a handler on the same HIT event — but handlers run before
# triggers are checked, so mark is already removed when the trigger
# fires. We need to check is_marked BEFORE the hit handler removes it.
#
# Solution: the trigger's condition checks the event data for the
# chain_link, which tells us the attack hit. The mark removal handler
# runs first, so we can't rely on is_marked in the trigger's condition.
# Instead, we track the "was marked at attack time" in the trigger.
# Actually — simpler approach: we register on ATTACK_DECLARED to note
# if the target was marked, then on HIT we use that info.
#
# Simplest correct approach: Use a two-stage trigger.
# Stage 1 (ATTACK_DECLARED): record whether target is marked.
# Stage 2 (HIT): if the target was marked at attack time, create token.
#
# Even simpler: mark removal and Cindra trigger both fire on HIT.
# Per rules 6.6, triggered effects are checked AFTER handlers execute.
# So is_marked is already False by the time we check. But Cindra's
# ability says "whenever you hit a marked hero" — the marked condition
# should be evaluated at the time the hit occurs, which is effectively
# when damage is dealt. The mark removal is also on hit, but Cindra's
# trigger should see the state as it was.
#
# Per FaB rules, the trigger condition is checked when the event occurs.
# The event bus processes: handlers first (state changes), then checks
# triggers. So by the time triggers are checked, mark is gone.
#
# Correct solution: check mark state at ATTACK_DECLARED time and store
# it, then create token on HIT. We'll use a compound approach.


@dataclass
class CindraRetributionTrigger(TriggeredEffect):
    """Cindra, Dracai of Retribution — whenever you hit a marked hero,
    create a Fealty token.

    Uses a two-phase approach:
    - On ATTACK_DECLARED, record if target is marked
    - On HIT, if target was marked, create the token
    """

    controller_index: int = 0
    one_shot: bool = False
    _target_was_marked: bool = False

    _effect_engine: EffectEngine | None = None
    _event_bus: EventBus | None = None
    _state_getter: object = None
    _game: object = None  # reference to Game for _make_fealty_token

    def condition(self, event: GameEvent) -> bool:
        if event.event_type == EventType.ATTACK_DECLARED:
            attacker_index = event.data.get("attacker_index")
            if attacker_index == self.controller_index:
                # Record marked state for HIT check
                target_index = event.target_player
                state = self._get_state()
                if state is not None and target_index is not None:
                    self._target_was_marked = state.players[target_index].is_marked
            return False  # don't fire a triggered event for this

        if event.event_type == EventType.HIT:
            if event.source is None:
                return False
            # Check the hit was by our attack
            source_owner = event.source.owner_index
            if source_owner != self.controller_index:
                return False
            return self._target_was_marked

        return False

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        """Create a Fealty token for the controller."""
        state = self._get_state()
        if state is None:
            return None

        # Reset the flag
        self._target_was_marked = False

        # Create Fealty token as a permanent for the controller
        player = state.players[self.controller_index]
        game = self._game
        if game is not None and hasattr(game, '_create_fealty_token'):
            game._create_fealty_token(self.controller_index)
        else:
            # Fallback: create a simple token representation
            _create_fealty_token_simple(state, self.controller_index)

        state = self._get_state()
        pname = state.players[self.controller_index].hero.definition.name.split(",")[0] if state and state.players[self.controller_index].hero else f"Player {self.controller_index}"
        log.info(
            f"  Cindra ability: {pname} creates a "
            f"Fealty token (hit marked hero)"
        )
        return None

    def _get_state(self) -> GameState | None:
        if self._state_getter and callable(self._state_getter):
            return self._state_getter()
        return None


def _create_fealty_token_simple(state: GameState, controller_index: int) -> None:
    """Create a minimal Fealty token as a permanent for the player.

    Tokens are represented as CardInstances with a synthetic definition.
    In a full implementation, we'd look up the Fealty token from the card
    database. For now, create a lightweight token.
    """
    from htc.cards.card import CardDefinition
    from htc.cards.instance import CardInstance
    from htc.enums import CardType, SubType, Zone

    token_def = CardDefinition(
        unique_id="fealty-token",
        name="Fealty",
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=None,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.TOKEN}),
        subtypes=frozenset({SubType.AURA}),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="Instant - Destroy this: The next card you play this turn is Draconic. At the beginning of your end phase, if you haven't created a Fealty token or played a Draconic card this turn, destroy this.",
        type_text="Draconic Token - Aura",
    )
    token = CardInstance(
        instance_id=state.next_instance_id(),
        definition=token_def,
        owner_index=controller_index,
        zone=Zone.PERMANENT,
    )
    state.players[controller_index].permanents.append(token)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


HERO_ABILITY_MAP: dict[str, type] = {
    "Arakni, Marionette": ArakniMarionetteTrigger,
    "Arakni, Web of Deceit": ArakniMarionetteTrigger,  # young version, same ability
    "Cindra, Dracai of Retribution": CindraRetributionTrigger,
    "Cindra": CindraRetributionTrigger,  # young version
}


def register_hero_abilities(
    hero_name: str,
    controller_index: int,
    event_bus: EventBus,
    effect_engine: EffectEngine,
    state_getter: object,
    game: object = None,
) -> None:
    """Register hero abilities as triggered effects on the EventBus.

    Called during game setup for each player's hero.
    """
    trigger_cls = HERO_ABILITY_MAP.get(hero_name)
    if trigger_cls is None:
        log.debug(f"  No hero ability registered for {hero_name}")
        return

    if trigger_cls is ArakniMarionetteTrigger:
        trigger = ArakniMarionetteTrigger(
            controller_index=controller_index,
            _effect_engine=effect_engine,
            _event_bus=event_bus,
            _state_getter=state_getter,
        )
        event_bus.register_trigger(trigger)
        log.info(f"  Registered Arakni Marionette ability for {hero_name.split(',')[0]}")

    elif trigger_cls is CindraRetributionTrigger:
        trigger = CindraRetributionTrigger(
            controller_index=controller_index,
            _effect_engine=effect_engine,
            _event_bus=event_bus,
            _state_getter=state_getter,
            _game=game,
        )
        # Cindra needs to listen to both ATTACK_DECLARED (to record mark state)
        # and HIT (to create token). We register once and handle both in condition().
        event_bus.register_trigger(trigger)
        log.info(f"  Registered Cindra ability for {hero_name.split(',')[0]}")
