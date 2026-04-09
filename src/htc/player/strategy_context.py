"""Loads strategy articles and builds system prompts for the LLM player.

Three layers:
- General strategy (always included): fundamentals, deckbuilding, defense theory
- Hero-specific (when matched): articles matching the hero name
- Playtester memory (when available): distilled learnings from prior games

Decision-type aware: emphasizes relevant theory based on what's being decided.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from htc.enums import DecisionType

log = logging.getLogger(__name__)

# Root of the project (three levels up from this file)
_REF_DIR = Path(__file__).resolve().parents[3] / "ref"

# General strategy files — always loaded
_GENERAL_FILES = [
    "strategy-fab-fundamentals.md",
    "strategy-defeating-defense.md",
    "strategy-deckbuilding.md",
]

# Hero name fragments mapped to article filenames
_HERO_ARTICLE_MAP: dict[str, list[str]] = {
    "arakni": ["strategy-arakni-masterclass.md"],
    "cindra": ["strategy-cindra-redline.md", "strategy-cindra-post-bnr.md"],
}

# Token budget for strategy context (characters, not tokens — rough 4:1 ratio)
_MAX_CONTEXT_CHARS = 24_000  # ~6000 tokens
_MAX_MEMORY_CHARS = 4_000  # ~1000 tokens for playtester learnings

_MEMORY_PATH = Path(__file__).resolve().parents[3] / "memory" / "playtester.md"

# Sections to extract from playtester.md (before Decision Quality Log)
_STRUCTURED_SECTIONS = [
    "Strategic Learnings",
    "User Corrections",
    "Hero Notes",
    "Matchup Notes",
]


def build_system_prompt(
    hero_name: str | None = None,
    opponent_name: str | None = None,
    decision_type: DecisionType | None = None,
) -> list[dict]:
    """Build the system prompt for the LLM player.

    Returns a list of content blocks for the Anthropic ``system`` parameter.
    The first block contains strategy context marked for prompt caching;
    the second (optional) block contains learnings from prior games;
    the last block contains per-decision guidance that changes each call.

    Args:
        hero_name: The hero's name (e.g. "Arakni, Marionette"). Used to load
            hero-specific strategy articles.
        opponent_name: The opponent's hero name. Used to load matchup-specific
            learnings from playtester memory.
        decision_type: The type of decision being made. Used to emphasize
            relevant strategy theory.
    """
    # --- Static block (cacheable across all decisions in a game) ---
    static_sections: list[str] = [_ROLE_PREAMBLE]

    general_text = _load_articles(_GENERAL_FILES)
    if general_text:
        static_sections.append(f"## General Strategy\n{general_text}")

    if hero_name:
        hero_articles = _find_hero_articles(hero_name)
        if hero_articles:
            hero_text = _load_articles(hero_articles)
            if hero_text:
                static_sections.append(f"## Hero Strategy ({hero_name})\n{hero_text}")

    static_text = "\n\n".join(static_sections)
    if len(static_text) > _MAX_CONTEXT_CHARS:
        static_text = static_text[:_MAX_CONTEXT_CHARS] + "\n\n[Strategy context truncated]"

    # --- Dynamic block (changes per decision type) ---
    dynamic_sections: list[str] = []
    if decision_type:
        guidance = _DECISION_GUIDANCE.get(decision_type)
        if guidance:
            dynamic_sections.append(f"## Decision Focus\n{guidance}")

    dynamic_sections.append(
        "## Instructions\n"
        "Use the make_decision tool to submit your choice. "
        "Pick the best option_id (or option_ids for multi-select) and give brief reasoning."
    )
    dynamic_text = "\n\n".join(dynamic_sections)

    # --- Learnings block (from prior games, cached per session) ---
    memory_text = _load_playtester_memory(hero_name, opponent_name)

    blocks = [
        {
            "type": "text",
            "text": static_text,
            "cache_control": {"type": "ephemeral"},
        },
    ]

    if memory_text:
        blocks.append({
            "type": "text",
            "text": memory_text,
            "cache_control": {"type": "ephemeral"},
        })

    blocks.append({
        "type": "text",
        "text": dynamic_text,
    })

    return blocks


def _find_hero_articles(hero_name: str) -> list[str]:
    """Find strategy article filenames matching the hero name."""
    hero_lower = hero_name.lower()
    for key, files in _HERO_ARTICLE_MAP.items():
        if key in hero_lower:
            return files

    # Also check for any strategy files containing the hero name
    found: list[str] = []
    for path in _REF_DIR.glob("strategy-*.md"):
        if any(part in path.stem.lower() for part in hero_lower.split()):
            found.append(path.name)
    return found


def _load_articles(filenames: list[str]) -> str:
    """Load and concatenate strategy article contents."""
    parts: list[str] = []
    for fname in filenames:
        path = _REF_DIR / fname
        if not path.exists():
            log.warning("Strategy article not found: %s", path)
            continue
        try:
            text = path.read_text(encoding="utf-8")
            # Take a reasonable excerpt — first N chars
            if len(text) > 8000:
                text = text[:8000] + "\n[...truncated]"
            parts.append(text)
        except OSError:
            log.warning("Failed to read strategy article: %s", path)
    return "\n\n---\n\n".join(parts)


_ROLE_PREAMBLE = """You are an expert Flesh and Blood TCG player making in-game decisions.

