"""auto_player.py — drive one seat of a FaB match via per-decision Anthropic API calls.

Replaces the long-lived Claude Code sub-agent player with a thin loop that makes
one Anthropic API call per decision (cached system prompt + per-decision user
message). This avoids the compounding-context cost of long-lived agents — each
call has constant input size instead of growing linearly with prior tool-call
output.

Wire protocol matches ``tools/agent_cli.py`` and ``tools/match_server.py``:
``GET /pending?player=<seat>`` → ``POST /action?player=<seat>``. Append a
rationale line to ``replays/<match_id>/player<seat>.log`` per decision so the
analyst pipeline still has its input.

Usage::

    python tools/auto_player.py \\
        --port 8089 \\
        --seat A \\
        --hero "Cindra, Dracai of Retribution" \\
        --deck ref/decks/decklist-cindra-blue.md \\
        --match-id cindra-blue-vs-arakni-004

Run two of these (one per seat) to drive a full match.

Requires the ``llm`` optional dependency: ``pip install -e .[llm]`` and an
``ANTHROPIC_API_KEY`` environment variable.
"""

from __future__ import annotations

# sys.path bootstrap so this works whether invoked via ``python tools/auto_player.py``
# or ``python -m tools.auto_player``. The subprocess launcher in tests sets
# ``sys.path[0]`` to the script directory, not the repo root, which would break
# any ``from engine...`` import. Same pattern as ``tools/match_server.py``.
import sys
from pathlib import Path

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import json
import logging
import os
import time
import urllib.error
import urllib.request


def _load_dotenv() -> None:
    """Load `KEY=VALUE` lines from a repo-root ``.env`` file into ``os.environ``.

    Existing environment variables win — `.env` only fills in keys that are
    not already set. Lines starting with ``#`` and blank lines are ignored.
    Surrounding single or double quotes on the value are stripped.

    Used so the operator can drop ``ANTHROPIC_API_KEY=sk-ant-...`` into a
    repo-local ``.env`` (gitignored) without restarting their shell or
    Claude Code session. No dependency on python-dotenv.
    """
    dotenv_path = Path(__file__).resolve().parent.parent / ".env"
    if not dotenv_path.exists():
        return
    try:
        for raw in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Strip a single matched pair of surrounding quotes.
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        # Silently ignore — operator can pass the env var directly instead.
        pass


_load_dotenv()


import anthropic  # noqa: E402 — must come after _load_dotenv() so the SDK sees the key

from engine.cards.card_db import CardDatabase  # noqa: E402 — sys.path bootstrap above
from engine.decks.deck_list import parse_markdown_decklist  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HTTP_TIMEOUT_S = 30
POLL_BACKOFF_S = 0.2
MAX_409_RETRIES = 3
DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_MAX_TOKENS = 512  # plenty for a tool call with a one-sentence rationale

# Default paths (resolved relative to repo root, set by sys.path bootstrap above).
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CARDS_TSV = REPO_ROOT / "data" / "cards.tsv"
DEFAULT_RULES_PATH = REPO_ROOT / "ref" / "rules" / "comprehensive-rules.md"

# Sections of the comprehensive rules to embed in the system prompt. Loaded by
# header text so the rules doc can grow without breaking us. The combination
# pads the system prompt above Opus 4.7's 4096-token cache minimum AND gives
# the model rules grounding for the most decision-relevant areas (combat,
# priority, costs, mark, ability keywords).
RULES_SECTIONS_TO_INCLUDE = (
    "### 1.11 Priority",
    "### 1.14 Costs",
    "### 4.3 Action Phase",
    "### 4.4 End Phase",
    "## 7 Combat",  # whole combat chapter — the densest decision-relevant rules
    "### 8.3 Ability Keywords",
    "### 9.3 Marked",
)

log = logging.getLogger("auto_player")


# Forced tool: the model MUST respond by calling this. Constrains output to
# valid JSON with the action_ids the engine expects + a one-sentence rationale
# the analyst pipeline can read.
SUBMIT_ACTION_TOOL: dict = {
    "name": "submit_action",
    "description": (
        "Submit your chosen action(s) for the current decision. "
        "action_ids must satisfy the decision's min_selections..max_selections "
        "and each must come verbatim from pending.options[].action_id."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "List of action_id strings copied verbatim from "
                    "pending.options[].action_id. For pass/skip use the "
                    "action_id whose action_type is 'pass' (typically the "
                    "literal string 'pass')."
                ),
            },
            "rationale": {
                "type": "string",
                "description": (
                    "One sentence (≤25 words) explaining the choice. "
                    "Logged for the analyst — be concrete (e.g. 'Klaive into "
                    "marked Cindra for tempo'), not abstract ('best play')."
                ),
            },
        },
        "required": ["action_ids", "rationale"],
        "additionalProperties": False,
    },
}


