"""Tests for target_filter seeing effect-granted supertypes.

Verifies that cost-reduction and power-bonus target filters correctly see
supertypes granted by continuous effects (e.g. Enflame's Draconic grant),
not just base definition supertypes.
"""

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.continuous import (
    ContinuousEffect,
    EffectDuration,
    ModStage,
    ModSubstage,
    NumericProperty,
    make_cost_modifier,
    make_power_modifier,
    make_supertype_grant,
)
from htc.enums import CardType, Color, Keyword, SubType, SuperType, Zone
from tests.conftest import make_game_shell


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_non_draconic_attack(
    instance_id: int = 1,
    name: str = "Plain Ninja Strike",
    power: int = 3,
    cost: int = 2,
    owner_index: int = 0,
) -> CardInstance:
    """Create a Ninja attack that is NOT inherently Draconic."""
    defn = CardDefinition(
        unique_id=f"plain-{instance_id}",
        name=name,
        color=Color.RED,
        pitch=1,
        cost=cost,
        power=power,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.NINJA}),
        keywords=frozenset(),
        functional_text="",
        type_text="Ninja Attack Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
    )


def _make_draconic_attack(
    instance_id: int = 2,
    name: str = "Draconic Strike",
    power: int = 4,
    cost: int = 1,
    owner_index: int = 0,
) -> CardInstance:
    """Create a Draconic Ninja attack (inherently Draconic)."""
    defn = CardDefinition(
        unique_id=f"draconic-{instance_id}",
        name=name,
        color=Color.RED,
        pitch=1,
        cost=cost,
        power=power,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.NINJA, SuperType.DRACONIC}),
        keywords=frozenset(),
        functional_text="",
        type_text="Draconic Ninja Attack Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
    )


def _grant_draconic(game, card, controller: int = 0) -> ContinuousEffect:
    """Register a continuous effect that grants Draconic to *card*."""
    effect = make_supertype_grant(
        frozenset({SuperType.DRACONIC}),
        controller,
        source_instance_id=999,
        duration=EffectDuration.END_OF_COMBAT,
        target_filter=lambda c, _cid=card.instance_id: c.instance_id == _cid,
    )
    game.effect_engine.add_continuous_effect(game.state, effect)
    return effect


# ---------------------------------------------------------------------------
# Tests: effect-granted Draconic visible to cost-reduction filters
# ---------------------------------------------------------------------------


def test_cost_reduction_sees_granted_draconic():
    """A card made Draconic by a continuous effect gets cost reduction from
    a filter that checks for Draconic supertype."""
    game = make_game_shell()
    card = _make_non_draconic_attack(cost=2)

    # Sanity: card is NOT inherently Draconic
    assert SuperType.DRACONIC not in card.definition.supertypes

    # Grant Draconic via continuous effect
    _grant_draconic(game, card)

    # Verify effect engine sees it as Draconic
    resolved = game.effect_engine.get_modified_supertypes(game.state, card)
    assert SuperType.DRACONIC in resolved

    # Add a cost reduction that targets Draconic cards using the
    # same pattern as Art of the Dragon: Blood and Ignite
    cost_effect = make_cost_modifier(
        -1,
        0,
        source_instance_id=888,
        duration=EffectDuration.END_OF_TURN,
        target_filter=lambda c: SuperType.DRACONIC in getattr(
            c, '_resolved_supertypes', c.definition.supertypes
        ),
    )
    game.effect_engine.add_continuous_effect(game.state, cost_effect)

    # The card should get the cost reduction because the effect engine
    # pre-resolves supertypes before evaluating target filters
    modified_cost = game.effect_engine.get_modified_cost(game.state, card)
    assert modified_cost == 1, (
        f"Expected cost 1 (2 base - 1 reduction), got {modified_cost}. "
        "Cost reduction filter should see effect-granted Draconic."
    )


def test_cost_reduction_without_draconic_grant():
    """A non-Draconic card does NOT get Draconic cost reduction."""
    game = make_game_shell()
    card = _make_non_draconic_attack(cost=2)

    # No Draconic grant — card stays plain Ninja
    cost_effect = make_cost_modifier(
        -1,
        0,
        source_instance_id=888,
        duration=EffectDuration.END_OF_TURN,
        target_filter=lambda c: SuperType.DRACONIC in getattr(
            c, '_resolved_supertypes', c.definition.supertypes
        ),
    )
    game.effect_engine.add_continuous_effect(game.state, cost_effect)

    modified_cost = game.effect_engine.get_modified_cost(game.state, card)
    assert modified_cost == 2, (
        f"Expected cost 2 (no reduction), got {modified_cost}. "
        "Non-Draconic card should not get Draconic cost reduction."
    )


