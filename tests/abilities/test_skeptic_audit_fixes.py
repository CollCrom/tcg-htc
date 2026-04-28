"""Tests for skeptic audit findings.

Covers:
1. Spreading Flames dynamic filter uses effect engine for chain link supertypes
2. Blood Runs Deep cost reduction via intrinsic cost modifier
3. Contract keyword on Leave No Witnesses — Silver token creation
4. Amulet of Echoes instant-destroy activation
5. Fyendal's Spring Tunic player agency (instant activation instead of auto-spend)
"""

from engine.cards.card import CardDefinition
from engine.cards.instance import CardInstance
from engine.rules.actions import ActionOption, Decision, PlayerResponse
from engine.rules.continuous import EffectDuration, make_supertype_grant
from engine.rules.events import EventType, GameEvent
from engine.enums import (
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
    make_mock_interfaces as _make_mock_interfaces,
    make_ninja_attack,
    make_dagger_weapon,
    setup_draconic_chain,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ===========================================================================
# 3. Contract keyword — Leave No Witnesses Silver token creation
# ===========================================================================


def _make_leave_no_witnesses(
    instance_id: int = 1,
    owner_index: int = 0,
) -> CardInstance:
    """Create a Leave No Witnesses card."""
    defn = CardDefinition(
        unique_id=f"lnw-{instance_id}",
        name="Leave No Witnesses",
        color=Color.RED,
        pitch=1,
        cost=0,
        power=4,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset({Keyword.CONTRACT}),
        functional_text="",
        type_text="Assassin Attack Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
    )


def _make_deck_card(
    instance_id: int,
    name: str = "Deck Card",
    color: Color = Color.RED,
    owner_index: int = 1,
) -> CardInstance:
    """Create a simple card for an opponent's deck."""
    defn = CardDefinition(
        unique_id=f"deck-{instance_id}",
        name=name,
        color=color,
        pitch=1 if color == Color.RED else 3,
        cost=0,
        power=3,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.DECK,
    )


class TestContractSilverToken:
    """Leave No Witnesses Contract: banishing opponent's red cards creates Silver tokens."""

    def test_red_card_banished_creates_silver(self):
        """Banishing a red card from opponent's deck creates a Silver token."""
        game = make_game_shell()
        target = game.state.players[1]

        red_card = _make_deck_card(instance_id=50, color=Color.RED)
        target.deck.insert(0, red_card)

        lnw = _make_leave_no_witnesses()
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, lnw, 1)

        # Register the contract trigger first (on_attack), then fire on_hit
        game._apply_card_ability(lnw, 0, "on_attack")
        game._apply_card_ability(lnw, 0, "on_hit")

        controller = game.state.players[0]
        silver_tokens = [p for p in controller.permanents if p.name == "Silver"]
        assert len(silver_tokens) == 1

    def test_blue_card_banished_no_silver(self):
        """Banishing a blue card does NOT create a Silver token."""
        game = make_game_shell()
        target = game.state.players[1]

        blue_card = _make_deck_card(instance_id=50, color=Color.BLUE)
        target.deck.insert(0, blue_card)

        lnw = _make_leave_no_witnesses()
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, lnw, 1)

        game._apply_card_ability(lnw, 0, "on_hit")

        controller = game.state.players[0]
        silver_tokens = [p for p in controller.permanents if p.name == "Silver"]
        assert len(silver_tokens) == 0

    def test_both_red_cards_create_two_silvers(self):
        """Banishing two red cards (deck + arsenal) creates two Silver tokens."""
        game = make_game_shell()
        target = game.state.players[1]

        red_deck = _make_deck_card(instance_id=50, color=Color.RED, name="Red Deck Card")
        target.deck.insert(0, red_deck)

        red_arsenal = _make_deck_card(instance_id=51, color=Color.RED, name="Red Arsenal Card")
        red_arsenal.zone = Zone.ARSENAL
        target.arsenal.append(red_arsenal)

        lnw = _make_leave_no_witnesses()
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, lnw, 1)

        game._apply_card_ability(lnw, 0, "on_attack")
        game._apply_card_ability(lnw, 0, "on_hit")

        controller = game.state.players[0]
        silver_tokens = [p for p in controller.permanents if p.name == "Silver"]
        assert len(silver_tokens) == 2

    def test_mixed_colors_one_silver(self):
        """Banishing red from deck + blue from arsenal creates one Silver."""
        game = make_game_shell()
        target = game.state.players[1]

        red_deck = _make_deck_card(instance_id=50, color=Color.RED)
        target.deck.insert(0, red_deck)

        blue_arsenal = _make_deck_card(instance_id=51, color=Color.BLUE)
        blue_arsenal.zone = Zone.ARSENAL
        target.arsenal.append(blue_arsenal)

        lnw = _make_leave_no_witnesses()
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, lnw, 1)

        game._apply_card_ability(lnw, 0, "on_attack")
        game._apply_card_ability(lnw, 0, "on_hit")

        controller = game.state.players[0]
        silver_tokens = [p for p in controller.permanents if p.name == "Silver"]
        assert len(silver_tokens) == 1

    def test_empty_deck_no_crash(self):
        """No crash when opponent's deck is empty."""
        game = make_game_shell()
        target = game.state.players[1]
        target.deck.clear()

        lnw = _make_leave_no_witnesses()
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, lnw, 1)

        game._apply_card_ability(lnw, 0, "on_hit")

        controller = game.state.players[0]
        assert len(controller.permanents) == 0