You will be given the current game state and a decision to make. Analyze the situation
using FaB strategy principles and choose the best option.

Key principles:
- 1 card = ~3 value points (attack, defense, or resource). Cards that exceed this are above-rate.
- Standard hand is 4 cards = ~12 total value. A good offensive turn deals 14-16+ damage.
- Blocking: only block if the value you save exceeds the value you lose from that card.
- Tempo: go-again attacks chain into more damage. Losing action points wastes tempo.
- Fatigue: track deck sizes. If you have more cards, you can afford to trade; if fewer, be aggressive.
- Arsenal: save high-impact cards for future turns. Don't arsenal mediocre cards.
- Equipment: use equipment blocks strategically — they're free defense but one-time use.
"""

_DECISION_GUIDANCE: dict[DecisionType, str] = {
    DecisionType.PLAY_OR_PASS: (
        "You are choosing what to play on your action phase. Consider:\n"
        "- Sequencing: play go-again cards first to chain attacks\n"
        "- Resource management: what do you need to pitch to play this?\n"
        "- Arsenal: would this card be better saved for next turn?\n"
        "- Passing: if you've dealt enough damage, or your remaining cards are "
        "better used next turn, pass to end turn"
    ),
    DecisionType.CHOOSE_DEFENDERS: (
        "You are choosing which cards to block with. Consider:\n"
        "- Value math: does the card's defense value exceed what you'd use it for offensively?\n"
        "- Breakpoints: block enough to reduce damage by a full card's worth (3+), or don't block at all\n"
        "- Life total: if you're high on life, take damage and keep cards for offense\n"
        "- Dominate/Intimidate: check if the attack has keywords that punish partial blocks\n"
        "- Equipment: use equipment blocks before card blocks when efficient"
    ),
    DecisionType.PLAY_REACTION_OR_PASS: (
        "You are choosing whether to play a reaction (attack or defense). Consider:\n"
        "- Attack reactions: does the extra damage push past a breakpoint?\n"
        "- Defense reactions: does the block value justify using this card now vs. later?\n"
        "- Hand quality: will you have enough good cards next turn if you use this?"
    ),
    DecisionType.CHOOSE_CARDS_TO_PITCH: (
        "You are choosing which card(s) to pitch for resources. Consider:\n"
        "- Pitch value: blue cards pitch for 3, yellow for 2, red for 1\n"
        "- Card quality: pitch your weakest remaining card\n"
        "- Future turns: pitched cards go to bottom of deck; consider what you want to draw later"
    ),
    DecisionType.CHOOSE_ARSENAL_CARD: (
        "You are choosing what to put in arsenal for next turn. Consider:\n"
        "- High-impact cards: save your best attack or key combo piece\n"
        "- Color: red cards hit hardest from arsenal since you draw a full hand to pitch\n"
        "- Flexibility: cards that are good in multiple situations are better arsenal choices"
    ),
    DecisionType.OPTIONAL_ABILITY: (
        "You are choosing whether to use an optional ability. Consider:\n"
        "- Is the ability's effect worth the cost right now?\n"
        "- Are there any downsides to using it (destroying equipment, losing resources)?"
    ),
}


# ---------------------------------------------------------------------------
# Playtester memory loading
# ---------------------------------------------------------------------------


def _load_playtester_memory(
    hero_name: str | None = None,
    opponent_name: str | None = None,
) -> str:
    """Load relevant distilled learnings from playtester memory.

    Reads the structured sections at the top of memory/playtester.md
    (before the Decision Quality Log) and filters hero/matchup notes
    to only include entries relevant to the current game.

    Returns empty string if no useful learnings exist.
    """
    if not _MEMORY_PATH.exists():
        return ""

    try:
        text = _MEMORY_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""

    sections = _parse_structured_sections(text)
    if not sections:
        return ""

    parts: list[str] = []

    # User corrections — highest priority, always included
    corrections = sections.get("User Corrections", "")
    if corrections and not corrections.startswith("*"):
        parts.append(
            "### User Corrections (HIGHEST PRIORITY — always follow these)\n"
            + corrections
        )

    # Strategic learnings — always included
    learnings = sections.get("Strategic Learnings", "")
    if learnings and not learnings.startswith("*"):
        parts.append("### Strategic Learnings\n" + learnings)

    # Hero notes — filtered by current hero
    hero_notes = sections.get("Hero Notes", "")
    if hero_name and hero_notes and not hero_notes.startswith("*"):
        filtered = _filter_subsections(hero_notes, hero_name)
        if filtered:
            parts.append("### Hero Notes\n" + filtered)

    # Matchup notes — filtered by current hero pair
    matchup_notes = sections.get("Matchup Notes", "")
    if hero_name and opponent_name and matchup_notes and not matchup_notes.startswith("*"):
        filtered = _filter_matchup_subsections(matchup_notes, hero_name, opponent_name)
        if filtered:
            parts.append("### Matchup Notes\n" + filtered)

    if not parts:
        return ""

    result = (
        "## Learnings from Prior Games\n\n"
        "These are patterns distilled from previous games. "
        "Apply them to inform your decisions.\n\n"
        + "\n\n".join(parts)
    )

    if len(result) > _MAX_MEMORY_CHARS:
        result = result[:_MAX_MEMORY_CHARS] + "\n\n[Learnings truncated]"

    return result


def _parse_structured_sections(text: str) -> dict[str, str]:
    """Extract the structured sections from playtester.md.

    Only parses sections listed in _STRUCTURED_SECTIONS, and stops
    at the Decision Quality Log to avoid picking up headers inside
    raw game analyses.
    """
    # Only look at content before the raw log
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
        # Find the next ## header
        match = re.search(r"\n## ", text[start:])
        if match:
            content = text[start : start + match.start()]
        else:
            content = text[start:]
        content = content.strip()
        if content:
            sections[name] = content

    return sections


def _filter_subsections(text: str, hero_name: str) -> str:
    """Filter ### subsections that match the hero name."""
    hero_key = hero_name.lower().split(",")[0].strip()

    blocks = re.split(r"(?=^### )", text, flags=re.MULTILINE)
    matched: list[str] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if block.startswith("### "):
            header = block.split("\n", 1)[0].lower()
            if hero_key in header:
                matched.append(block)
        else:
            # General notes not under a ### header — always include
            matched.append(block)

    return "\n\n".join(matched)


def _filter_matchup_subsections(
    text: str, hero_name: str, opponent_name: str,
) -> str:
    """Filter ### subsections that match the hero pair (in either order)."""
    hero_key = hero_name.lower().split(",")[0].strip()
    opp_key = opponent_name.lower().split(",")[0].strip()

    blocks = re.split(r"(?=^### )", text, flags=re.MULTILINE)
    matched: list[str] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if block.startswith("### "):
            header = block.split("\n", 1)[0].lower()
            if hero_key in header and opp_key in header:
                matched.append(block)
        else:
            matched.append(block)

    return "\n\n".join(matched)
