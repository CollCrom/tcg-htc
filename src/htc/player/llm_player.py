"""LLM-powered player that uses Claude to make gameplay decisions.

Implements PlayerInterface by calling the Anthropic API for each decision.
Strategy context is loaded from ref/strategy-*.md articles and the game
state is narrated into readable text by state_narrator.
"""

from __future__ import annotations

import json
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
        if hero is None:
            me = game_state.players[decision.player_index]
            if me.hero:
                hero = me.hero.name

        # Build strategy-aware system prompt
        system_prompt = build_system_prompt(
            hero_name=hero,
            decision_type=decision.decision_type,
        )

        try:
            response = self._call_llm(system_prompt, user_message)
            result = self._parse_response(response, decision)
        except Exception:
            log.exception("LLM call failed, falling back to first option")
            result = self._fallback(decision)

        # Log the decision
        record = DecisionRecord(
            turn=game_state.turn_number,
            decision_type=decision.decision_type.value,
            prompt=decision.prompt,
            chosen_option=", ".join(result.selected_option_ids),
            reasoning=getattr(self, "_last_reasoning", ""),
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

    def _call_llm(self, system_prompt: str, user_message: str) -> str:
        """Call the Claude API and return the text response."""
        client = _get_client()
        response = client.messages.create(
            model=self.model,
            max_tokens=256,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

    def _parse_response(self, response_text: str, decision: Decision) -> PlayerResponse:
        """Parse the LLM's JSON response into a PlayerResponse.

        Handles both single-select (option_id) and multi-select (option_ids).
        Falls back to first option if parsing fails.
        """
        self._last_reasoning = ""

        # Try to extract JSON from the response
        text = response_text.strip()
        # Handle markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (``` markers)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    data = json.loads(text[start:end])
                except json.JSONDecodeError:
                    log.warning("Failed to parse LLM response as JSON: %s", text[:200])
                    return self._fallback(decision)
            else:
                log.warning("No JSON found in LLM response: %s", text[:200])
                return self._fallback(decision)

        self._last_reasoning = data.get("reasoning", "")

        # Multi-select response
        if "option_ids" in data:
            ids = data["option_ids"]
            if isinstance(ids, list):
                valid = {o.action_id for o in decision.options}
                selected = [i for i in ids if i in valid]
                if selected:
                    return PlayerResponse(selected_option_ids=selected)
                log.warning("LLM returned invalid option_ids: %s (valid: %s)", ids, valid)
                return self._fallback(decision)

        # Single-select response
        option_id = data.get("option_id", "")
        valid_ids = {o.action_id for o in decision.options}
        if option_id in valid_ids:
            return PlayerResponse(selected_option_ids=[option_id])

        log.warning("LLM returned invalid option_id: %r (valid: %s)", option_id, valid_ids)
        return self._fallback(decision)

    def _fallback(self, decision: Decision) -> PlayerResponse:
        """Fall back to the first legal option."""
        if decision.options:
            return PlayerResponse(selected_option_ids=[decision.options[0].action_id])
        return PlayerResponse()
