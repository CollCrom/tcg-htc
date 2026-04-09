"""LLM-powered player that uses Claude to make gameplay decisions.

Implements PlayerInterface by calling the Anthropic API for each decision.
Uses tool_use for structured output to guarantee valid JSON responses.
Strategy context is loaded from ref/strategy-*.md articles and the game
state is narrated into readable text by state_narrator.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from htc.engine.actions import Decision, PlayerResponse
from htc.state.game_state import GameState

from htc.player.api_client import DEFAULT_MODEL, get_client
from htc.player.state_narrator import narrate
from htc.player.strategy_context import build_system_prompt

log = logging.getLogger(__name__)


def _build_tool(multi: bool, reasoning: bool) -> dict:
    """Build the tool schema, optionally including the reasoning field."""
    if multi:
        props: dict = {
            "option_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The action_ids of your chosen options",
            },
        }
        required = ["option_ids"]
    else:
        props = {
            "option_id": {
                "type": "string",
                "description": "The action_id of your chosen option",
            },
        }
        required = ["option_id"]

    if reasoning:
        props["reasoning"] = {
            "type": "string",
            "description": "Brief explanation (1-2 sentences)",
        }
        required.append("reasoning")

    desc = "Submit your gameplay decision."
    if reasoning:
        desc = "Submit your gameplay decision with reasoning."

    return {
        "name": "make_decision",
        "description": desc,
        "input_schema": {
            "type": "object",
            "properties": props,
            "required": required,
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
        reasoning: Include reasoning in tool schema. Disable for batch runs
            to save ~30-40% output tokens.
    """

    model: str = DEFAULT_MODEL
    temperature: float = 0.3
    hero_name: str | None = None
    reasoning: bool = True
    transcript: list[DecisionRecord] = field(default_factory=list)
    _last_reasoning: str = field(default="", init=False, repr=False)

    def decide(self, game_state: GameState, decision: Decision) -> PlayerResponse:
        """Make a gameplay decision using Claude.

        Falls back to the first legal option on API errors.
        Skips the LLM entirely for trivial single-option decisions.
        """
        if not decision.options:
            return PlayerResponse()

        # Skip LLM for trivial decisions (only one option)
        if len(decision.options) == 1:
            only = decision.options[0]
            self._last_reasoning = "(auto — single option)"
            result = PlayerResponse(selected_option_ids=[only.action_id])
            self.transcript.append(DecisionRecord(
                turn=game_state.turn_number,
                decision_type=decision.decision_type.value,
                prompt=decision.prompt,
                chosen_option=only.action_id,
                reasoning=self._last_reasoning,
                options_count=1,
            ))
            return result

        # Build the narrated game state
        user_message = narrate(game_state, decision)

        # Resolve hero names from game state
        hero = self.hero_name
        if hero is None and decision.player_index < len(game_state.players):
            me = game_state.players[decision.player_index]
            if me.hero:
                hero = me.hero.name

        opp_hero = None
        opp_idx = 1 - decision.player_index
        if opp_idx < len(game_state.players):
            opp = game_state.players[opp_idx]
            if opp.hero:
                opp_hero = opp.hero.name

        # Build strategy-aware system prompt (returns cache-aware blocks)
        system_prompt = build_system_prompt(
            hero_name=hero,
            opponent_name=opp_hero,
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
        self, system_prompt: list[dict], user_message: str, decision: Decision,
    ) -> PlayerResponse:
        """Call Claude with tool_use for structured output."""
        client = get_client()

        is_multi = decision.max_selections > 1
        tool = _build_tool(multi=is_multi, reasoning=self.reasoning)

        response = client.messages.create(
            model=self.model,
            max_tokens=512 if self.reasoning else 128,
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
                if self.reasoning:
                    self._last_reasoning = data.get("reasoning", "")
                else:
                    self._last_reasoning = "(reasoning disabled)"

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
