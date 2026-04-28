"""Tests for the event system."""
from engine.rules.events import (
    EventBus,
    EventType,
    GameEvent,
    ReplacementEffect,
    TriggeredEffect,
)


def test_event_handler_called():
    """Handlers should be called when events are emitted."""
    bus = EventBus()
    received = []

    bus.register_handler(EventType.DEAL_DAMAGE, lambda e: received.append(e))
    bus.emit(GameEvent(event_type=EventType.DEAL_DAMAGE, amount=5))

    assert len(received) == 1
    assert received[0].amount == 5


def test_multiple_handlers():
    """Multiple handlers for same event type should all fire."""
    bus = EventBus()
    counts = {"a": 0, "b": 0}

    bus.register_handler(EventType.DRAW_CARD, lambda e: counts.__setitem__("a", counts["a"] + 1))
    bus.register_handler(EventType.DRAW_CARD, lambda e: counts.__setitem__("b", counts["b"] + 1))
    bus.emit(GameEvent(event_type=EventType.DRAW_CARD))

    assert counts["a"] == 1
    assert counts["b"] == 1


def test_handler_not_called_for_wrong_type():
    """Handlers should only fire for their registered event type."""
    bus = EventBus()
    received = []

    bus.register_handler(EventType.DEAL_DAMAGE, lambda e: received.append(e))
    bus.emit(GameEvent(event_type=EventType.DRAW_CARD))

    assert len(received) == 0


def test_replacement_effect_modifies_event():
    """Replacement effects should modify events before handlers run."""
    bus = EventBus()
    received = []

    class HalveDamage(ReplacementEffect):
        def condition(self, event):
            return event.event_type == EventType.DEAL_DAMAGE
        def replace(self, event):
            event.amount = event.amount // 2
            event.modified = True
            return event

    bus.register_replacement(HalveDamage())
    bus.register_handler(EventType.DEAL_DAMAGE, lambda e: received.append(e))
    bus.emit(GameEvent(event_type=EventType.DEAL_DAMAGE, amount=6))

    assert len(received) == 1
    assert received[0].amount == 3
    assert received[0].modified


def test_replacement_effect_cancels_event():
    """Replacement effects can cancel events entirely."""
    bus = EventBus()
    received = []

    class PreventDamage(ReplacementEffect):
        def condition(self, event):
            return event.event_type == EventType.DEAL_DAMAGE
        def replace(self, event):
            event.cancelled = True
            event.amount = 0
            return event

    bus.register_replacement(PreventDamage())
    bus.register_handler(EventType.DEAL_DAMAGE, lambda e: received.append(e))
    bus.emit(GameEvent(event_type=EventType.DEAL_DAMAGE, amount=5))

    # Handler should NOT be called when event is cancelled
    assert len(received) == 0


def test_one_shot_replacement_removed():
    """One-shot replacement effects should only fire once."""
    bus = EventBus()
    amounts = []

    class PreventOnce(ReplacementEffect):
        def condition(self, event):
            return event.event_type == EventType.DEAL_DAMAGE
        def replace(self, event):
            event.amount = 0
            return event

    bus.register_replacement(PreventOnce(one_shot=True))
    bus.register_handler(EventType.DEAL_DAMAGE, lambda e: amounts.append(e.amount))

    bus.emit(GameEvent(event_type=EventType.DEAL_DAMAGE, amount=5))
    bus.emit(GameEvent(event_type=EventType.DEAL_DAMAGE, amount=3))

    assert amounts == [0, 3]  # first prevented, second not


def test_triggered_effect_fires():
    """Triggered effects should create pending events."""
    bus = EventBus()

    class OnHitDrawCard(TriggeredEffect):
        def condition(self, event):
            return event.event_type == EventType.HIT
        def create_triggered_event(self, triggering_event):
            return GameEvent(
                event_type=EventType.DRAW_CARD,
                target_player=0,
            )

    bus.register_trigger(OnHitDrawCard())
    bus.emit(GameEvent(event_type=EventType.HIT, amount=3))

    pending = bus.get_pending_triggers()
    assert len(pending) == 1
    assert pending[0].event_type == EventType.DRAW_CARD


def test_one_shot_trigger_removed():
    """One-shot triggers should only fire once."""
    bus = EventBus()

    class OnceOnHit(TriggeredEffect):
        def condition(self, event):
            return event.event_type == EventType.HIT
        def create_triggered_event(self, triggering_event):
            return GameEvent(event_type=EventType.GAIN_LIFE, amount=1)

    bus.register_trigger(OnceOnHit(one_shot=True))
    bus.emit(GameEvent(event_type=EventType.HIT, amount=1))
    bus.emit(GameEvent(event_type=EventType.HIT, amount=1))

    pending = bus.get_pending_triggers()
    assert len(pending) == 1  # only fired once


def test_replacement_only_applies_once_per_event():
    """A replacement effect can only replace an event once (rules 6.4.5)."""
    bus = EventBus()

    class AddOneDamage(ReplacementEffect):
        def condition(self, event):
            return event.event_type == EventType.DEAL_DAMAGE
        def replace(self, event):
            event.amount += 1
            return event

    effect = AddOneDamage()
    bus.register_replacement(effect)
    # Even though the effect stays registered, it shouldn't apply twice to same event
    result = bus.emit(GameEvent(event_type=EventType.DEAL_DAMAGE, amount=5))
    assert result.amount == 6  # +1, not +2


def test_clear_removes_all():
    """clear() should remove all effects."""
    bus = EventBus()

    class Dummy(ReplacementEffect):
        def condition(self, event): return True
        def replace(self, event):
            event.amount = 0
            return event

    class DummyTrigger(TriggeredEffect):
        def condition(self, event): return True
        def create_triggered_event(self, e):
            return GameEvent(event_type=EventType.GAIN_LIFE)

    bus.register_replacement(Dummy())
    bus.register_trigger(DummyTrigger())
    bus.clear()

    result = bus.emit(GameEvent(event_type=EventType.DEAL_DAMAGE, amount=5))
    assert result.amount == 5  # no replacement applied
    assert len(bus.get_pending_triggers()) == 0  # no triggers fired
