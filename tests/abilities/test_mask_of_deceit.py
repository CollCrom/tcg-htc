"""Tests for Mask of Deceit and Agent of Chaos / Demi-Hero infrastructure.

Verifies:
1. Demi-Heroes loaded into player state from deck list
2. Mask of Deceit defending triggers Agent of Chaos transformation
3. Random selection when attacker is NOT marked
4. Player choice when attacker IS marked
5. Hero transformation changes player.hero and preserves original_hero
6. Blade Break destroys Mask of Deceit after defending
7. Loader auto-includes Agent of Chaos for Arakni, Marionette
"""

from __future__ import annotations

from random import Random

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.cards.abilities.equipment import MaskOfDeceitTrigger, register_equipment_triggers
from htc.decks.deck_list import DeckList
from htc.decks.loader import AGENT_OF_CHAOS_DEMI_HEROES, parse_deck_list
from htc.engine.actions import Decision, PlayerResponse
from htc.engine.events import EventBus, EventType, GameEvent
from htc.engine.effects import EffectEngine
from htc.enums import (
    CardType,
    DecisionType,
    EquipmentSlot,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from htc.state.combat_state import ChainLink
from htc.state.game_state import GameState
from htc.state.player_state import PlayerState
from tests.conftest import make_card, make_equipment, make_game_shell, make_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hero(
    name: str = "Arakni, Marionette",
    instance_id: int = 900,
    owner_index: int = 0,
    health: int = 20,
    intellect: int = 4,
) -> CardInstance:
    """Create a hero CardInstance for testing."""
    defn = CardDefinition(
        unique_id=f"hero-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=None,
        health=health,
        intellect=intellect,
        arcane=None,
        types=frozenset({CardType.HERO}),
        subtypes=frozenset(),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset(),
        functional_text="",
        type_text="Hero - Assassin",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HERO,
    )


def _make_demi_hero(
    name: str = "Arakni, Black Widow",
    instance_id: int = 800,
    owner_index: int = 0,
) -> CardInstance:
    """Create a Demi-Hero CardInstance for testing."""
    defn = CardDefinition(
        unique_id=f"demi-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=None,
        health=None,  # Demi-Hero health is * (keep current)
        intellect=None,
        arcane=None,
        types=frozenset({CardType.DEMI_HERO}),
        subtypes=frozenset(),
        supertypes=frozenset({SuperType.CHAOS, SuperType.ASSASSIN}),
        keywords=frozenset(),
        functional_text="",
        type_text="Chaos Assassin Demi-Hero",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HERO,
    )


def _make_mask_of_deceit(instance_id: int = 50, owner_index: int = 0) -> CardInstance:
    """Create Mask of Deceit equipment."""
    defn = CardDefinition(
        unique_id=f"mask-deceit-{instance_id}",
        name="Mask of Deceit",
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=2,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.EQUIPMENT}),
        subtypes=frozenset({SubType.HEAD}),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset({Keyword.BLADE_BREAK}),
        functional_text=(
            "Arakni Specialization. When this defends, become a random Agent of "
            "Chaos. If the attacking hero is marked, instead choose the Agent of "
            "Chaos. Blade Break"
        ),
        type_text="Assassin Equipment - Head",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HEAD,
    )


