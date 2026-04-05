"""Scenario: Timing and sequencing edge cases from strategy articles.

Tests:
1. Dragonscaler Flight Path — equipment instant registers as attack_reaction_effect,
   should be available during the reaction step. Validates the handler correctly
   requires a Draconic active attack and grants go again + weapon untap.
2. Take the Tempo — NOT IMPLEMENTED in abilities. Skipped.
3. Kiss of Death full damage math via Flick — Flick destroys KoD dagger, deals
   1 damage (Flick), Kiss on-hit fires for 1 additional life loss. Total: 2.
4. Fealty + Ignite sequencing — Break Fealty to grant Draconic supertype to
   next card. That card gets Ignite's cost reduction because it's now Draconic.
5. Fire Tenet: Strike First is NOT Draconic — Fire Tenet has Ninja supertype only,
   NOT Draconic. Should NOT count toward Draconic chain link totals for Enflame,
   Spreading Flames, etc.

Sources: strategy-cindra-redline.md, strategy-arakni-masterclass.md
"""

from __future__ import annotations

import logging

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.cards.abilities.equipment import _dragonscaler_flight_path, _flick_knives
from htc.cards.abilities.ninja import (
    _ignite_on_attack,
    count_draconic_chain_links,
    _enflame_the_firebrand_on_attack,
    _spreading_flames_on_attack,
)
from htc.cards.abilities.tokens import _fealty_instant
from htc.engine.continuous import EffectDuration, make_cost_modifier
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
from tests.conftest import make_game_shell
from tests.abilities.conftest import (
    make_ability_context,
    make_dagger_weapon,
    make_draconic_ninja_attack,
    make_ninja_attack,
    make_weapon_proxy,
    setup_draconic_chain,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared card factories
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


def _make_flight_path(instance_id: int = 52, owner_index: int = 0) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"flight-path-{instance_id}",
        name="Dragonscaler Flight Path",
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
        supertypes=frozenset({SuperType.DRACONIC}),
        keywords=frozenset(),
        functional_text="Instant - {r}{r}{r}, destroy this: Target Draconic attack gets go again.",
        type_text="Draconic Equipment - Legs",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.LEGS,
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


def _make_kiss_of_death(instance_id: int = 60, owner_index: int = 0) -> CardInstance:
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


def _make_fealty_token(instance_id: int = 500, owner_index: int = 0) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"fealty-{instance_id}",
        name="Fealty",
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=None,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.TOKEN}),
        subtypes=frozenset({SubType.AURA}),
        supertypes=frozenset({SuperType.DRACONIC}),
        keywords=frozenset(),
        functional_text="Instant - Destroy this: The next card you play this turn is Draconic.",
        type_text="Draconic Token - Aura",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.PERMANENT,
    )


def _make_fire_tenet(instance_id: int = 300, owner_index: int = 0, color: Color = Color.RED) -> CardInstance:
    """Fire Tenet: Strike First — Ninja Attack Action (NOT Draconic)."""
    pitch = {Color.RED: 1, Color.YELLOW: 2, Color.BLUE: 3}.get(color, 1)
    power = {Color.RED: 3, Color.YELLOW: 2, Color.BLUE: 1}.get(color, 3)
    defn = CardDefinition(
        unique_id=f"fire-tenet-{instance_id}",
        name="Fire Tenet: Strike First",
        color=color,
        pitch=pitch,
        cost=0,
        power=power,
        defense=2,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.NINJA}),  # Ninja, NOT Draconic
        keywords=frozenset({Keyword.GO_AGAIN}),
        functional_text="When this attacks, your next Draconic attack this combat chain gets +1{p}.",
        type_text="Ninja Action - Attack",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
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

    return game


# ---------------------------------------------------------------------------
# Test 1: Dragonscaler Flight Path timing
# ---------------------------------------------------------------------------


