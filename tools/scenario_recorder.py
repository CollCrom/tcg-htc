"""Capture board state snapshots during scenario test execution.

Provides a ScenarioRecorder that wraps a Game object and captures
snapshots automatically on every interesting state-changing event.
Tests can still call recorder.snap("description") for additional
manual snapshots if needed.

The snapshots are stored keyed by test name and written to JSON files
after each test completes.
"""

from __future__ import annotations

import json
from pathlib import Path

from htc.engine.events import EventType, GameEvent
from tools.snapshot import capture_snapshot


# Default output directory (gitignored)
SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "scenario_snapshots"

# Maximum snapshots per test to avoid huge JSON files
MAX_SNAPSHOTS = 30

# Events worth snapshotting (interesting state changes)
_INTERESTING_EVENTS: set[EventType] = {
    EventType.ATTACK_DECLARED,
    EventType.DEFEND_DECLARED,
    EventType.HIT,
    EventType.DEAL_DAMAGE,
    EventType.PLAY_CARD,
    EventType.DRAW_CARD,
    EventType.COMBAT_CHAIN_CLOSES,
    EventType.START_OF_TURN,
    EventType.END_OF_TURN,
    EventType.CREATE_TOKEN,
    EventType.BANISH,
    EventType.BECOME_AGENT,
    EventType.DESTROY,
    EventType.DISCARD,
    EventType.LOSE_LIFE,
    EventType.GAIN_LIFE,
    EventType.START_OF_ACTION_PHASE,
}


def _describe_event(event: GameEvent) -> str:
    """Generate a human-readable description from a game event."""
    etype = event.event_type.name

    # Card name helper
    card_name = ""
    if event.card:
        card_name = event.card.name
    elif event.source:
        card_name = event.source.name

    # Player helper
    player_label = ""
    if event.target_player is not None:
        player_label = f"Player {event.target_player}"

    if event.event_type == EventType.ATTACK_DECLARED:
        return f"ATTACK_DECLARED: {card_name}" if card_name else "ATTACK_DECLARED"

    if event.event_type == EventType.DEFEND_DECLARED:
        return f"DEFEND_DECLARED: {card_name}" if card_name else "DEFEND_DECLARED"

    if event.event_type == EventType.HIT:
        if event.amount:
            return f"HIT: {card_name} hits for {event.amount}" if card_name else f"HIT: {event.amount} damage"
        return f"HIT: {card_name}" if card_name else "HIT"

    if event.event_type == EventType.DEAL_DAMAGE:
        target = player_label or "target"
        if card_name:
            return f"DEAL_DAMAGE: {card_name} deals {event.amount} to {target}"
        return f"DEAL_DAMAGE: {event.amount} to {target}"

    if event.event_type == EventType.PLAY_CARD:
        return f"PLAY_CARD: {card_name}" if card_name else "PLAY_CARD"

    if event.event_type == EventType.DRAW_CARD:
        return f"DRAW_CARD: {player_label} draws" if player_label else "DRAW_CARD"

    if event.event_type == EventType.COMBAT_CHAIN_CLOSES:
        return "COMBAT_CHAIN_CLOSES"

    if event.event_type == EventType.START_OF_TURN:
        turn = event.data.get("turn_number", "?")
        return f"START_OF_TURN: Turn {turn}"

    if event.event_type == EventType.END_OF_TURN:
        return f"END_OF_TURN: {player_label}" if player_label else "END_OF_TURN"

    if event.event_type == EventType.START_OF_ACTION_PHASE:
        return "START_OF_ACTION_PHASE"

    if event.event_type == EventType.CREATE_TOKEN:
        return f"CREATE_TOKEN: {card_name}" if card_name else "CREATE_TOKEN"

    if event.event_type == EventType.BANISH:
        return f"BANISH: {card_name}" if card_name else "BANISH"

    if event.event_type == EventType.DESTROY:
        return f"DESTROY: {card_name}" if card_name else "DESTROY"

    if event.event_type == EventType.BECOME_AGENT:
        return f"BECOME_AGENT: {card_name}" if card_name else "BECOME_AGENT"

    if event.event_type == EventType.DISCARD:
        return f"DISCARD: {card_name}" if card_name else "DISCARD"

    if event.event_type == EventType.LOSE_LIFE:
        return f"LOSE_LIFE: {player_label} loses {event.amount}" if player_label else f"LOSE_LIFE: {event.amount}"

    if event.event_type == EventType.GAIN_LIFE:
        return f"GAIN_LIFE: {player_label} gains {event.amount}" if player_label else f"GAIN_LIFE: {event.amount}"

    # Fallback
    parts = [etype]
    if card_name:
        parts.append(card_name)
    if event.amount:
        parts.append(str(event.amount))
    return ": ".join(parts)


class ScenarioRecorder:
    """Records board state snapshots during a scenario test.

    When bound to a game, automatically captures snapshots on every
    interesting state-changing event via the game's event bus.
    Manual snap() calls still work for additional custom snapshots.

    Usage in a test::

        def test_something(self, scenario_recorder):
            game = make_game_shell()
            recorder = scenario_recorder.bind(game)
            # ... test logic — snapshots happen automatically ...
    """

    def __init__(self, test_name: str, output_dir: Path | None = None):
        self.test_name = test_name
        self.output_dir = output_dir or SNAPSHOT_DIR
        self._game = None
        self._snapshots: list[dict] = []
        self._original_emit = None

    def bind(self, game) -> "ScenarioRecorder":
        """Bind this recorder to a Game object.

        Captures an initial snapshot and hooks into the event bus
        to auto-capture snapshots on interesting events.
        Returns self for chaining.
        """
        self._game = game

        # Capture initial state
        self._take_snapshot("Initial state")

        # Wrap the event bus emit() to auto-snapshot after events
        original_emit = game.events.emit
        self._original_emit = original_emit

        def _instrumented_emit(event: GameEvent) -> GameEvent:
            result = original_emit(event)
            # Snapshot after the event executes (if interesting and not cancelled)
            if (
                not result.cancelled
                and result.event_type in _INTERESTING_EVENTS
                and len(self._snapshots) < MAX_SNAPSHOTS
            ):
                description = _describe_event(result)
                self._take_snapshot(description)
            return result

        game.events.emit = _instrumented_emit
        return self

    def snap(self, description: str) -> None:
        """Capture a manual snapshot of the current board state.

        Args:
            description: Human-readable label for this snapshot.
        """
        if self._game is None:
            raise RuntimeError(
                "ScenarioRecorder.bind(game) must be called before snap()"
            )
        self._take_snapshot(description)

    def _take_snapshot(self, description: str) -> None:
        """Internal: capture a snapshot if under the cap."""
        if len(self._snapshots) >= MAX_SNAPSHOTS:
            return
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