def _setup_mask_test(*, attacker_marked: bool = False):
    """Set up a game shell with Mask of Deceit and Demi-Heroes.

    Returns (game, mask, demi_heroes_list, chain_link).
    """
    game = make_game_shell()
    state = game.state

    # Player 0 = defender with Mask of Deceit
    hero_0 = _make_hero(instance_id=900, owner_index=0)
    state.players[0].hero = hero_0
    state.players[0].life_total = 20

    mask = _make_mask_of_deceit(instance_id=50, owner_index=0)
    state.players[0].equipment[EquipmentSlot.HEAD] = mask

    # Add demi-heroes
    dh_names = ["Arakni, Black Widow", "Arakni, Funnel Web", "Arakni, Tarantula"]
    dh_list = []
    for i, name in enumerate(dh_names):
        dh = _make_demi_hero(name=name, instance_id=800 + i, owner_index=0)
        dh_list.append(dh)
    state.players[0].demi_heroes = dh_list

    # Player 1 = attacker
    hero_1 = _make_hero(name="Cindra", instance_id=901, owner_index=1)
    state.players[1].hero = hero_1
    state.players[1].is_marked = attacker_marked

    # Set up an active combat chain link (player 1 attacking player 0)
    attack_card = make_card(instance_id=10, name="Big Attack", power=5, owner_index=1)
    link = ChainLink(
        link_number=1,
        active_attack=attack_card,
        attack_target_index=0,
    )
    state.combat_chain.chain_links.append(link)

    return game, mask, dh_list, link


# ---------------------------------------------------------------------------
# Task 1: Demi-Hero / Agent of Chaos infrastructure
# ---------------------------------------------------------------------------


class TestDeckListDemiHeroes:
    """DeckList.demi_heroes field and loader auto-inclusion."""

    def test_deck_list_has_demi_heroes_field(self):
        dl = DeckList(hero_name="Test Hero")
        assert dl.demi_heroes == []

    def test_loader_auto_includes_agent_of_chaos_for_arakni(self):
        text = """\
Hero: Arakni, Marionette
Weapons: Hunter's Klaive
Equipment: Mask of Deceit
---
3x Kiss of Death (Red)
"""
        dl = parse_deck_list(text)
        assert dl.demi_heroes == list(AGENT_OF_CHAOS_DEMI_HEROES)

    def test_loader_no_auto_include_for_other_heroes(self):
        text = """\
Hero: Cindra, Dracai of Retribution
Weapons: Claw of Vynserakai
Equipment: Mask of Momentum
---
3x Some Card (Red)
"""
        dl = parse_deck_list(text)
        assert dl.demi_heroes == []

    def test_loader_explicit_demi_heroes_override(self):
        text = """\
Hero: Arakni, Marionette
Weapons: Hunter's Klaive
Demi-Heroes: Arakni, Black Widow; Arakni, Tarantula
Equipment: Mask of Deceit
---
3x Kiss of Death (Red)
"""
        dl = parse_deck_list(text)
        # Explicit takes priority — no auto-include
        assert "Arakni, Black Widow" in dl.demi_heroes
        assert "Arakni, Tarantula" in dl.demi_heroes
        # Only the two explicitly listed, not all 6
        assert len(dl.demi_heroes) == 2


class TestPlayerStateDemiHeroes:
    """PlayerState demi_heroes and original_hero fields."""

    def test_player_state_has_demi_heroes_field(self):
        ps = PlayerState(index=0)
        assert ps.demi_heroes == []

    def test_player_state_has_original_hero_field(self):
        ps = PlayerState(index=0)
        assert ps.original_hero is None

    def test_demi_heroes_loaded_into_player_state(self):
        """Demi-Heroes from deck list are stored in player.demi_heroes."""
        game, _, dh_list, _ = _setup_mask_test()
        assert len(game.state.players[0].demi_heroes) == 3
        assert game.state.players[0].demi_heroes[0].name == "Arakni, Black Widow"


# ---------------------------------------------------------------------------
# Task 1: Hero transformation
# ---------------------------------------------------------------------------


