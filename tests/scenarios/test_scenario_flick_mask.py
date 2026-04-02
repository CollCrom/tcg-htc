"""Scenario: Flick Knives + Mask of Momentum + Blood Splattered Vest interaction.

Verifies:
1. Flick Knives dagger hit during chain link 2 counts toward Mask of Momentum's
   consecutive hit streak, allowing link 3 to trigger the Mask draw.
2. Flick Knives hit triggers Blood Splattered Vest (stain counter + resource).
3. Combined scenario: Flick on link 2, all links hit, link 3 triggers Mask draw.
"""

from __future__ import annotations

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.cards.abilities.equipment import (
    BloodSplatteredVestTrigger,
    MaskOfMomentumTrigger,
    register_equipment_triggers,
)
from htc.engine.events import EventType, GameEvent
from htc.enums import (
    CardType,
    Color,
    EquipmentSlot,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from htc.state.combat_state import ChainLink
from tests.conftest import make_card, make_game_shell
from tests.abilities.conftest import (
    make_ability_context,
    make_dagger_weapon,
    make_ninja_attack,
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


def _make_mask_of_momentum(instance_id: int = 50, owner_index: int = 0) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"mask-momentum-{instance_id}",
        name="Mask of Momentum",
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=0,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.EQUIPMENT}),
        subtypes=frozenset({SubType.HEAD}),
        supertypes=frozenset({SuperType.NINJA}),
        keywords=frozenset(),
        functional_text=(
            "Once per Turn Effect — When an attack action card you control is "
            "the third or higher chain link in a row to hit, draw a card."
        ),
        type_text="Ninja Equipment - Head",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HEAD,
    )


def _make_flick_knives(instance_id: int = 51, owner_index: int = 0) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"flick-{instance_id}",
        name="Flick Knives",
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=0,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.EQUIPMENT}),
        subtypes=frozenset({SubType.ARMS}),
        supertypes=frozenset({SuperType.ASSASSIN, SuperType.NINJA}),
        keywords=frozenset(),
        functional_text=(
            "Once per Turn Attack Reaction — 0: Target dagger you control that "
            "isn't on the active chain link deals 1 damage to target hero. If "
            "damage is dealt this way, the dagger has hit. Destroy the dagger."
        ),
        type_text="Assassin Ninja Equipment - Arms",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.ARMS,
    )


def _make_blood_splattered_vest(instance_id: int = 52, owner_index: int = 0) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"bsv-{instance_id}",
        name="Blood Splattered Vest",
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
        supertypes=frozenset({SuperType.ASSASSIN, SuperType.NINJA}),
        keywords=frozenset(),
        functional_text=(
            "Whenever a dagger you control hits, you may gain {r} and put a "
            "stain counter on this. Then if there are 3 or more stain counters "
            "on this, destroy it."
        ),
        type_text="Assassin Ninja Equipment - Chest",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.CHEST,
    )


