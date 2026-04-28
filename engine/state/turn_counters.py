from __future__ import annotations

from dataclasses import dataclass, field


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

    # Track card names played this turn for effects that check duplicate plays
    # (e.g. Amulet of Echoes: "if they have played 2 or more cards with the
    # same name this turn").
    card_names_played: list[str] = field(default_factory=list)

    # Track Fealty token creation and Draconic card plays for Fealty's
    # end-phase self-destruct condition.
    fealty_created_this_turn: bool = False
    draconic_card_played_this_turn: bool = False
    returned_to_brood_this_turn: bool = False

    def has_duplicate_card_name(self) -> bool:
        """Return True if any card name appears 2+ times this turn."""
        seen: set[str] = set()
        for name in self.card_names_played:
            if name in seen:
                return True
            seen.add(name)
        return False

    def reset(self) -> None:
        self.__init__()  # type: ignore[misc]