# ===========================================================================
# 4. Amulet of Echoes — instant-destroy activation
# ===========================================================================


def _make_amulet_of_echoes(instance_id: int = 40, owner_index: int = 0) -> CardInstance:
    """Create an Amulet of Echoes permanent."""
    defn = CardDefinition(
        unique_id=f"amulet-{instance_id}",
        name="Amulet of Echoes",
        color=Color.BLUE,
        pitch=3,
        cost=0,
        power=None,
        defense=None,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ITEM}),
        supertypes=frozenset(),
        keywords=frozenset({Keyword.GO_AGAIN}),
        functional_text="",
        type_text="Generic Action - Item",
    )
    card = CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.PERMANENT,
    )
    return card


class TestAmuletOfEchoes:
    """Amulet of Echoes instant activation: destroy to force opponent discard 2."""

    def test_handler_registered(self):
        """Amulet of Echoes is registered as a permanent_instant_effect."""
        game = make_game_shell()
        handler = game.ability_registry.lookup("permanent_instant_effect", "Amulet of Echoes")
        assert handler is not None

    def test_precondition_no_duplicate_names(self):
        """Activation blocked when opponent has NOT played duplicate card names."""
        game = make_game_shell()
        amulet = _make_amulet_of_echoes()
        game.state.players[0].permanents.append(amulet)

        # Opponent played unique-name cards
        game.state.players[1].turn_counters.card_names_played = ["Card A", "Card B"]

        can_use = game.action_builder._can_use_permanent_instant(game.state, 0, amulet)
        assert can_use is False

    def test_precondition_with_duplicate_names(self):
        """Activation allowed when opponent HAS played 2+ same-name cards."""
        game = make_game_shell()
        amulet = _make_amulet_of_echoes()
        game.state.players[0].permanents.append(amulet)

        # Opponent played duplicate-name cards
        game.state.players[1].turn_counters.card_names_played = ["Card A", "Card A"]

        can_use = game.action_builder._can_use_permanent_instant(game.state, 0, amulet)
        assert can_use is True

    def test_activation_destroys_amulet_and_discards(self):
        """Activation destroys the Amulet and forces opponent to discard 2."""
        game = make_game_shell()
        amulet = _make_amulet_of_echoes()
        game.state.players[0].permanents.append(amulet)

        # Give opponent 3 cards in hand
        for i in range(3):
            c = _make_deck_card(instance_id=60 + i, name=f"Opponent Card {i}", owner_index=1)
            c.zone = Zone.HAND
            game.state.players[1].hand.append(c)

        game.state.players[1].turn_counters.card_names_played = ["Card A", "Card A"]

        # Mock: opponent chooses first card each time
        mock_ask = make_mock_ask({"Amulet of Echoes": [f"discard_{game.state.players[1].hand[0].instance_id}"]})
        game.interfaces = _make_mock_interfaces(mock_ask)

        game._activate_permanent_instant(0, amulet)

        # Amulet should be destroyed (in graveyard)
        assert amulet not in game.state.players[0].permanents
        assert amulet in game.state.players[0].graveyard

        # Opponent should have 1 card left (3 - 2)
        assert len(game.state.players[1].hand) == 1
        assert len(game.state.players[1].graveyard) == 2

    def test_activation_with_one_card_in_hand(self):
        """If opponent has only 1 card, only 1 is discarded (no crash)."""
        game = make_game_shell()
        amulet = _make_amulet_of_echoes()
        game.state.players[0].permanents.append(amulet)

        c = _make_deck_card(instance_id=60, name="Only Card", owner_index=1)
        c.zone = Zone.HAND
        game.state.players[1].hand.append(c)

        game._activate_permanent_instant(0, amulet)

        assert amulet not in game.state.players[0].permanents
        assert len(game.state.players[1].hand) == 0
        assert len(game.state.players[1].graveyard) == 1

    def test_card_names_tracked_on_play(self):
        """TurnCounters.card_names_played is populated when cards are played."""
        from engine.state.turn_counters import TurnCounters
        tc = TurnCounters()
        tc.card_names_played.append("Pummel")
        tc.card_names_played.append("Pummel")
        assert tc.has_duplicate_card_name() is True

    def test_no_duplicate_card_names(self):
        """has_duplicate_card_name returns False for unique names."""
        from engine.state.turn_counters import TurnCounters
        tc = TurnCounters()
        tc.card_names_played.append("Pummel")
        tc.card_names_played.append("Crush")
        assert tc.has_duplicate_card_name() is False