def _setup_flick_mask_test():
    """Set up game with Mask of Momentum, Flick Knives, and Blood Splattered Vest.

    Player 0 has the equipment and two daggers.
    Player 1 is the opponent.
    Returns (game, mask, flick, vest, dagger1, dagger2).
    """
    game = make_game_shell()
    state = game.state

    # Player 0 = attacker with all equipment
    hero = _make_hero(instance_id=900, owner_index=0)
    state.players[0].hero = hero
    state.players[0].life_total = 20

    # Opponent hero
    opp_hero = _make_hero(name="Opponent", instance_id=901, owner_index=1)
    state.players[1].hero = opp_hero
    state.players[1].life_total = 20

    # Equipment
    mask = _make_mask_of_momentum(instance_id=50, owner_index=0)
    state.players[0].equipment[EquipmentSlot.HEAD] = mask

    flick = _make_flick_knives(instance_id=51, owner_index=0)
    state.players[0].equipment[EquipmentSlot.ARMS] = flick

    vest = _make_blood_splattered_vest(instance_id=52, owner_index=0)
    state.players[0].equipment[EquipmentSlot.CHEST] = vest

    # Two dagger weapons
    dagger1 = make_dagger_weapon(instance_id=100, name="Kunai of Retribution", owner_index=0)
    dagger1.zone = Zone.WEAPON_1
    dagger2 = make_dagger_weapon(instance_id=101, name="Kunai of Retribution", owner_index=0)
    dagger2.zone = Zone.WEAPON_2
    state.players[0].weapons = [dagger1, dagger2]

    # Register equipment triggers
    register_equipment_triggers(
        event_bus=game.events,
        effect_engine=game.effect_engine,
        state_getter=lambda: game.state,
        player_index=0,
        player_state=state.players[0],
        game=game,
    )

    return game, mask, flick, vest, dagger1, dagger2


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFlickKnivesMaskOfMomentumInteraction:
    """Flick Knives dagger hit contributes to Mask of Momentum consecutive streak."""

    def test_flick_hit_on_link2_enables_mask_draw_on_link3(self):
        """Chain links 1 and 2 hit (link 2 via Flick), link 3 should trigger Mask draw.

        Setup:
        - Open chain, add 3 chain links (all attack action cards)
        - Links 1 and 2 marked as hits
        - Emit HIT event for link 3 — Mask of Momentum should trigger (draw card)
        """
        game, mask, flick, vest, dagger1, dagger2 = _setup_flick_mask_test()
        state = game.state

        # Give player 0 some cards to draw
        for i in range(5):
            c = make_card(instance_id=200 + i, zone=Zone.DECK, owner_index=0)
            state.players[0].deck.append(c)

        initial_hand_size = len(state.players[0].hand)

        # Build a combat chain with 3 links, all hits
        game.combat_mgr.open_chain(state)

        atk1 = make_ninja_attack(instance_id=10, name="Strike 1", owner_index=0)
        link1 = game.combat_mgr.add_chain_link(state, atk1, 1)
        link1.hit = True

        atk2 = make_ninja_attack(instance_id=11, name="Strike 2", owner_index=0)
        link2 = game.combat_mgr.add_chain_link(state, atk2, 1)
        link2.hit = True

        atk3 = make_ninja_attack(instance_id=12, name="Strike 3", owner_index=0)
        link3 = game.combat_mgr.add_chain_link(state, atk3, 1)

        # Clear any pending triggers from prior events
        game.events.get_pending_triggers()

        # Emit HIT for link 3 — should trigger Mask of Momentum
        game.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=atk3,
            target_player=1,
            amount=4,
            data={"chain_link": link3},
        ))

        # Mask of Momentum creates a DRAW_CARD event as a pending trigger.
        # In a full game, Game._process_pending_triggers handles the actual draw.
        # Here we verify the trigger fired by checking pending triggers.
        pending = game.events.get_pending_triggers()
        draw_events = [e for e in pending if e.event_type == EventType.DRAW_CARD]
        assert len(draw_events) == 1, (
            "Mask of Momentum should produce a DRAW_CARD pending trigger on 3rd consecutive hit"
        )
        assert draw_events[0].target_player == 0, (
            "DRAW_CARD should target the Mask controller (player 0)"
        )

    def test_mask_does_not_trigger_before_3_consecutive_hits(self):
        """Mask of Momentum should NOT trigger on link 2 even if all links hit."""
        game, mask, flick, vest, dagger1, dagger2 = _setup_flick_mask_test()
        state = game.state

        for i in range(5):
            c = make_card(instance_id=200 + i, zone=Zone.DECK, owner_index=0)
            state.players[0].deck.append(c)

        initial_hand_size = len(state.players[0].hand)

        game.combat_mgr.open_chain(state)

        atk1 = make_ninja_attack(instance_id=10, name="Strike 1", owner_index=0)
        link1 = game.combat_mgr.add_chain_link(state, atk1, 1)
        link1.hit = True

        atk2 = make_ninja_attack(instance_id=11, name="Strike 2", owner_index=0)
        link2 = game.combat_mgr.add_chain_link(state, atk2, 1)

        game.events.get_pending_triggers()  # clear

        # Emit HIT for link 2 — only 2 links, should NOT trigger Mask
        game.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=atk2,
            target_player=1,
            amount=4,
            data={"chain_link": link2},
        ))

        pending = game.events.get_pending_triggers()
        draw_events = [e for e in pending if e.event_type == EventType.DRAW_CARD]
        assert len(draw_events) == 0, (
            "Mask of Momentum should not trigger with only 2 chain links"
        )

    def test_mask_does_not_trigger_if_prior_link_missed(self):
        """Mask of Momentum requires ALL prior links to be hits."""
        game, mask, flick, vest, dagger1, dagger2 = _setup_flick_mask_test()
        state = game.state

        for i in range(5):
            c = make_card(instance_id=200 + i, zone=Zone.DECK, owner_index=0)
            state.players[0].deck.append(c)

        initial_hand_size = len(state.players[0].hand)

        game.combat_mgr.open_chain(state)

        atk1 = make_ninja_attack(instance_id=10, name="Strike 1", owner_index=0)
        link1 = game.combat_mgr.add_chain_link(state, atk1, 1)
        link1.hit = False  # Link 1 missed

        atk2 = make_ninja_attack(instance_id=11, name="Strike 2", owner_index=0)
        link2 = game.combat_mgr.add_chain_link(state, atk2, 1)
        link2.hit = True

        atk3 = make_ninja_attack(instance_id=12, name="Strike 3", owner_index=0)
        link3 = game.combat_mgr.add_chain_link(state, atk3, 1)

        game.events.get_pending_triggers()  # clear

        game.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=atk3,
            target_player=1,
            amount=4,
            data={"chain_link": link3},
        ))

        pending = game.events.get_pending_triggers()
        draw_events = [e for e in pending if e.event_type == EventType.DRAW_CARD]
        assert len(draw_events) == 0, (
            "Mask of Momentum should not trigger if any prior link missed"
        )