class TestHeroTransformation:
    """_become_agent_of_chaos changes player.hero and preserves original."""

    def test_transformation_changes_hero(self):
        game, _, dh_list, _ = _setup_mask_test()
        agent = dh_list[0]
        game._become_agent_of_chaos(0, agent)
        assert game.state.players[0].hero is agent
        assert game.state.players[0].hero.name == "Arakni, Black Widow"

    def test_transformation_preserves_original_hero(self):
        game, _, dh_list, _ = _setup_mask_test()
        original = game.state.players[0].hero
        game._become_agent_of_chaos(0, dh_list[0])
        assert game.state.players[0].original_hero is original
        assert game.state.players[0].original_hero.name == "Arakni, Marionette"

    def test_second_transformation_keeps_first_original(self):
        """Multiple transformations only save the initial hero."""
        game, _, dh_list, _ = _setup_mask_test()
        original = game.state.players[0].hero
        game._become_agent_of_chaos(0, dh_list[0])
        game._become_agent_of_chaos(0, dh_list[1])
        # original_hero should still point to the very first hero
        assert game.state.players[0].original_hero is original
        assert game.state.players[0].hero.name == "Arakni, Funnel Web"

    def test_transformation_does_not_change_life(self):
        game, _, dh_list, _ = _setup_mask_test()
        game.state.players[0].life_total = 15
        game._become_agent_of_chaos(0, dh_list[0])
        assert game.state.players[0].life_total == 15

    def test_transformation_emits_become_agent_event(self):
        game, _, dh_list, _ = _setup_mask_test()
        events_captured = []
        game.events.register_handler(
            EventType.BECOME_AGENT,
            lambda e: events_captured.append(e),
        )
        game._become_agent_of_chaos(0, dh_list[0])
        assert len(events_captured) == 1
        assert events_captured[0].event_type == EventType.BECOME_AGENT
        assert events_captured[0].target_player == 0
        assert events_captured[0].data["new_hero"] == "Arakni, Black Widow"


# ---------------------------------------------------------------------------
# Task 2: Mask of Deceit triggered effect
# ---------------------------------------------------------------------------


