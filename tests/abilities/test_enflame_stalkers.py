"""Tests for Enflame the Firebrand and Stalker's Steps abilities.

Enflame the Firebrand (Draconic Ninja Attack Action, Red):
- Cost 0, Power 2, Defense 3, Pitch 1
- Keywords: (none inherent — Go Again is conditional, see ability text)
- "When this attacks, if you control 2 or more Draconic chain links,
   this gets go again, 3 or more, your attacks are Draconic this combat
   chain, 4 or more, this gets +2{p}."

Stalker's Steps (Assassin Equipment, Legs):
- Defense 0, Arcane Barrier 1
- "Attack Reaction - Destroy this: Target attack with stealth gets go again."
"""

from htc.cards.abilities.ninja import count_draconic_chain_links
from htc.engine.actions import PlayerResponse
from htc.enums import (
    CardType,
    Color,
    EquipmentSlot,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from tests.conftest import make_card, make_equipment, make_game_shell
from tests.abilities.conftest import (
    make_ability_context,
    make_draconic_ninja_attack,
    make_ninja_attack,
    make_stealth_attack,
    make_attack_reaction,
    setup_draconic_chain,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_enflame(instance_id: int = 50, owner_index: int = 0):
    """Create an Enflame the Firebrand card for testing."""
    from htc.cards.card import CardDefinition
    from htc.cards.instance import CardInstance

    defn = CardDefinition(
        unique_id=f"enflame-{instance_id}",
        name="Enflame the Firebrand",
        color=Color.RED,
        pitch=1,
        cost=0,
        power=2,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.DRACONIC, SuperType.NINJA}),
        keywords=frozenset(),
        functional_text=(
            "When this attacks, if you control 2 or more Draconic chain links, "
            "this gets go again, 3 or more, your attacks are Draconic this combat "
            "chain, 4 or more, this gets +2{p}."
        ),
        type_text="Draconic Ninja Action - Attack",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
    )


def _make_stalkers_steps(instance_id: int = 60, owner_index: int = 0):
    """Create Stalker's Steps equipment for testing."""
    return make_equipment(
        instance_id=instance_id,
        name="Stalker's Steps",
        defense=0,
        subtype=SubType.LEGS,
        keywords=frozenset({Keyword.ARCANE_BARRIER}),
        keyword_values={"Arcane Barrier": 1},
        owner_index=owner_index,
    )


_setup_draconic_chain = setup_draconic_chain
_build_ctx = make_ability_context


# ===========================================================================
# Enflame the Firebrand tests
# ===========================================================================