SYSTEM_PROMPT_TEMPLATE = """You are driving seat {seat} (Player {seat}) in a Flesh and Blood TCG match.
You play **{hero}**{blurb_suffix}.

Each request gives you the current pending decision. Respond by calling the
`submit_action` tool with the chosen action_ids and a one-sentence rationale.

# Decision payload (in the user message)

JSON with:
- `decision_type` — kind of choice (play_or_pass, defenders, resolve, choose_target, ...).
- `prompt` — short human-readable prompt.
- `min_selections`, `max_selections` — number of action_ids you must pick.
- `options[]` — each has `action_id` (string, opaque), `action_type`, `description`, sometimes `card_instance_id`.
- `state` — your view: `you` (hand, life, AP, resources, equipment, mark, arsenal), `opponent` (PUBLIC zones only — no hand contents), `combat_chain`, `turn`. Opponent hand is REDACTED — never assume its contents.

# Output rules

- Always call `submit_action`. action_ids must be copied verbatim from pending.options[].action_id.
- For pass/skip, pick the option whose action_type is "pass" (action_id usually the literal string "pass").
- If max_selections == 1, action_ids must have exactly one element.
- If min_selections > 1, you MUST pick at least min_selections distinct action_ids.

# Strategy tenets (in priority order)

1. **Don't over-pass.** If you have AP and a productive play, take it. Random play passes constantly — you must not.
2. **Defenders.** Evaluate the threat. 0-1 power chip damage usually goes to face (preserve cards). Save defense reactions for big swings (≥4 power, lethal range, or modifier-stacked attacks). Deck and AP scarcity matter — if you're short on cards next turn, defending is more attractive.
3. **Reactions.** Usually pass unless the card is materially relevant to the current attack.
4. **Pre-game equipment selection.** Pick equipment that supports your hero's gameplan (state will be a placeholder `pre_game_setup` for these prompts; choose by `description`).
5. **Resource pitching.** Pitch the lowest-pitch card whose value isn't needed this turn. Don't pitch 3-pitch Blues for 1-resource activations unless you'll spend ≥2 resources this turn.
6. **Closing speed.** When ahead on life and tempo, push damage. When behind, set up bigger swings — survive ≥1 more turn cycle to get there.

# Your deck

```
{deck_text}
```

# Card reference (your deck — type line + functional text per unique card)

The deck list above gives names and counts; this section gives you the actual
text on every card you might draw. Cited verbatim from the project's card
database. Same deck = same reference, sorted alphabetically — kept stable so
the system prompt prefix caches across decisions.

{card_reference}

# Rules excerpts

Decision-relevant sections of the official Comprehensive Rules. Use these to
ground rule-edge calls (priority order, mark removal timing, chain-link
mechanics). Match-static — same on every decision.

{rules_excerpt}

End of system context. The user message is one decision payload — respond with `submit_action`."""


# ---------------------------------------------------------------------------
# System-prompt builders (cache-stable: deterministic ordering, no per-call data)
# ---------------------------------------------------------------------------


def _build_card_reference(deck_text: str, db: CardDatabase) -> str:
    """Return a markdown reference of every unique card in the deck.

    Includes hero, weapons, equipment, demi-heroes, and main-deck cards. One
    block per unique name (variants — Red/Yellow/Blue — share the same text;
    color is implicit from the deck list above). Sorted alphabetically so the
    output is byte-identical across calls with the same deck — required for
    prompt caching to hit.

    Cards not found in the database are silently skipped (the engine warns
    separately at deck-load time, no need to duplicate).
    """
    deck = parse_markdown_decklist(deck_text)
    names: set[str] = {deck.hero_name}
    names.update(deck.weapons)
    names.update(deck.equipment)
    names.update(deck.demi_heroes)
    names.update(entry.name for entry in deck.cards)

    blocks: list[str] = []
    for name in sorted(names):
        card = db.get_by_name(name)
        if card is None:
            continue
        type_text = (card.type_text or "").strip()
        functional = (card.functional_text or "").strip() or "_(no rules text)_"
        blocks.append(f"### {card.name}\n_{type_text}_\n{functional}")
    return "\n\n".join(blocks)


