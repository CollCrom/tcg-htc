from __future__ import annotations

from dataclasses import dataclass, field

from htc.cards.card import CardDefinition
from htc.enums import Zone


@dataclass
class CardInstance:
    """A card that exists in a game — has identity and mutable state.

    CardDefinition holds the static data; CardInstance adds per-game state
    like which zone it's in, counters, tapped state, etc.
    """

    instance_id: int
    definition: CardDefinition
    owner_index: int
    zone: Zone
    controller_index: int | None = None
    is_tapped: bool = False
    face_up: bool = True
    counters: dict[str, int] = field(default_factory=dict)

    # --- Delegation to definition ---

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def cost(self) -> int | None:
        return self.definition.cost

    @property
    def pitch(self) -> int | None:
        return self.definition.pitch

    @property
    def base_power(self) -> int | None:
        return self.definition.power

    @property
    def base_defense(self) -> int | None:
        return self.definition.defense

    @property
    def keyword_values(self) -> dict:
        return self.definition.keyword_values

    def __repr__(self) -> str:
        return f"CardInstance({self.instance_id}, {self.definition!r}, zone={self.zone.value})"
