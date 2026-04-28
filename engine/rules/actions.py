from __future__ import annotations

from dataclasses import dataclass, field

from engine.enums import ActionType, DecisionType


@dataclass
class ActionOption:
    """One legal option within a decision."""

    action_id: str
    description: str
    action_type: ActionType
    card_instance_id: int | None = None

    # --- Factory methods ---

    @staticmethod
    def play_card(card_instance_id: int, name: str, color_label: str, suffix: str = "") -> ActionOption:
        """Create a 'play card' option.  *suffix* is appended in parentheses when non-empty."""
        desc = f"Play {name}{color_label}"
        if suffix:
            desc += f" ({suffix})"
        return ActionOption(
            action_id=f"play_{card_instance_id}",
            description=desc,
            action_type=ActionType.PLAY_CARD,
            card_instance_id=card_instance_id,
        )

    @staticmethod
    def defend_with(card_instance_id: int, name: str, defense: int, *, extra: str = "") -> ActionOption:
        """Create a 'defend with card' option."""
        desc = f"Defend with {name} (defense={defense}"
        if extra:
            desc += f", {extra}"
        desc += ")"
        return ActionOption(
            action_id=f"defend_{card_instance_id}",
            description=desc,
            action_type=ActionType.DEFEND_WITH,
            card_instance_id=card_instance_id,
        )

    @staticmethod
    def activate(card_instance_id: int, description: str) -> ActionOption:
        """Create an 'activate ability' option for a weapon or equipment."""
        return ActionOption(
            action_id=f"activate_{card_instance_id}",
            description=description,
            action_type=ActionType.ACTIVATE_ABILITY,
            card_instance_id=card_instance_id,
        )


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