def _load_rules_excerpt(rules_path: Path) -> str:
    """Slice the comprehensive-rules.md doc to ``RULES_SECTIONS_TO_INCLUDE``.

    For each header in the include list, copy from that header through to the
    next sibling-level header (or higher). Skips quietly if the file or any
    individual header is missing — used as padding, not load-bearing.
    """
    if not rules_path.exists():
        return "_(rules file not found at "
        f"{rules_path} — proceeding without rules excerpt)_"
    text = rules_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    def section(start_header: str) -> str:
        start_idx: int | None = None
        start_depth = start_header.count("#", 0, start_header.index(" "))
        for i, ln in enumerate(lines):
            if ln.strip().startswith(start_header):
                start_idx = i
                break
        if start_idx is None:
            return ""
        # Find next header at the same or shallower depth.
        end_idx = len(lines)
        for j in range(start_idx + 1, len(lines)):
            stripped = lines[j].lstrip()
            if not stripped.startswith("#"):
                continue
            hashes = len(stripped) - len(stripped.lstrip("#"))
            if hashes <= start_depth:
                end_idx = j
                break
        return "\n".join(lines[start_idx:end_idx]).rstrip()

    chunks = [section(h) for h in RULES_SECTIONS_TO_INCLUDE]
    return "\n\n".join(c for c in chunks if c)


# ---------------------------------------------------------------------------
# HTTP helpers (mirror tests/integration/test_match_server.py shape)
# ---------------------------------------------------------------------------


