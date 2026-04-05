"""Scenario: Agent of Chaos lifecycle — transformation, persistence, return-to-brood.

Verifies:
1. Mask of Deceit defending triggers transformation to Agent of Chaos.
2. Marked opponent → player chooses agent; unmarked → random selection.
3. Agent persists through opponent's turn (their END_OF_TURN doesn't revert).
4. Return-to-brood fires at controller's next end phase.
5. No re-transformation after returning to brood in same end phase
   (returned_to_brood_this_turn flag).
"""

from __future__ import annotations

from random import Random

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.cards.abilities.equipment import (
    MaskOfDeceitTrigger,
    register_equipment_triggers,
)
from htc.engine.actions import Decision, PlayerResponse
from htc.engine.events import EventType, GameEvent
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
from tests.conftest import make_card, make_game_shell


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hero(
    name: str = "Arakni, Marionette",
    instance_id: int = 900,
    owner_index: int = 0,
    health: int = 20,
) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"hero-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=None,
        health=health,
        intellect=4,
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
    defn = CardDefinition(
        unique_id=f"demi-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=None,
        health=None,
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
        functional_text="",
        type_text="Assassin Equipment - Head",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HEAD,
    )


def _setup_agent_test(*, attacker_marked: bool = False, num_agents: int = 3):
    """Set up game for Agent of Chaos testing.

    Player 0 = defender (Arakni) with Mask of Deceit and demi-heroes.
    Player 1 = attacker (opponent).

    Returns (game, mask, demi_heroes, chain_link).
    """
    game = make_game_shell()
    state = game.state
    state.rng = Random(42)

    # Player 0 = Arakni (defender)
    hero_0 = _make_hero(instance_id=900, owner_index=0)
    state.players[0].hero = hero_0
    state.players[0].life_total = 20

    mask = _make_mask_of_deceit(instance_id=50, owner_index=0)
    state.players[0].equipment[EquipmentSlot.HEAD] = mask

    # Create demi-heroes
    agent_names = [
        "Arakni, Black Widow",
        "Arakni, Trap-Door",
        "Arakni, Orb-Weaver",
    ]
    demi_heroes = []
    for i, name in enumerate(agent_names[:num_agents]):
        dh = _make_demi_hero(name=name, instance_id=800 + i, owner_index=0)
        demi_heroes.append(dh)
    state.players[0].demi_heroes = demi_heroes

    # Player 1 = attacker
    hero_1 = _make_hero(name="Cindra, Drachai of Two Talons", instance_id=901, owner_index=1)
    state.players[1].hero = hero_1
    state.players[1].life_total = 20

    if attacker_marked:
        state.players[1].is_marked = True

    # Register equipment triggers (including Mask of Deceit)
    register_equipment_triggers(
        event_bus=game.events,
        effect_engine=game.effect_engine,
        state_getter=lambda: game.state,
        player_index=0,
        player_state=state.players[0],
        game=game,
    )

    # Set up an active combat chain link with an attack from player 1
    game.combat_mgr.open_chain(state)
    attack = make_card(
        instance_id=10, name="Opponent Attack", power=4,
        is_attack=True, zone=Zone.COMBAT_CHAIN, owner_index=1,
    )
    link = game.combat_mgr.add_chain_link(state, attack, 0)

    return game, mask, demi_heroes, link


# ---------------------------------------------------------------------------
# Tests: Transformation
# ---------------------------------------------------------------------------


