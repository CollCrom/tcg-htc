"""LLM-powered player that uses Claude to make gameplay decisions.

Implements PlayerInterface by calling the Anthropic API for each decision.
Uses tool_use for structured output to guarantee valid JSON responses.
Strategy context is loaded from ref/strategy-*.md articles and the game
state is narrated into readable text by state_narrator.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from htc.engine.actions import Decision, PlayerResponse
from htc.state.game_state import GameState

from htc.player.state_narrator import narrate
from htc.player.strategy_context import build_system_prompt

log = logging.getLogger(__name__)

# Lazy import — anthropic is an optional dependency
_anthropic_client = None


def _get_client():  # type: ignore[no-untyped-def]
    """Lazily initialize the Anthropic client."""
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Set it to use the LLM player."
            )
        _anthropic_client = anthropic.Anthropic(api_key=api_key)
    return _anthropic_client


# Tool definition for single-select decisions
_SINGLE_SELECT_TOOL = {
    "name": "make_decision",
    "description": "Submit your gameplay decision with reasoning.",
    "input_schema": {
        "type": "object",
        "properties": {
            "option_id": {
                "type": "string",
                "description": "The action_id of your chosen option",
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation (1-2 sentences)",
            },
        },
        "required": ["option_id", "reasoning"],
    },
}

# Tool definition for multi-select decisions (defend, pitch, etc.)
_MULTI_SELECT_TOOL = {
    "name": "make_decision",
    "description": "Submit your gameplay decision with reasoning.",
    "input_schema": {
        "type": "object",
        "properties": {
            "option_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The action_ids of your chosen options",
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation (1-2 sentences)",
            },
        },
        "required": ["option_ids", "reasoning"],
    },
}


@dataclass
class DecisionRecord:
    """Record of a single decision for the game transcript."""

    turn: int
    decision_type: str
    prompt: str
    chosen_option: str
    reasoning: str
    options_count: int


@dataclass
class LLMPlayer:
    """Player that uses Claude to make strategic gameplay decisions.

    Implements the PlayerInterface protocol.

    Args:
        model: Claude model to use. Defaults to claude-sonnet-4-6 for speed.
        temperature: Sampling temperature. Lower = more deterministic.
        hero_name: Hero name for loading hero-specific strategy articles.
    """

    model: str = "claude-sonnet-4-6"
    temperature: float = 0.3
    hero_name: str | None = None
    transcript: list[DecisionRecord] = field(default_factory=list)
    _last_reasoning: str = field(default="", init=False, repr=False)

    def decide(self, game_state: GameState, decision: Decision) -> PlayerResponse:
        """Make a gameplay decision using Claude.

        Falls back to the first legal option on API errors.
        """
        if not decision.options:
            return PlayerResponse()

        # Build the narrated game state
        user_message = narrate(game_state, decision)

        # Resolve hero name from game state if not set
        hero = self.hero_name
        if hero is None and decision.player_index < len(game_state.players):
            me = game_state.players[decision.player_index]
            if me.hero:
                hero = me.hero.name

        # Build strategy-aware system prompt
        system_prompt = build_system_prompt(
            hero_name=hero,
            decision_type=decision.decision_type,
        )

        try:
            result = self._call_llm(system_prompt, user_message, decision)
        except Exception:
            log.exception("LLM call failed, falling back to first option")
            self._last_reasoning = "(API error — fallback)"
            result = self._fallback(decision)

        # Log the decision
        record = DecisionRecord(
            turn=game_state.turn_number,
            decision_type=decision.decision_type.value,
            prompt=decision.prompt,
            chosen_option=", ".join(result.selected_option_ids),
            reasoning=self._last_reasoning,
            options_count=len(decision.options),
        )
        self.transcript.append(record)
        log.debug(
            "LLM decision: %s -> %s | Reasoning: %s",
            decision.prompt,
            result.selected_option_ids,
            record.reasoning,
        )

        return result

    def _call_llm(
        self, system_prompt: str, user_message: str, decision: Decision,
    ) -> PlayerResponse:
        """Call Claude with tool_use for structured output."""
        client = _get_client()

        is_multi = decision.max_selections > 1
        tool = _MULTI_SELECT_TOOL if is_multi else _SINGLE_SELECT_TOOL

        response = client.messages.create(
            model=self.model,
            max_tokens=512,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            tools=[tool],
            tool_choice={"type": "tool", "name": "make_decision"},
        )

        # Extract tool use result
        for block in response.content:
            if block.type == "tool_use" and block.name == "make_decision":
                data = block.input
                self._last_reasoning = data.get("reasoning", "")

                valid_ids = {o.action_id for o in decision.options}

                if is_multi:
                    ids = data.get("option_ids", [])
                    selected = [i for i in ids if i in valid_ids]
                    if selected:
                        return PlayerResponse(selected_option_ids=selected)
                    # If multi-select returned nothing valid, try single
                    single = data.get("option_id", "")
                    if single in valid_ids:
                        return PlayerResponse(selected_option_ids=[single])
                else:
                    option_id = data.get("option_id", "")
                    if option_id in valid_ids:
                        return PlayerResponse(selected_option_ids=[option_id])

                log.warning(
                    "LLM returned invalid option(s): %s (valid: %s)",
                    data, valid_ids,
                )
                return self._fallback(decision)

        # No tool_use block found — shouldn't happen with tool_choice forced
        log.warning("No tool_use block in LLM response")
        return self._fallback(decision)

    def _fallback(self, decision: Decision) -> PlayerResponse:
        """Fall back to the first legal option."""
        if decision.options:
            return PlayerResponse(selected_option_ids=[decision.options[0].action_id])
        return PlayerResponse()
