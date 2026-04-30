"""Event system for Flesh and Blood game engine.

All game state changes flow through events. This enables:
- Triggered effects: fire after events occur
- Replacement effects: intercept and modify events before they happen
- Prevention effects: modify damage events

Events are emitted by the engine, processed through replacement effects,
executed to change game state, then checked for triggered effects.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from engine.cards.instance import CardInstance

log = logging.getLogger(__name__)


class EventType(Enum):
    """All event types in the game."""
    # Damage
    DEAL_DAMAGE = auto()
    DAMAGE_PREVENTED = auto()  # emitted when a replacement effect reduces DEAL_DAMAGE

    # Card movement
    DRAW_CARD = auto()
    PLAY_CARD = auto()
    DISCARD = auto()
    BANISH = auto()
    DESTROY = auto()

    # Combat
    ATTACK_DECLARED = auto()
    DEFEND_DECLARED = auto()
    HIT = auto()
    COMBAT_CHAIN_CLOSES = auto()

    # Turn structure
    START_OF_TURN = auto()
    END_OF_TURN = auto()
    START_OF_ACTION_PHASE = auto()

    # Resources
    GAIN_ACTION_POINT = auto()
    GAIN_RESOURCE_POINT = auto()
    PITCH_CARD = auto()

    # Life
    GAIN_LIFE = auto()
    LOSE_LIFE = auto()

    # Transformation
    BECOME_AGENT = auto()  # Demi-Hero transformation (Agent of Chaos)

    # Misc
    CREATE_TOKEN = auto()
    COUNTER_ADDED = auto()
    COUNTER_REMOVED = auto()


@dataclass
class GameEvent:
    """A game event that can be intercepted, modified, or trigger effects.

    Attributes:
        event_type: What kind of event this is.
        source: The card or object that caused this event (if any).
        target_player: The player index affected (if applicable).
        card: The card involved (if applicable).
        amount: Numeric value (damage amount, life gained, etc.).
        data: Additional event-specific data.
        cancelled: If True, the event was cancelled by a replacement effect.
        modified: If True, the event was modified by a replacement effect.
    """
    event_type: EventType
    source: CardInstance | None = None
    target_player: int | None = None
    card: CardInstance | None = None
    amount: int = 0
    data: dict[str, Any] = field(default_factory=dict)
    cancelled: bool = False
    modified: bool = False


class EventBus:
    """Central event dispatcher.

    Processes events through the pipeline:
    1. Check replacement effects (may modify or cancel the event)
    2. Execute the event (change game state)
    3. Check triggered effects (queue new layers)

    The actual game state changes are handled by the Game class via
    registered handlers. The EventBus just manages the flow.
    """

    def __init__(self) -> None:
        # Handlers called to execute the event (change game state)
        self._handlers: dict[EventType, list] = {}
        # Replacement effects that may intercept events
        self._replacement_effects: list[ReplacementEffect] = []
        # Triggered effects that fire after events
        self._triggered_effects: list[TriggeredEffect] = []
        # Queue of triggered events waiting to be processed
        self._pending_triggers: list[GameEvent] = []

    def register_handler(self, event_type: EventType, handler) -> None:
        """Register a handler that executes when an event of this type occurs."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def register_replacement(self, effect: ReplacementEffect) -> None:
        """Register a replacement effect."""
        self._replacement_effects.append(effect)

    def unregister_replacement(self, effect: ReplacementEffect) -> None:
        """Remove a replacement effect."""
        if effect in self._replacement_effects:
            self._replacement_effects.remove(effect)

    def register_trigger(self, effect: TriggeredEffect) -> None:
        """Register a triggered effect."""
        self._triggered_effects.append(effect)

    def unregister_trigger(self, effect: TriggeredEffect) -> None:
        """Remove a triggered effect."""
        if effect in self._triggered_effects:
            self._triggered_effects.remove(effect)

    def emit(self, event: GameEvent) -> GameEvent:
        """Emit an event through the full pipeline.

        Returns the (possibly modified) event after processing.
        """
        # Step 1: Apply replacement effects (rules 6.4, 6.5)
        # Order: Self/Identity -> Standard -> Prevention -> Event -> Outcome
        event = self._apply_replacements(event)

        if event.cancelled:
            log.debug(f"Event {event.event_type.name} cancelled by replacement effect")
            return event

        # Step 2: Execute handlers (change game state)
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            handler(event)

        # Step 3: Check triggered effects (rules 6.6)
        self._check_triggers(event)

        return event

    def _apply_replacements(self, event: GameEvent) -> GameEvent:
        """Apply replacement effects to an event before it executes.

        Rules 6.5: Self/Identity -> Standard -> Prevention -> Event -> Outcome
        """
        # Process each applicable replacement effect
        applied: set[int] = set()  # track by id to prevent double-application (6.4.5)

        for effect in list(self._replacement_effects):
            effect_id = id(effect)
            if effect_id in applied:
                continue
            if effect.condition(event):
                event = effect.replace(event)
                applied.add(effect_id)
                if effect.one_shot:
                    self._replacement_effects.remove(effect)
                if event.cancelled:
                    break

        return event

    def _check_triggers(self, event: GameEvent) -> None:
        """Check all triggered effects against this event.

        Rules 6.6.5: Effect must exist before event to trigger.
        Rules 6.6.6: Triggered layers added before next priority.
        """
        for effect in list(self._triggered_effects):
            if effect.condition(event):
                triggered_event = effect.create_triggered_event(event)
                if triggered_event:
                    self._pending_triggers.append(triggered_event)
                if effect.one_shot:
                    self._triggered_effects.remove(effect)

    def get_pending_triggers(self) -> list[GameEvent]:
        """Get and clear pending triggered events."""
        triggers = list(self._pending_triggers)
        self._pending_triggers.clear()
        return triggers

    def clear(self) -> None:
        """Clear all registered effects (for end of turn, etc.)."""
        self._replacement_effects.clear()
        self._triggered_effects.clear()
        self._pending_triggers.clear()

    def clear_expired(self, current_duration_check) -> None:
        """Remove effects whose duration has expired."""
        self._replacement_effects = [
            e for e in self._replacement_effects
            if not current_duration_check(e)
        ]
        self._triggered_effects = [
            e for e in self._triggered_effects
            if not current_duration_check(e)
        ]

    def iter_replacement_effects(self) -> list[ReplacementEffect]:
        """Snapshot of currently registered replacement effects.

        Returns a defensive copy so callers can iterate without worrying
        about mid-iteration registration. Used by
        :func:`engine.state.snapshot.snapshot_for` to surface
        publicly-known active effects (e.g. damage prevention from
        Shelter from the Storm) that don't otherwise show up as modified
        card values.
        """
        return list(self._replacement_effects)


