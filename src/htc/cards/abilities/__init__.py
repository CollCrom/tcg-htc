"""Card ability implementations.

Each module registers ability handlers with the AbilityRegistry.
"""

from htc.cards.abilities.generic import register_generic_abilities
from htc.cards.abilities.assassin import register_assassin_abilities
from htc.cards.abilities.ninja import register_ninja_abilities
from htc.cards.abilities.equipment import register_equipment_abilities

__all__ = [
    "register_generic_abilities",
    "register_assassin_abilities",
    "register_ninja_abilities",
    "register_equipment_abilities",
]