def test_inherent_draconic_still_gets_cost_reduction():
    """An inherently Draconic card still gets cost reduction (regression check)."""
    game = make_game_shell()
    card = _make_draconic_attack(cost=3)

    cost_effect = make_cost_modifier(
        -1,
        0,
        source_instance_id=888,
        duration=EffectDuration.END_OF_TURN,
        target_filter=lambda c: SuperType.DRACONIC in getattr(
            c, '_resolved_supertypes', c.definition.supertypes
        ),
    )
    game.effect_engine.add_continuous_effect(game.state, cost_effect)

    modified_cost = game.effect_engine.get_modified_cost(game.state, card)
    assert modified_cost == 2, (
        f"Expected cost 2 (3 base - 1 reduction), got {modified_cost}"
    )


# ---------------------------------------------------------------------------
# Tests: effect-granted Draconic visible to power-bonus filters
# ---------------------------------------------------------------------------


def test_power_bonus_sees_granted_draconic():
    """A card made Draconic by a continuous effect gets power bonus from
    a filter that checks for Draconic supertype."""
    game = make_game_shell()
    card = _make_non_draconic_attack(power=3)

    # Grant Draconic
    _grant_draconic(game, card)

    # Power bonus targeting Draconic cards
    power_effect = make_power_modifier(
        1,
        0,
        source_instance_id=888,
        duration=EffectDuration.END_OF_COMBAT,
        target_filter=lambda c: SuperType.DRACONIC in getattr(
            c, '_resolved_supertypes', c.definition.supertypes
        ),
    )
    game.effect_engine.add_continuous_effect(game.state, power_effect)

    modified_power = game.effect_engine.get_modified_power(game.state, card)
    assert modified_power == 4, (
        f"Expected power 4 (3 base + 1 bonus), got {modified_power}. "
        "Power bonus filter should see effect-granted Draconic."
    )


def test_power_bonus_without_draconic_grant():
    """A non-Draconic card does NOT get Draconic power bonus."""
    game = make_game_shell()
    card = _make_non_draconic_attack(power=3)

    # No Draconic grant
    power_effect = make_power_modifier(
        1,
        0,
        source_instance_id=888,
        duration=EffectDuration.END_OF_COMBAT,
        target_filter=lambda c: SuperType.DRACONIC in getattr(
            c, '_resolved_supertypes', c.definition.supertypes
        ),
    )
    game.effect_engine.add_continuous_effect(game.state, power_effect)

    modified_power = game.effect_engine.get_modified_power(game.state, card)
    assert modified_power == 3, (
        f"Expected power 3 (no bonus), got {modified_power}"
    )


# ---------------------------------------------------------------------------
# Tests: _resolved_supertypes cleanup (no stale state)
# ---------------------------------------------------------------------------


def test_resolved_supertypes_cleaned_up_after_query():
    """_resolved_supertypes should not persist on the card after querying."""
    game = make_game_shell()
    card = _make_non_draconic_attack()

    _grant_draconic(game, card)

    # Query triggers resolution + cleanup
    game.effect_engine.get_modified_power(game.state, card)

    # _resolved_supertypes should be cleaned up
    assert not hasattr(card, '_resolved_supertypes'), (
        "_resolved_supertypes should be deleted after resolution"
    )


def test_resolved_supertypes_cleaned_up_after_cost_query():
    """_resolved_supertypes should not persist after cost query."""
    game = make_game_shell()
    card = _make_non_draconic_attack()

    game.effect_engine.get_modified_cost(game.state, card)

    assert not hasattr(card, '_resolved_supertypes')


def test_resolved_supertypes_cleaned_up_after_keyword_query():
    """_resolved_supertypes should not persist after keyword query."""
    game = make_game_shell()
    card = _make_non_draconic_attack()

    game.effect_engine.get_modified_keywords(game.state, card)

    assert not hasattr(card, '_resolved_supertypes')


# ---------------------------------------------------------------------------
# Tests: defense also sees granted supertypes
# ---------------------------------------------------------------------------