class TestMaskOfDeceitTrigger:
    """Mask of Deceit defends -> Agent of Chaos transformation."""

    def test_trigger_fires_on_defend_declared(self):
        """When Mask of Deceit is used to defend, the trigger fires."""
        game, mask, dh_list, link = _setup_mask_test(attacker_marked=False)

        # Seed the RNG so random choice is deterministic
        game.state.rng = Random(42)

        # Register the trigger
        register_equipment_triggers(
            event_bus=game.events,
            effect_engine=game.effect_engine,
            state_getter=lambda: game.state,
            player_index=0,
            player_state=game.state.players[0],
            game=game,
        )

        # Emit DEFEND_DECLARED with mask as source
        game.events.emit(GameEvent(
            event_type=EventType.DEFEND_DECLARED,
            source=mask,
            target_player=0,
            data={"chain_link": link},
        ))
        game._process_pending_triggers()

        # Hero should have been transformed
        assert game.state.players[0].hero.name in [dh.name for dh in dh_list]

    def test_random_selection_when_not_marked(self):
        """When attacker is NOT marked, agent is randomly selected."""
        game, mask, dh_list, link = _setup_mask_test(attacker_marked=False)
        game.state.rng = Random(42)

        register_equipment_triggers(
            event_bus=game.events,
            effect_engine=game.effect_engine,
            state_getter=lambda: game.state,
            player_index=0,
            player_state=game.state.players[0],
            game=game,
        )

        game.events.emit(GameEvent(
            event_type=EventType.DEFEND_DECLARED,
            source=mask,
            target_player=0,
            data={"chain_link": link},
        ))
        game._process_pending_triggers()

        # Verify transformation happened (we can't predict which one with
        # certainty without knowing the RNG, but it should be one of them)
        hero_name = game.state.players[0].hero.name
        assert hero_name in [dh.name for dh in dh_list]
        assert game.state.players[0].original_hero is not None

    def test_player_choice_when_marked(self):
        """When attacker IS marked, player chooses which Agent of Chaos."""
        game, mask, dh_list, link = _setup_mask_test(attacker_marked=True)

        # Set up mock ask to choose the second demi-hero
        target_dh = dh_list[1]  # Arakni, Funnel Web
        game.interfaces = [None, None]  # not used; we override _ask

        def mock_ask(decision: Decision) -> PlayerResponse:
            if decision.decision_type == DecisionType.CHOOSE_AGENT:
                return PlayerResponse(
                    selected_option_ids=[f"agent_{target_dh.instance_id}"]
                )
            return PlayerResponse(selected_option_ids=["pass"])

        game._ask = mock_ask

        register_equipment_triggers(
            event_bus=game.events,
            effect_engine=game.effect_engine,
            state_getter=lambda: game.state,
            player_index=0,
            player_state=game.state.players[0],
            game=game,
        )

        game.events.emit(GameEvent(
            event_type=EventType.DEFEND_DECLARED,
            source=mask,
            target_player=0,
            data={"chain_link": link},
        ))
        game._process_pending_triggers()

        assert game.state.players[0].hero.name == "Arakni, Funnel Web"

    def test_no_trigger_on_other_equipment_defend(self):
        """Trigger does NOT fire when a different equipment defends."""
        game, mask, dh_list, link = _setup_mask_test()
        game.state.rng = Random(42)

        # Add some other equipment
        other_eq = make_equipment(instance_id=99, name="Other Helm", subtype=SubType.CHEST)
        other_eq.owner_index = 0

        register_equipment_triggers(
            event_bus=game.events,
            effect_engine=game.effect_engine,
            state_getter=lambda: game.state,
            player_index=0,
            player_state=game.state.players[0],
            game=game,
        )

        # Emit DEFEND_DECLARED with the OTHER equipment as source
        game.events.emit(GameEvent(
            event_type=EventType.DEFEND_DECLARED,
            source=other_eq,
            target_player=0,
            data={"chain_link": link},
        ))
        game._process_pending_triggers()

        # Hero should NOT have been transformed
        assert game.state.players[0].hero.name == "Arakni, Marionette"

    def test_no_demi_heroes_available(self):
        """If no demi-heroes are loaded, trigger fires but does nothing."""
        game, mask, _, link = _setup_mask_test()
        game.state.players[0].demi_heroes = []  # clear them

        register_equipment_triggers(
            event_bus=game.events,
            effect_engine=game.effect_engine,
            state_getter=lambda: game.state,
            player_index=0,
            player_state=game.state.players[0],
            game=game,
        )

        game.events.emit(GameEvent(
            event_type=EventType.DEFEND_DECLARED,
            source=mask,
            target_player=0,
            data={"chain_link": link},
        ))
        game._process_pending_triggers()

        # No transformation
        assert game.state.players[0].hero.name == "Arakni, Marionette"


# ---------------------------------------------------------------------------
# Task 2: Blade Break
# ---------------------------------------------------------------------------


class TestBladeBreak:
    """Blade Break destroys Mask of Deceit after defending."""

    def test_blade_break_destroys_mask(self):
        """Equipment with Blade Break keyword is destroyed after defending.

        This is handled by keyword_engine.apply_equipment_degradation(),
        called during the Close Step. We test it directly.
        """
        game = make_game_shell()
        state = game.state

        mask = _make_mask_of_deceit(instance_id=50, owner_index=0)
        state.players[0].equipment[EquipmentSlot.HEAD] = mask

        # Simulate: mask defended in the combat chain
        attack = make_card(instance_id=10, name="Attack", power=5, owner_index=1)
        link = ChainLink(link_number=1, active_attack=attack, attack_target_index=0)
        link.defending_cards.append(mask)
        state.combat_chain.chain_links.append(link)

        # Apply equipment degradation (same as Close Step)
        game.keyword_engine.apply_equipment_degradation(state)

        # Mask should be destroyed (moved to graveyard, slot cleared)
        assert state.players[0].equipment[EquipmentSlot.HEAD] is None
        assert mask in state.players[0].graveyard
        assert mask.zone == Zone.GRAVEYARD
