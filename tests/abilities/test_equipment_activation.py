"""Tests for equipment activation infrastructure and Dragonscaler Flight Path.

Verifies:
1. Equipment attack reactions (Tide Flippers, Blacktek Whisperers, Stalker's Steps)
   are now offered as options during the reaction step.
2. Dragonscaler Flight Path equipment instant activation: cost reduction,
   Go Again grant, weapon untap, precondition checks.
3. Keyword parsing: _is_keyword_inherent correctly distinguishes inherent
   vs conditional keywords.
"""

from htc.cards.abilities.equipment import (
    _dragonscaler_flight_path,
    _tide_flippers,
)
from htc.cards.abilities.ninja import count_draconic_chain_links
from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
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
    setup_draconic_chain,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dragonscaler(instance_id: int = 60, owner_index: int = 0):
    """Create Dragonscaler Flight Path equipment for testing."""
    defn = CardDefinition(
        unique_id=f"dragonscaler-{instance_id}",
        name="Dragonscaler Flight Path",
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=1,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.EQUIPMENT}),
        subtypes=frozenset({SubType.LEGS}),
        supertypes=frozenset({SuperType.DRACONIC}),
        keywords=frozenset({Keyword.BATTLEWORN}),
        functional_text=(
            "**Instant** - {r}{r}{r}, destroy this: Target Draconic attack gets "
            "**go again**. If it's a weapon or ally attack, you may attack with "
            "it an additional time this turn. This ability costs {r} less to "
            "activate for each Draconic chain link you control."
        ),
        type_text="Draconic Equipment - Legs",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.LEGS,
    )


def _make_weapon_proxy(weapon: CardInstance, instance_id: int, owner_index: int = 0):
    """Create an attack proxy for a weapon."""
    proxy_def = CardDefinition(
        unique_id=f"proxy-{weapon.definition.unique_id}",
        name=f"{weapon.name} (attack)",
        color=None,
        pitch=None,
        cost=None,
        power=weapon.definition.power,
        defense=None,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=weapon.definition.supertypes,
        keywords=weapon.definition.keywords,
        functional_text="",
        type_text="Weapon attack proxy",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=proxy_def,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
        is_proxy=True,
        proxy_source_id=weapon.instance_id,
    )


def _make_draconic_weapon(instance_id: int = 100, owner_index: int = 0, name: str = "Claw of Vynserakai"):
    """Create a Draconic weapon for testing."""
    defn = CardDefinition(
        unique_id=f"draconic-weapon-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=None,
        power=3,
        defense=None,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.WEAPON}),
        subtypes=frozenset({SubType.CLAW, SubType.TWO_HAND}),
        supertypes=frozenset({SuperType.DRACONIC, SuperType.NINJA}),
        keywords=frozenset(),
        functional_text="",
        type_text="Draconic Ninja Weapon - Claw (2H)",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.WEAPON_1,
    )


def _equip(game, equipment, player_index=0, slot=EquipmentSlot.LEGS):
    """Equip equipment onto a player."""
    game.state.players[player_index].equipment[slot] = equipment


# _setup_draconic_chain and _build_ctx are now in conftest as
# setup_draconic_chain and make_ability_context.
_setup_draconic_chain = setup_draconic_chain
_build_ctx = make_ability_context


def _add_pitchable_card(game, player_index=0, pitch=3, instance_id=200):
    """Add a pitchable card to a player's hand."""
    defn = CardDefinition(
        unique_id=f"filler-{instance_id}",
        name="Blue Filler",
        color=Color.BLUE,
        pitch=pitch,
        cost=0,
        power=None,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset(),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    card = CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=player_index,
        zone=Zone.HAND,
    )
    game.state.players[player_index].hand.append(card)
    return card


# ===========================================================================
# Task 4: Equipment attack reactions are now offered
# ===========================================================================


