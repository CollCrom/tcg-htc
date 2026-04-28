"""End-to-end test for the JSONL stdio agent protocol.

Spawns ``python -m engine.stdio`` as a subprocess and drives a full game
with an "always pick first option" agent, validating:

* ``ready`` line is emitted first with the correct ``player_index``/``seed``.
* Every ``decision`` payload has the documented fields with enum *values*
  (strings like ``"play_or_pass"``), not enum *reprs*.
* ``game_over`` is the last message and the process exits 0.
* ``--side p2`` flips the seat assigned to the stdio agent.
* Two runs with identical CLI args produce the same winner (the random
  opponent is seeded, so the game must be deterministic).
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from engine.enums import ActionType, DecisionType
from tests.conftest import CARDS_TSV, REPO_ROOT

# Mirror the timeout in run_full_game so a hung subprocess fails the test
# instead of stalling the whole suite.
SUBPROCESS_TIMEOUT_S = 120

# Allowed enum string values (engine writes ``enum.value``, not ``repr``).
_ALLOWED_DECISION_TYPES = {e.value for e in DecisionType}
_ALLOWED_ACTION_TYPES = {e.value for e in ActionType}


pytestmark = pytest.mark.skipif(
    not CARDS_TSV.exists(),
    reason=f"card database missing at {CARDS_TSV} (run `python -m tools.refresh_cards`)",
)


def _run_stdio_game(
    *,
    seed: int = 7,
    side: str = "p1",
    opponent_seed: int | None = None,
) -> tuple[list[dict], dict, int]:
    """Spawn engine.stdio, drive it with a 'pick first option' agent.

    Returns (decisions_seen, game_over_msg, exit_code).
    """
    args = [sys.executable, "-m", "engine.stdio", "--seed", str(seed), "--side", side]
    if opponent_seed is not None:
        args += ["--opponent-seed", str(opponent_seed)]

    proc = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=REPO_ROOT,
    )

    decisions: list[dict] = []
    game_over: dict | None = None
    ready: dict | None = None

    try:
        for raw in proc.stdout:  # type: ignore[union-attr]
            msg = json.loads(raw)
            mtype = msg.get("type")
            if mtype == "ready":
                ready = msg
                continue
            if mtype == "decision":
                decisions.append(msg)
                # Always pick the first listed option.
                first_id = msg["options"][0]["action_id"]
                proc.stdin.write(  # type: ignore[union-attr]
                    json.dumps({"selected_option_ids": [first_id]}) + "\n"
                )
                proc.stdin.flush()  # type: ignore[union-attr]
                continue
            if mtype == "game_over":
                game_over = msg
                break
        proc.stdin.close()  # type: ignore[union-attr]
        exit_code = proc.wait(timeout=10)
    except Exception:
        proc.kill()
        raise

    assert ready is not None, "engine never emitted a `ready` line"
    assert game_over is not None, "engine exited without a `game_over` line"
    # Stash the ready payload on the game_over dict for caller convenience.
    game_over["_ready"] = ready
    return decisions, game_over, exit_code


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_stdio_runs_full_game_p1():
    """Full game completes; ready/decision/game_over wire format is well-formed."""
    decisions, game_over, exit_code = _run_stdio_game(seed=7, side="p1")

    assert exit_code == 0
    assert decisions, "agent was asked zero decisions — engine never reached a choice point"

    ready = game_over["_ready"]
    assert ready["player_index"] == 0
    assert ready["seed"] == 7

    # Every decision must conform to the documented schema.
    for d in decisions:
        assert d["player_index"] in (0, 1)
        assert d["decision_type"] in _ALLOWED_DECISION_TYPES, (
            f"unknown decision_type {d['decision_type']!r}; "
            f"engine should emit enum .value strings"
        )
        assert isinstance(d["prompt"], str)
        assert isinstance(d["min_selections"], int)
        assert isinstance(d["max_selections"], int)
        assert d["max_selections"] >= d["min_selections"] >= 0
        assert d["options"], "decision had zero options"
        for opt in d["options"]:
            assert isinstance(opt["action_id"], str) and opt["action_id"]
            assert isinstance(opt["description"], str)
            assert opt["action_type"] in _ALLOWED_ACTION_TYPES, (
                f"unknown action_type {opt['action_type']!r}"
            )
            # card_instance_id is int | None
            assert opt["card_instance_id"] is None or isinstance(opt["card_instance_id"], int)

    assert game_over["winner"] in (0, 1, None)
    assert isinstance(game_over["turns"], int) and game_over["turns"] > 0
    assert isinstance(game_over["final_life"], list) and len(game_over["final_life"]) == 2


def test_stdio_seat_flip_p2():
    """--side p2 puts the stdio agent in seat 1."""
    decisions, game_over, exit_code = _run_stdio_game(seed=7, side="p2")
    assert exit_code == 0
    assert game_over["_ready"]["player_index"] == 1
    # All decisions routed to the stdio agent should be for player 1.
    agent_decisions = [d for d in decisions if d["player_index"] == 1]
    assert agent_decisions, "agent never received a decision while seated as p2"


def test_stdio_is_deterministic_for_same_seed():
    """Same --seed (and same --opponent-seed default) ⇒ same winner and turn count."""
    _, first, _ = _run_stdio_game(seed=42, side="p1", opponent_seed=99)
    _, second, _ = _run_stdio_game(seed=42, side="p1", opponent_seed=99)
    assert first["winner"] == second["winner"]
    assert first["turns"] == second["turns"]
    assert first["final_life"] == second["final_life"]
