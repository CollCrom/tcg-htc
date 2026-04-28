from __future__ import annotations

from typing import Protocol

from engine.rules.actions import Decision, PlayerResponse
from engine.state.game_state import GameState


class PlayerInterface(Protocol):
    """How a player (human, AI, random) communicates with the engine.

    The engine calls decide() whenever it needs player input. The
    implementation examines the Decision's options and returns a response.
    """

    def decide(self, game_state: GameState, decision: Decision) -> PlayerResponse: ...