class TestEquipmentReactionsOffered:
    """Verify that equipment with attack_reaction_effect handlers appear
    as options in the reaction step decision."""

    def test_tide_flippers_offered_as_reaction(self):
        """Tide Flippers should appear in reaction options for the attacker."""
        game = make_game_shell()
        tide = make_equipment(
            instance_id=60, name="Tide Flippers", defense=0,
            subtype=SubType.LEGS, owner_index=0,
        )
        _equip(game, tide, player_index=0, slot=EquipmentSlot.LEGS)

        # Set up a low-power attack on the chain
        game.combat_mgr.open_chain(game.state)
        atk = make_ninja_attack(instance_id=1, power=2, cost=0, owner_index=0)
        game.combat_mgr.add_chain_link(game.state, atk, 1)

        # Build reaction decision for the attacker (player 0)
        decision = game.action_builder.build_reaction_decision(
            game.state, priority_player=0, attacker_index=0, defender_index=1,
        )

        # Tide Flippers should be in the options
        eq_options = [o for o in decision.options if "Tide Flippers" in o.description]
        assert len(eq_options) == 1, f"Expected Tide Flippers option, got: {[o.description for o in decision.options]}"
        assert eq_options[0].action_id == f"activate_{tide.instance_id}"

    def test_stalkers_steps_offered_as_reaction(self):
        """Stalker's Steps should appear in reaction options for the attacker."""
        game = make_game_shell()
        stalkers = make_equipment(
            instance_id=61, name="Stalker's Steps", defense=0,
            subtype=SubType.LEGS, owner_index=0,
        )
        _equip(game, stalkers, player_index=0, slot=EquipmentSlot.LEGS)

        # Set up an attack on the chain
        game.combat_mgr.open_chain(game.state)
        atk = make_ninja_attack(instance_id=1, power=4, cost=0, owner_index=0)
        game.combat_mgr.add_chain_link(game.state, atk, 1)

        decision = game.action_builder.build_reaction_decision(
            game.state, priority_player=0, attacker_index=0, defender_index=1,
        )

        eq_options = [o for o in decision.options if "Stalker's Steps" in o.description]
        assert len(eq_options) == 1

    def test_equipment_reaction_not_offered_to_defender(self):
        """Equipment attack reactions should NOT be offered to the defender."""
        game = make_game_shell()
        tide = make_equipment(
            instance_id=60, name="Tide Flippers", defense=0,
            subtype=SubType.LEGS, owner_index=1,
        )
        _equip(game, tide, player_index=1, slot=EquipmentSlot.LEGS)

        game.combat_mgr.open_chain(game.state)
        atk = make_ninja_attack(instance_id=1, power=2, cost=0, owner_index=0)
        game.combat_mgr.add_chain_link(game.state, atk, 1)

        # Build reaction decision for the defender (player 1)
        decision = game.action_builder.build_reaction_decision(
            game.state, priority_player=1, attacker_index=0, defender_index=1,
        )

        eq_options = [o for o in decision.options if "Tide Flippers" in o.description]
        assert len(eq_options) == 0, "Equipment attack reactions should not be offered to defender"

    def test_tide_flippers_execution_via_activate(self):
        """Tide Flippers can be activated and executes correctly: destroys self, grants Go Again."""
        game = make_game_shell()
        tide = make_equipment(
            instance_id=60, name="Tide Flippers", defense=0,
            subtype=SubType.LEGS, owner_index=0,
        )
        _equip(game, tide, player_index=0, slot=EquipmentSlot.LEGS)

        # Set up a low-power attack on the chain
        game.combat_mgr.open_chain(game.state)
        atk = make_ninja_attack(instance_id=1, power=2, cost=0, owner_index=0)
        link = game.combat_mgr.add_chain_link(game.state, atk, 1)

        # Execute the equipment activation
        game._activate_equipment(0, tide)

        # Tide Flippers should be destroyed (moved to graveyard)
        assert game.state.players[0].equipment[EquipmentSlot.LEGS] is None
        assert tide in game.state.players[0].graveyard

        # Attack should have Go Again
        attack_keywords = game.effect_engine.get_modified_keywords(game.state, atk)
        assert Keyword.GO_AGAIN in attack_keywords


# ===========================================================================
# Dragonscaler Flight Path tests
# ===========================================================================


