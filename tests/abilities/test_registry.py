"""Tests for AbilityRegistry — registration, lookup, and AbilityContext."""

from unittest.mock import MagicMock

from htc.engine.abilities import AbilityContext, AbilityRegistry
from htc.engine.effects import EffectEngine
from htc.engine.events import EventBus
from htc.engine.keyword_engine import KeywordEngine
from htc.engine.combat import CombatManager
from htc.enums import Zone
from tests.conftest import make_card, make_state


def test_register_and_lookup():
    """Registering an ability and looking it up returns the handler."""
    registry = AbilityRegistry()
    handler = MagicMock()
    registry.register("on_play", "Test Card", handler)
    assert registry.lookup("on_play", "Test Card") is handler


def test_lookup_missing_returns_none():
    """Looking up an unregistered card returns None."""
    registry = AbilityRegistry()
    assert registry.lookup("on_play", "Nonexistent Card") is None


def test_lookup_wrong_timing_returns_none():
    """Looking up a card at a timing it's not registered for returns None."""
    registry = AbilityRegistry()
    handler = MagicMock()
    registry.register("on_play", "Test Card", handler)
    assert registry.lookup("on_attack", "Test Card") is None


def test_lookup_invalid_timing_returns_none():
    """Looking up an invalid timing returns None instead of raising."""
    registry = AbilityRegistry()
    assert registry.lookup("bad_timing", "Test Card") is None


def test_register_invalid_timing_raises():
    """Registering with an invalid timing raises ValueError."""
    registry = AbilityRegistry()
    import pytest
    with pytest.raises(ValueError, match="Unknown timing"):
        registry.register("bad_timing", "Test Card", MagicMock())


def test_register_multiple_timings():
    """Same card can have handlers at different timings."""
    registry = AbilityRegistry()
    h1 = MagicMock()
    h2 = MagicMock()
    registry.register("on_play", "Test Card", h1)
    registry.register("on_hit", "Test Card", h2)
    assert registry.lookup("on_play", "Test Card") is h1
    assert registry.lookup("on_hit", "Test Card") is h2


def test_ability_context_construction():
    """AbilityContext can be constructed with all required fields."""
    state = make_state()
    card = make_card(zone=Zone.COMBAT_CHAIN)
    effect_engine = EffectEngine()
    events = EventBus()
    keyword_engine = KeywordEngine(effect_engine, events, lambda d: None)
    combat_mgr = CombatManager(effect_engine)

    ctx = AbilityContext(
        state=state,
        source_card=card,
        controller_index=0,
        chain_link=None,
        effect_engine=effect_engine,
        events=events,
        ask=lambda d: None,
        keyword_engine=keyword_engine,
        combat_mgr=combat_mgr,
    )
    assert ctx.state is state
    assert ctx.source_card is card
    assert ctx.controller_index == 0
    assert ctx.chain_link is None


def test_color_variants_share_ability():
    """Cards with the same name but different colors share an ability handler."""
    registry = AbilityRegistry()
    handler = MagicMock()
    registry.register("attack_reaction_effect", "Razor Reflex", handler)

    # All color variants look up by the same name
    assert registry.lookup("attack_reaction_effect", "Razor Reflex") is handler