class TestDragonscalerFlightPathTiming:
    """Dragonscaler Flight Path is an instant equipment activation.
    It should be offered during the reaction step and should correctly
    grant Go Again to a Draconic attack and untap a weapon if applicable.

    Source: strategy-cindra-redline.md
    """

    def test_flight_path_grants_go_again_to_draconic_attack(self, scenario_recorder):
        """Flight Path should grant Go Again to the active Draconic attack."""
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        flight_path = _make_flight_path(instance_id=52, owner_index=0)
        state.players[0].equipment[EquipmentSlot.LEGS] = flight_path

        # Open combat chain and add a Draconic attack
        game.combat_mgr.open_chain(state)
        atk = make_draconic_ninja_attack(instance_id=1, name="Dragon Power", power=4, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, atk, 1)

        # Activate Flight Path
        ctx = make_ability_context(game, flight_path, controller_index=0, chain_link=link)
        _dragonscaler_flight_path(ctx)

        # Check: Go Again was granted
        modified_kw = game.effect_engine.get_modified_keywords(state, atk)
        assert Keyword.GO_AGAIN in modified_kw, (
            "Dragonscaler Flight Path should grant Go Again to a Draconic attack"
        )

        # Check: equipment was destroyed
        assert flight_path.zone == Zone.GRAVEYARD, (
            "Flight Path should be destroyed (in graveyard) after activation"
        )

    def test_flight_path_no_effect_on_non_draconic(self, scenario_recorder):
        """Flight Path should have no effect on a non-Draconic attack."""
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        flight_path = _make_flight_path(instance_id=52, owner_index=0)
        state.players[0].equipment[EquipmentSlot.LEGS] = flight_path

        # Open combat chain and add a non-Draconic (plain Ninja) attack
        game.combat_mgr.open_chain(state)
        atk = make_ninja_attack(instance_id=1, name="Leg Tap", power=4, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, atk, 1)

        # Activate Flight Path
        ctx = make_ability_context(game, flight_path, controller_index=0, chain_link=link)
        _dragonscaler_flight_path(ctx)

        # Should NOT grant Go Again (non-Draconic attack)
        modified_kw = game.effect_engine.get_modified_keywords(state, atk)
        assert Keyword.GO_AGAIN not in modified_kw, (
            "Flight Path should not grant Go Again to a non-Draconic attack"
        )

    def test_flight_path_untaps_weapon_on_proxy_attack(self, scenario_recorder):
        """Flight Path should untap the source weapon when the active attack
        is a weapon proxy, allowing an additional weapon attack.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        flight_path = _make_flight_path(instance_id=52, owner_index=0)
        state.players[0].equipment[EquipmentSlot.LEGS] = flight_path

        # Set up a Draconic weapon and its attack proxy
        weapon = make_dagger_weapon(instance_id=100, name="Claw of Vynserakai", owner_index=0)
        weapon.definition = CardDefinition(
            unique_id="claw-100",
            name="Claw of Vynserakai",
            color=None,
            pitch=None,
            cost=0,
            power=3,
            defense=None,
            health=None,
            intellect=None,
            arcane=None,
            types=frozenset({CardType.WEAPON}),
            subtypes=frozenset({SubType.DAGGER, SubType.ONE_HAND}),
            supertypes=frozenset({SuperType.DRACONIC, SuperType.NINJA}),
            keywords=frozenset(),
            functional_text="",
            type_text="Draconic Ninja Weapon - Dagger (1H)",
        )
        weapon.is_tapped = True  # Already attacked
        state.players[0].weapons = [weapon]

        # Create a proxy for the weapon attack with Draconic supertype
        proxy = make_weapon_proxy(weapon, instance_id=200, owner_index=0)

        game.combat_mgr.open_chain(state)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = weapon

        ctx = make_ability_context(game, flight_path, controller_index=0, chain_link=link)
        _dragonscaler_flight_path(ctx)

        assert not weapon.is_tapped, (
            "Flight Path should untap the source weapon when used on a weapon proxy attack"
        )

    def test_flight_path_registered_as_equipment_instant(self, scenario_recorder):
        """Flight Path should be registered as equipment_instant_effect in the
        ability registry, which means it's offered during priority windows
        (reaction steps), not just attack reaction windows.
        """
        game = _setup_base_game()
        recorder = scenario_recorder.bind(game)

        handler = game.ability_registry.lookup("equipment_instant_effect", "Dragonscaler Flight Path")
        assert handler is not None, (
            "Dragonscaler Flight Path should be registered as equipment_instant_effect "
            "so it can be offered during instant-speed priority windows"
        )


# ---------------------------------------------------------------------------
# Test 2: Take the Tempo — SKIPPED (not implemented)
# ---------------------------------------------------------------------------

class TestTakeTheTempoHitCount:
    """Take the Tempo counts HITS not chain links.

    SKIPPED: Take the Tempo is not implemented in the ability registry.
    The card is in cards.tsv but has no on_hit handler registered.

    When implemented, it should count Flick Knives dagger hits toward
    the hit total (similar to how Mask of Momentum works with Flick).
    """

    def test_take_the_tempo_not_implemented(self, scenario_recorder):
        """Verify Take the Tempo is not yet in the ability registry."""
        game = _setup_base_game()
        recorder = scenario_recorder.bind(game)

        handler = game.ability_registry.lookup("on_hit", "Take the Tempo")
        assert handler is None, (
            "Take the Tempo is expected to not be implemented yet. "
            "If this fails, the card was implemented and real tests should replace this stub."
        )


# ---------------------------------------------------------------------------
# Test 3: Kiss of Death full damage math via Flick
# ---------------------------------------------------------------------------


class TestKissOfDeathFlickDamageMath:
    """Flick destroys Kiss of Death dagger, deals 1 damage (Flick),
    Kiss on-hit fires for 1 additional life loss. Total: 2 damage from
    a 0-cost activation.

    Source: strategy-arakni-masterclass.md
    """

    def test_kiss_of_death_flick_total_damage_is_2(self, scenario_recorder):
        """Flick + Kiss of Death on-hit should deal exactly 2 total life points.

        Breakdown: Flick deals 1 damage (DEAL_DAMAGE), Kiss on-hit causes
        1 life loss (LOSE_LIFE). Net life change = -2.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        flick = _make_flick_knives(instance_id=51, owner_index=0)
        state.players[0].equipment[EquipmentSlot.ARMS] = flick

        # One dagger is attacking (on-chain), Kiss of Death is off-chain
        dagger_attacking = make_dagger_weapon(instance_id=100, name="Kunai of Retribution", owner_index=0)
        kiss = _make_kiss_of_death(instance_id=60, owner_index=0)
        state.players[0].weapons = [dagger_attacking, kiss]

        game.combat_mgr.open_chain(state)
        proxy = make_weapon_proxy(dagger_attacking, instance_id=200, owner_index=0)
        link = game.combat_mgr.add_chain_link(state, proxy, 1)
        link.attack_source = dagger_attacking

        initial_life = state.players[1].life_total

        ctx = make_ability_context(game, flick, controller_index=0, chain_link=link)
        _flick_knives(ctx)

        final_life = state.players[1].life_total
        total_damage = initial_life - final_life

        assert total_damage == 2, (
            f"Flick + Kiss of Death should deal exactly 2 total damage "
            f"(1 from Flick + 1 from Kiss on-hit). "
            f"Got {total_damage}: {initial_life} -> {final_life}"
        )

    def test_kiss_on_hit_fires_via_flick(self, scenario_recorder):
        """Kiss of Death's on_hit ('they lose 1 life') should fire when
        the dagger is destroyed via Flick Knives.
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

        # Track LOSE_LIFE events (Kiss of Death on-hit)
        life_loss_events = []
        game.events.register_handler(
            EventType.LOSE_LIFE,
            lambda e: life_loss_events.append(e),
        )

        ctx = make_ability_context(game, flick, controller_index=0, chain_link=link)
        _flick_knives(ctx)

        assert len(life_loss_events) >= 1, (
            "Kiss of Death on_hit should trigger a LOSE_LIFE event when "
            "flicked via Flick Knives"
        )


# ---------------------------------------------------------------------------
# Test 4: Fealty + Ignite sequencing
# ---------------------------------------------------------------------------


class TestFealtyIgniteSequencing:
    """Break Fealty to grant Draconic supertype to next card.
    Then that card gets Ignite's cost reduction because it's now Draconic.

    Source: strategy-cindra-redline.md
    """

    def test_fealty_grants_draconic_to_next_card(self, scenario_recorder):
        """Breaking Fealty should make the next played card Draconic via
        continuous effect (supertype grant).
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        fealty = _make_fealty_token(instance_id=500, owner_index=0)
        state.players[0].permanents.append(fealty)

        # Activate Fealty instant (destroy it, grant Draconic to next card)
        ctx = make_ability_context(game, fealty, controller_index=0)
        _fealty_instant(ctx)

        # Fealty should be destroyed
        assert fealty.zone == Zone.GRAVEYARD, "Fealty should be in graveyard after activation"

        # Now play a Ninja attack (no Draconic supertype by default)
        atk = make_ninja_attack(instance_id=1, name="Leg Tap", power=4, owner_index=0)
        atk.zone = Zone.COMBAT_CHAIN  # Simulating being played

        # Check: the effect engine should see it as Draconic
        supertypes = game.effect_engine.get_modified_supertypes(state, atk)
        assert SuperType.DRACONIC in supertypes, (
            "After breaking Fealty, the next card played should have the Draconic "
            "supertype granted by the continuous effect"
        )

    def test_ignite_cost_reduction_applies_to_fealty_granted_draconic(self, scenario_recorder):
        """Ignite should reduce cost of Fealty-granted Draconic cards.

        Sequence:
        1. Play Ignite (on-attack: next Draconic card costs 1 less)
        2. Break Fealty (next card is Draconic)
        3. Next Ninja card should now be Draconic AND cost 1 less
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        # Step 1: Set up Ignite on attack
        game.combat_mgr.open_chain(state)
        ignite_card = make_draconic_ninja_attack(
            instance_id=1, name="Ignite", power=2, owner_index=0,
        )
        link = game.combat_mgr.add_chain_link(state, ignite_card, 1)

        ctx = make_ability_context(game, ignite_card, controller_index=0, chain_link=link)
        _ignite_on_attack(ctx)

        # Step 2: Break Fealty to grant Draconic to next card
        fealty = _make_fealty_token(instance_id=500, owner_index=0)
        state.players[0].permanents.append(fealty)

        fealty_ctx = make_ability_context(game, fealty, controller_index=0)
        _fealty_instant(fealty_ctx)

        # Step 3: The next card played is a 1-cost Ninja attack
        next_card = make_ninja_attack(
            instance_id=2, name="Dragon Power", power=4, cost=1, owner_index=0,
        )
        next_card.zone = Zone.COMBAT_CHAIN

        # Verify Draconic was granted
        supertypes = game.effect_engine.get_modified_supertypes(state, next_card)
        assert SuperType.DRACONIC in supertypes, (
            "After Fealty activation, the next card should be Draconic"
        )

        # Verify cost reduction from Ignite applies
        modified_cost = game.effect_engine.get_modified_cost(state, next_card)
        assert modified_cost == 0, (
            f"Ignite should reduce cost of Draconic card by 1: "
            f"base cost 1 - 1 (Ignite) = 0. Got {modified_cost}"
        )


# ---------------------------------------------------------------------------
# Test 5: Fire Tenet: Strike First is NOT Draconic
# ---------------------------------------------------------------------------


class TestFireTenetNotDraconic:
    """Fire Tenet: Strike First has the Ninja supertype only, NOT Draconic.
    It should NOT count toward Draconic chain link totals for Enflame,
    Spreading Flames, etc.

    This is a common competitive mistake — players assume Fire Tenet is
    Draconic because it references Draconic attacks.

    Source: strategy-cindra-redline.md
    """

    def test_fire_tenet_definition_has_ninja_not_draconic(self, scenario_recorder):
        """Fire Tenet's definition supertypes should be {Ninja} only."""
        game = _setup_base_game()
        recorder = scenario_recorder.bind(game)

        fire_tenet = _make_fire_tenet(instance_id=300, owner_index=0)

        assert SuperType.NINJA in fire_tenet.definition.supertypes, (
            "Fire Tenet should have the Ninja supertype"
        )
        assert SuperType.DRACONIC not in fire_tenet.definition.supertypes, (
            "Fire Tenet should NOT have the Draconic supertype — it's a common "
            "competitive mistake to assume it's Draconic because it references "
            "Draconic attacks"
        )

    def test_fire_tenet_does_not_count_as_draconic_chain_link(self, scenario_recorder):
        """Fire Tenet on the chain should NOT increase the Draconic chain link count.

        Scenario:
        - CL1: Draconic attack (counts)
        - CL2: Fire Tenet (should NOT count)
        - Total Draconic chain links = 1
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)

        # CL1: Draconic attack
        draconic_atk = make_draconic_ninja_attack(instance_id=1, power=4, owner_index=0)
        game.combat_mgr.add_chain_link(state, draconic_atk, 1)

        # CL2: Fire Tenet (Ninja only, not Draconic)
        fire_tenet = _make_fire_tenet(instance_id=300, owner_index=0)
        game.combat_mgr.add_chain_link(state, fire_tenet, 1)

        # Count Draconic chain links
        ctx = make_ability_context(game, fire_tenet, controller_index=0)
        draconic_count = count_draconic_chain_links(ctx)

        assert draconic_count == 1, (
            f"Only the explicitly Draconic attack should count. "
            f"Fire Tenet is Ninja, not Draconic. Got count={draconic_count}"
        )

    def test_fire_tenet_among_draconic_chain_for_enflame(self, scenario_recorder):
        """Verify Fire Tenet doesn't inflate the count for Enflame thresholds.

        Scenario: CL1=Draconic, CL2=Fire Tenet, CL3=Enflame.
        Enflame sees 2 Draconic links (CL1 + CL3 itself), not 3.
        Fire Tenet on CL2 does NOT count.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)

        # CL1: Draconic attack
        draconic1 = make_draconic_ninja_attack(instance_id=1, power=3, owner_index=0)
        game.combat_mgr.add_chain_link(state, draconic1, 1)

        # CL2: Fire Tenet (NOT Draconic)
        fire_tenet = _make_fire_tenet(instance_id=300, owner_index=0)
        game.combat_mgr.add_chain_link(state, fire_tenet, 1)

        # CL3: Enflame the Firebrand (Draconic Ninja)
        enflame = make_draconic_ninja_attack(
            instance_id=3, name="Enflame the Firebrand", power=2, owner_index=0,
        )
        link3 = game.combat_mgr.add_chain_link(state, enflame, 1)

        ctx = make_ability_context(game, enflame, controller_index=0, chain_link=link3)
        draconic_count = count_draconic_chain_links(ctx)

        # Should be 2: CL1 (Draconic) + CL3 (Enflame, Draconic). NOT CL2.
        assert draconic_count == 2, (
            f"Draconic count should be 2 (CL1 + CL3). Fire Tenet on CL2 is Ninja only. "
            f"Got {draconic_count}"
        )
