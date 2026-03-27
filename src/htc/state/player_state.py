from __future__ import annotations

from dataclasses import dataclass, field

from htc.cards.instance import CardInstance
from htc.enums import EquipmentSlot, Zone
from htc.state.turn_counters import TurnCounters


@dataclass
class PlayerState:
    """All per-player game state: zones, life, assets, counters."""

    index: int  # 0 or 1
    hero: CardInstance | None = None
    life_total: int = 0

    # Zones
    hand: list[CardInstance] = field(default_factory=list)
    deck: list[CardInstance] = field(default_factory=list)  # top = index 0
    arsenal: list[CardInstance] = field(default_factory=list)  # max 1 typically
    pitch: list[CardInstance] = field(default_factory=list)
    graveyard: list[CardInstance] = field(default_factory=list)
    banished: list[CardInstance] = field(default_factory=list)
    soul: list[CardInstance] = field(default_factory=list)

    # Equipment slots
    equipment: dict[EquipmentSlot, CardInstance | None] = field(default_factory=lambda: {
        EquipmentSlot.HEAD: None,
        EquipmentSlot.CHEST: None,
        EquipmentSlot.ARMS: None,
        EquipmentSlot.LEGS: None,
    })
    weapons: list[CardInstance] = field(default_factory=list)  # up to 2

    # Permanents this player controls (items, auras, allies, etc.)
    permanents: list[CardInstance] = field(default_factory=list)

    # Per-turn tracking
    turn_counters: TurnCounters = field(default_factory=TurnCounters)

    # Marked condition (rules 9.3): hero is marked until hit by opponent's source
    is_marked: bool = False

    def get_zone_cards(self, zone: Zone) -> list[CardInstance]:
        """Get the list of cards in a given zone for this player."""
        match zone:
            case Zone.HAND:
                return self.hand
            case Zone.DECK:
                return self.deck
            case Zone.ARSENAL:
                return self.arsenal
            case Zone.PITCH:
                return self.pitch
            case Zone.GRAVEYARD:
                return self.graveyard
            case Zone.BANISHED:
                return self.banished
            case Zone.SOUL:
                return self.soul
            case _:
                return []

    def remove_card(self, card: CardInstance) -> bool:
        """Remove a card from whichever zone list it's in. Returns True if found."""
        for zone_list in [self.hand, self.deck, self.arsenal, self.pitch,
                          self.graveyard, self.banished, self.soul,
                          self.weapons, self.permanents]:
            if card in zone_list:
                zone_list.remove(card)
                return True
        for slot, eq in self.equipment.items():
            if eq is card:
                self.equipment[slot] = None
                return True
        return False

    def find_card(self, instance_id: int) -> CardInstance | None:
        """Find a card by instance ID across all zones."""
        for zone in [self.hand, self.deck, self.arsenal, self.pitch,
                     self.graveyard, self.banished, self.soul,
                     self.weapons, self.permanents]:
            for card in zone:
                if card.instance_id == instance_id:
                    return card
        for eq in self.equipment.values():
            if eq and eq.instance_id == instance_id:
                return eq
        if self.hero and self.hero.instance_id == instance_id:
            return self.hero
        return None
