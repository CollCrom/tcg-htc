"""Scenario: Flick Knives interaction tests.

Verifies three specific Flick Knives interactions:
1. Mask of Momentum streak preserved through Flick dagger hit — the Flick
   dagger hitting on a chain link where the main attack was blocked should
   set link.hit = True, preserving the consecutive hit streak for Mask.
2. Kiss of Death on-hit triggers when flicked — the destroyed dagger's
   on_hit ability should fire because Flick says "the dagger has hit."
3. Graphene Chelicera Flick does NOT trigger on-hit — the token weapon
   has no registered on_hit ability, so no special effect should fire.

These use manual state setup via make_game_shell() for precise control
over equipment, combat chain, and event tracking.
"""

from __future__ import annotations

import logging

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.cards.abilities.equipment import (
    MaskOfMomentumTrigger,
    _flick_knives,
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
from tests.conftest import make_game_shell
from tests.abilities.conftest import (
    make_ability_context,
    make_dagger_weapon,
    make_ninja_attack,
    make_weapon_proxy,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Card Factories
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
        functional_text="",
        type_text="Assassin Ninja Equipment - Arms",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.ARMS,
    )


def _make_mask_of_momentum(instance_id: int = 50, owner_index: int = 0) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"mask-{instance_id}",
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
        functional_text="",
        type_text="Ninja Equipment - Head",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HEAD,
    )


def _make_kiss_of_death(instance_id: int = 60, owner_index: int = 0) -> CardInstance:
    """Create a Kiss of Death card (Assassin Dagger Attack Action).

    In real play this is in hand/deck, but for Flick interaction testing
    we create it as a weapon-like dagger in the weapons list.  The key
    property is that the ability registry has an on_hit handler for it.
    """
    defn = CardDefinition(
        unique_id=f"kiss-{instance_id}",
        name="Kiss of Death",
        color=Color.RED,
        pitch=1,
        cost=0,
        power=2,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.WEAPON}),
        subtypes=frozenset({SubType.DAGGER, SubType.ONE_HAND}),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset({Keyword.STEALTH}),
        functional_text="When this hits a hero, they lose 1{h}.",
        type_text="Assassin Weapon - Dagger (1H)",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.WEAPON_1,
    )


def _make_graphene_chelicera(instance_id: int = 70, owner_index: int = 0) -> CardInstance:
    """Create a Graphene Chelicera token weapon."""
    defn = CardDefinition(
        unique_id="graphene-chelicera-token",
        name="Graphene Chelicera",
        color=None,
        pitch=None,
        cost=None,
        power=1,
        defense=None,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.TOKEN, CardType.WEAPON}),
        subtypes=frozenset({SubType.ARMS, SubType.DAGGER, SubType.ONE_HAND}),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset({Keyword.GO_AGAIN}),
        functional_text="Once per Turn Action - {r}: Attack with this for 1, with go again.",
        type_text="Assassin Arms Equipment Token",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.WEAPON_1,
    )


def _setup_base_game():
    """Create a game shell with heroes set up for Cindra (P0) vs Opponent (P1)."""
    game = make_game_shell()
    state = game.state

    hero = _make_hero(instance_id=900, owner_index=0)
    state.players[0].hero = hero
    state.players[0].life_total = 20

    opp_hero = _make_hero(name="Opponent", instance_id=901, owner_index=1)
    state.players[1].hero = opp_hero
    state.players[1].life_total = 20

    # Give P0 a card in deck so Mask of Momentum draw has something to draw
    filler = CardInstance(
        instance_id=999,
        definition=CardDefinition(
            unique_id="filler-999",
            name="Filler Card",
            color=Color.BLUE,
            pitch=3,
            cost=0,
            power=None,
            defense=3,
            health=None,
            intellect=None,
            arcane=None,
            types=frozenset({CardType.ACTION}),
            subtypes=frozenset(),
            supertypes=frozenset({SuperType.NINJA}),
            keywords=frozenset(),
            functional_text="",
            type_text="",
        ),
        owner_index=0,
        zone=Zone.DECK,
    )
    state.players[0].deck.append(filler)

    return game


