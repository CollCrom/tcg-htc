"""Entry point: run a game with one player driven over stdin/stdout JSONL.

Usage::

    python -m engine.stdio --side p1 --seed 7

Wire format
-----------
On startup the engine emits one ``ready`` line so the agent knows which
seat it controls and can prepare. After that, each time the engine needs
input from the agent, it writes one ``decision`` JSON line to stdout and
waits for one JSON response line on stdin. When the game ends, a single
``game_over`` line is written and the process exits 0.

    # engine -> agent
    {"type": "ready", "player_index": 0, "seed": 7}
    {"type": "decision", "player_index": 0, "decision_type": "play_or_pass",
     "prompt": "...", "min_selections": 1, "max_selections": 1,
     "options": [{"action_id": "pass", "description": "Pass",
                  "action_type": "pass", "card_instance_id": null}],
     "state": {"you": {...}, "opponent": {...},
               "combat_chain": {...}, "turn": {...}}}
    {"type": "game_over", "winner": 0, "turns": 14, "final_life": [0, 4]}

    # agent -> engine
    {"selected_option_ids": ["pass"]}

The ``state`` field on every ``decision`` is a per-player snapshot from
the agent's viewpoint with hidden zones redacted (opponent hand becomes
``hand_size``; opponent face-down banished becomes a count). Cards
include both base and effect-modified values. Schema is defined in
``engine/state/snapshot.py``.

The opponent is a random player (seeded). Logs go to stderr so stdout
stays a clean JSONL channel.

Exit codes
----------
0   game completed (winner reported in game_over)
2   bad CLI args / unreachable cards file
3   agent closed stdin or sent malformed JSON
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from engine._demo_deck import BRAVO_DECK_TEXT
from engine.cards.card_db import CardDatabase
from engine.decks.loader import parse_deck_list
from engine.player.random_player import RandomPlayer
from engine.player.stdio_player import StdioPlayer, emit_event
from engine.rules.game import Game

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CARDS = REPO_ROOT / "data" / "cards.tsv"


def _read_deck(path: Path | None) -> str:
    if path is None:
        return BRAVO_DECK_TEXT
    return path.read_text(encoding="utf-8")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m engine.stdio",
        description="Play a FaB game with one seat driven over JSONL stdio.",
    )
    p.add_argument(
        "--side",
        choices=("p1", "p2"),
        default="p1",
        help="Which seat the stdio agent controls (default: p1).",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Master RNG seed for the game.",
    )
    p.add_argument(
        "--opponent-seed",
        type=int,
        default=None,
        help="RNG seed for the random opponent (defaults to --seed + 1).",
    )
    p.add_argument(
        "--cards",
        type=Path,
        default=DEFAULT_CARDS,
        help=f"Path to the card database TSV (default: {DEFAULT_CARDS}).",
    )
    p.add_argument(
        "--deck",
        type=Path,
        default=None,
        help="Path to a deck list (default: built-in Bravo, Showstopper). Both seats use this deck.",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Log engine events to stderr (stdout stays JSONL-only).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    # Logs to stderr so stdout remains a clean JSONL channel for the agent.
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(message)s",
        stream=sys.stderr,
    )

    if not args.cards.exists():
        print(f"error: card database not found: {args.cards}", file=sys.stderr)
        return 2

    db = CardDatabase.load(args.cards)
    deck_text = _read_deck(args.deck)
    deck1 = parse_deck_list(deck_text)
    deck2 = parse_deck_list(deck_text)

    stdio_index = 0 if args.side == "p1" else 1
    opp_seed = args.opponent_seed if args.opponent_seed is not None else args.seed + 1

    stdio_player = StdioPlayer(player_index=stdio_index)
    random_player = RandomPlayer(seed=opp_seed)

    if stdio_index == 0:
        p1, p2 = stdio_player, random_player
    else:
        p1, p2 = random_player, stdio_player

    # Announce which seat the agent has so it can prep before the first decision.
    emit_event({"type": "ready", "player_index": stdio_index, "seed": args.seed})

    game = Game(db, deck1, deck2, p1, p2, seed=args.seed)
    # Wire the effect engine into the stdio player so per-decision snapshots
    # can include effect-modified values (modified power on the active
    # attack, modified cost on cards in hand, etc.).
    stdio_player.effect_engine = game.effect_engine

    try:
        result = game.play()
    except RuntimeError as exc:
        # Surfaces malformed-agent errors raised by StdioPlayer.
        print(f"error: {exc}", file=sys.stderr)
        return 3

    emit_event(
        {
            "type": "game_over",
            "winner": result.winner,
            "turns": result.turns,
            "final_life": list(result.final_life),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
