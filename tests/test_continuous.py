"""Tests for continuous effects and the staging system."""

from htc.engine.continuous import (
    ContinuousEffect,
    EffectDuration,
    ModStage,
    ModSubstage,
    NumericProperty,
    make_cost_modifier,
    make_defense_modifier,
    make_keyword_grant,
    make_power_modifier,
)
from htc.engine.effects import EffectEngine
from htc.enums import Keyword, SubType, Zone
from htc.state.combat_state import ChainLink
from htc.state.game_state import GameState
from htc.state.player_state import PlayerState
from tests.conftest import make_card


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state() -> GameState:
    state = GameState()
    state.players = [
        PlayerState(index=0, life_total=20),
        PlayerState(index=1, life_total=20),
    ]
    return state


# ---------------------------------------------------------------------------
# Basic queries — no effects
# ---------------------------------------------------------------------------


def test_no_effects_returns_base_power():
    engine = EffectEngine()
    state = _make_state()
    card = make_card(power=5)
    assert engine.get_modified_power(state, card) == 5


def test_no_effects_returns_base_defense():
    engine = EffectEngine()
    state = _make_state()
    card = make_card(defense=3)
    assert engine.get_modified_defense(state, card) == 3


def test_no_effects_returns_base_cost():
    engine = EffectEngine()
    state = _make_state()
    card = make_card(cost=2)
    assert engine.get_modified_cost(state, card) == 2


def test_none_power_returns_zero():
    engine = EffectEngine()
    state = _make_state()
    card = make_card(power=None, is_attack=False, name="No Power Card")
    assert engine.get_modified_power(state, card) == 0


# ---------------------------------------------------------------------------
# Single numeric effect
# ---------------------------------------------------------------------------


def test_power_modifier_adds():
    engine = EffectEngine()
    state = _make_state()
    card = make_card(power=3)

    effect = make_power_modifier(2, controller_index=0)
    engine.add_continuous_effect(state, effect)

    assert engine.get_modified_power(state, card) == 5


def test_power_modifier_subtracts():
    engine = EffectEngine()
    state = _make_state()
    card = make_card(power=5)

    effect = make_power_modifier(-3, controller_index=0)
    engine.add_continuous_effect(state, effect)

    assert engine.get_modified_power(state, card) == 2


def test_defense_modifier():
    engine = EffectEngine()
    state = _make_state()
    card = make_card(defense=2)

    effect = make_defense_modifier(1, controller_index=0)
    engine.add_continuous_effect(state, effect)

    assert engine.get_modified_defense(state, card) == 3


def test_cost_modifier():
    engine = EffectEngine()
    state = _make_state()
    card = make_card(cost=3)

    effect = make_cost_modifier(-1, controller_index=0)
    engine.add_continuous_effect(state, effect)

    assert engine.get_modified_cost(state, card) == 2


# ---------------------------------------------------------------------------
# Staging / substage ordering
# ---------------------------------------------------------------------------


def test_set_then_add_ordering():
    """SET (substage 2) should apply before ADD_TO (substage 5)."""
    engine = EffectEngine()
    state = _make_state()
    card = make_card(power=3)

    # Add +2 first (timestamp 1)
    add_effect = make_power_modifier(2, controller_index=0)
    engine.add_continuous_effect(state, add_effect)

    # Set to 5 second (timestamp 2) — but SET substage comes before ADD_TO
    set_effect = ContinuousEffect(
        controller_index=0,
        stage=ModStage.NUMERIC,
        substage=ModSubstage.SET,
        numeric_property=NumericProperty.POWER,
        modify_numeric=lambda v: 5,
    )
    engine.add_continuous_effect(state, set_effect)

    # SET(5) then ADD(+2) = 7
    assert engine.get_modified_power(state, card) == 7


def test_timestamp_ordering_within_substage():
    """Within same substage, earlier timestamp applies first."""
    engine = EffectEngine()
    state = _make_state()
    card = make_card(power=0)

    # First: +3
    engine.add_continuous_effect(state, make_power_modifier(3, controller_index=0))
    # Second: +2
    engine.add_continuous_effect(state, make_power_modifier(2, controller_index=0))

    # Both ADD_TO, order doesn't matter for addition: 0 + 3 + 2 = 5
    assert engine.get_modified_power(state, card) == 5


