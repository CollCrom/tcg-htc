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
    is_proxy: bool = False
    proxy_source_id: int | None = None  # instance_id of the weapon that created this proxy
    definition_override: CardDefinition | None = None  # copy effect override

    # --- Delegation to definition ---

    @property
    def _effective_definition(self) -> CardDefinition:
        """The definition to use for property lookups.

        When ``definition_override`` is set (e.g. by a copy effect),
        all property lookups delegate to the override instead of the
        original definition. The card keeps its identity (instance_id,
        zone, counters, etc.) but takes on the copied card's stats.
        """
        return self.definition_override if self.definition_override is not None else self.definition

    @property
    def name(self) -> str:
        return self._effective_definition.name

    @property
    def cost(self) -> int | None:
        return self._effective_definition.cost

    @property
    def pitch(self) -> int | None:
        return self._effective_definition.pitch

    @property
    def base_power(self) -> int | None:
        return self._effective_definition.power

    @property
    def base_defense(self) -> int | None:
        return self._effective_definition.defense

    @property
    def keyword_values(self) -> dict:
        return self._effective_definition.keyword_values

    def __repr__(self) -> str:
        return f"CardInstance({self.instance_id}, {self.definition!r}, zone={self.zone.value})"
