from __future__ import annotations

from dataclasses import dataclass, field
from random import Random

from htc.cards.instance import CardInstance
from htc.enums import CombatStep, LayerKind, Phase
from htc.state.combat_state import CombatChainState
from htc.state.player_state import PlayerState


@dataclass
class Layer:
    """An object on the stack waiting to resolve."""

    layer_id: int
    kind: LayerKind
    card: CardInstance | None = None  # for card-layers
    source_instance_id: int | None = None
    controller_index: int = 0
    targets: list[int] = field(default_factory=list)  # instance_ids
    has_go_again: bool = False


@dataclass
class GameState:
    """Top-level container for all game state."""

    players: list[PlayerState] = field(default_factory=list)
    turn_number: int = 0
    turn_player_index: int = 0
    phase: Phase = Phase.START
    combat_step: CombatStep | None = None
    combat_chain: CombatChainState = field(default_factory=CombatChainState)
    stack: list[Layer] = field(default_factory=list)  # LIFO: last = top
    continuous_effects: list = field(default_factory=list)  # list[ContinuousEffect]
    priority_player_index: int | None = None
    action_points: dict[int, int] = field(default_factory=lambda: {0: 0, 1: 0})
    resource_points: dict[int, int] = field(default_factory=lambda: {0: 0, 1: 0})
    rng: Random = field(default_factory=Random)
    winner: int | None = None
    game_over: bool = False
    _next_instance_id: int = 0
    _next_layer_id: int = 0

    def next_instance_id(self) -> int:
        self._next_instance_id += 1
        return self._next_instance_id

    def next_layer_id(self) -> int:
        self._next_layer_id += 1
        return self._next_layer_id

    @property
    def turn_player(self) -> PlayerState:
        return self.players[self.turn_player_index]

    @property
    def non_turn_player(self) -> PlayerState:
        return self.players[1 - self.turn_player_index]

    def opponent_of(self, player_index: int) -> PlayerState:
        return self.players[1 - player_index]

    def find_card(self, instance_id: int) -> CardInstance | None:
        """Find a card by instance ID across all players."""
        for p in self.players:
            card = p.find_card(instance_id)
            if card is not None:
                return card
        # Check stack
        for layer in self.stack:
            if layer.card and layer.card.instance_id == instance_id:
                return layer.card
        return None
