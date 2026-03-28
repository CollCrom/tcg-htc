"""Shared test card factories for ability tests.

Centralizes card construction helpers used across multiple ability test
files. Avoids duplication of CardDefinition boilerplate.
"""

from __future__ import annotations

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.enums import (
    CardType,
    Color,
    Keyword,
    SubType,
    SuperType,
    Zone,
)


def make_dagger_attack(
    instance_id: int = 1,
    power: int = 3,
    cost: int = 0,
    owner_index: int = 0,
    name: str = "Dagger Strike",
    keywords: frozenset = frozenset(),
    supertypes: frozenset | None = None,
) -> CardInstance:
    """Create a dagger attack action card for testing."""
    if supertypes is None:
        supertypes = frozenset({SuperType.ASSASSIN})
    defn = CardDefinition(
        unique_id=f"dagger-{instance_id}",
        name=name,
        color=Color.RED,
        pitch=1,
        cost=cost,
        power=power,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK, SubType.DAGGER}),
        supertypes=supertypes,
        keywords=keywords,
        functional_text="",
        type_text="Assassin Dagger Attack Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
    )


def make_stealth_attack(
    instance_id: int = 1,
    power: int = 3,
    cost: int = 0,
    owner_index: int = 0,
    name: str = "Stealth Strike",
    supertypes: frozenset | None = None,
) -> CardInstance:
    """Create an attack action card with Stealth for testing."""
    if supertypes is None:
        supertypes = frozenset({SuperType.ASSASSIN})
    defn = CardDefinition(
        unique_id=f"stealth-{instance_id}",
        name=name,
        color=Color.RED,
        pitch=1,
        cost=cost,
        power=power,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=supertypes,
        keywords=frozenset({Keyword.STEALTH}),
        functional_text="",
        type_text="Assassin Attack Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
    )


def make_ninja_attack(
    instance_id: int = 1,
    name: str = "Ninja Strike",
    *,
    power: int = 4,
    cost: int = 1,
    owner_index: int = 0,
    supertypes: frozenset | None = None,
    keywords: frozenset = frozenset(),
) -> CardInstance:
    """Create a Ninja attack action card for testing."""
    if supertypes is None:
        supertypes = frozenset({SuperType.NINJA})
    defn = CardDefinition(
        unique_id=f"ninja-{instance_id}",
        name=name,
        color=Color.RED,
        pitch=1,
        cost=cost,
        power=power,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=supertypes,
        keywords=keywords,
        functional_text="",
        type_text="Ninja Attack Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
    )


def make_attack_reaction(
    name: str = "Attack Reaction",
    instance_id: int = 10,
    color: Color = Color.RED,
    defense: int = 3,
    owner_index: int = 0,
    cost: int = 0,
    supertypes: frozenset | None = None,
    pitch: int = 1,
) -> CardInstance:
    """Create an attack reaction card for testing."""
    if supertypes is None:
        supertypes = frozenset()
    defn = CardDefinition(
        unique_id=f"ar-{instance_id}",
        name=name,
        color=color,
        pitch=pitch,
        cost=cost,
        power=None,
        defense=defense,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ATTACK_REACTION}),
        subtypes=frozenset(),
        supertypes=supertypes,
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HAND,
    )


def make_defense_reaction(
    name: str = "Defense Reaction",
    instance_id: int = 20,
    color: Color = Color.RED,
    defense: int = 4,
    owner_index: int = 1,
    keywords: frozenset | None = None,
    keyword_values: dict | None = None,
    subtypes: frozenset | None = None,
    supertypes: frozenset | None = None,
) -> CardInstance:
    """Create a defense reaction card for testing."""
    defn = CardDefinition(
        unique_id=f"dr-{instance_id}",
        name=name,
        color=color,
        pitch=1,
        cost=0,
        power=None,
        defense=defense,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.DEFENSE_REACTION}),
        subtypes=subtypes or frozenset(),
        supertypes=supertypes or frozenset(),
        keywords=keywords or frozenset(),
        functional_text="",
        type_text="",
        keyword_values=keyword_values or {},
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HAND,
    )


def make_non_attack_action(
    name: str,
    instance_id: int = 30,
    color: Color = Color.RED,
    owner_index: int = 0,
    supertypes: frozenset | None = None,
    keywords: frozenset | None = None,
) -> CardInstance:
    """Create a non-attack action card for testing."""
    defn = CardDefinition(
        unique_id=f"naa-{instance_id}",
        name=name,
        color=color,
        pitch=1,
        cost=0,
        power=None,
        defense=2,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset(),
        supertypes=supertypes or frozenset({SuperType.ASSASSIN}),
        keywords=keywords if keywords is not None else frozenset({Keyword.GO_AGAIN}),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HAND,
    )


def make_draconic_ninja_attack(
    instance_id: int = 1,
    name: str = "Draconic Ninja Strike",
    *,
    power: int = 4,
    cost: int = 1,
    owner_index: int = 0,
    keywords: frozenset = frozenset(),
) -> CardInstance:
    """Create a Draconic Ninja attack action card."""
    defn = CardDefinition(
        unique_id=f"draconic-ninja-{instance_id}",
        name=name,
        color=Color.RED,
        pitch=1,
        cost=cost,
        power=power,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.NINJA, SuperType.DRACONIC}),
        keywords=keywords,
        functional_text="",
        type_text="Draconic Ninja Attack Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
    )


def make_draconic_attack(
    instance_id: int = 1,
    name: str = "Draconic Strike",
    *,
    power: int = 4,
    cost: int = 1,
    owner_index: int = 0,
    keywords: frozenset = frozenset(),
) -> CardInstance:
    """Create a Draconic attack action card."""
    defn = CardDefinition(
        unique_id=f"draconic-{instance_id}",
        name=name,
        color=Color.RED,
        pitch=1,
        cost=cost,
        power=power,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.DRACONIC}),
        keywords=keywords,
        functional_text="",
        type_text="Draconic Attack Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
    )


def make_dagger_weapon(
    instance_id: int = 100,
    name: str = "Kunai of Retribution",
    owner_index: int = 0,
) -> CardInstance:
    """Create a dagger weapon."""
    defn = CardDefinition(
        unique_id=f"dagger-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=0,
        power=1,
        defense=None,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.WEAPON}),
        subtypes=frozenset({SubType.DAGGER, SubType.ONE_HAND}),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="",
        type_text="Weapon - Dagger (1H)",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.WEAPON_1,
    )
