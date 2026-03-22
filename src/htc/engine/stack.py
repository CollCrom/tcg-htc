from __future__ import annotations

from htc.cards.instance import CardInstance
from htc.enums import LayerKind, Zone
from htc.state.game_state import GameState, Layer


class StackManager:
    """Manages the LIFO stack of layers."""

    def add_card_layer(
        self,
        state: GameState,
        card: CardInstance,
        controller_index: int,
        targets: list[int] | None = None,
    ) -> Layer:
        """Put a card on the stack as a card-layer."""
        layer = Layer(
            layer_id=state.next_layer_id(),
            kind=LayerKind.CARD,
            card=card,
            source_instance_id=card.instance_id,
            controller_index=controller_index,
            targets=targets or [],
            has_go_again=card.definition.has_go_again,
        )
        card.zone = Zone.STACK
        state.stack.append(layer)
        return layer

    def resolve_top(self, state: GameState) -> Layer | None:
        """Resolve the top layer of the stack. Returns the resolved layer."""
        if not state.stack:
            return None
        return state.stack.pop()

    def is_empty(self, state: GameState) -> bool:
        return len(state.stack) == 0

    def top(self, state: GameState) -> Layer | None:
        return state.stack[-1] if state.stack else None
