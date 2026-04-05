"""Scenario: Attack reaction target validation.

Verifies the ActionBuilder correctly offers/withholds attack reactions based
on the active attack type:

1. To the Point / Incision / Scar Tissue — only on dagger attacks (card subtype
   or weapon proxy of a dagger weapon), NOT on non-dagger weapon proxies.
2. Stains of the Redback — only on stealth attacks.
3. Ancestral Empowerment — only on Ninja attack action cards (not proxies).
4. Tide Flippers — only on attack action cards with base power <= 2 (not proxies).
"""

from __future__ import annotations

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.action_builder import ActionBuilder
from htc.enums import (
    CardType,
    Color,
    EquipmentSlot,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from tests.conftest import make_card, make_game_shell, make_weapon
from tests.abilities.conftest import (
    make_attack_reaction,
    make_dagger_attack,
    make_dagger_weapon,
    make_ninja_attack,
    make_stealth_attack,
    make_weapon_proxy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hero(
    name: str = "Cindra, Drachai of Two Talons",
    instance_id: int = 900,
    owner_index: int = 0,
) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"hero-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=None,
        health=20,
        intellect=4,
        arcane=None,
        types=frozenset({CardType.HERO}),
        subtypes=frozenset(),
        supertypes=frozenset({SuperType.NINJA}),
        keywords=frozenset(),
        functional_text="",
        type_text="Hero - Ninja",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HERO,
    )


def _make_named_reaction(name: str, instance_id: int = 10, owner_index: int = 0) -> CardInstance:
    """Create an attack reaction with a specific card name for target filtering."""
    defn = CardDefinition(
        unique_id=f"ar-{name.lower().replace(' ', '-')}-{instance_id}",
        name=name,
        color=Color.RED,
        pitch=1,
        cost=0,
        power=None,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ATTACK_REACTION}),
        subtypes=frozenset(),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset(),
        functional_text="",
        type_text="Assassin Attack Reaction",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HAND,
    )


def _make_tide_flippers(instance_id: int = 60, owner_index: int = 0) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"tide-{instance_id}",
        name="Tide Flippers",
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=0,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.EQUIPMENT}),
        subtypes=frozenset({SubType.LEGS}),
        supertypes=frozenset({SuperType.NINJA}),
        keywords=frozenset(),
        functional_text=(
            "Attack Reaction — Destroy Tide Flippers: Target attack action card "
            "with 2 or less base power gains go again."
        ),
        type_text="Ninja Equipment - Legs",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.LEGS,
    )


def _make_non_dagger_weapon(instance_id: int = 110, owner_index: int = 0):
    """Create a non-dagger weapon (e.g. staff) for testing."""
    return make_weapon(
        instance_id=instance_id,
        name="Test Staff",
        power=3,
        subtypes=frozenset({SubType.STAFF, SubType.TWO_HAND}),
        owner_index=owner_index,
    )


def _setup_reaction_test():
    """Set up game for attack reaction target testing.

    Returns game with heroes set up. Caller adds attacks/chain as needed.
    """
    game = make_game_shell()
    state = game.state

    hero = _make_hero(instance_id=900, owner_index=0)
    state.players[0].hero = hero
    state.players[0].life_total = 20

    opp_hero = _make_hero(name="Opponent", instance_id=901, owner_index=1)
    state.players[1].hero = opp_hero
    state.players[1].life_total = 20

    return game


# ---------------------------------------------------------------------------
# Tests: Dagger-targeting reactions (To the Point, Incision, Scar Tissue)
# ---------------------------------------------------------------------------