class TestAgentOfChaosTransformation:
    """Mask of Deceit triggers Agent of Chaos transformation on defend."""

    def test_unmarked_gives_random_agent(self, scenario_recorder):
        """When attacker is NOT marked, a random Agent of Chaos is chosen."""
        game, mask, demi_heroes, link = _setup_agent_test(attacker_marked=False)
        state = game.state
        recorder = scenario_recorder.bind(game)

        recorder.snap("Setup: Arakni with Mask of Deceit, attacker unmarked")

        # Emit DEFEND_DECLARED from the Mask
        game.events.emit(GameEvent(
            event_type=EventType.DEFEND_DECLARED,
            source=mask,
            target_player=0,
            data={"chain_link": link},
        ))

        recorder.snap("After DEFEND_DECLARED — random Agent of Chaos chosen")

        # Hero should have changed to one of the demi-heroes
        assert state.players[0].hero in demi_heroes, (
            "Player hero should be one of the demi-heroes after random transformation"
        )
        # Original hero should be saved
        assert state.players[0].original_hero is not None, (
            "Original hero should be preserved during transformation"
        )

    def test_marked_gives_player_choice(self, scenario_recorder):
        """When attacker IS marked, player chooses which Agent of Chaos.

        We mock the ask callback to always choose the second demi-hero.
        """
        game, mask, demi_heroes, link = _setup_agent_test(attacker_marked=True)
        state = game.state
        recorder = scenario_recorder.bind(game)

        recorder.snap("Setup: Arakni with Mask of Deceit, attacker IS marked")

        # Mock the game's _ask to choose the second demi-hero
        target_agent = demi_heroes[1]  # "Arakni, Trap-Door"
        original_ask = game._ask

        def mock_ask(decision):
            if hasattr(decision, 'decision_type') and decision.decision_type == DecisionType.CHOOSE_AGENT:
                return PlayerResponse(
                    selected_option_ids=[f"agent_{target_agent.instance_id}"]
                )
            return PlayerResponse(selected_option_ids=["pass"])

        game._ask = mock_ask

        game.events.emit(GameEvent(
            event_type=EventType.DEFEND_DECLARED,
            source=mask,
            target_player=0,
            data={"chain_link": link},
        ))

        recorder.snap("After DEFEND_DECLARED — player chose Arakni, Trap-Door")

        assert state.players[0].hero == target_agent, (
            f"Player should have become {target_agent.name} (chosen), "
            f"but is {state.players[0].hero.name}"
        )

    def test_transformation_preserves_life_total(self, scenario_recorder):
        """Life total should not change during Agent of Chaos transformation."""
        game, mask, demi_heroes, link = _setup_agent_test(attacker_marked=False)
        state = game.state
        recorder = scenario_recorder.bind(game)

        life_before = state.players[0].life_total

        recorder.snap("Setup: Arakni at 20 life, pre-transformation")

        game.events.emit(GameEvent(
            event_type=EventType.DEFEND_DECLARED,
            source=mask,
            target_player=0,
            data={"chain_link": link},
        ))

        recorder.snap("After transformation — life total should be unchanged")

        assert state.players[0].life_total == life_before, (
            "Life total should be preserved during transformation"
        )


# ---------------------------------------------------------------------------
# Tests: Return-to-brood lifecycle
# ---------------------------------------------------------------------------


