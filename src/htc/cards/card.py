from __future__ import annotations

from dataclasses import dataclass

from htc.enums import CardType, Color, Keyword, SubType, SuperType


@dataclass(frozen=True)
class CardDefinition:
    """Immutable card data loaded from FaB Cube CSV.

    A card is unique by (name, pitch). Color variants like
    "Adrenaline Rush (Red)" and "Adrenaline Rush (Blue)" are
    separate CardDefinition instances.
    """

    unique_id: str
    name: str
    color: Color | None
    pitch: int | None
    cost: int | None
    power: int | None
    defense: int | None
    health: int | None
    intellect: int | None
    arcane: int | None
    types: frozenset[CardType]
    subtypes: frozenset[SubType]
    supertypes: frozenset[SuperType]
    keywords: frozenset[Keyword]
    functional_text: str
    type_text: str

    # --- Convenience properties ---

    @property
    def is_attack(self) -> bool:
        return SubType.ATTACK in self.subtypes

    @property
    def is_action(self) -> bool:
        return CardType.ACTION in self.types

    @property
    def is_attack_action(self) -> bool:
        return self.is_action and self.is_attack

    @property
    def is_non_attack_action(self) -> bool:
        return self.is_action and not self.is_attack

    @property
    def is_instant(self) -> bool:
        return CardType.INSTANT in self.types

    @property
    def is_defense_reaction(self) -> bool:
        return CardType.DEFENSE_REACTION in self.types

    @property
    def is_attack_reaction(self) -> bool:
        return CardType.ATTACK_REACTION in self.types

    @property
    def is_equipment(self) -> bool:
        return CardType.EQUIPMENT in self.types

    @property
    def is_weapon(self) -> bool:
        return CardType.WEAPON in self.types

    @property
    def is_hero(self) -> bool:
        return CardType.HERO in self.types

    @property
    def is_token(self) -> bool:
        return CardType.TOKEN in self.types

    @property
    def is_deck_card(self) -> bool:
        return bool(self.types & {
            CardType.ACTION,
            CardType.ATTACK_REACTION,
            CardType.BLOCK,
            CardType.DEFENSE_REACTION,
            CardType.INSTANT,
            CardType.MENTOR,
            CardType.RESOURCE,
        })

    @property
    def is_arena_card(self) -> bool:
        return not self.is_hero and not self.is_token and not self.is_deck_card

    _PERMANENT_SUBTYPES = frozenset({
        SubType.AFFLICTION, SubType.ALLY, SubType.ASH, SubType.AURA,
        SubType.CONSTRUCT, SubType.FIGMENT, SubType.INVOCATION,
        SubType.ITEM, SubType.LANDMARK,
    })

    @property
    def is_permanent_when_resolved(self) -> bool:
        """Deck-cards with these subtypes become permanents on resolution (1.3.3)."""
        return bool(self.subtypes & self._PERMANENT_SUBTYPES)

    @property
    def has_go_again(self) -> bool:
        return Keyword.GO_AGAIN in self.keywords

    @property
    def has_dominate(self) -> bool:
        return Keyword.DOMINATE in self.keywords

    @property
    def color_label(self) -> str:
        """Formatted color string for display, e.g. ' (Red)' or ''."""
        return f" ({self.color.value})" if self.color else ""

    def __repr__(self) -> str:
        return f"CardDefinition({self.name!r}{self.color_label})"
