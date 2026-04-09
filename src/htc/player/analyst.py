"""Post-game analysis: reviews decisions and writes summary to memory.

Takes a game transcript (list of DecisionRecords) and game outcome,
calls Claude to generate strategic analysis, and writes to memory/playtester.md.
After writing the raw analysis, distills accumulated game analyses into
structured learnings (Strategic Learnings, Hero Notes, Matchup Notes).
"""

from __future__ import annotations

import logging
import re
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

    # Distill accumulated analyses into structured learnings
    try:
        _distill_learnings(my_hero, opp_hero, model)
    except Exception:
        log.exception("Distillation failed — raw analysis still saved")

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


# ---------------------------------------------------------------------------
# Distillation: structured learnings from accumulated analyses
# ---------------------------------------------------------------------------

_STRUCTURED_SECTIONS = [
    "Strategic Learnings",
    "User Corrections",
    "Hero Notes",
    "Matchup Notes",
]

_DISTILL_SYSTEM = """\
You are distilling game analysis notes into structured learnings for a \
Flesh and Blood TCG AI player. Extract actionable patterns and organize them.

Output format (use exactly these markdown headers):

### Strategic Learnings
(General patterns that apply across all games — bullet points)

### Hero Notes
#### [Hero Name]
(Hero-specific observations — bullet points per hero)

### Matchup Notes
#### [Hero A] vs [Hero B]
(Matchup-specific patterns — bullet points per matchup)

Rules:
- Be concise — each bullet is 1-2 sentences max
- Only include actionable insights that improve future play
- Merge duplicates — consolidate patterns seen across multiple games
- Preserve existing learnings that aren't contradicted by new data
- Drop vague observations — keep only concrete, applicable advice
- Do NOT include raw game stats, just the strategic lessons\
"""


def _distill_learnings(my_hero: str, opp_hero: str, model: str) -> None:
    """Distill accumulated game analyses into structured learnings.

    Reads all game analyses from playtester.md, calls Claude to extract
    patterns, and rewrites the structured sections at the top of the file.
    User Corrections are always preserved untouched.
    """
    if not _MEMORY_PATH.exists():
        return

    full_text = _MEMORY_PATH.read_text(encoding="utf-8")

    # Find the Decision Quality Log and its analyses
    log_marker = "## Decision Quality Log"
    log_idx = full_text.find(log_marker)
    if log_idx < 0:
        return

    analyses_text = full_text[log_idx:]

    # Only distill if there's at least one real analysis (not just stats)
    if "Key Decisions" not in analyses_text and "Patterns" not in analyses_text:
        log.info("No real analyses to distill yet, skipping")
        return

    # Extract existing structured sections
    existing = _parse_sections(full_text)
    existing_context = ""
    for name in ["Strategic Learnings", "Hero Notes", "Matchup Notes"]:
        content = existing.get(name, "")
        if content and not content.startswith("*"):
            existing_context += f"### Existing {name}\n{content}\n\n"

    # Build the distillation prompt
    user_msg = ""
    if existing_context:
        user_msg += f"## Current Learnings (update/extend these)\n\n{existing_context}\n"
    user_msg += f"## Game Analyses\n\n{analyses_text}"

    # Truncate if too long
    if len(user_msg) > 20_000:
        user_msg = user_msg[:20_000] + "\n\n[...truncated]"

    client = get_client()
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        temperature=0.2,
        system=_DISTILL_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    distilled = response.content[0].text

    # Parse distilled output and rewrite the structured sections
    _rewrite_structured_sections(full_text, distilled)
    log.info("Distilled learnings written to %s", _MEMORY_PATH)


def _parse_sections(text: str) -> dict[str, str]:
    """Extract structured sections from playtester.md (before Decision Quality Log)."""
    log_idx = text.find("## Decision Quality Log")
    if log_idx >= 0:
        text = text[:log_idx]

    sections: dict[str, str] = {}
    for name in _STRUCTURED_SECTIONS:
        marker = f"## {name}"
        start = text.find(marker)
        if start < 0:
            continue
        start += len(marker)
        match = re.search(r"\n## ", text[start:])
        if match:
            content = text[start : start + match.start()]
        else:
            content = text[start:]
        sections[name] = content.strip()

    return sections


def _extract_distilled_section(text: str, header: str) -> str:
    """Extract content after a ### header from the distilled output."""
    marker = f"### {header}"
    start = text.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    # Find next ### header
    match = re.search(r"\n### ", text[start:])
    if match:
        return text[start : start + match.start()].strip()
    return text[start:].strip()


def _rewrite_structured_sections(full_text: str, distilled: str) -> None:
    """Rewrite the structured sections of playtester.md with distilled learnings.

    Preserves:
    - The file header
    - User Corrections (never touched by distillation)
    - The Decision Quality Log and all raw analyses
    """
    existing = _parse_sections(full_text)

    # Extract distilled sections
    new_learnings = _extract_distilled_section(distilled, "Strategic Learnings")
    new_hero = _extract_distilled_section(distilled, "Hero Notes")
    new_matchup = _extract_distilled_section(distilled, "Matchup Notes")

    # Preserve user corrections
    user_corrections = existing.get("User Corrections",
                                    "*Direct guidance from the user. Highest priority — always follow these.*")

    # Preserve the raw log (Decision Quality Log and everything after)
    log_marker = "## Decision Quality Log"
    log_idx = full_text.find(log_marker)
    raw_log = full_text[log_idx:] if log_idx >= 0 else f"{log_marker}\n"

    default_matchup = "*What does not apply per matchup.*"

    # Rebuild the file
    new_text = (
        "# Playtester Memory\n\n"
        "Persistent learnings across sessions. "
        "The user reviews this file to evaluate decision quality and provide guidance.\n\n"
        f"## Strategic Learnings\n\n"
        f"{new_learnings or '*Patterns discovered across games — update as games are played.*'}\n\n"
        f"## User Corrections\n\n{user_corrections}\n\n"
        f"## Hero Notes\n\n"
        f"{new_hero or '*Hero-specific observations from gameplay.*'}\n\n"
        f"## Matchup Notes\n\n"
        f"{new_matchup or default_matchup}\n\n"
        f"{raw_log}"
    )

    _MEMORY_PATH.write_text(new_text, encoding="utf-8")