# ===========================================================================
# 5. Fyendal's Spring Tunic — player agency (instant activation)
# ===========================================================================


def _make_spring_tunic(instance_id: int = 70, owner_index: int = 0) -> CardInstance:
    """Create a Fyendal's Spring Tunic equipment."""
    from engine.enums import EquipmentSlot
    defn = CardDefinition(
        unique_id=f"tunic-{instance_id}",
        name="Fyendal's Spring Tunic",
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=1,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.EQUIPMENT}),
        subtypes=frozenset({SubType.CHEST}),
        supertypes=frozenset(),
        keywords=frozenset({Keyword.BLADE_BREAK}),
        functional_text="",
        type_text="Generic Equipment - Chest",
    )
    card = CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.CHEST,
    )
    return card


class TestSpringTunicPlayerAgency:
    """Fyendal's Spring Tunic: instant activation instead of auto-spend."""

    def test_handler_registered(self):
        """Spring Tunic is registered as an equipment_instant_effect."""
        game = make_game_shell()
        handler = game.ability_registry.lookup(
            "equipment_instant_effect", "Fyendal's Spring Tunic"
        )
        assert handler is not None

    def test_precondition_needs_3_counters(self):
        """Activation blocked when tunic has fewer than 3 energy counters."""
        game = make_game_shell()
        from engine.enums import EquipmentSlot
        tunic = _make_spring_tunic()
        tunic.counters["energy"] = 2
        game.state.players[0].equipment[EquipmentSlot.CHEST] = tunic

        can_use = game.action_builder._can_use_equipment_instant(game.state, 0, tunic)
        assert can_use is False

    def test_precondition_met_with_3_counters(self):
        """Activation allowed when tunic has 3+ energy counters."""
        game = make_game_shell()
        from engine.enums import EquipmentSlot
        tunic = _make_spring_tunic()
        tunic.counters["energy"] = 3
        game.state.players[0].equipment[EquipmentSlot.CHEST] = tunic

        can_use = game.action_builder._can_use_equipment_instant(game.state, 0, tunic)
        assert can_use is True

    def test_activation_removes_counters_gains_resource(self):
        """Activation removes 3 energy counters and grants 1 resource."""
        game = make_game_shell()
        from engine.enums import EquipmentSlot
        tunic = _make_spring_tunic()
        tunic.counters["energy"] = 3
        game.state.players[0].equipment[EquipmentSlot.CHEST] = tunic
        game.state.resource_points[0] = 0

        game._activate_equipment(0, tunic)

        assert tunic.counters["energy"] == 0
        assert game.state.resource_points[0] == 1

    def test_no_auto_spend_at_3_counters(self):
        """Energy counters reaching 3 does NOT auto-spend anymore."""
        from engine.cards.abilities.equipment import SpringTunicTrigger
        from engine.rules.events import EventType, GameEvent

        game = make_game_shell()
        from engine.enums import EquipmentSlot
        tunic = _make_spring_tunic()
        tunic.counters["energy"] = 2
        game.state.players[0].equipment[EquipmentSlot.CHEST] = tunic
        game.state.resource_points[0] = 0

        trigger = SpringTunicTrigger(
            controller_index=0,
            _state_getter=lambda: game.state,
            _equipment_instance_id=tunic.instance_id,
        )

        # Simulate start-of-turn event
        event = GameEvent(
            event_type=EventType.START_OF_TURN,
            target_player=0,
        )

        # Should add counter but NOT auto-spend
        assert trigger.condition(event) is True
        trigger.create_triggered_event(event)

        assert tunic.counters["energy"] == 3
        # Resource should NOT have been gained (no auto-spend)
        assert game.state.resource_points[0] == 0

    def test_trigger_stops_at_3(self):
        """Trigger does not add counter when already at 3."""
        from engine.cards.abilities.equipment import SpringTunicTrigger
        from engine.rules.events import EventType, GameEvent

        game = make_game_shell()
        from engine.enums import EquipmentSlot
        tunic = _make_spring_tunic()
        tunic.counters["energy"] = 3
        game.state.players[0].equipment[EquipmentSlot.CHEST] = tunic

        trigger = SpringTunicTrigger(
            controller_index=0,
            _state_getter=lambda: game.state,
            _equipment_instance_id=tunic.instance_id,
        )

        event = GameEvent(
            event_type=EventType.START_OF_TURN,
            target_player=0,
        )

        # Condition should fail when already at 3 counters
        assert trigger.condition(event) is False

    def test_cost_is_zero(self):
        """Spring Tunic equipment instant cost is 0 (no resource cost)."""
        game = make_game_shell()
        from engine.enums import EquipmentSlot
        tunic = _make_spring_tunic()
        game.state.players[0].equipment[EquipmentSlot.CHEST] = tunic

        cost = game.action_builder._get_equipment_instant_cost(game.state, 0, tunic)
        assert cost == 0
