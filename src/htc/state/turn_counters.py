from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TurnCounters:
    """Per-turn statistics, reset at start of each turn.

    Many FaB cards check "if you've done X this turn" — this is the mechanism
    to support those conditions. Mirrors Talishar's $CS_* indices.
    """

    num_attacks_played: int = 0
    num_attack_cards_played: int = 0
    num_non_attack_actions_played: int = 0
    num_instants_played: int = 0
    num_defense_reactions_played: int = 0
    num_cards_drawn: int = 0
    num_cards_pitched: int = 0
    num_cards_defended_from_hand: int = 0
    damage_taken: int = 0
    damage_dealt: int = 0
    life_gained: int = 0
    life_lost: int = 0
    num_weapon_attacks: int = 0
    has_boosted: bool = False
    has_attacked: bool = False

    def reset(self) -> None:
        self.__init__()  # type: ignore[misc]