class TestDaggerReactionTargets:
    """To the Point, Incision, and Scar Tissue only work on dagger attacks."""

    def test_dagger_reaction_allowed_on_dagger_attack_card(self, scenario_recorder):
        """Dagger reactions should be allowed when active attack has Dagger subtype."""
        game = _setup_reaction_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)
        atk = make_dagger_attack(instance_id=10, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, atk, 1)

        recorder.snap("Setup: dagger attack card on chain")

        for name in ("To the Point", "Incision", "Scar Tissue"):
            card = _make_named_reaction(name, instance_id=20)
            result = game.action_builder._can_play_attack_reaction(state, 0, card)
            assert result, f"{name} should be playable on dagger attack card"

        recorder.snap("All dagger reactions allowed on dagger attack card")

    def test_dagger_reaction_allowed_on_dagger_weapon_proxy(self, scenario_recorder):
        """Dagger reactions should be allowed on weapon proxy of a dagger weapon."""
        game = _setup_reaction_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        dagger = make_dagger_weapon(instance_id=100, owner_index=0)
        state.players[0].weapons = [dagger]

        game.combat_mgr.open_chain(state)
        proxy = make_weapon_proxy(dagger, instance_id=200, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = dagger

        recorder.snap("Setup: dagger weapon proxy on chain")

        for name in ("To the Point", "Incision", "Scar Tissue"):
            card = _make_named_reaction(name, instance_id=20)
            result = game.action_builder._can_play_attack_reaction(state, 0, card)
            assert result, f"{name} should be playable on dagger weapon proxy"

        recorder.snap("All dagger reactions allowed on dagger weapon proxy")

    def test_dagger_reaction_rejected_on_non_dagger_attack(self, scenario_recorder):
        """Dagger reactions should be rejected on non-dagger attack action cards."""
        game = _setup_reaction_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)
        atk = make_ninja_attack(instance_id=10, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, atk, 1)

        recorder.snap("Setup: non-dagger Ninja attack on chain")

        for name in ("To the Point", "Incision", "Scar Tissue"):
            card = _make_named_reaction(name, instance_id=20)
            result = game.action_builder._can_play_attack_reaction(state, 0, card)
            assert not result, f"{name} should NOT be playable on non-dagger attack"

        recorder.snap("All dagger reactions correctly rejected on non-dagger attack")

    def test_dagger_reaction_rejected_on_non_dagger_weapon_proxy(self, scenario_recorder):
        """Dagger reactions should be rejected on non-dagger weapon proxies (e.g. staff)."""
        game = _setup_reaction_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        staff = _make_non_dagger_weapon(instance_id=110, owner_index=0)
        state.players[0].weapons = [staff]

        game.combat_mgr.open_chain(state)
        proxy = make_weapon_proxy(staff, instance_id=200, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = staff

        recorder.snap("Setup: non-dagger weapon proxy (staff) on chain")

        for name in ("To the Point", "Incision", "Scar Tissue"):
            card = _make_named_reaction(name, instance_id=20)
            result = game.action_builder._can_play_attack_reaction(state, 0, card)
            assert not result, f"{name} should NOT be playable on non-dagger weapon proxy"

        recorder.snap("All dagger reactions correctly rejected on staff proxy")


# ---------------------------------------------------------------------------
# Tests: Stains of the Redback — stealth only
# ---------------------------------------------------------------------------


class TestStainsOfTheRedbackTarget:
    """Stains of the Redback only offered on stealth attacks."""

    def test_stains_allowed_on_stealth_attack(self, scenario_recorder):
        """Stains should be playable when the active attack has Stealth."""
        game = _setup_reaction_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)
        atk = make_stealth_attack(instance_id=10, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, atk, 1)

        recorder.snap("Setup: stealth attack on chain")

        card = _make_named_reaction("Stains of the Redback", instance_id=20)
        result = game.action_builder._can_play_attack_reaction(state, 0, card)

        recorder.snap("Stains of the Redback allowed on stealth attack")

        assert result, "Stains of the Redback should be playable on stealth attack"

    def test_stains_rejected_on_non_stealth_attack(self, scenario_recorder):
        """Stains should NOT be playable when the active attack lacks Stealth."""
        game = _setup_reaction_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)
        atk = make_ninja_attack(instance_id=10, owner_index=0)  # no stealth
        link = game.combat_mgr.add_chain_link(state, atk, 1)

        recorder.snap("Setup: non-stealth Ninja attack on chain")

        card = _make_named_reaction("Stains of the Redback", instance_id=20)
        result = game.action_builder._can_play_attack_reaction(state, 0, card)

        recorder.snap("Stains of the Redback correctly rejected on non-stealth")

        assert not result, "Stains of the Redback should NOT be playable on non-stealth attack"


# ---------------------------------------------------------------------------
# Tests: Ancestral Empowerment — Ninja attack action only
# ---------------------------------------------------------------------------