class TestDragonscalerFlightPath:
    """Test Dragonscaler Flight Path equipment instant activation."""

    def test_cost_reduction_zero_draconic(self):
        """Base cost is 3 with zero Draconic chain links."""
        game = make_game_shell()
        dragonscaler = _make_dragonscaler()
        _equip(game, dragonscaler)

        # No combat chain open = 0 Draconic links
        cost = game.action_builder._get_equipment_instant_cost(
            game.state, 0, dragonscaler,
        )
        assert cost == 3

    def test_cost_reduction_one_draconic(self):
        """Cost is 2 with one Draconic chain link."""
        game = make_game_shell()
        dragonscaler = _make_dragonscaler()
        _equip(game, dragonscaler)
        _setup_draconic_chain(game, 1)

        cost = game.action_builder._get_equipment_instant_cost(
            game.state, 0, dragonscaler,
        )
        assert cost == 2

    def test_cost_reduction_two_draconic(self):
        """Cost is 1 with two Draconic chain links."""
        game = make_game_shell()
        dragonscaler = _make_dragonscaler()
        _equip(game, dragonscaler)
        _setup_draconic_chain(game, 2)

        cost = game.action_builder._get_equipment_instant_cost(
            game.state, 0, dragonscaler,
        )
        assert cost == 1

    def test_cost_reduction_three_draconic(self):
        """Cost is 0 with three Draconic chain links."""
        game = make_game_shell()
        dragonscaler = _make_dragonscaler()
        _equip(game, dragonscaler)
        _setup_draconic_chain(game, 3)

        cost = game.action_builder._get_equipment_instant_cost(
            game.state, 0, dragonscaler,
        )
        assert cost == 0

    def test_cost_reduction_four_draconic(self):
        """Cost floors at 0 with four+ Draconic chain links."""
        game = make_game_shell()
        dragonscaler = _make_dragonscaler()
        _equip(game, dragonscaler)
        _setup_draconic_chain(game, 4)

        cost = game.action_builder._get_equipment_instant_cost(
            game.state, 0, dragonscaler,
        )
        assert cost == 0

    def test_grant_go_again_to_draconic_attack(self):
        """Dragonscaler grants Go Again to the active Draconic attack."""
        game = make_game_shell()
        dragonscaler = _make_dragonscaler()
        _equip(game, dragonscaler)
        attacks = _setup_draconic_chain(game, 1)
        atk = attacks[0]

        ctx = _build_ctx(game, dragonscaler, controller_index=0)
        _dragonscaler_flight_path(ctx)

        # Attack should now have Go Again
        attack_keywords = game.effect_engine.get_modified_keywords(game.state, atk)
        assert Keyword.GO_AGAIN in attack_keywords

    def test_destroys_self(self):
        """Dragonscaler destroys itself on activation."""
        game = make_game_shell()
        dragonscaler = _make_dragonscaler()
        _equip(game, dragonscaler)
        _setup_draconic_chain(game, 1)

        ctx = _build_ctx(game, dragonscaler, controller_index=0)
        _dragonscaler_flight_path(ctx)

        # Equipment slot should be empty
        assert game.state.players[0].equipment[EquipmentSlot.LEGS] is None
        # Should be in graveyard
        assert dragonscaler in game.state.players[0].graveyard

    def test_weapon_untap_for_additional_attack(self):
        """If the active attack is a weapon proxy, untap the source weapon."""
        game = make_game_shell()
        dragonscaler = _make_dragonscaler()
        _equip(game, dragonscaler)

        # Create a Draconic weapon and proxy
        weapon = _make_draconic_weapon(instance_id=100)
        weapon.is_tapped = True
        game.state.players[0].weapons.append(weapon)

        proxy = _make_weapon_proxy(weapon, instance_id=101)
        game.combat_mgr.open_chain(game.state)
        link = game.combat_mgr.add_chain_link(game.state, proxy, 1)
        link.attack_source = weapon

        ctx = _build_ctx(game, dragonscaler, controller_index=0, chain_link=link)
        _dragonscaler_flight_path(ctx)

        # Weapon should be untapped
        assert not weapon.is_tapped
        # Attack should have Go Again
        attack_keywords = game.effect_engine.get_modified_keywords(game.state, proxy)
        assert Keyword.GO_AGAIN in attack_keywords

    def test_no_untap_for_card_attack(self):
        """Non-weapon attacks should get Go Again but no weapon untap."""
        game = make_game_shell()
        dragonscaler = _make_dragonscaler()
        _equip(game, dragonscaler)
        attacks = _setup_draconic_chain(game, 1)
        atk = attacks[0]
        assert not atk.is_proxy  # Not a weapon proxy

        ctx = _build_ctx(game, dragonscaler, controller_index=0)
        _dragonscaler_flight_path(ctx)

        # Go Again should be granted
        attack_keywords = game.effect_engine.get_modified_keywords(game.state, atk)
        assert Keyword.GO_AGAIN in attack_keywords

    def test_not_offered_when_attack_not_draconic(self):
        """Dragonscaler should NOT be offered when the active attack is not Draconic."""
        game = make_game_shell()
        dragonscaler = _make_dragonscaler()
        _equip(game, dragonscaler)

        # Non-Draconic attack
        game.combat_mgr.open_chain(game.state)
        atk = make_ninja_attack(instance_id=1, power=4, cost=0, owner_index=0)
        game.combat_mgr.add_chain_link(game.state, atk, 1)

        # Give resources
        _add_pitchable_card(game, player_index=0, pitch=3)

        # Check precondition
        can_use = game.action_builder._can_use_equipment_instant(
            game.state, 0, dragonscaler,
        )
        assert not can_use, "Dragonscaler should not be usable on non-Draconic attack"

    def test_not_offered_when_no_active_attack(self):
        """Dragonscaler should NOT be offered when there's no active attack."""
        game = make_game_shell()
        dragonscaler = _make_dragonscaler()
        _equip(game, dragonscaler)

        # No combat chain open
        can_use = game.action_builder._can_use_equipment_instant(
            game.state, 0, dragonscaler,
        )
        assert not can_use

    def test_not_offered_when_cant_afford(self):
        """Dragonscaler should NOT be offered when the player can't afford it."""
        game = make_game_shell()
        dragonscaler = _make_dragonscaler()
        _equip(game, dragonscaler)
        _setup_draconic_chain(game, 1)  # cost = 2

        # Player has 0 resources and no pitchable cards
        assert game.state.resource_points[0] == 0
        assert len(game.state.players[0].hand) == 0

        can_afford = game.action_builder._can_afford_resource_cost(
            game.state, 0, 2,
        )
        assert not can_afford

    def test_offered_when_can_afford(self):
        """Dragonscaler IS offered when preconditions and cost are met."""
        game = make_game_shell()
        dragonscaler = _make_dragonscaler()
        _equip(game, dragonscaler)
        _setup_draconic_chain(game, 1)  # cost = 2

        # Give the player enough resources
        _add_pitchable_card(game, player_index=0, pitch=3)

        # Build reaction decision for attacker
        decision = game.action_builder.build_reaction_decision(
            game.state, priority_player=0, attacker_index=0, defender_index=1,
        )

        ds_options = [o for o in decision.options if "Dragonscaler" in o.description]
        assert len(ds_options) == 1, f"Expected Dragonscaler option, got: {[o.description for o in decision.options]}"

    def test_not_offered_opponents_draconic_attack(self):
        """Dragonscaler should NOT be offered on opponent's Draconic attack."""
        game = make_game_shell()
        dragonscaler = _make_dragonscaler()
        _equip(game, dragonscaler)

        # Opponent's Draconic attack
        game.combat_mgr.open_chain(game.state)
        atk = make_draconic_ninja_attack(instance_id=1, owner_index=1)
        game.combat_mgr.add_chain_link(game.state, atk, 0)

        can_use = game.action_builder._can_use_equipment_instant(
            game.state, 0, dragonscaler,
        )
        assert not can_use

    def test_handler_does_nothing_on_non_draconic(self):
        """Handler returns early if attack is not Draconic."""
        game = make_game_shell()
        dragonscaler = _make_dragonscaler()
        _equip(game, dragonscaler)

        game.combat_mgr.open_chain(game.state)
        atk = make_ninja_attack(instance_id=1, power=4, cost=0, owner_index=0)
        game.combat_mgr.add_chain_link(game.state, atk, 1)

        ctx = _build_ctx(game, dragonscaler, controller_index=0)
        _dragonscaler_flight_path(ctx)

        # Equipment should NOT be destroyed (handler returned early)
        assert game.state.players[0].equipment[EquipmentSlot.LEGS] is dragonscaler

    def test_registered_in_ability_registry(self):
        """Dragonscaler Flight Path is registered as equipment_instant_effect."""
        game = make_game_shell()
        handler = game.ability_registry.lookup(
            "equipment_instant_effect", "Dragonscaler Flight Path",
        )
        assert handler is not None