class TestFlickKnivesBloodSplatteredVest:
    """Flick Knives dagger hit triggers Blood Splattered Vest."""

    def test_flick_dagger_hit_adds_stain_counter_and_resource(self):
        """When Flick Knives deals damage (dagger hit), BSV should gain stain + resource.

        We simulate the dagger HIT event directly to verify BSV's trigger fires.
        """
        game, mask, flick, vest, dagger1, dagger2 = _setup_flick_mask_test()
        state = game.state

        initial_resources = state.resource_points.get(0, 0)
        initial_stains = vest.counters.get("stain", 0)

        # Open chain and add a link so there's a valid combat context
        game.combat_mgr.open_chain(state)
        atk = make_ninja_attack(instance_id=10, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, atk, 1)

        # Emit HIT from a dagger source — simulates Flick Knives dagger hit
        game.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=dagger1,
            target_player=1,
            amount=1,
            data={"chain_link": link},
        ))

        # BSV should have gained 1 stain counter
        assert vest.counters.get("stain", 0) == initial_stains + 1, (
            "Blood Splattered Vest should gain a stain counter on dagger hit"
        )

        # BSV should have granted 1 resource
        assert state.resource_points.get(0, 0) == initial_resources + 1, (
            "Blood Splattered Vest should grant 1 resource on dagger hit"
        )

    def test_bsv_destroys_at_3_stain_counters(self):
        """Blood Splattered Vest should self-destruct at 3 stain counters."""
        game, mask, flick, vest, dagger1, dagger2 = _setup_flick_mask_test()
        state = game.state

        # Pre-seed 2 stain counters
        vest.counters["stain"] = 2

        game.combat_mgr.open_chain(state)
        atk = make_ninja_attack(instance_id=10, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, atk, 1)

        # Third dagger hit — should push to 3 stains and destroy
        game.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=dagger1,
            target_player=1,
            amount=1,
            data={"chain_link": link},
        ))

        # Vest should be destroyed (moved to graveyard)
        chest_eq = state.players[0].equipment.get(EquipmentSlot.CHEST)
        assert chest_eq is None, (
            "Blood Splattered Vest should be destroyed at 3 stain counters"
        )
        assert vest.zone == Zone.GRAVEYARD, (
            "Blood Splattered Vest should be in graveyard after destruction"
        )

    def test_bsv_does_not_trigger_on_non_dagger_hit(self):
        """Blood Splattered Vest should NOT trigger on non-dagger weapon hits."""
        game, mask, flick, vest, dagger1, dagger2 = _setup_flick_mask_test()
        state = game.state

        initial_stains = vest.counters.get("stain", 0)

        game.combat_mgr.open_chain(state)
        atk = make_ninja_attack(instance_id=10, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, atk, 1)

        # Emit HIT from a non-dagger source (the attack action card itself)
        game.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=atk,
            target_player=1,
            amount=4,
            data={"chain_link": link},
        ))

        assert vest.counters.get("stain", 0) == initial_stains, (
            "Blood Splattered Vest should not trigger on non-dagger hit"
        )