class TestReturnToBrood:
    """Agent of Chaos return-to-brood timing."""

    def test_agent_persists_through_opponents_end_phase(self, scenario_recorder):
        """Agent should NOT revert during opponent's end of turn."""
        game, mask, demi_heroes, link = _setup_agent_test(attacker_marked=False)
        state = game.state
        recorder = scenario_recorder.bind(game)

        # Transform
        game.events.emit(GameEvent(
            event_type=EventType.DEFEND_DECLARED,
            source=mask,
            target_player=0,
            data={"chain_link": link},
        ))

        agent_hero = state.players[0].hero
        assert agent_hero in demi_heroes

        recorder.snap("After transformation — Agent of Chaos active")

        # Opponent's end of turn (player 1) — agent should persist
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=1,
        ))

        recorder.snap("After opponent's END_OF_TURN — Agent should persist")

        assert state.players[0].hero == agent_hero, (
            "Agent should persist through opponent's end of turn"
        )
        assert state.players[0].original_hero is not None, (
            "Original hero should still be saved"
        )

    def test_return_to_brood_at_controllers_end_phase(self, scenario_recorder):
        """Agent should revert to original hero at controller's end of turn."""
        game, mask, demi_heroes, link = _setup_agent_test(attacker_marked=False)
        state = game.state
        recorder = scenario_recorder.bind(game)

        original_hero = state.players[0].hero

        # Transform
        game.events.emit(GameEvent(
            event_type=EventType.DEFEND_DECLARED,
            source=mask,
            target_player=0,
            data={"chain_link": link},
        ))

        assert state.players[0].hero != original_hero

        recorder.snap("After transformation — Agent active, original hero saved")

        # Controller's end of turn (player 0) — should revert
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))

        recorder.snap("After controller's END_OF_TURN — returned to brood")

        assert state.players[0].hero == original_hero, (
            "Hero should revert to original at controller's end of turn"
        )
        assert state.players[0].original_hero is None, (
            "original_hero should be cleared after returning to brood"
        )

    def test_returned_to_brood_flag_set(self, scenario_recorder):
        """returned_to_brood_this_turn flag should be set after reverting."""
        game, mask, demi_heroes, link = _setup_agent_test(attacker_marked=False)
        state = game.state
        recorder = scenario_recorder.bind(game)

        assert not state.players[0].turn_counters.returned_to_brood_this_turn

        # Transform
        game.events.emit(GameEvent(
            event_type=EventType.DEFEND_DECLARED,
            source=mask,
            target_player=0,
            data={"chain_link": link},
        ))

        recorder.snap("After transformation — returned_to_brood flag is False")

        # Controller's end of turn — revert
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))

        recorder.snap("After return to brood — flag should be True")

        assert state.players[0].turn_counters.returned_to_brood_this_turn, (
            "returned_to_brood_this_turn should be True after reverting"
        )

    def test_no_retransform_after_return_to_brood(self, scenario_recorder):
        """After returning to brood, the agent should NOT re-transform in the same end phase.

        This tests the lifecycle: transform → opponent turn → controller end phase
        → revert. A second END_OF_TURN for the same player should not cause
        another transformation (the return-to-brood handler fires once only).
        """
        game, mask, demi_heroes, link = _setup_agent_test(attacker_marked=False)
        state = game.state
        recorder = scenario_recorder.bind(game)

        original_hero = state.players[0].hero

        # Transform
        game.events.emit(GameEvent(
            event_type=EventType.DEFEND_DECLARED,
            source=mask,
            target_player=0,
            data={"chain_link": link},
        ))

        recorder.snap("After transformation — Agent active")

        # Controller's end of turn — revert
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))

        assert state.players[0].hero == original_hero

        recorder.snap("After first END_OF_TURN — returned to brood")

        # A second END_OF_TURN for the same player — should NOT re-transform
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))

        recorder.snap("After second END_OF_TURN — should NOT re-transform")

        assert state.players[0].hero == original_hero, (
            "Hero should remain as original after return-to-brood — no re-transform"
        )

    def test_no_demi_heroes_means_no_transformation(self, scenario_recorder):
        """If no demi-heroes are available, Mask of Deceit should not transform."""
        game, mask, demi_heroes, link = _setup_agent_test(
            attacker_marked=False, num_agents=0,
        )
        state = game.state
        recorder = scenario_recorder.bind(game)

        # Clear demi-heroes
        state.players[0].demi_heroes = []
        original_hero = state.players[0].hero

        recorder.snap("Setup: Arakni with Mask of Deceit, no demi-heroes available")

        game.events.emit(GameEvent(
            event_type=EventType.DEFEND_DECLARED,
            source=mask,
            target_player=0,
            data={"chain_link": link},
        ))

        recorder.snap("After DEFEND_DECLARED — no transformation (no demi-heroes)")

        assert state.players[0].hero == original_hero, (
            "Without demi-heroes, Mask of Deceit should not transform"
        )
