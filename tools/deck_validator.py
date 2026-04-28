"""Deck validation: enforce deckbuilding constraints.

Checks Legendary (max 1 copy) and Specialization (hero restriction)
constraints, plus general FaB deck legality rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from engine.cards.card_db import CardDatabase
from engine.decks.deck_list import DeckList
from engine.enums import Keyword


@dataclass
class ValidationError:
    """A single deck validation error."""

    card_name: str
    message: str


def validate_deck(deck: DeckList, db: CardDatabase) -> list[ValidationError]:
    """Validate a deck list against deckbuilding constraints.

    Checks:
    - Legendary: max 1 copy of any card with the Legendary keyword.
    - Specialization: card can only be in deck if hero matches.
      (Note: Specialization hero matching requires card text parsing,
      which is Phase 5. For now we just flag cards with Specialization
      and check that the hero name appears in the card's functional text.)

    Returns a list of ValidationError instances. Empty list means valid.
    """
    errors: list[ValidationError] = []

    # Check deck cards
    for entry in deck.cards:
        card_def = db.get_by_name(entry.name, entry.color)
        if card_def is None:
            continue

        # Legendary (8.3): max 1 copy
        if Keyword.LEGENDARY in card_def.keywords and entry.count > 1:
            errors.append(ValidationError(
                card_name=entry.name,
                message=f"Legendary card '{entry.name}' has {entry.count} copies (max 1)",
            ))

        # Specialization (8.3): only if hero matches
        if Keyword.SPECIALIZATION in card_def.keywords:
            # Check if the hero name appears in the card's functional text
            # This is a heuristic — full implementation needs card text parsing (Phase 5)
            hero_def = db.get_by_name(deck.hero_name)
            if hero_def is not None:
                # The specialization text typically says "Specialization ([Hero Name])"
                # Check both the hero name and the card's functional text
                hero_name_lower = deck.hero_name.lower()
                func_text_lower = card_def.functional_text.lower()
                type_text_lower = card_def.type_text.lower()
                if (
                    hero_name_lower not in func_text_lower
                    and hero_name_lower not in type_text_lower
                ):
                    errors.append(ValidationError(
                        card_name=entry.name,
                        message=(
                            f"Specialization card '{entry.name}' may not be legal "
                            f"with hero '{deck.hero_name}'"
                        ),
                    ))

    # Check weapons and equipment for Legendary
    def _check_legendary_copies(
        names: list[str], category: str,
    ) -> None:
        counts: dict[str, int] = {}
        for name in names:
            counts[name] = counts.get(name, 0) + 1
        for name, count in counts.items():
            defn = db.get_by_name(name)
            if defn and Keyword.LEGENDARY in defn.keywords and count > 1:
                errors.append(ValidationError(
                    card_name=name,
                    message=f"Legendary {category} '{name}' has {count} copies (max 1)",
                ))

    _check_legendary_copies(deck.weapons, "weapon")
    _check_legendary_copies(deck.equipment, "equipment")

    return errors
