from __future__ import annotations

from dataclasses import dataclass, field

from htc.cards.instance import CardInstance


@dataclass
class ChainLink:
    """A single attack in the combat chain."""

    link_number: int
    active_attack: CardInstance | None = None
    attack_source: CardInstance | None = None  # weapon if attack-proxy
    attack_target_index: int = 0  # player index being attacked
    defending_cards: list[CardInstance] = field(default_factory=list)
    damage_dealt: int = 0
    hit: bool = False
    defense_reactions_blocked: bool = False


@dataclass
class CombatChainState:
    """State of the combat chain zone."""

    is_open: bool = False
    chain_links: list[ChainLink] = field(default_factory=list)

    @property
    def active_link(self) -> ChainLink | None:
        return self.chain_links[-1] if self.chain_links else None

    @property
    def num_chain_links(self) -> int:
        return len(self.chain_links)

    def reset(self) -> None:
        self.is_open = False
        self.chain_links.clear()