# ---------------------------------------------------------------------------
# Test 1: Mask of Momentum streak preserved through Flick dagger hit
# ---------------------------------------------------------------------------


class TestFlickKnivesMaskOfMomentumStreak:
    """Verify that Flick Knives dagger hit on a chain link where the main
    attack was blocked still sets link.hit = True, preserving the Mask of
    Momentum consecutive hit streak.

    Scenario:
    - CL1: Attack hits (undefended) -> link.hit = True (consecutive = 1)
    - CL2: Attack blocked, but Flick dagger hits -> link.hit = True (consecutive = 2)
    - CL3: Attack hits -> link.hit = True (consecutive = 3) -> Mask draws
    """

    def test_flick_dagger_hit_sets_chain_link_hit_flag(self, scenario_recorder):
        """Flick Knives' 'the dagger has hit' should set link.hit = True
        on the chain link, even when the main attack was blocked.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        flick = _make_flick_knives(instance_id=51, owner_index=0)
        state.players[0].equipment[EquipmentSlot.ARMS] = flick

        # Two daggers: one attacks, one is off-chain for Flick
        dagger1 = make_dagger_weapon(instance_id=100, name="Kunai of Retribution", owner_index=0)
        dagger2 = make_dagger_weapon(instance_id=101, name="Kunai of Retribution", owner_index=0)
        dagger2.zone = Zone.WEAPON_2
        state.players[0].weapons = [dagger1, dagger2]

        # Open combat chain
        game.combat_mgr.open_chain(state)

        # CL1: Attack with dagger1 proxy — this link is already resolved as a hit
        proxy1 = make_weapon_proxy(dagger1, instance_id=200, owner_index=0)
        link1 = game.combat_mgr.add_chain_link(state, proxy1, 1)
        link1.attack_source = dagger1
        link1.hit = True  # Simulating undefended hit

        # CL2: Attack with a ninja action card — blocked, but Flick fires
        atk2 = make_ninja_attack(instance_id=2, name="Ninja Strike CL2", power=3, owner_index=0)
        link2 = game.combat_mgr.add_chain_link(state, atk2, 1)
        link2.damage_dealt = 0  # Main attack was fully blocked

        # Flick fires on CL2 — dagger2 is off-chain
        ctx = make_ability_context(game, flick, controller_index=0, chain_link=link2)
        _flick_knives(ctx)

        # The key assertion: Flick's "the dagger has hit" should mark
        # this chain link as a hit for Mask of Momentum tracking.
        assert link2.hit is True, (
            "Flick Knives 'the dagger has hit' should set link.hit = True "
            "on the chain link (preserving Mask of Momentum streak)"
        )

    def test_mask_of_momentum_draws_on_3rd_consecutive_with_flick_assist(self, scenario_recorder):
        """Full 3-link scenario: CL1 hit, CL2 blocked+Flick hit, CL3 hit
        should trigger Mask of Momentum's draw on the 3rd consecutive hit.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        # Equip Mask of Momentum and Flick Knives
        mask = _make_mask_of_momentum(instance_id=50, owner_index=0)
        flick = _make_flick_knives(instance_id=51, owner_index=0)
        state.players[0].equipment[EquipmentSlot.HEAD] = mask
        state.players[0].equipment[EquipmentSlot.ARMS] = flick

        # Register Mask of Momentum trigger on the event bus
        mask_trigger = MaskOfMomentumTrigger(
            controller_index=0,
            _state_getter=lambda: game.state,
            _effect_engine=game.effect_engine,
            _event_bus=game.events,
        )
        game.events.register_trigger(mask_trigger)

        # Two daggers: one attacks on CL1, other is off-chain for Flick on CL2
        dagger1 = make_dagger_weapon(instance_id=100, name="Kunai of Retribution", owner_index=0)
        dagger2 = make_dagger_weapon(instance_id=101, name="Kunai of Retribution", owner_index=0)
        dagger2.zone = Zone.WEAPON_2
        state.players[0].weapons = [dagger1, dagger2]

        # Open combat chain
        game.combat_mgr.open_chain(state)

        # CL1: Dagger attack hits (undefended)
        proxy1 = make_weapon_proxy(dagger1, instance_id=200, owner_index=0)
        link1 = game.combat_mgr.add_chain_link(state, proxy1, 1)
        link1.attack_source = dagger1
        link1.hit = True

        # CL2: Ninja attack action — blocked, but Flick fires
        atk2 = make_ninja_attack(instance_id=2, name="Leg Tap", power=4, owner_index=0)
        link2 = game.combat_mgr.add_chain_link(state, atk2, 1)
        link2.damage_dealt = 0  # fully blocked

        ctx = make_ability_context(game, flick, controller_index=0, chain_link=link2)
        _flick_knives(ctx)
        # After Flick, link2.hit should be True (see test above)

        # CL3: Ninja attack action hits — this is the 3rd consecutive hit
        atk3 = make_ninja_attack(instance_id=3, name="Rising Knee Thrust", power=5, owner_index=0)
        link3 = game.combat_mgr.add_chain_link(state, atk3, 1)
        link3.hit = True

        # Track draw events
        draw_events = []
        game.events.register_handler(
            EventType.DRAW_CARD,
            lambda e: draw_events.append(e),
        )

        initial_deck_size = len(state.players[0].deck)

        # Emit HIT event for CL3 — this should trigger Mask of Momentum
        # because all 3 chain links are hits (CL1 natural, CL2 via Flick, CL3 natural)
        game.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=atk3,
            target_player=1,
            amount=5,
            data={"chain_link": link3},
        ))

        # Process any pending triggers from the HIT event
        game._process_pending_triggers()

        assert len(draw_events) >= 1, (
            "Mask of Momentum should trigger a DRAW_CARD event on the 3rd "
            "consecutive chain link hit (CL1=hit, CL2=Flick hit, CL3=hit). "
            f"Draw events: {draw_events}, "
            f"Chain link hits: CL1={link1.hit}, CL2={link2.hit}, CL3={link3.hit}"
        )


