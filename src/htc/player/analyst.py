"""Post-game analysis: reviews decisions and writes summary to memory.

Takes a game transcript (list of DecisionRecords) and game outcome,
calls Claude to generate strategic analysis, and writes to memory/playtester.md.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from htc.player.api_client import DEFAULT_MODEL, get_client
from htc.player.llm_player import DecisionRecord

log = logging.getLogger(__name__)

_MEMORY_PATH = Path(__file__).resolve().parents[3] / "memory" / "playtester.md"


def analyze_game(
    transcript: list[DecisionRecord],
    winner: int | None,
    my_index: int,
    my_hero: str,
    opp_hero: str,
    my_life: int,
    opp_life: int,
    my_deck_size: int,
    opp_deck_size: int,
    total_turns: int,
    model: str = DEFAULT_MODEL,
) -> str:
    """Analyze a completed game and write summary to memory.

    Args:
        transcript: List of DecisionRecords from the LLM player.
        winner: Index of the winning player (None if draw).
        my_index: The LLM player's index (0 or 1).
        my_hero: Name of the LLM player's hero.
        opp_hero: Name of the opponent's hero.
        my_life: LLM player's final life total.
        opp_life: Opponent's final life total.
        my_deck_size: LLM player's remaining deck size.
        opp_deck_size: Opponent's remaining deck size.
        total_turns: Total number of turns in the game.
        model: Claude model to use for analysis.

    Returns:
        The analysis text that was written to memory.
    """
    # Build transcript summary for the LLM
    result_str = "WIN" if winner == my_index else ("LOSS" if winner is not None else "DRAW")
    game_summary = (
        f"Game: {my_hero} vs {opp_hero}\n"
        f"Result: {result_str}\n"
        f"Turns: {total_turns}\n"
        f"Final state: You {my_life} life / {my_deck_size} deck | "
        f"Opp {opp_life} life / {opp_deck_size} deck\n"
    )

    # Format transcript
    decision_log: list[str] = []
    for rec in transcript:
        decision_log.append(
            f"T{rec.turn} [{rec.decision_type}] {rec.prompt} -> {rec.chosen_option}"
            + (f" ({rec.reasoning})" if rec.reasoning else "")
        )

    transcript_text = "\n".join(decision_log) if decision_log else "(no decisions recorded)"

    # Call Claude to analyze
    system_prompt = (
        "You are a Flesh and Blood TCG analyst reviewing a completed game. "
        "Analyze the decisions made and provide actionable insights.\n\n"
        "Structure your analysis with these sections:\n"
        "1. **Result Summary** — one-line game result\n"
        "2. **Key Decisions** — 3-5 most impactful decisions (good or bad)\n"
        "3. **Mistakes** — any clearly suboptimal plays with explanation\n"
        "4. **Patterns** — strategic observations worth remembering\n\n"
        "Be concise and specific. Focus on decisions that actually mattered."
    )

    user_message = f"{game_summary}\n\nDecision Log:\n{transcript_text}"

    try:
        client = get_client()
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            temperature=0.2,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        analysis = response.content[0].text
    except Exception:
        log.exception("Analysis LLM call failed, writing basic summary")
        analysis = (
            f"## Game: {my_hero} vs {opp_hero} — {result_str}\n"
            f"Turns: {total_turns} | Final: {my_life}/{my_deck_size} vs {opp_life}/{opp_deck_size}\n"
            f"Decisions: {len(transcript)}\n"
            "(LLM analysis unavailable)"
        )

    # Write to memory
    _append_to_memory(analysis, my_hero, opp_hero, result_str)

    return analysis


def _append_to_memory(analysis: str, my_hero: str, opp_hero: str, result: str) -> None:
    """Append analysis to memory/playtester.md."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    entry = (
        f"\n\n---\n\n"
        f"### Game Analysis — {my_hero} vs {opp_hero} ({result}) — {timestamp}\n\n"
        f"{analysis}\n"
    )

    # Create file with header if it doesn't exist
    if not _MEMORY_PATH.exists():
        _MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        header = (
            "# Playtester Memory\n\n"
            "## Strategic Learnings\n\n"
            "(Patterns discovered across games will be added here.)\n\n"
            "## User Corrections\n\n"
            "(Direct guidance from the user — highest priority.)\n\n"
            "## Hero Notes\n\n"
            "## Matchup Notes\n\n"
            "## Decision Quality Log\n"
        )
        _MEMORY_PATH.write_text(header, encoding="utf-8")

    # Append the analysis
    with open(_MEMORY_PATH, "a", encoding="utf-8") as f:
        f.write(entry)

    log.info("Game analysis written to %s", _MEMORY_PATH)