def test_multiply_then_add_ordering():
    """MULTIPLY (substage 3) applies before ADD_TO (substage 5)."""
    engine = EffectEngine()
    state = _make_state()
    card = make_card(power=3)

    # Add +1
    engine.add_continuous_effect(state, make_power_modifier(1, controller_index=0))

    # Multiply by 2 — substage 3, comes before ADD_TO substage 5
    multiply_effect = ContinuousEffect(
        controller_index=0,
        stage=ModStage.NUMERIC,
        substage=ModSubstage.MULTIPLY,
        numeric_property=NumericProperty.POWER,
        modify_numeric=lambda v: v * 2,
    )
    engine.add_continuous_effect(state, multiply_effect)

    # base=3, MULTIPLY(×2)=6, ADD(+1)=7
    assert engine.get_modified_power(state, card) == 7


def test_base_numeric_before_numeric():
    """Stage 7 (BASE_NUMERIC) applies before stage 8 (NUMERIC)."""
    engine = EffectEngine()
    state = _make_state()
    card = make_card(power=3)

    # Stage 8: +2
    engine.add_continuous_effect(state, make_power_modifier(2, controller_index=0))

    # Stage 7: set base to 10
    base_set = ContinuousEffect(
        controller_index=0,
        stage=ModStage.BASE_NUMERIC,
        substage=ModSubstage.SET,
        numeric_property=NumericProperty.POWER,
        modify_numeric=lambda v: 10,
    )
    engine.add_continuous_effect(state, base_set)

    # BASE_NUMERIC SET(10), then NUMERIC ADD(+2) = 12
    assert engine.get_modified_power(state, card) == 12


# ---------------------------------------------------------------------------
# Target filtering
# ---------------------------------------------------------------------------


def test_target_filter_applies_selectively():
    engine = EffectEngine()
    state = _make_state()
    attack = make_card(instance_id=1, power=3)
    non_attack = make_card(instance_id=2, power=2, is_attack=False, name="Non-Attack")

    # Only buff attacks
    effect = make_power_modifier(
        5, controller_index=0,
        target_filter=lambda c: SubType.ATTACK in c.definition.subtypes,
    )
    engine.add_continuous_effect(state, effect)

    assert engine.get_modified_power(state, attack) == 8  # 3 + 5
    assert engine.get_modified_power(state, non_attack) == 2  # unchanged


# ---------------------------------------------------------------------------
# Conditional effects
# ---------------------------------------------------------------------------


def test_conditional_effect_applies_when_true():
    engine = EffectEngine()
    state = _make_state()
    card = make_card(power=3)

    effect = make_power_modifier(
        2, controller_index=0,
        condition=lambda s: s.turn_number > 0,
    )
    engine.add_continuous_effect(state, effect)

    state.turn_number = 0
    assert engine.get_modified_power(state, card) == 3  # condition false

    state.turn_number = 1
    assert engine.get_modified_power(state, card) == 5  # condition true


# ---------------------------------------------------------------------------
# Duration / cleanup
# ---------------------------------------------------------------------------


def test_end_of_turn_cleanup():
    engine = EffectEngine()
    state = _make_state()
    card = make_card(power=3)

    eot = make_power_modifier(2, controller_index=0, duration=EffectDuration.END_OF_TURN)
    perm = make_power_modifier(1, controller_index=0, duration=EffectDuration.PERMANENT)
    engine.add_continuous_effect(state, eot)
    engine.add_continuous_effect(state, perm)

    assert engine.get_modified_power(state, card) == 6  # 3+2+1

    engine.cleanup_expired_effects(state, EffectDuration.END_OF_TURN)

    assert engine.get_modified_power(state, card) == 4  # 3+1 (eot removed)


def test_end_of_combat_cleanup():
    engine = EffectEngine()
    state = _make_state()
    card = make_card(power=3)

    eoc = make_power_modifier(2, controller_index=0, duration=EffectDuration.END_OF_COMBAT)
    eot = make_power_modifier(1, controller_index=0, duration=EffectDuration.END_OF_TURN)
    engine.add_continuous_effect(state, eoc)
    engine.add_continuous_effect(state, eot)

    assert engine.get_modified_power(state, card) == 6

    engine.cleanup_expired_effects(state, EffectDuration.END_OF_COMBAT)

    assert engine.get_modified_power(state, card) == 4  # eoc removed, eot stays


