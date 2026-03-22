from __future__ import annotations

from dataclasses import dataclass, field

from htc.enums import ActionType, DecisionType


@dataclass
class ActionOption:
    """One legal option within a decision."""

    action_id: str
    description: str
    action_type: ActionType
    card_instance_id: int | None = None


@dataclass
class Decision:
    """A question the engine asks a player.

    The engine yields these; players return PlayerResponse.
    This is the core interface between the engine and player implementations.
    """

    player_index: int
    decision_type: DecisionType
    prompt: str
    options: list[ActionOption] = field(default_factory=list)
    min_selections: int = 1
    max_selections: int = 1


@dataclass
class PlayerResponse:
    """A player's answer to a Decision."""

    selected_option_ids: list[str] = field(default_factory=list)

    @property
    def first(self) -> str | None:
        return self.selected_option_ids[0] if self.selected_option_ids else None
