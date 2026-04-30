"""Unit tests for tools/auto_player.py.

These tests cover the parts that do not require live API access or a running
match server:

* The forced-tool schema shape (so the SDK won't reject our tool definition).
* Log-line formatting (so the analyst pipeline gets parseable input).
* System-prompt construction (so deck text and seat actually land in the prompt).

End-to-end testing (real Anthropic API + match_server + a finished game) is left
for manual verification with an ``ANTHROPIC_API_KEY`` — see
``playbook/two_agent_match.md``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AUTO_PLAYER = REPO_ROOT / "tools" / "auto_player.py"

# Skip this whole module if anthropic isn't installed (CI without the llm extra).
pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("anthropic") is None,
    reason="anthropic SDK not installed (install with: pip install -e .[llm])",
)


def _load_auto_player():
    """Import tools/auto_player.py as a module without running its CLI."""
    spec = importlib.util.spec_from_file_location("auto_player", AUTO_PLAYER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["auto_player"] = module
    spec.loader.exec_module(module)
    return module


def test_submit_action_tool_schema_is_valid_json_schema():
    """The forced-tool schema must satisfy the constraints the API enforces."""
    ap = _load_auto_player()
    tool = ap.SUBMIT_ACTION_TOOL

    assert tool["name"] == "submit_action"
    assert isinstance(tool["description"], str) and tool["description"]

    schema = tool["input_schema"]
    assert schema["type"] == "object"
    # Both fields are required so the model can't silently omit either.
    assert set(schema["required"]) == {"action_ids", "rationale"}
    # Reject unknown keys — keeps the model from inventing fields.
    assert schema["additionalProperties"] is False

    action_ids = schema["properties"]["action_ids"]
    assert action_ids["type"] == "array"
    assert action_ids["items"] == {"type": "string"}

    rationale = schema["properties"]["rationale"]
    assert rationale["type"] == "string"


def test_log_line_mid_game_has_full_state():
    """Mid-game log lines should include turn / life / resource pitch."""
    ap = _load_auto_player()
    pending = {
        "state": {
            "turn": {"number": 4},
            "you": {"life": 32, "resource_points": 1},
            "opponent": {"life": 28},
        },
    }
    line = ap._log_line("A", pending, ["play_42"], "swing for tempo")

    assert line.startswith("[Turn 4 | A@32 | Opp@28 | Pitch:1] play_42 — swing for tempo")
    assert line.endswith("\n")


def test_log_line_pre_game_setup_uses_placeholder():
    """Pre-game setup state lacks turn/life — log line must still parse."""
    ap = _load_auto_player()
    pending = {"state": {"phase": "pre_game_setup"}}
    line = ap._log_line("B", pending, ["equip_3"], "pick chest armor for surv")

    assert line.startswith("[pre_game | seat B] equip_3 — pick chest armor for surv")
    assert line.endswith("\n")


def test_log_line_tolerates_missing_state_fields():
    """If the state shape is unexpected, format defensively rather than crash."""
    ap = _load_auto_player()
    line = ap._log_line("A", {}, ["pass"], "no info")

    # All the per-field fallbacks are "?", not exceptions.
    assert "Turn ?" in line
    assert "A@?" in line
    assert "Opp@?" in line
    assert "Pitch:?" in line


def test_log_line_joins_multi_select_action_ids():
    """Multi-select decisions submit several action_ids — the log line must show all of them."""
    ap = _load_auto_player()
    pending = {
        "state": {
            "turn": {"number": 5},
            "you": {"life": 20, "resource_points": 0},
            "opponent": {"life": 18},
        },
    }
    line = ap._log_line("A", pending, ["defend_12", "defend_15"], "block big swing")

    assert "defend_12,defend_15" in line


def test_system_prompt_includes_seat_hero_and_deck_text(tmp_path: Path):
    """System prompt must surface seat, hero, and the full deck text (cached)."""
    ap = _load_auto_player()

    deck_text = "## Hero\nCindra\n\n## Deck\n3x Whittle from Bone (Red)\n"
    formatted = ap.SYSTEM_PROMPT_TEMPLATE.format(
        seat="A",
        hero="Cindra, Dracai of Retribution",
        blurb_suffix=" (Blue Cindra)",
        deck_text=deck_text,
    )

    assert "Player A" in formatted
    assert "Cindra, Dracai of Retribution" in formatted
    assert "Blue Cindra" in formatted
    assert "Whittle from Bone (Red)" in formatted
    # Strategy tenets must be present — the bare per-decision driver depends on
    # these for play quality (no working memory across calls).
    assert "Don't over-pass" in formatted
    assert "Defenders" in formatted


def test_main_rejects_invalid_seat(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """--seat C should exit with non-zero code (no live API needed)."""
    ap = _load_auto_player()

    deck = tmp_path / "fake_deck.md"
    deck.write_text("## Hero\nFake\n", encoding="utf-8")

    rc = ap.main([
        "--port", "1",
        "--seat", "C",
        "--hero", "Fake",
        "--deck", str(deck),
        "--match-id", "test-match",
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "must be A or B" in err


def test_main_rejects_missing_deck(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """A non-existent --deck path should fail before any HTTP call."""
    ap = _load_auto_player()

    rc = ap.main([
        "--port", "1",
        "--seat", "A",
        "--hero", "Fake",
        "--deck", str(tmp_path / "does_not_exist.md"),
        "--match-id", "test-match",
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "deck file not found" in err