class TestAncestralEmpowermentTarget:
    """Ancestral Empowerment only offered on Ninja attack action cards."""

    def test_ancestral_allowed_on_ninja_attack_action(self, scenario_recorder):
        """Ancestral should be playable on a Ninja attack action card."""
        game = _setup_reaction_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)
        atk = make_ninja_attack(instance_id=10, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, atk, 1)

        recorder.snap("Setup: Ninja attack action card on chain")

        card = _make_named_reaction("Ancestral Empowerment", instance_id=20)
        result = game.action_builder._can_play_attack_reaction(state, 0, card)

        recorder.snap("Ancestral Empowerment allowed on Ninja attack action")

        assert result, "Ancestral Empowerment should be playable on Ninja attack action"

    def test_ancestral_rejected_on_weapon_proxy(self, scenario_recorder):
        """Ancestral should NOT be playable on weapon proxy attacks."""
        game = _setup_reaction_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        dagger = make_dagger_weapon(instance_id=100, owner_index=0)
        state.players[0].weapons = [dagger]

        game.combat_mgr.open_chain(state)
        proxy = make_weapon_proxy(dagger, instance_id=200, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = dagger

        recorder.snap("Setup: dagger weapon proxy on chain")

        card = _make_named_reaction("Ancestral Empowerment", instance_id=20)
        result = game.action_builder._can_play_attack_reaction(state, 0, card)

        recorder.snap("Ancestral Empowerment rejected on weapon proxy")

        assert not result, "Ancestral Empowerment should NOT be playable on weapon proxy"

    def test_ancestral_rejected_on_non_ninja_attack(self, scenario_recorder):
        """Ancestral should NOT be playable on non-Ninja attack action cards."""
        game = _setup_reaction_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)
        atk = make_dagger_attack(
            instance_id=10, owner_index=0,
            supertypes=frozenset({SuperType.ASSASSIN}),  # Assassin, not Ninja
        )
        link = game.combat_mgr.add_chain_link(state, atk, 1)

        recorder.snap("Setup: Assassin (non-Ninja) dagger attack on chain")

        card = _make_named_reaction("Ancestral Empowerment", instance_id=20)
        result = game.action_builder._can_play_attack_reaction(state, 0, card)

        recorder.snap("Ancestral Empowerment rejected on non-Ninja attack")

        assert not result, "Ancestral Empowerment should NOT be playable on non-Ninja attack"


# ---------------------------------------------------------------------------
# Tests: Tide Flippers — attack action with base power <= 2
# ---------------------------------------------------------------------------


class TestTideFlippersTarget:
    """Tide Flippers only offered on attack action cards with base power <= 2."""

    def test_tide_flippers_allowed_on_low_power_attack(self, scenario_recorder):
        """Tide Flippers should be usable on attack action with power <= 2."""
        game = _setup_reaction_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        tide = _make_tide_flippers(instance_id=60, owner_index=0)
        state.players[0].equipment[EquipmentSlot.LEGS] = tide

        game.combat_mgr.open_chain(state)
        atk = make_ninja_attack(instance_id=10, power=2, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, atk, 1)

        recorder.snap("Setup: power-2 Ninja attack on chain, Tide Flippers equipped")

        result = game.action_builder._can_use_equipment_reaction(state, 0, tide)

        recorder.snap("Tide Flippers allowed on power-2 attack")

        assert result, "Tide Flippers should be usable on attack with power 2"

    def test_tide_flippers_rejected_on_high_power_attack(self, scenario_recorder):
        """Tide Flippers should NOT be usable on attack action with power > 2."""
        game = _setup_reaction_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        tide = _make_tide_flippers(instance_id=60, owner_index=0)
        state.players[0].equipment[EquipmentSlot.LEGS] = tide

        game.combat_mgr.open_chain(state)
        atk = make_ninja_attack(instance_id=10, power=4, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, atk, 1)

        recorder.snap("Setup: power-4 Ninja attack on chain, Tide Flippers equipped")

        result = game.action_builder._can_use_equipment_reaction(state, 0, tide)

        recorder.snap("Tide Flippers rejected on power-4 attack")

        assert not result, "Tide Flippers should NOT be usable on attack with power 4"

    def test_tide_flippers_rejected_on_weapon_proxy(self, scenario_recorder):
        """Tide Flippers should NOT be usable on weapon proxy attacks."""
        game = _setup_reaction_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        tide = _make_tide_flippers(instance_id=60, owner_index=0)
        state.players[0].equipment[EquipmentSlot.LEGS] = tide

        dagger = make_dagger_weapon(instance_id=100, owner_index=0)
        state.players[0].weapons = [dagger]

        game.combat_mgr.open_chain(state)
        proxy = make_weapon_proxy(dagger, instance_id=200, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = dagger

        recorder.snap("Setup: dagger weapon proxy on chain, Tide Flippers equipped")

        result = game.action_builder._can_use_equipment_reaction(state, 0, tide)

        recorder.snap("Tide Flippers rejected on weapon proxy")

        assert not result, "Tide Flippers should NOT be usable on weapon proxy"

    def test_tide_flippers_allowed_on_power_0_attack(self, scenario_recorder):
        """Tide Flippers should be usable on an attack with power 0."""
        game = _setup_reaction_test()
        state = game.state
        recorder = scenario_recorder.bind(game)

        tide = _make_tide_flippers(instance_id=60, owner_index=0)
        state.players[0].equipment[EquipmentSlot.LEGS] = tide

        game.combat_mgr.open_chain(state)
        atk = make_ninja_attack(instance_id=10, power=0, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, atk, 1)

        recorder.snap("Setup: power-0 Ninja attack on chain, Tide Flippers equipped")

        result = game.action_builder._can_use_equipment_reaction(state, 0, tide)

        recorder.snap("Tide Flippers allowed on power-0 attack")

        assert result, "Tide Flippers should be usable on attack with power 0"