@dataclass
class ReplacementEffect:
    """A replacement effect that intercepts events before they occur.

    Rules 6.4: Replaces an event with a modified event.
    """
    source: CardInstance | None = None
    one_shot: bool = False  # True for fixed-prevention effects

    def condition(self, event: GameEvent) -> bool:
        """Return True if this replacement applies to the given event."""
        return False

    def replace(self, event: GameEvent) -> GameEvent:
        """Modify the event. May cancel it by setting event.cancelled = True."""
        return event

    def describe(self) -> dict | None:
        """Public-information description of this effect for snapshots.

        Override on subclasses to expose effects whose activations are
        publicly visible but whose ongoing influence isn't otherwise
        reflected in card-level modified values (e.g. Shelter from the
        Storm registers a damage-prevention replacement that the
        opponent can't see in the chain or modified_power).

        Return ``None`` (default) to keep the effect hidden from
        snapshots — appropriate for purely-internal replacements that
        either aren't player-facing or are already evident elsewhere.

        The returned dict shape is intentionally loose; recommended
        fields:

        * ``source_name``: the card name that created this effect.
        * ``controller``: player_index that controls / owns the effect.
        * ``target_player``: player_index the effect applies to (if any).
        * ``kind``: short slug like ``"damage_prevention"``.
        * ``remaining_uses``: int charges left (if usage-limited).
        * ``summary``: one-line human-readable description.
        """
        return None


@dataclass
class TriggeredEffect:
    """A triggered effect that fires after an event occurs.

    Rules 6.6: Format: "When/Whenever [EVENT] [ABILITIES]"
    """
    source: CardInstance | None = None
    one_shot: bool = False  # True for "the next time" effects

    def condition(self, event: GameEvent) -> bool:
        """Return True if this trigger fires for the given event."""
        return False

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        """Create the triggered event/layer to be added to the stack."""
        return None
