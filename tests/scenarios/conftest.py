"""Pytest fixtures for scenario tests.

Provides the `scenario_recorder` fixture that captures board state
snapshots during test execution. Tests opt in by requesting the fixture.
"""

from __future__ import annotations

import pytest

from tools.scenario_recorder import ScenarioRecorder


@pytest.fixture
def scenario_recorder(request):
    """Create a ScenarioRecorder for the current test.

    Usage::

        def test_something(self, scenario_recorder):
            game = make_game_shell()
            recorder = scenario_recorder.bind(game)
            recorder.snap("After setup")
            # ... test logic ...
            recorder.snap("After resolution")

    Snapshots are written to scenario_snapshots/ after the test completes.
    """
    test_name = request.node.nodeid
    recorder = ScenarioRecorder(test_name)
    yield recorder
    recorder.write()