def test_defense_modifier_sees_granted_draconic():
    """Defense modifier filter should also see effect-granted supertypes."""
    game = make_game_shell()
    card = _make_non_draconic_attack(power=3)

    _grant_draconic(game, card)

    defense_effect = ContinuousEffect(
        source_instance_id=888,
        controller_index=0,
        stage=ModStage.NUMERIC,
        substage=ModSubstage.ADD_TO,
        duration=EffectDuration.END_OF_COMBAT,
        target_filter=lambda c: SuperType.DRACONIC in getattr(
            c, '_resolved_supertypes', c.definition.supertypes
        ),
        numeric_property=NumericProperty.DEFENSE,
        modify_numeric=lambda v: v + 2,
    )
    game.effect_engine.add_continuous_effect(game.state, defense_effect)

    modified_defense = game.effect_engine.get_modified_defense(game.state, card)
    # base defense is 3, + 2 bonus = 5
    assert modified_defense == 5


# ---------------------------------------------------------------------------
# Tests: Enflame-style scenario (end-to-end with supertype grant + filter)
# ---------------------------------------------------------------------------


def test_enflame_draconic_grant_enables_cost_reduction():
    """Simulate Enflame's tier-3 effect: grant Draconic to all attacks,
    then verify a cost reduction targeting Draconic cards applies to
    a non-inherently-Draconic attack."""
    game = make_game_shell()

    # Two cards: one inherently Draconic, one not
    draconic_card = _make_draconic_attack(instance_id=1, cost=2)
    plain_card = _make_non_draconic_attack(instance_id=2, cost=2)

    # Enflame tier-3: "your attacks are Draconic this combat chain"
    enflame_grant = make_supertype_grant(
        frozenset({SuperType.DRACONIC}),
        0,
        source_instance_id=999,
        duration=EffectDuration.END_OF_COMBAT,
        target_filter=lambda c: c.owner_index == 0,
    )
    game.effect_engine.add_continuous_effect(game.state, enflame_grant)

    # Ignite-style cost reduction: "next Draconic card costs 1 less"
    cost_effect = make_cost_modifier(
        -1,
        0,
        source_instance_id=888,
        duration=EffectDuration.END_OF_COMBAT,
        target_filter=lambda c: SuperType.DRACONIC in getattr(
            c, '_resolved_supertypes', c.definition.supertypes
        ),
    )
    game.effect_engine.add_continuous_effect(game.state, cost_effect)

    # Both should get cost reduction
    draconic_cost = game.effect_engine.get_modified_cost(game.state, draconic_card)
    plain_cost = game.effect_engine.get_modified_cost(game.state, plain_card)

    assert draconic_cost == 1, f"Inherent Draconic: expected 1 (2-1), got {draconic_cost}"
    assert plain_cost == 1, (
        f"Effect-granted Draconic: expected 1, got {plain_cost}. "
        "Enflame's Draconic grant should be visible to Ignite's cost filter."
    )


def test_enflame_draconic_grant_enables_power_bonus():
    """Simulate Enflame tier-3 + Spreading Flames: grant Draconic to all
    attacks, then verify a power bonus targeting Draconic cards applies."""
    game = make_game_shell()

    plain_card = _make_non_draconic_attack(instance_id=1, power=3)

    # Grant Draconic to all controller-0 cards
    enflame_grant = make_supertype_grant(
        frozenset({SuperType.DRACONIC}),
        0,
        source_instance_id=999,
        duration=EffectDuration.END_OF_COMBAT,
        target_filter=lambda c: c.owner_index == 0,
    )
    game.effect_engine.add_continuous_effect(game.state, enflame_grant)

    # Spreading Flames style: Draconic attacks get +1 power
    power_effect = make_power_modifier(
        1,
        0,
        source_instance_id=777,
        duration=EffectDuration.END_OF_COMBAT,
        target_filter=lambda c: SuperType.DRACONIC in getattr(
            c, '_resolved_supertypes', c.definition.supertypes
        ),
    )
    game.effect_engine.add_continuous_effect(game.state, power_effect)

    modified_power = game.effect_engine.get_modified_power(game.state, plain_card)
    assert modified_power == 4, (
        f"Expected power 4 (3 base + 1 from Spreading Flames), got {modified_power}. "
        "Enflame's Draconic grant should be visible to Spreading Flames' filter."
    )
