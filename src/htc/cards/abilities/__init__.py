"""Card ability implementations.

Each module registers ability handlers with the AbilityRegistry.
"""

from htc.cards.abilities.generic import register_generic_abilities

__all__ = ["register_generic_abilities"]
