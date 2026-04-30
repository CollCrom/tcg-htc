"""JSONL stdio PlayerInterface — for external agents driving the engine.

The engine runs in this Python process and writes one JSON object per line
to ``stdout`` whenever it needs a decision. The agent (parent process)
reads that line, decides, and writes one JSON object per line back to the
engine's ``stdin``.

Wire format
-----------
Engine → agent (one of):

    {"type": "decision", "player_index": 0, "decision_type": "play_or_pass",
     "prompt": "Choose an action", "min_selections": 1, "max_selections": 1,
     "options": [
         {"action_id": "play_42", "description": "Play Pummel (Red)",
          "action_type": "play_card", "card_instance_id": 42},
         {"action_id": "pass", "description": "Pass", "action_type": "pass",
          "card_instance_id": null}
     ],
     "state": {"you": {...}, "opponent": {...},
               "combat_chain": {...}, "turn": {...}}}

    {"type": "game_over", "winner": 0, "turns": 14, "final_life": [0, 4]}

The ``state`` field is a per-player snapshot from the deciding seat's
viewpoint: the viewer's own zones (hand, arsenal, etc.) are fully
visible; the opponent's hidden zones are replaced with sizes or
face-down placeholders. See :func:`engine.state.snapshot.snapshot_for`
for the exact schema. Cards include both base values and effect-modified
values (post-continuous-effects) so the agent can reason about the
current game-relevant numbers without re-implementing the effect engine.

Agent → engine:

    {"selected_option_ids": ["play_42"]}

One JSON object per line, UTF-8, ``\\n`` terminated. The engine flushes
after every write so agents can rely on line-buffered IO.

This module deliberately has zero dependencies on Anthropic / LLM code so
it can be driven from any language that can read and write lines.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from typing import IO, TYPE_CHECKING

from engine.rules.actions import Decision, PlayerResponse
from engine.state.game_state import GameState
from engine.state.snapshot import snapshot_for

if TYPE_CHECKING:
    from engine.rules.effects import EffectEngine
    from engine.rules.events import EventBus


class StdioPlayer:
    """A PlayerInterface that exchanges JSONL messages over stdin/stdout.

    The default streams are ``sys.stdin`` / ``sys.stdout`` so the engine can
    be launched as a subprocess by an agent. Pass explicit streams to drive
    it from tests or to redirect to pipes/sockets.

    Usage::

        player = StdioPlayer(player_index=0)
        game = Game(db, deck1, deck2, player, opponent, seed=7)
        # AFTER constructing Game (so the effect engine exists):
        player.effect_engine = game.effect_engine
        game.play()

    The effect engine is required so the snapshot can include
    effect-modified values (modified power on the active attack,
    modified cost on cards in hand, etc.).
    """

    def __init__(
        self,
        player_index: int,
        *,
        effect_engine: EffectEngine | None = None,
        events: EventBus | None = None,
        stdin: IO[str] | None = None,
        stdout: IO[str] | None = None,
    ) -> None:
        self.player_index = player_index
        self.effect_engine: EffectEngine | None = effect_engine
        # Optional EventBus reference so snapshots can include
        # ``active_effects[]`` (e.g. damage prevention from Shelter from
        # the Storm). Wire after Game construction:
        # ``player.events = game.events``.
        self.events: EventBus | None = events
        self._stdin = stdin if stdin is not None else sys.stdin
        self._stdout = stdout if stdout is not None else sys.stdout

    # ------------------------------------------------------------------
    # PlayerInterface
    # ------------------------------------------------------------------

    def decide(self, game_state: GameState, decision: Decision) -> PlayerResponse:
        if self.effect_engine is None:
            raise RuntimeError(
                "StdioPlayer.effect_engine must be set before decide() is called "
                "(typically by the entry point after constructing Game)"
            )
        self._send(self._encode_decision(decision, game_state))
        line = self._stdin.readline()
        if not line:
            raise RuntimeError(
                "stdio agent closed the input stream before responding to a decision"
            )
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"agent sent invalid JSON: {line!r}") from exc

        ids = payload.get("selected_option_ids")
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise RuntimeError(
                f"agent response missing list[str] 'selected_option_ids': {payload!r}"
            )
        return PlayerResponse(selected_option_ids=ids)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _encode_decision(self, decision: Decision, game_state: GameState) -> dict:
        # effect_engine is asserted non-None at the top of decide().
        assert self.effect_engine is not None
        state_snapshot = snapshot_for(
            game_state, self.player_index, self.effect_engine, self.events,
        )
        return {
            "type": "decision",
            "player_index": decision.player_index,
            "decision_type": decision.decision_type.value,
            "prompt": decision.prompt,
            "min_selections": decision.min_selections,
            "max_selections": decision.max_selections,
            "options": [
                {
                    **asdict(opt),
                    # asdict gives the enum object; serialize its value
                    "action_type": opt.action_type.value,
                }
                for opt in decision.options
            ],
            "state": state_snapshot,
        }

    def _send(self, payload: dict) -> None:
        self._stdout.write(json.dumps(payload, ensure_ascii=False))
        self._stdout.write("\n")
        self._stdout.flush()


def emit_event(payload: dict, *, stdout: IO[str] | None = None) -> None:
    """Write a non-decision JSONL message (e.g. game_over) to *stdout*.

    Convenience for entry points that need to bracket a game with status
    messages on the same channel the player uses.
    """
    out = stdout if stdout is not None else sys.stdout
    out.write(json.dumps(payload, ensure_ascii=False))
    out.write("\n")
    out.flush()
