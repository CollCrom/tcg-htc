"""Tests for skeptic audit findings.

Covers:
1. Spreading Flames dynamic filter uses effect engine for chain link supertypes
2. Blood Runs Deep cost reduction via intrinsic cost modifier
3. Contract keyword on Leave No Witnesses — Silver token creation
4. Amulet of Echoes instant-destroy activation
5. Fyendal's Spring Tunic player agency (instant activation instead of auto-spend)
"""

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.actions import ActionOption, Decision, PlayerResponse
from htc.engine.continuous import EffectDuration, make_supertype_grant
from htc.engine.events import EventType, GameEvent
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
from tests.conftest import (
    make_card,
    make_game_shell,
    make_mock_ask,
    make_pitch_card,
)
from tests.abilities.conftest import (
    make_draconic_ninja_attack,
    make_ninja_attack,
    make_dagger_weapon,
    setup_draconic_chain,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_interfaces(ask_fn):
    """Create mock player interfaces that delegate to ask_fn."""
    _MockPlayer = type("P", (), {"decide": lambda s, state, d: ask_fn(d)})
    return [_MockPlayer(), _MockPlayer()]


def _make_blood_runs_deep(
    instance_id: int = 1,
    cost: int = 3,
    owner_index: int = 0,
) -> CardInstance:
    """Create a Blood Runs Deep card."""
    defn = CardDefinition(
        unique_id=f"brd-{instance_id}",
        name="Blood Runs Deep",
        color=Color.RED,
        pitch=1,
        cost=cost,
        power=4,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.DRACONIC, SuperType.NINJA}),
        keywords=frozenset({Keyword.GO_AGAIN}),
        functional_text="",
        type_text="Draconic Ninja Attack Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HAND,
    )


# ===========================================================================
# 1. Spreading Flames — dynamic filter uses effect engine for chain links
# ===========================================================================


class TestSpreadingFlamesDynamicFilter:
    """Spreading Flames filter counts Draconic chain links via effect engine."""

    def test_effect_granted_draconic_counted_in_chain(self):
        """Chain link with effect-granted Draconic is counted by the filter."""
        game = make_game_shell()

        # Set up chain: link 0 = inherent Draconic, link 1 = non-Draconic (will get grant)
        game.combat_mgr.open_chain(game.state)
        d1 = make_draconic_ninja_attack(instance_id=1, name="Draconic 1", power=4)
        game.combat_mgr.add_chain_link(game.state, d1, 1)

        # A non-Draconic attack that will get Draconic via continuous effect
        non_drac = make_ninja_attack(instance_id=2, name="Granted Draconic", power=2)
        game.combat_mgr.add_chain_link(game.state, non_drac, 1)

        # Grant Draconic to non_drac via continuous effect
        grant = make_supertype_grant(
            frozenset({SuperType.DRACONIC}),
            controller_index=0,
            duration=EffectDuration.END_OF_COMBAT,
            target_filter=lambda c: c.instance_id == non_drac.instance_id,
        )
        game.effect_engine.add_continuous_effect(game.state, grant)

        # Now add a 3rd Draconic attack (Spreading Flames itself)
        sf = make_draconic_ninja_attack(
            instance_id=3, name="Spreading Flames", power=3,
        )
        game.combat_mgr.add_chain_link(game.state, sf, 1)

        # Apply Spreading Flames on_attack
        game._apply_card_ability(sf, 0, "on_attack")

        # With effect engine, we should count 3 Draconic chain links
        # (d1=inherent, non_drac=granted, sf=inherent).
        # Attack with power 2 (< 3) should get +1 power.
        mod_power = game.effect_engine.get_modified_power(game.state, non_drac)
        assert mod_power == 3  # 2 base + 1 from Spreading Flames

    def test_non_draconic_not_counted(self):
        """Chain link without Draconic (even effect-granted) is not counted."""
        game = make_game_shell()

        game.combat_mgr.open_chain(game.state)
        d1 = make_draconic_ninja_attack(instance_id=1, name="Draconic 1", power=4)
        game.combat_mgr.add_chain_link(game.state, d1, 1)

        # Non-Draconic attack — no grant
        non_drac = make_ninja_attack(instance_id=2, name="Plain Ninja", power=1)
        game.combat_mgr.add_chain_link(game.state, non_drac, 1)

        sf = make_draconic_ninja_attack(
            instance_id=3, name="Spreading Flames", power=3,
        )
        game.combat_mgr.add_chain_link(game.state, sf, 1)

        game._apply_card_ability(sf, 0, "on_attack")

        # Only 2 Draconic links (d1, sf). non_drac (power=1 < 2) is not Draconic
        # so it does NOT get +1 power.
        mod_power = game.effect_engine.get_modified_power(game.state, non_drac)
        assert mod_power == 1  # unchanged


# ===========================================================================
# 2. Blood Runs Deep — cost reduction
# ===========================================================================


class TestBloodRunsDeepCostReduction:
    """Blood Runs Deep costs {r} less for each Draconic chain link."""

    def test_cost_reduced_by_draconic_chain_links(self):
        """Cost is reduced by the number of Draconic chain links."""
        game = make_game_shell()
        brd = _make_blood_runs_deep(cost=3)

        # Set up 2 Draconic chain links
        setup_draconic_chain(game, 2)

        cost = game.effect_engine.get_modified_cost(game.state, brd)
        assert cost == 1  # 3 - 2 = 1

    def test_cost_reduced_to_zero(self):
        """Cost cannot go below zero."""
        game = make_game_shell()
        brd = _make_blood_runs_deep(cost=2)

        setup_draconic_chain(game, 3)

        cost = game.effect_engine.get_modified_cost(game.state, brd)
        assert cost == 0  # max(0, 2 - 3)

    def test_no_chain_no_reduction(self):
        """Without Draconic chain links, cost is unchanged."""
        game = make_game_shell()
        brd = _make_blood_runs_deep(cost=3)

        cost = game.effect_engine.get_modified_cost(game.state, brd)
        assert cost == 3

    def test_modifier_registered(self):
        """Blood Runs Deep cost modifier is registered on effect engine."""
        game = make_game_shell()
        assert "Blood Runs Deep" in game.effect_engine._intrinsic_cost_modifiers

    def test_effect_granted_draconic_counted(self):
        """Chain links with effect-granted Draconic count for cost reduction."""
        game = make_game_shell()
        brd = _make_blood_runs_deep(cost=3)

        game.combat_mgr.open_chain(game.state)
        # 1 inherent Draconic
        d1 = make_draconic_ninja_attack(instance_id=10, name="Draconic 1")
        game.combat_mgr.add_chain_link(game.state, d1, 1)

        # 1 non-Draconic with Draconic grant
        non_drac = make_ninja_attack(instance_id=11, name="Granted Draconic")
        game.combat_mgr.add_chain_link(game.state, non_drac, 1)

        grant = make_supertype_grant(
            frozenset({SuperType.DRACONIC}),
            controller_index=0,
            duration=EffectDuration.END_OF_COMBAT,
            target_filter=lambda c: c.instance_id == non_drac.instance_id,
        )
        game.effect_engine.add_continuous_effect(game.state, grant)

        cost = game.effect_engine.get_modified_cost(game.state, brd)
        assert cost == 1  # 3 - 2 = 1
