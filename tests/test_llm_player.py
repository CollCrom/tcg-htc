"""Tests for the LLM player modules (state_narrator, strategy_context, llm_player).

These tests verify the non-API-calling parts: narration, prompt building,
and response parsing.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.actions import ActionOption, ActionType, Decision, PlayerResponse
from htc.enums import (
    CardType,
    Color,
    DecisionType,
    EquipmentSlot,
    Keyword,
    Phase,
    SubType,
    SuperType,
    Zone,
)
from htc.player.state_narrator import narrate
from htc.player.strategy_context import build_system_prompt
from htc.state.combat_state import CombatChainState
from htc.state.game_state import GameState
from htc.state.player_state import PlayerState


def _make_card_def(
    name: str = "Test Card",
    color: Color | None = Color.RED,
    cost: int | None = 1,
    power: int | None = 3,
    defense: int | None = 3,
    pitch: int | None = 1,
    keywords: frozenset[Keyword] = frozenset(),
    types: frozenset[CardType] = frozenset({CardType.ACTION}),
    subtypes: frozenset[SubType] = frozenset({SubType.ATTACK}),
) -> CardDefinition:
    return CardDefinition(
        unique_id=f"test-{name.lower().replace(' ', '-')}",
        name=name,
        color=color,
        pitch=pitch,
        cost=cost,
        power=power,
        defense=defense,
        health=None,
        intellect=None,
        arcane=None,
        types=types,
        subtypes=subtypes,
        supertypes=frozenset({SuperType.GENERIC}),
        keywords=keywords,
        functional_text="",
        type_text="Action Attack",
    )


def _make_instance(
    instance_id: int,
    definition: CardDefinition,
    zone: Zone = Zone.HAND,
    owner: int = 0,
) -> CardInstance:
    return CardInstance(
        instance_id=instance_id,
        definition=definition,
        owner_index=owner,
        zone=zone,
    )


def _make_game_state() -> GameState:
    """Create a minimal game state for testing."""
    hero_def = _make_card_def(
        name="Test Hero",
        color=None,
        cost=None,
        power=None,
        defense=None,
        pitch=None,
        types=frozenset({CardType.HERO}),
        subtypes=frozenset(),
    )
    hero0 = _make_instance(100, hero_def, Zone.HERO, owner=0)
    hero1 = _make_instance(101, hero_def, Zone.HERO, owner=1)

    card_def = _make_card_def(
        name="Wounding Blow",
        color=Color.RED,
        cost=1,
        power=4,
        defense=3,
        pitch=1,
        keywords=frozenset({Keyword.GO_AGAIN}),
    )
    hand_card = _make_instance(1, card_def, Zone.HAND, owner=0)

    blue_def = _make_card_def(
        name="Scar for a Scar",
        color=Color.BLUE,
        cost=2,
        power=3,
        defense=3,
        pitch=3,
    )
    hand_card2 = _make_instance(2, blue_def, Zone.HAND, owner=0)

    p0 = PlayerState(index=0, hero=hero0, life_total=20)
    p0.hand = [hand_card, hand_card2]
    p0.deck = [_make_instance(i, card_def, Zone.DECK, owner=0) for i in range(10, 30)]

    p1 = PlayerState(index=1, hero=hero1, life_total=18)
    p1.hand = [_make_instance(50, card_def, Zone.HAND, owner=1)]
    p1.deck = [_make_instance(i, card_def, Zone.DECK, owner=1) for i in range(60, 80)]

    gs = GameState(players=[p0, p1], turn_number=3, turn_player_index=0, phase=Phase.ACTION)
    return gs


class TestStateNarrator:
    """Test the state_narrator module."""

    def test_narrate_basic(self) -> None:
        gs = _make_game_state()
        decision = Decision(
            player_index=0,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Choose an action",
            options=[
                ActionOption(
                    action_id="play_1",
                    description="Play Wounding Blow (Red)",
                    action_type=ActionType.PLAY_CARD,
                    card_instance_id=1,
                ),
                ActionOption(
                    action_id="pass",
                    description="Pass",
                    action_type=ActionType.PASS,
                ),
            ],
        )

        text = narrate(gs, decision)

        # Check key elements are present
        assert "Turn 3" in text
        assert "Your turn" in text
        assert "20 life" in text
        assert "18 life" in text
        assert "Wounding Blow" in text
        assert "Scar for a Scar" in text
        assert "Go again" in text
        assert "[play_1]" in text
        assert "[pass]" in text
        assert "DECISION" in text

    def test_narrate_includes_hand_details(self) -> None:
        gs = _make_game_state()
        decision = Decision(
            player_index=0,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Choose",
            options=[],
        )
        text = narrate(gs, decision)
        # Card stats should appear in hand listing
        assert "cost 1" in text
        assert "power 4" in text
        assert "def 3" in text

    def test_narrate_opponent_turn(self) -> None:
        gs = _make_game_state()
        decision = Decision(
            player_index=0,
            decision_type=DecisionType.CHOOSE_DEFENDERS,
            prompt="Choose defenders",
            options=[],
        )
        gs.turn_player_index = 1  # opponent's turn
        text = narrate(gs, decision)
        assert "Opponent's turn" in text

    def test_narrate_marked_status(self) -> None:
        gs = _make_game_state()
        gs.players[0].is_marked = True
        decision = Decision(
            player_index=0,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Choose",
            options=[],
        )
        text = narrate(gs, decision)
        assert "MARKED" in text

    def test_narrate_equipment(self) -> None:
        gs = _make_game_state()
        equip_def = _make_card_def(
            name="Mask of Deceit",
            types=frozenset({CardType.EQUIPMENT}),
            subtypes=frozenset({SubType.HEAD}),
            keywords=frozenset({Keyword.WARD}),
            power=None,
            cost=None,
            pitch=None,
        )
        equip = _make_instance(200, equip_def, Zone.HEAD, owner=0)
        gs.players[0].equipment[EquipmentSlot.HEAD] = equip

        decision = Decision(
            player_index=0,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Choose",
            options=[],
        )
        text = narrate(gs, decision)
        assert "Mask of Deceit" in text
        assert "Ward" in text


class TestStrategyContext:
    """Test the strategy_context module."""

    def test_build_prompt_basic(self) -> None:
        prompt = build_system_prompt()
        assert "Flesh and Blood" in prompt
        assert "option_id" in prompt  # response format
        assert "General Strategy" in prompt

    def test_build_prompt_with_hero(self) -> None:
        prompt = build_system_prompt(hero_name="Arakni, Marionette")
        assert "Hero Strategy" in prompt
        assert "Arakni" in prompt

    def test_build_prompt_decision_guidance(self) -> None:
        prompt = build_system_prompt(decision_type=DecisionType.CHOOSE_DEFENDERS)
        assert "Decision Focus" in prompt
        assert "block" in prompt.lower()

    def test_build_prompt_play_guidance(self) -> None:
        prompt = build_system_prompt(decision_type=DecisionType.PLAY_OR_PASS)
        assert "Decision Focus" in prompt
        assert "sequencing" in prompt.lower() or "Sequencing" in prompt


class TestLLMPlayerParsing:
    """Test LLM response parsing without actual API calls."""

    def test_parse_valid_json(self) -> None:
        from htc.player.llm_player import LLMPlayer

        player = LLMPlayer()
        decision = Decision(
            player_index=0,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Choose",
            options=[
                ActionOption("play_1", "Play card", ActionType.PLAY_CARD),
                ActionOption("pass", "Pass", ActionType.PASS),
            ],
        )

        response = '{"option_id": "play_1", "reasoning": "Best attack option"}'
        result = player._parse_response(response, decision)
        assert result.selected_option_ids == ["play_1"]
        assert player._last_reasoning == "Best attack option"

    def test_parse_json_in_code_block(self) -> None:
        from htc.player.llm_player import LLMPlayer

        player = LLMPlayer()
        decision = Decision(
            player_index=0,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Choose",
            options=[
                ActionOption("play_1", "Play card", ActionType.PLAY_CARD),
                ActionOption("pass", "Pass", ActionType.PASS),
            ],
        )

        response = '```json\n{"option_id": "pass", "reasoning": "No good attacks"}\n```'
        result = player._parse_response(response, decision)
        assert result.selected_option_ids == ["pass"]

    def test_parse_invalid_option_falls_back(self) -> None:
        from htc.player.llm_player import LLMPlayer

        player = LLMPlayer()
        decision = Decision(
            player_index=0,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Choose",
            options=[
                ActionOption("play_1", "Play card", ActionType.PLAY_CARD),
                ActionOption("pass", "Pass", ActionType.PASS),
            ],
        )

        response = '{"option_id": "play_999", "reasoning": "?"}'
        result = player._parse_response(response, decision)
        # Falls back to first option
        assert result.selected_option_ids == ["play_1"]

    def test_parse_multi_select(self) -> None:
        from htc.player.llm_player import LLMPlayer

        player = LLMPlayer()
        decision = Decision(
            player_index=0,
            decision_type=DecisionType.CHOOSE_DEFENDERS,
            prompt="Choose defenders",
            min_selections=0,
            max_selections=4,
            options=[
                ActionOption("defend_1", "Defend with A", ActionType.DEFEND_WITH),
                ActionOption("defend_2", "Defend with B", ActionType.DEFEND_WITH),
                ActionOption("pass", "Pass", ActionType.PASS),
            ],
        )

        response = '{"option_ids": ["defend_1", "defend_2"], "reasoning": "Block both"}'
        result = player._parse_response(response, decision)
        assert result.selected_option_ids == ["defend_1", "defend_2"]

    def test_parse_garbage_falls_back(self) -> None:
        from htc.player.llm_player import LLMPlayer

        player = LLMPlayer()
        decision = Decision(
            player_index=0,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Choose",
            options=[
                ActionOption("play_1", "Play card", ActionType.PLAY_CARD),
            ],
        )

        result = player._parse_response("I think you should play the card", decision)
        assert result.selected_option_ids == ["play_1"]

    def test_fallback_on_api_error(self) -> None:
        from htc.player.llm_player import LLMPlayer

        player = LLMPlayer()
        gs = _make_game_state()
        decision = Decision(
            player_index=0,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Choose",
            options=[
                ActionOption("play_1", "Play card", ActionType.PLAY_CARD),
                ActionOption("pass", "Pass", ActionType.PASS),
            ],
        )

        # Mock _call_llm to raise an error
        with patch.object(player, "_call_llm", side_effect=RuntimeError("API down")):
            result = player.decide(gs, decision)

        assert result.selected_option_ids == ["play_1"]
        assert len(player.transcript) == 1