class TestEnflameTheFirebrand:
    """Tests for Enflame the Firebrand on_attack ability."""

    def test_no_bonus_with_zero_draconic_links(self):
        """With 0 Draconic chain links, Enflame gets no on-attack bonuses."""
        game = make_game_shell()
        game.combat_mgr.open_chain(game.state)
        enflame = _make_enflame()
        link = game.combat_mgr.add_chain_link(game.state, enflame, 1)

        # Enflame itself IS Draconic, so with just itself there's 1 Draconic link
        # No bonus at threshold 1
        game._apply_card_ability(enflame, 0, "on_attack")

        # Power should be base (2) -- no +2 bonus
        power = game.effect_engine.get_modified_power(game.state, enflame)
        assert power == 2

    def test_no_bonus_with_one_draconic_link(self):
        """With only 1 Draconic chain link (Enflame itself), no bonuses apply."""
        game = make_game_shell()
        game.combat_mgr.open_chain(game.state)
        enflame = _make_enflame()
        link = game.combat_mgr.add_chain_link(game.state, enflame, 1)

        game._apply_card_ability(enflame, 0, "on_attack")

        # Only 1 Draconic link (Enflame itself) -- no thresholds met
        power = game.effect_engine.get_modified_power(game.state, enflame)
        assert power == 2

    def test_no_go_again_without_two_draconic_links(self):
        """Enflame does NOT have Go Again without 2+ Draconic chain links.

        Go Again is conditional (granted by ability at 2+ Draconic links),
        not an inherent keyword. The Fabrary dataset incorrectly lists it.
        """
        game = make_game_shell()
        game.combat_mgr.open_chain(game.state)
        enflame = _make_enflame()
        link = game.combat_mgr.add_chain_link(game.state, enflame, 1)

        # Apply on_attack with only 1 Draconic link (Enflame itself)
        game._apply_card_ability(enflame, 0, "on_attack")

        # Go Again should NOT be present — neither inherent nor ability-granted
        kws = game.effect_engine.get_modified_keywords(game.state, enflame)
        assert Keyword.GO_AGAIN not in kws

    def test_go_again_at_two_draconic_links(self):
        """With 2+ Draconic chain links, Enflame gets go again from ability."""
        game = make_game_shell()
        # Set up 1 prior Draconic link + Enflame = 2 total
        _setup_draconic_chain(game, 1)
        enflame = _make_enflame()
        link = game.combat_mgr.add_chain_link(game.state, enflame, 1)

        game._apply_card_ability(enflame, 0, "on_attack")

        # Go again should be granted by the ability (not inherent)
        kws = game.effect_engine.get_modified_keywords(game.state, enflame)
        assert Keyword.GO_AGAIN in kws

    def test_draconic_supertype_grant_at_three_links(self):
        """With 3+ Draconic chain links, all attacks become Draconic."""
        game = make_game_shell()
        # Set up 2 prior Draconic links + Enflame = 3 total
        _setup_draconic_chain(game, 2)
        enflame = _make_enflame()
        link = game.combat_mgr.add_chain_link(game.state, enflame, 1)

        game._apply_card_ability(enflame, 0, "on_attack")

        # A non-Draconic Ninja attack should now be Draconic
        ninja_atk = make_ninja_attack(instance_id=100, owner_index=0)
        supertypes = game.effect_engine.get_modified_supertypes(game.state, ninja_atk)
        assert SuperType.DRACONIC in supertypes

    def test_draconic_grant_does_not_affect_opponent(self):
        """The Draconic grant only affects the controller's cards."""
        game = make_game_shell()
        _setup_draconic_chain(game, 2)
        enflame = _make_enflame()
        game.combat_mgr.add_chain_link(game.state, enflame, 1)

        game._apply_card_ability(enflame, 0, "on_attack")

        # Opponent's attack should NOT be Draconic
        opp_atk = make_ninja_attack(instance_id=101, owner_index=1)
        supertypes = game.effect_engine.get_modified_supertypes(game.state, opp_atk)
        assert SuperType.DRACONIC not in supertypes

    def test_plus_two_power_at_four_links(self):
        """With 4+ Draconic chain links, Enflame gets +2 power."""
        game = make_game_shell()
        # Set up 3 prior Draconic links + Enflame = 4 total
        _setup_draconic_chain(game, 3)
        enflame = _make_enflame()
        link = game.combat_mgr.add_chain_link(game.state, enflame, 1)

        game._apply_card_ability(enflame, 0, "on_attack")

        # Power should be 2 (base) + 2 (bonus) = 4
        power = game.effect_engine.get_modified_power(game.state, enflame)
        assert power == 4

    def test_all_bonuses_at_four_links(self):
        """With 4+ Draconic chain links, all three bonuses apply."""
        game = make_game_shell()
        _setup_draconic_chain(game, 3)
        enflame = _make_enflame()
        link = game.combat_mgr.add_chain_link(game.state, enflame, 1)

        game._apply_card_ability(enflame, 0, "on_attack")

        # Go again
        kws = game.effect_engine.get_modified_keywords(game.state, enflame)
        assert Keyword.GO_AGAIN in kws

        # Draconic grant on non-Draconic card
        ninja_atk = make_ninja_attack(instance_id=100, owner_index=0)
        supertypes = game.effect_engine.get_modified_supertypes(game.state, ninja_atk)
        assert SuperType.DRACONIC in supertypes

        # +2 power
        power = game.effect_engine.get_modified_power(game.state, enflame)
        assert power == 4

    def test_count_draconic_uses_effect_engine(self):
        """count_draconic_chain_links respects supertype grants from effects."""
        game = make_game_shell()
        game.combat_mgr.open_chain(game.state)

        # Add a non-Draconic Ninja attack
        ninja_atk = make_ninja_attack(instance_id=1, owner_index=0)
        game.combat_mgr.add_chain_link(game.state, ninja_atk, 1)

        # Before granting Draconic: 0 Draconic chain links
        enflame = _make_enflame(instance_id=2)
        link = game.combat_mgr.add_chain_link(game.state, enflame, 1)
        ctx = _build_ctx(game, enflame, chain_link=link)
        # Enflame itself is Draconic, so count = 1 (just Enflame)
        assert count_draconic_chain_links(ctx) == 1

        # Grant Draconic to all controller's cards via effect
        from htc.engine.continuous import EffectDuration, make_supertype_grant
        effect = make_supertype_grant(
            frozenset({SuperType.DRACONIC}),
            0,
            duration=EffectDuration.END_OF_COMBAT,
            target_filter=lambda c: c.owner_index == 0,
        )
        game.effect_engine.add_continuous_effect(game.state, effect)

        # Now ninja_atk should count as Draconic too
        assert count_draconic_chain_links(ctx) == 2

    def test_enflame_registered_in_ability_registry(self):
        """Enflame the Firebrand has an on_attack handler registered."""
        game = make_game_shell()
        handler = game.ability_registry.lookup("on_attack", "Enflame the Firebrand")
        assert handler is not None