def test_zone_effect_cleanup():
    engine = EffectEngine()
    state = _make_state()
    source = make_card(instance_id=10, power=1)
    source.zone = Zone.HAND
    state.players[0].hand.append(source)

    target = make_card(instance_id=20, power=3)

    effect = ContinuousEffect(
        source_instance_id=10,
        source_zone=Zone.HAND,
        controller_index=0,
        stage=ModStage.NUMERIC,
        substage=ModSubstage.ADD_TO,
        duration=EffectDuration.WHILE_SOURCE_IN_ZONE,
        numeric_property=NumericProperty.POWER,
        modify_numeric=lambda v: v + 2,
    )
    engine.add_continuous_effect(state, effect)

    assert engine.get_modified_power(state, target) == 5

    # Move source to graveyard
    state.players[0].hand.remove(source)
    source.zone = Zone.GRAVEYARD
    state.players[0].graveyard.append(source)

    engine.cleanup_zone_effects(state)

    assert engine.get_modified_power(state, target) == 3  # effect removed


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------


def test_keyword_grant():
    engine = EffectEngine()
    state = _make_state()
    card = make_card()

    assert Keyword.GO_AGAIN not in engine.get_modified_keywords(state, card)

    effect = make_keyword_grant(
        frozenset({Keyword.GO_AGAIN}),
        controller_index=0,
    )
    engine.add_continuous_effect(state, effect)

    assert Keyword.GO_AGAIN in engine.get_modified_keywords(state, card)


def test_keyword_removal():
    engine = EffectEngine()
    state = _make_state()

    card = make_card(name="Go Again Card", keywords=frozenset({Keyword.GO_AGAIN}))

    assert Keyword.GO_AGAIN in engine.get_modified_keywords(state, card)

    effect = ContinuousEffect(
        controller_index=0,
        stage=ModStage.ABILITIES,
        substage=ModSubstage.ADD_TO,
        duration=EffectDuration.END_OF_TURN,
        keywords_to_remove=frozenset({Keyword.GO_AGAIN}),
    )
    engine.add_continuous_effect(state, effect)

    assert Keyword.GO_AGAIN not in engine.get_modified_keywords(state, card)


# ---------------------------------------------------------------------------
# Floor at zero
# ---------------------------------------------------------------------------


def test_power_floored_at_zero():
    engine = EffectEngine()
    state = _make_state()
    card = make_card(power=3)

    effect = make_power_modifier(-99, controller_index=0)
    engine.add_continuous_effect(state, effect)

    assert engine.get_modified_power(state, card) == 0


def test_cost_floored_at_zero():
    engine = EffectEngine()
    state = _make_state()
    card = make_card(cost=1)

    effect = make_cost_modifier(-10, controller_index=0)
    engine.add_continuous_effect(state, effect)

    assert engine.get_modified_cost(state, card) == 0


# ---------------------------------------------------------------------------
# Effect registration / removal
# ---------------------------------------------------------------------------


def test_add_and_remove_effect():
    engine = EffectEngine()
    state = _make_state()
    card = make_card(power=3)

    effect = make_power_modifier(2, controller_index=0)
    engine.add_continuous_effect(state, effect)
    assert engine.get_modified_power(state, card) == 5

    engine.remove_continuous_effect(state, effect.effect_id)
    assert engine.get_modified_power(state, card) == 3


def test_effect_ids_are_unique():
    engine = EffectEngine()
    state = _make_state()

    e1 = make_power_modifier(1, controller_index=0)
    e2 = make_power_modifier(2, controller_index=0)
    engine.add_continuous_effect(state, e1)
    engine.add_continuous_effect(state, e2)

    assert e1.effect_id != e2.effect_id
    assert e1.timestamp < e2.timestamp


# ---------------------------------------------------------------------------
# Integration: CombatManager uses modified values
# ---------------------------------------------------------------------------


def test_combat_manager_uses_modified_power():
    from htc.engine.combat import CombatManager

    engine = EffectEngine()
    state = _make_state()
    combat_mgr = CombatManager(engine)

    attack = make_card(power=3)
    link = ChainLink(
        link_number=1,
        active_attack=attack,
        attack_target_index=1,
    )

    assert combat_mgr.get_attack_power(state, link) == 3

    engine.add_continuous_effect(state, make_power_modifier(4, controller_index=0))

    assert combat_mgr.get_attack_power(state, link) == 7


def test_combat_manager_uses_modified_defense():
    from htc.engine.combat import CombatManager

    engine = EffectEngine()
    state = _make_state()
    combat_mgr = CombatManager(engine)

    attack = make_card(power=5)
    defender = make_card(instance_id=2, defense=2)
    link = ChainLink(
        link_number=1,
        active_attack=attack,
        attack_target_index=1,
        defending_cards=[defender],
    )

    assert combat_mgr.get_total_defense(state, link) == 2

    engine.add_continuous_effect(state, make_defense_modifier(1, controller_index=0))

    assert combat_mgr.get_total_defense(state, link) == 3
    assert combat_mgr.calculate_damage(state, link) == 2  # 5 power - 3 defense
