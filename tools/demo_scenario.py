"""Generate demo snapshots by running a real Cindra vs Arakni game.

Uses a logging handler to capture snapshots AFTER each action is fully
resolved (including triggered effects), giving accurate board state.

Usage:
    python3 tools/demo_scenario.py          # writes demo_snapshots.json
    python3 tools/demo_scenario.py out.json  # custom output path
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from htc.cards.card_db import CardDatabase
from htc.engine.game import Game
from htc.player.random_player import RandomPlayer

# Reuse the integration test's markdown parser
from tests.integration.test_full_game import parse_markdown_decklist

from tools.snapshot import capture_snapshot

DATA_DIR = PROJECT_ROOT / "data"
REF_DIR = PROJECT_ROOT / "ref"


class LogSnapshotHandler(logging.Handler):
    """Captures a snapshot every time an interesting log message is emitted.

    Since log.info() calls happen AFTER the action is resolved (including
    triggered effects), the captured state is accurate and complete.
    """

    PATTERNS = [
        "attacks with",
        "chains ",
        "defends with",
        "Hit!",
        "Blocked!",
        " plays ",
        " arsenals ",
        " activates ",
        "Flick Knives:",
        "Marked ",
        "Mark removed",
        "becomes ",
        "returns to the brood",
        "Created ",
        "Token destroyed",
        "destroyed",
        "Pitched ",
        "end phase",
        "damage to",
        "=== Turn",
    ]

    SKIP = ["Registered", "energy counter", "Piercing"]

    def __init__(self, game: Game, max_snapshots: int = 60):
        super().__init__()
        self.game = game
        self.snapshots: list[dict] = []
        self.max_snapshots = max_snapshots
        self._last_desc = None

    def emit(self, record: logging.LogRecord) -> None:
        if len(self.snapshots) >= self.max_snapshots:
            return
        msg = record.getMessage().strip()
        if not msg:
            return

        for skip in self.SKIP:
            if skip in msg:
                return

        if not any(pat in msg for pat in self.PATTERNS):
            return

        # Deduplicate identical consecutive descriptions
        if msg == self._last_desc:
            return
        self._last_desc = msg

        try:
            snap = capture_snapshot(
                self.game.state,
                msg,
                effect_engine=self.game.effect_engine,
            )
            self.snapshots.append(snap)
        except Exception:
            pass


def main():
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("demo_snapshots.json")

    # Suppress default logging to console
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    # Load card database and decklists
    db = CardDatabase.load(DATA_DIR / "cards.tsv")
    cindra_text = (REF_DIR / "decklist-cindra-blue.md").read_text()
    arakni_text = (REF_DIR / "decklist-arakni.md").read_text()
    cindra_deck = parse_markdown_decklist(cindra_text)
    arakni_deck = parse_markdown_decklist(arakni_text)

    # Create game with a fixed seed for reproducibility
    p1 = RandomPlayer(seed=0)
    p2 = RandomPlayer(seed=100)
    game = Game(db, cindra_deck, arakni_deck, p1, p2, seed=0)

    # Set up the game
    game._setup_game()

    # Attach the logging-based snapshot handler
    handler = LogSnapshotHandler(game, max_snapshots=150)
    root_logger.addHandler(handler)

    # Capture initial state
    snap = capture_snapshot(game.state, "Game start — hands dealt", effect_engine=game.effect_engine)
    handler.snapshots.append(snap)

    # Run turns
    while not game.state.game_over and game.state.turn_number < 200:
        game._run_turn()
        if len(handler.snapshots) >= handler.max_snapshots:
            break

    # Final state
    if game.state.game_over and len(handler.snapshots) < handler.max_snapshots:
        winner = game.state.winner
        ps = game.state.players
        if winner is not None:
            name = ps[winner].hero.definition.name.split(",")[0] if ps[winner].hero else f"Player {winner}"
            snap = capture_snapshot(game.state, f"Game over — {name} wins!", effect_engine=game.effect_engine)
        else:
            snap = capture_snapshot(game.state, "Game over — draw", effect_engine=game.effect_engine)
        handler.snapshots.append(snap)

    # Cleanup
    root_logger.removeHandler(handler)

    # Write
    output_path.write_text(json.dumps(handler.snapshots, indent=2))
    print(f"Captured {len(handler.snapshots)} snapshots -> {output_path}")


if __name__ == "__main__":
    main()