# ===========================================================================
# Stalker's Steps tests
# ===========================================================================


class TestStalkersSteps:
    """Tests for Stalker's Steps attack reaction ability."""

    def test_grants_go_again_to_stealth_attack(self):
        """Stalker's Steps grants go again to an attack with Stealth."""
        game = make_game_shell()
        game.combat_mgr.open_chain(game.state)
        stealth_atk = make_stealth_attack(instance_id=1, owner_index=0)
        game.combat_mgr.add_chain_link(game.state, stealth_atk, 1)

        # Equip Stalker's Steps
        steps = _make_stalkers_steps(owner_index=0)
        game.state.players[0].equipment[EquipmentSlot.LEGS] = steps

        game._apply_card_ability(
            make_attack_reaction("Stalker's Steps", instance_id=60, owner_index=0),
            0, "attack_reaction_effect",
        )

        kws = game.effect_engine.get_modified_keywords(game.state, stealth_atk)
        assert Keyword.GO_AGAIN in kws

    def test_destroys_self_on_use(self):
        """Stalker's Steps is destroyed (moved to graveyard) when used."""
        game = make_game_shell()
        game.combat_mgr.open_chain(game.state)
        stealth_atk = make_stealth_attack(instance_id=1, owner_index=0)
        game.combat_mgr.add_chain_link(game.state, stealth_atk, 1)

        steps = _make_stalkers_steps(owner_index=0)
        game.state.players[0].equipment[EquipmentSlot.LEGS] = steps

        game._apply_card_ability(
            make_attack_reaction("Stalker's Steps", instance_id=60, owner_index=0),
            0, "attack_reaction_effect",
        )

        # Equipment slot should be cleared
        assert game.state.players[0].equipment.get(EquipmentSlot.LEGS) is None
        # Equipment should be in graveyard
        assert steps in game.state.players[0].graveyard

    def test_no_effect_without_stealth(self):
        """Stalker's Steps does nothing if the attack doesn't have Stealth."""
        game = make_game_shell()
        game.combat_mgr.open_chain(game.state)
        # Regular ninja attack without Stealth
        ninja_atk = make_ninja_attack(instance_id=1, owner_index=0)
        game.combat_mgr.add_chain_link(game.state, ninja_atk, 1)

        steps = _make_stalkers_steps(owner_index=0)
        game.state.players[0].equipment[EquipmentSlot.LEGS] = steps

        game._apply_card_ability(
            make_attack_reaction("Stalker's Steps", instance_id=60, owner_index=0),
            0, "attack_reaction_effect",
        )

        # Go again should NOT be granted (no stealth)
        kws = game.effect_engine.get_modified_keywords(game.state, ninja_atk)
        assert Keyword.GO_AGAIN not in kws

        # Equipment should NOT be destroyed
        assert game.state.players[0].equipment.get(EquipmentSlot.LEGS) is not None

    def test_stalkers_steps_registered(self):
        """Stalker's Steps has an attack_reaction_effect handler registered."""
        game = make_game_shell()
        handler = game.ability_registry.lookup("attack_reaction_effect", "Stalker's Steps")
        assert handler is not None
