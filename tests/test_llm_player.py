"""Tests for the LLM player modules (state_narrator, strategy_context, llm_player, analyst).

These tests verify the non-API-calling parts: narration, prompt building,
response parsing, and post-game analysis.
"""

from __future__ import annotations

from pathlib import Path
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
from htc.player.llm_player import DecisionRecord, LLMPlayer
from htc.player.state_narrator import narrate
from htc.player.strategy_context import build_system_prompt
from htc.state.combat_state import CombatChainState
from htc.state.game_state import GameState
from htc.state.player_state import PlayerState

_MOCK_CLIENT = "htc.player.llm_player.get_client"
_MOCK_ANALYST_CLIENT = "htc.player.analyst.get_client"


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


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


def _play_or_pass_decision(**overrides) -> Decision:
    """Standard two-option play-or-pass decision."""
    defaults = dict(
        player_index=0,
        decision_type=DecisionType.PLAY_OR_PASS,
        prompt="Choose",
        options=[
            ActionOption("play_1", "Play card", ActionType.PLAY_CARD),
            ActionOption("pass", "Pass", ActionType.PASS),
        ],
    )
    defaults.update(overrides)
    return Decision(**defaults)


def _make_tool_response(tool_input: dict):
    """Create a mock API response with a tool_use block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = "make_decision"
    block.input = tool_input
    response = MagicMock()
    response.content = [block]
    return response


def _get_call_kwarg(mock_client, key: str):
    """Extract a kwarg from the mock messages.create call."""
    call_kwargs = mock_client.return_value.messages.create.call_args
    return call_kwargs.kwargs.get(key, call_kwargs[1].get(key))


# ---------------------------------------------------------------------------
# State narrator tests
# ---------------------------------------------------------------------------


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

        # Compact format checks
        assert "T3" in text
        assert "YOUR" in text
        assert "HP 20" in text
        assert "Opp HP 18" in text
        assert "Wounding Blow" in text
        assert "Scar for a Scar" in text
        assert "Go again" in text
        assert "[play_1]" in text
        assert "[pass]" in text
        assert "DECIDE" in text

    def test_narrate_uses_compact_card_format(self) -> None:
        gs = _make_game_state()
        decision = Decision(
            player_index=0,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Choose",
            options=[],
        )
        text = narrate(gs, decision)
        # Abbreviated color codes
        assert "(R)" in text
        assert "(B)" in text
        # Compact stat notation
        assert "1c" in text
        assert "4p" in text
        assert "3d" in text
        # Hand is inline with | separator
        assert "Hand:" in text
        assert "|" in text

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
        assert "OPP" in text

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

    def test_narrate_differentials_shown(self) -> None:
        gs = _make_game_state()
        decision = Decision(
            player_index=0,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Choose",
            options=[],
        )
        text = narrate(gs, decision)
        assert "Δlife +2" in text

    def test_narrate_no_differentials_when_equal(self) -> None:
        gs = _make_game_state()
        gs.players[1].life_total = 20  # same life
        gs.players[1].deck = list(gs.players[0].deck)  # same deck size
        decision = Decision(
            player_index=0,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Choose",
            options=[],
        )
        text = narrate(gs, decision)
        assert "Δlife" not in text


# ---------------------------------------------------------------------------
# Strategy context tests
# ---------------------------------------------------------------------------


class TestStrategyContext:
    """Test the strategy_context module."""

    def _full_text(self, blocks: list[dict]) -> str:
        return "\n\n".join(b["text"] for b in blocks)

    def test_build_prompt_returns_cache_blocks(self) -> None:
        blocks = build_system_prompt()
        assert isinstance(blocks, list)
        assert len(blocks) == 2
        assert blocks[0]["type"] == "text"
        assert blocks[0]["cache_control"] == {"type": "ephemeral"}
        assert "cache_control" not in blocks[1]

    def test_build_prompt_basic(self) -> None:
        blocks = build_system_prompt()
        full = self._full_text(blocks)
        assert "Flesh and Blood" in full
        assert "option_id" in full
        assert "General Strategy" in full

    def test_build_prompt_with_hero(self) -> None:
        blocks = build_system_prompt(hero_name="Arakni, Marionette")
        full = self._full_text(blocks)
        assert "Hero Strategy" in full
        assert "Arakni" in full

    def test_build_prompt_decision_guidance(self) -> None:
        blocks = build_system_prompt(decision_type=DecisionType.CHOOSE_DEFENDERS)
        full = self._full_text(blocks)
        assert "Decision Focus" in full
        assert "block" in full.lower()

    def test_build_prompt_play_guidance(self) -> None:
        blocks = build_system_prompt(decision_type=DecisionType.PLAY_OR_PASS)
        full = self._full_text(blocks)
        assert "Decision Focus" in full
        assert "sequencing" in full.lower() or "Sequencing" in full

    def test_static_content_in_cached_block(self) -> None:
        blocks = build_system_prompt(
            hero_name="Arakni, Marionette",
            decision_type=DecisionType.PLAY_OR_PASS,
        )
        cached = blocks[0]["text"]
        dynamic = blocks[1]["text"]
        assert "General Strategy" in cached
        assert "Hero Strategy" in cached
        assert "Decision Focus" in dynamic


# ---------------------------------------------------------------------------
# LLM player tool_use tests
# ---------------------------------------------------------------------------


class TestLLMPlayerToolUse:
    """Test LLM player with mocked tool_use API responses."""

    def test_single_select(self) -> None:
        player = LLMPlayer()
        gs = _make_game_state()
        decision = _play_or_pass_decision()

        mock_resp = _make_tool_response(
            {"option_id": "play_1", "reasoning": "Best attack option"}
        )
        with patch(_MOCK_CLIENT) as mock_client:
            mock_client.return_value.messages.create.return_value = mock_resp
            result = player.decide(gs, decision)

        assert result.selected_option_ids == ["play_1"]
        assert player._last_reasoning == "Best attack option"
        assert len(player.transcript) == 1

    def test_multi_select(self) -> None:
        player = LLMPlayer()
        gs = _make_game_state()
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

        mock_resp = _make_tool_response(
            {"option_ids": ["defend_1", "defend_2"], "reasoning": "Block both"}
        )
        with patch(_MOCK_CLIENT) as mock_client:
            mock_client.return_value.messages.create.return_value = mock_resp
            result = player.decide(gs, decision)

        assert result.selected_option_ids == ["defend_1", "defend_2"]

    def test_invalid_option_falls_back(self) -> None:
        player = LLMPlayer()
        gs = _make_game_state()
        decision = _play_or_pass_decision()

        mock_resp = _make_tool_response({"option_id": "play_999", "reasoning": "?"})
        with patch(_MOCK_CLIENT) as mock_client:
            mock_client.return_value.messages.create.return_value = mock_resp
            result = player.decide(gs, decision)

        assert result.selected_option_ids == ["play_1"]

    def test_fallback_on_api_error(self) -> None:
        player = LLMPlayer()
        gs = _make_game_state()
        decision = _play_or_pass_decision()

        with patch(_MOCK_CLIENT, side_effect=RuntimeError("API down")):
            result = player.decide(gs, decision)

        assert result.selected_option_ids == ["play_1"]
        assert len(player.transcript) == 1

    def test_no_tool_block_falls_back(self) -> None:
        player = LLMPlayer()
        gs = _make_game_state()
        decision = _play_or_pass_decision()

        text_block = MagicMock()
        text_block.type = "text"
        response = MagicMock()
        response.content = [text_block]

        with patch(_MOCK_CLIENT) as mock_client:
            mock_client.return_value.messages.create.return_value = response
            result = player.decide(gs, decision)

        assert result.selected_option_ids == ["play_1"]

    def test_transcript_records_reasoning(self) -> None:
        player = LLMPlayer()
        gs = _make_game_state()
        decision = _play_or_pass_decision(prompt="Choose an action")

        mock_resp = _make_tool_response(
            {"option_id": "pass", "reasoning": "Nothing to play"}
        )
        with patch(_MOCK_CLIENT) as mock_client:
            mock_client.return_value.messages.create.return_value = mock_resp
            player.decide(gs, decision)

        assert len(player.transcript) == 1
        assert player.transcript[0].reasoning == "Nothing to play"
        assert player.transcript[0].chosen_option == "pass"

    def test_trivial_decision_skips_llm(self) -> None:
        """Single-option decisions should not call the API."""
        player = LLMPlayer()
        gs = _make_game_state()
        decision = _play_or_pass_decision(
            options=[ActionOption("pass", "Pass", ActionType.PASS)],
        )

        with patch(_MOCK_CLIENT) as mock_client:
            result = player.decide(gs, decision)
            mock_client.return_value.messages.create.assert_not_called()

        assert result.selected_option_ids == ["pass"]
        assert len(player.transcript) == 1
        assert "auto" in player.transcript[0].reasoning

    def test_system_prompt_passed_as_blocks(self) -> None:
        """Verify the API receives system prompt as cache-aware blocks."""
        player = LLMPlayer()
        gs = _make_game_state()
        decision = _play_or_pass_decision()

        mock_resp = _make_tool_response({"option_id": "play_1", "reasoning": "Go"})
        with patch(_MOCK_CLIENT) as mock_client:
            mock_client.return_value.messages.create.return_value = mock_resp
            player.decide(gs, decision)

            system_arg = _get_call_kwarg(mock_client, "system")
            assert isinstance(system_arg, list)
            assert system_arg[0]["cache_control"] == {"type": "ephemeral"}

    def test_reasoning_disabled_omits_from_schema(self) -> None:
        """With reasoning=False, tool schema should not include reasoning."""
        player = LLMPlayer(reasoning=False)
        gs = _make_game_state()
        decision = _play_or_pass_decision()

        mock_resp = _make_tool_response({"option_id": "play_1"})
        with patch(_MOCK_CLIENT) as mock_client:
            mock_client.return_value.messages.create.return_value = mock_resp
            result = player.decide(gs, decision)

            tool = _get_call_kwarg(mock_client, "tools")[0]
            assert "reasoning" not in tool["input_schema"]["properties"]
            assert "reasoning" not in tool["input_schema"]["required"]
            assert _get_call_kwarg(mock_client, "max_tokens") == 128

        assert result.selected_option_ids == ["play_1"]
        assert player._last_reasoning == "(reasoning disabled)"

    def test_reasoning_enabled_includes_in_schema(self) -> None:
        """With reasoning=True (default), tool schema includes reasoning."""
        player = LLMPlayer(reasoning=True)
        gs = _make_game_state()
        decision = _play_or_pass_decision()

        mock_resp = _make_tool_response(
            {"option_id": "play_1", "reasoning": "Good attack"}
        )
        with patch(_MOCK_CLIENT) as mock_client:
            mock_client.return_value.messages.create.return_value = mock_resp
            result = player.decide(gs, decision)

            tool = _get_call_kwarg(mock_client, "tools")[0]
            assert "reasoning" in tool["input_schema"]["properties"]
            assert _get_call_kwarg(mock_client, "max_tokens") == 512

        assert player._last_reasoning == "Good attack"

    def test_multi_select_filters_invalid_ids(self) -> None:
        """Mixed valid/invalid option_ids should keep only valid ones."""
        player = LLMPlayer()
        gs = _make_game_state()
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

        mock_resp = _make_tool_response(
            {"option_ids": ["defend_1", "bogus_99", "defend_2", "fake_id"],
             "reasoning": "Block everything"}
        )
        with patch(_MOCK_CLIENT) as mock_client:
            mock_client.return_value.messages.create.return_value = mock_resp
            result = player.decide(gs, decision)

        assert result.selected_option_ids == ["defend_1", "defend_2"]


# ---------------------------------------------------------------------------
# Analyst tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def _redirect_analyst_memory(tmp_path: Path):
    """Redirect analyst memory writes to a tmp directory."""
    import htc.player.analyst as analyst_mod

    original_path = analyst_mod._MEMORY_PATH
    analyst_mod._MEMORY_PATH = tmp_path / "playtester.md"
    yield analyst_mod
    analyst_mod._MEMORY_PATH = original_path


def _make_transcript() -> list[DecisionRecord]:
    return [
        DecisionRecord(
            turn=1, decision_type="play_or_pass", prompt="Choose",
            chosen_option="play_1", reasoning="Go aggro", options_count=3,
        ),
        DecisionRecord(
            turn=1, decision_type="pitch", prompt="Pitch a card",
            chosen_option="pitch_2", reasoning="Blue for resources", options_count=2,
        ),
    ]


class TestAnalyst:
    """Test the post-game analyst module."""

    def test_analyze_game_success(self, _redirect_analyst_memory) -> None:
        analyst_mod = _redirect_analyst_memory
        from htc.player.analyst import analyze_game

        text_block = MagicMock()
        text_block.text = "## Analysis\nGreat game, good aggro."
        response = MagicMock()
        response.content = [text_block]

        with patch(_MOCK_ANALYST_CLIENT) as mock_client:
            mock_client.return_value.messages.create.return_value = response
            result = analyze_game(
                transcript=_make_transcript(),
                winner=0, my_index=0,
                my_hero="Cindra", opp_hero="Arakni",
                my_life=5, opp_life=0,
                my_deck_size=10, opp_deck_size=15,
                total_turns=20,
            )

        assert "Analysis" in result
        assert "Great game" in result
        mem = analyst_mod._MEMORY_PATH.read_text()
        assert "Cindra vs Arakni" in mem
        assert "WIN" in mem

    def test_analyze_game_api_failure_fallback(self, _redirect_analyst_memory) -> None:
        analyst_mod = _redirect_analyst_memory
        from htc.player.analyst import analyze_game

        with patch(_MOCK_ANALYST_CLIENT, side_effect=RuntimeError("No API")):
            result = analyze_game(
                transcript=_make_transcript(),
                winner=1, my_index=0,
                my_hero="Cindra", opp_hero="Arakni",
                my_life=0, opp_life=12,
                my_deck_size=5, opp_deck_size=20,
                total_turns=15,
            )

        assert "LOSS" in result
        assert "LLM analysis unavailable" in result
        mem = analyst_mod._MEMORY_PATH.read_text()
        assert "LOSS" in mem

    def test_analyze_game_draw(self, _redirect_analyst_memory) -> None:
        from htc.player.analyst import analyze_game

        with patch(_MOCK_ANALYST_CLIENT, side_effect=RuntimeError("No API")):
            result = analyze_game(
                transcript=[], winner=None, my_index=0,
                my_hero="Cindra", opp_hero="Arakni",
                my_life=1, opp_life=1,
                my_deck_size=0, opp_deck_size=0,
                total_turns=50,
            )

        assert "DRAW" in result
