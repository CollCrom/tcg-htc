"""Capture board state snapshots during scenario test execution.

Provides a ScenarioRecorder that wraps a Game object and captures
snapshots via tools.snapshot.capture_snapshot(). Tests call
recorder.snap("description") at key moments to record board state.

The snapshots are stored keyed by test name and written to JSON files
after each test completes.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.snapshot import capture_snapshot


# Default output directory (gitignored)
SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "scenario_snapshots"


class ScenarioRecorder:
    """Records board state snapshots during a scenario test.

    Usage in a test::

        def test_something(self, scenario_recorder):
            game = make_game_shell()
            recorder = scenario_recorder.bind(game)
            # ... set up state ...
            recorder.snap("After setup")
            # ... do combat ...
            recorder.snap("After combat resolution")
    """

    def __init__(self, test_name: str, output_dir: Path | None = None):
        self.test_name = test_name
        self.output_dir = output_dir or SNAPSHOT_DIR
        self._game = None
        self._snapshots: list[dict] = []

    def bind(self, game) -> "ScenarioRecorder":
        """Bind this recorder to a Game object.

        Must be called before snap(). Returns self for chaining.
        """
        self._game = game
        return self

    def snap(self, description: str) -> None:
        """Capture a snapshot of the current board state.

        Args:
            description: Human-readable label for this snapshot
                (e.g. "After setup", "After attack hits").
        """
        if self._game is None:
            raise RuntimeError(
                "ScenarioRecorder.bind(game) must be called before snap()"
            )
        snapshot = capture_snapshot(
            self._game.state,
            description,
            effect_engine=self._game.effect_engine,
        )
        snapshot["test_name"] = self.test_name
        snapshot["snap_index"] = len(self._snapshots)
        self._snapshots.append(snapshot)

    @property
    def snapshots(self) -> list[dict]:
        """Return the list of captured snapshots."""
        return list(self._snapshots)

    def write(self) -> Path | None:
        """Write snapshots to a JSON file. Returns the path, or None if empty."""
        if not self._snapshots:
            return None

        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Sanitize test name for filename
        safe_name = self.test_name.replace("::", "__").replace("/", "_")
        output_path = self.output_dir / f"{safe_name}.json"
        output_path.write_text(json.dumps(self._snapshots, indent=2))
        return output_path