# ===========================================================================
# Keyword parsing tests
# ===========================================================================


class TestKeywordParsing:
    """Test _is_keyword_inherent for correct keyword classification."""

    def test_enflame_no_inherent_go_again(self):
        """Enflame the Firebrand: Go Again is conditional (gets go again)."""
        from htc.cards.card_db import _is_keyword_inherent
        text = (
            "When this attacks, if you control 2 or more Draconic chain links, "
            "this gets **go again**, 3 or more, your attacks are Draconic this "
            "combat chain, 4 or more, this gets +2{p}."
        )
        assert not _is_keyword_inherent(Keyword.GO_AGAIN, text)

    def test_surging_strike_has_inherent_go_again(self):
        """Surging Strike: Go Again is inherent (standalone bold)."""
        from htc.cards.card_db import _is_keyword_inherent
        assert _is_keyword_inherent(Keyword.GO_AGAIN, "**Go again**")

    def test_keyword_not_in_text_trusted(self):
        """Keywords not mentioned in text at all are trusted from Card Keywords."""
        from htc.cards.card_db import _is_keyword_inherent
        assert _is_keyword_inherent(Keyword.STEALTH, "Some other text")

    def test_gains_is_conditional(self):
        """'gains go again' is conditional."""
        from htc.cards.card_db import _is_keyword_inherent
        assert not _is_keyword_inherent(
            Keyword.GO_AGAIN,
            "This gains **go again**.",
        )

    def test_has_is_conditional(self):
        """'has go again' is conditional."""
        from htc.cards.card_db import _is_keyword_inherent
        assert not _is_keyword_inherent(
            Keyword.GO_AGAIN,
            "If this hits, it has **go again**.",
        )

    def test_loses_is_conditional(self):
        """'loses dominate' is conditional."""
        from htc.cards.card_db import _is_keyword_inherent
        assert not _is_keyword_inherent(
            Keyword.DOMINATE,
            "This loses **dominate**.",
        )

    def test_standalone_bold_is_inherent(self):
        """Standalone bold keyword is inherent."""
        from htc.cards.card_db import _is_keyword_inherent
        assert _is_keyword_inherent(
            Keyword.DOMINATE,
            "**Dominate**\nDo something else.",
        )

    def test_mixed_inherent_and_conditional(self):
        """If keyword appears both standalone and conditional, it's inherent."""
        from htc.cards.card_db import _is_keyword_inherent
        text = "**Go again**. If something else, this gets **go again**."
        assert _is_keyword_inherent(Keyword.GO_AGAIN, text)

    def test_real_card_data_enflame(self):
        """Verify Enflame does NOT have Go Again in parsed card data."""
        from htc.cards.card_db import CardDatabase
        db = CardDatabase.load("data/cards.tsv")
        enflame = db.get_by_name("Enflame the Firebrand")
        assert enflame is not None
        assert Keyword.GO_AGAIN not in enflame.keywords

    def test_real_card_data_surging_strike(self):
        """Verify Surging Strike DOES have Go Again in parsed card data."""
        from htc.cards.card_db import CardDatabase
        db = CardDatabase.load("data/cards.tsv")
        surging = db.get_by_name("Surging Strike")
        assert surging is not None
        assert Keyword.GO_AGAIN in surging.keywords