def _http_get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _http_post(url: str, body: dict) -> tuple[int, dict]:
    """POST JSON; return (status_code, parsed_body). Raises on 5xx."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            return resp.getcode(), json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        if 500 <= exc.code < 600:
            raise RuntimeError(f"POST {url} failed {exc.code}: {exc.read().decode()}") from exc
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


# ---------------------------------------------------------------------------
# Logging — write a rationale line per decision to player$SEAT.log
# ---------------------------------------------------------------------------


def _log_line(seat: str, pending: dict, action_ids: list[str], rationale: str) -> str:
    """Format a single rationale line in the same shape player sub-agents use.

    ``[Turn N | Hero@HP | Opp@HP | Pitch:N] action_ids — rationale``

    Tolerant of the pre-game-setup placeholder (no full state).
    """
    state = pending.get("state") or {}
    if state.get("phase") == "pre_game_setup":
        return f"[pre_game | seat {seat}] {','.join(action_ids)} — {rationale}\n"

    turn = (state.get("turn") or {}).get("number", "?")
    you = state.get("you") or {}
    opp = state.get("opponent") or {}
    you_life = you.get("life", "?")
    opp_life = opp.get("life", "?")
    pitch = you.get("resource_points", "?")
    return (
        f"[Turn {turn} | {seat}@{you_life} | Opp@{opp_life} | Pitch:{pitch}] "
        f"{','.join(action_ids)} — {rationale}\n"
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def run(args: argparse.Namespace) -> int:
    base = f"http://127.0.0.1:{args.port}"
    seat = args.seat.upper()
    if seat not in ("A", "B"):
        print(f"--seat must be A or B, got {seat!r}", file=sys.stderr)
        return 2

    deck_path = Path(args.deck)
    if not deck_path.exists():
        print(f"deck file not found: {deck_path}", file=sys.stderr)
        return 2
    deck_text = deck_path.read_text(encoding="utf-8")

    cards_path = Path(args.cards)
    if not cards_path.exists():
        print(f"cards database not found: {cards_path}", file=sys.stderr)
        return 2
    db = CardDatabase.load(cards_path)
    card_reference = _build_card_reference(deck_text, db)

    rules_path = Path(args.rules)
    rules_excerpt = _load_rules_excerpt(rules_path)

    blurb_suffix = f" ({args.blurb})" if args.blurb else ""
    system_text = SYSTEM_PROMPT_TEMPLATE.format(
        seat=seat,
        hero=args.hero,
        blurb_suffix=blurb_suffix,
        deck_text=deck_text,
        card_reference=card_reference,
        rules_excerpt=rules_excerpt,
    )
    log.info(
        "system_prompt built: %d chars (target ≥16K for Opus 4.7 cache to engage)",
        len(system_text),
    )

    log_path = Path("replays") / args.match_id / f"player{seat}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY

    # Token-usage counters. Useful for verifying caching is hitting.
    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_cache_write = 0
    decisions = 0

    log.info(
        "auto_player seat=%s hero=%s match=%s model=%s",
        seat, args.hero, args.match_id, args.model,
    )

    while True:
        # 1. Poll for a pending decision.
        try:
            pending_resp = _http_get(f"{base}/pending?player={seat}")
        except urllib.error.URLError as exc:
            print(f"[{seat}] match server unreachable: {exc}", file=sys.stderr)
            return 1

        status = pending_resp.get("status") or {}
        phase = status.get("status")
        if phase in ("game_over", "error"):
            log.info("[%s] %s — exiting (decisions=%d)", seat, phase, decisions)
            break

        pending = pending_resp.get("pending")
        if pending is None:
            time.sleep(POLL_BACKOFF_S)
            continue

        # 2. Ask the model.
        try:
            response = client.messages.create(
                model=args.model,
                max_tokens=DEFAULT_MAX_TOKENS,
                system=[
                    {
                        "type": "text",
                        "text": system_text,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=[SUBMIT_ACTION_TOOL],
                tool_choice={"type": "tool", "name": "submit_action"},
                messages=[
                    {"role": "user", "content": json.dumps(pending, ensure_ascii=False)},
                ],
            )
        except anthropic.APIError as exc:
            print(f"[{seat}] anthropic API error: {exc}", file=sys.stderr)
            return 1

        # Track token usage so the operator can see caching working.
        usage = response.usage
        total_input += getattr(usage, "input_tokens", 0) or 0
        total_output += getattr(usage, "output_tokens", 0) or 0
        total_cache_read += getattr(usage, "cache_read_input_tokens", 0) or 0
        total_cache_write += getattr(usage, "cache_creation_input_tokens", 0) or 0

        action_ids: list[str] | None = None
        rationale = ""
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "submit_action":
                action_ids = block.input.get("action_ids")
                rationale = block.input.get("rationale", "")
                break
        if action_ids is None or not isinstance(action_ids, list):
            print(
                f"[{seat}] model did not call submit_action; stop_reason="
                f"{response.stop_reason}, content={response.content!r}",
                file=sys.stderr,
            )
            return 1

        # 3. Append rationale line.
        try:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(_log_line(seat, pending, action_ids, rationale))
        except OSError as exc:
            log.warning("[%s] failed to append log line: %s", seat, exc)

        # 4. Submit. Tolerate the same races the integration test does:
        #    - 409 "unknown action_ids" → engine moved to a different decision
        #      between our GET and POST.
        #    - 409 "no pending decision" → engine briefly cleared the seat's
        #      pending state. Re-poll either returns the next decision or null.
        for _attempt in range(MAX_409_RETRIES):
            code, ack = _http_post(
                f"{base}/action?player={seat}",
                {"selected_option_ids": action_ids},
            )
            if code == 200 and ack.get("ok"):
                decisions += 1
                break
            if code == 409:
                err = str(ack.get("error", ""))
                if "unknown action_ids" in err or "no pending decision" in err:
                    log.info("[%s] race on submit, re-polling: %s", seat, err)
                    break  # break inner; outer loop re-polls and re-asks
            print(
                f"[{seat}] act rejected (code={code}): {ack}",
                file=sys.stderr,
            )
            return 1

    # Final summary — useful for verifying caching hit rate.
    print(
        f"[{seat}] done. decisions={decisions} "
        f"input_tokens={total_input} output_tokens={total_output} "
        f"cache_read={total_cache_read} cache_write={total_cache_write}"
    )
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python tools/auto_player.py",
        description=(
            "Drive one seat of a FaB match via per-decision Anthropic API calls "
            "(cheaper alternative to long-lived Claude Code sub-agent players)."
        ),
    )
    p.add_argument("--port", type=int, required=True, help="Match server port.")
    p.add_argument("--seat", required=True, help="Seat to drive: A or B.")
    p.add_argument("--hero", required=True, help="Hero name (from deck file).")
    p.add_argument("--deck", required=True, help="Path to markdown decklist.")
    p.add_argument("--match-id", required=True, help="Match id (must match server).")
    p.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=(
            f"Anthropic model id (default: {DEFAULT_MODEL}). "
            "For high-volume per-decision driving, consider claude-sonnet-4-6 "
            "or claude-haiku-4-5 to reduce cost."
        ),
    )
    p.add_argument(
        "--blurb", default=None,
        help="Optional one-line deck characterization (e.g. 'Blue Cindra').",
    )
    p.add_argument(
        "--cards", default=str(DEFAULT_CARDS_TSV),
        help=(
            f"Path to the card database TSV (default: {DEFAULT_CARDS_TSV}). "
            "Cited verbatim into the cached system prompt as a card-text reference."
        ),
    )
    p.add_argument(
        "--rules", default=str(DEFAULT_RULES_PATH),
        help=(
            f"Path to comprehensive-rules.md (default: {DEFAULT_RULES_PATH}). "
            "Decision-relevant excerpts are embedded in the cached system prompt."
        ),
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