# ---------------------------------------------------------------------------
# Test 2: Kiss of Death on-hit triggers when flicked
# ---------------------------------------------------------------------------


class TestFlickKnivesOnHitTrigger:
    """Verify that when Flick Knives destroys a dagger with an on_hit ability,
    the dagger's on_hit effect fires because Flick says 'the dagger has hit.'

    Kiss of Death's on_hit: 'When this hits a hero, they lose 1{h}.'
    The Flick HIT event should cause the engine to apply Kiss of Death's
    on_hit ability for the destroyed dagger.
    """

    def test_flick_emits_hit_event_with_dagger_source(self, scenario_recorder):
        """Flick Knives should emit a HIT event with the destroyed dagger
        as the source, enabling on-hit trigger dispatch.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        flick = _make_flick_knives(instance_id=51, owner_index=0)
        state.players[0].equipment[EquipmentSlot.ARMS] = flick

        # Attacking dagger + Kiss of Death as off-chain dagger
        dagger_attacking = make_dagger_weapon(instance_id=100, name="Kunai of Retribution", owner_index=0)
        kiss = _make_kiss_of_death(instance_id=60, owner_index=0)
        state.players[0].weapons = [dagger_attacking, kiss]

        # Open chain, attack with the regular dagger
        game.combat_mgr.open_chain(state)
        proxy = make_weapon_proxy(dagger_attacking, instance_id=200, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = dagger_attacking

        # Track HIT events
        hit_events = []
        game.events.register_handler(
            EventType.HIT,
            lambda e: hit_events.append(e),
        )

        ctx = make_ability_context(game, flick, controller_index=0, chain_link=link)
        _flick_knives(ctx)

        # Flick should emit a HIT event sourced from Kiss of Death
        assert len(hit_events) >= 1, (
            "Flick Knives should emit a HIT event for the destroyed dagger"
        )
        assert hit_events[0].source.name == "Kiss of Death", (
            f"HIT event source should be Kiss of Death, got {hit_events[0].source.name}"
        )
        assert hit_events[0].amount == 1, (
            "Flick dagger hit should deal 1 damage"
        )

    def test_kiss_of_death_on_hit_fires_via_flick(self, scenario_recorder):
        """When Kiss of Death is flicked and hits, the opponent should
        lose 1 life from Kiss of Death's on_hit ability.

        Kiss of Death: 'When this hits a hero, they lose 1{h}.'
        This tests whether the engine dispatches on_hit for the flicked
        dagger's HIT event (not just the main attack's HIT).
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        flick = _make_flick_knives(instance_id=51, owner_index=0)
        state.players[0].equipment[EquipmentSlot.ARMS] = flick

        dagger_attacking = make_dagger_weapon(instance_id=100, name="Kunai of Retribution", owner_index=0)
        kiss = _make_kiss_of_death(instance_id=60, owner_index=0)
        state.players[0].weapons = [dagger_attacking, kiss]

        game.combat_mgr.open_chain(state)
        proxy = make_weapon_proxy(dagger_attacking, instance_id=200, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = dagger_attacking

        initial_life = state.players[1].life_total

        # Track life loss events (Kiss of Death uses LOSE_LIFE, not DEAL_DAMAGE)
        life_loss_events = []
        game.events.register_handler(
            EventType.LOSE_LIFE,
            lambda e: life_loss_events.append(e),
        )

        ctx = make_ability_context(game, flick, controller_index=0, chain_link=link)
        _flick_knives(ctx)

        # Flick deals 1 damage (DEAL_DAMAGE). If Kiss of Death's on_hit also
        # fires, the opponent loses 1 additional life (LOSE_LIFE).
        # Total life change: -1 (Flick damage) -1 (Kiss on_hit life loss) = -2
        flick_damage = initial_life - state.players[1].life_total

        # At minimum, Flick should deal 1 damage
        assert flick_damage >= 1, (
            f"Flick should deal at least 1 damage, opponent life went from "
            f"{initial_life} to {state.players[1].life_total}"
        )

        # The on_hit for Kiss of Death should also fire, causing 1 life loss
        # This tests whether the engine dispatches on_hit for flicked daggers.
        # If this fails, the engine needs to be updated to call
        # _apply_card_ability(dagger, controller, "on_hit") when Flick hits.
        assert len(life_loss_events) >= 1, (
            "Kiss of Death's on_hit ('they lose 1 life') should fire when "
            "the dagger hits via Flick Knives. The engine should dispatch "
            "on_hit for the destroyed dagger, not just the main attack. "
            f"Life loss events: {life_loss_events}, "
            f"Life change: {initial_life} -> {state.players[1].life_total}"
        )
        assert life_loss_events[0].amount == 1, (
            f"Kiss of Death on_hit should cause 1 life loss, got {life_loss_events[0].amount}"
        )


# ---------------------------------------------------------------------------
# Test 3: Graphene Chelicera Flick does NOT trigger on-hit
# ---------------------------------------------------------------------------


class TestFlickKnivesGrapheneChelicera:
    """Verify that flicking a Graphene Chelicera deals damage but does NOT
    trigger any on-hit effect, because the token has no registered on_hit
    ability.

    This contrasts with Test 2 (Kiss of Death), which DOES have on_hit.
    """

    def test_graphene_chelicera_can_be_flicked(self, scenario_recorder):
        """Graphene Chelicera is a dagger (SubType.DAGGER), so Flick Knives
        should be able to target and destroy it.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        flick = _make_flick_knives(instance_id=51, owner_index=0)
        state.players[0].equipment[EquipmentSlot.ARMS] = flick

        dagger_attacking = make_dagger_weapon(instance_id=100, name="Kunai of Retribution", owner_index=0)
        chelicera = _make_graphene_chelicera(instance_id=70, owner_index=0)
        state.players[0].weapons = [dagger_attacking, chelicera]

        game.combat_mgr.open_chain(state)
        proxy = make_weapon_proxy(dagger_attacking, instance_id=200, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = dagger_attacking

        initial_life = state.players[1].life_total

        ctx = make_ability_context(game, flick, controller_index=0, chain_link=link)
        _flick_knives(ctx)

        # Chelicera should be destroyed
        assert chelicera not in state.players[0].weapons, (
            "Graphene Chelicera should be removed from weapons after Flick"
        )
        assert chelicera.zone == Zone.GRAVEYARD, (
            "Graphene Chelicera should be in graveyard after Flick"
        )

        # Damage should be dealt
        assert state.players[1].life_total == initial_life - 1, (
            f"Flick should deal 1 damage: {initial_life} -> {state.players[1].life_total}"
        )

    def test_graphene_chelicera_flick_no_on_hit_effect(self, scenario_recorder):
        """Flicking Graphene Chelicera should NOT trigger any on-hit effect.

        Graphene Chelicera has no on_hit ability registered in the ability
        registry. When flicked, it deals 1 damage and emits HIT, but no
        additional effects should fire (no life loss, no mark, no draw, etc.).
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        flick = _make_flick_knives(instance_id=51, owner_index=0)
        state.players[0].equipment[EquipmentSlot.ARMS] = flick

        dagger_attacking = make_dagger_weapon(instance_id=100, name="Kunai of Retribution", owner_index=0)
        chelicera = _make_graphene_chelicera(instance_id=70, owner_index=0)
        state.players[0].weapons = [dagger_attacking, chelicera]

        game.combat_mgr.open_chain(state)
        proxy = make_weapon_proxy(dagger_attacking, instance_id=200, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = dagger_attacking

        # Track ALL event types to verify no unexpected effects
        life_loss_events = []
        draw_events = []
        game.events.register_handler(
            EventType.LOSE_LIFE,
            lambda e: life_loss_events.append(e),
        )
        game.events.register_handler(
            EventType.DRAW_CARD,
            lambda e: draw_events.append(e),
        )

        initial_life = state.players[1].life_total

        ctx = make_ability_context(game, flick, controller_index=0, chain_link=link)
        _flick_knives(ctx)

        # Flick deals 1 damage (via DEAL_DAMAGE), but no on-hit effects
        assert state.players[1].life_total == initial_life - 1, (
            f"Only Flick's 1 damage should apply: {initial_life} -> {state.players[1].life_total}"
        )

        # No LOSE_LIFE events (that would come from an on_hit like Kiss of Death)
        assert len(life_loss_events) == 0, (
            f"Graphene Chelicera has no on_hit — no LOSE_LIFE events should fire. "
            f"Got: {life_loss_events}"
        )

        # No DRAW_CARD events (no Mask of Momentum or other draw triggers)
        assert len(draw_events) == 0, (
            f"No draw effects should trigger from flicking Graphene Chelicera. "
            f"Got: {draw_events}"
        )

    def test_graphene_chelicera_vs_kiss_of_death_contrast(self, scenario_recorder):
        """Contrast test: with both Graphene Chelicera and another dagger
        available, verify Flick picks one and the behavior matches expectations.

        This test sets up both weapons but only one off-chain dagger is
        available (the other is attacking). Flick picks the first available
        off-chain dagger.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        flick = _make_flick_knives(instance_id=51, owner_index=0)
        state.players[0].equipment[EquipmentSlot.ARMS] = flick

        # Only chelicera is off-chain (kunai is attacking)
        dagger_attacking = make_dagger_weapon(instance_id=100, name="Kunai of Retribution", owner_index=0)
        chelicera = _make_graphene_chelicera(instance_id=70, owner_index=0)
        state.players[0].weapons = [dagger_attacking, chelicera]

        game.combat_mgr.open_chain(state)
        proxy = make_weapon_proxy(dagger_attacking, instance_id=200, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = dagger_attacking

        # Track events
        hit_events = []
        game.events.register_handler(EventType.HIT, lambda e: hit_events.append(e))

        ctx = make_ability_context(game, flick, controller_index=0, chain_link=link)
        _flick_knives(ctx)

        # Flick should pick Graphene Chelicera (only off-chain dagger)
        assert len(hit_events) == 1, (
            f"Expected exactly 1 HIT event from Flick, got {len(hit_events)}"
        )
        assert hit_events[0].source.name == "Graphene Chelicera", (
            f"Flick should use Graphene Chelicera as source, got {hit_events[0].source.name}"
        )
        assert chelicera not in state.players[0].weapons, (
            "Graphene Chelicera should be destroyed after Flick"
        )
