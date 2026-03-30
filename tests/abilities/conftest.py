"""Shared test card factories and helpers for ability tests.

Centralizes card construction helpers used across multiple ability test
files. Avoids duplication of CardDefinition boilerplate.
"""

from __future__ import annotations

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.abilities import AbilityContext
from htc.engine.actions import PlayerResponse
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


def make_mock_interfaces(ask_fn):
    """Create mock player interfaces that delegate to *ask_fn*.

    Returns a two-element list of mock players whose ``decide`` method
    calls ``ask_fn(decision)`` for every decision.
    """
    _MockPlayer = type("P", (), {"decide": lambda s, state, d: ask_fn(d)})
    return [_MockPlayer(), _MockPlayer()]


def make_weapon_proxy(
    weapon: CardInstance,
    instance_id: int,
    owner_index: int = 0,
) -> CardInstance:
    """Create an attack proxy for a weapon, mimicking engine behaviour."""
    defn = CardDefinition(
        unique_id=f"proxy-{weapon.definition.unique_id}",
        name=f"{weapon.name} (attack)",
        color=None,
        pitch=None,
        cost=None,
        power=weapon.definition.power,
        defense=None,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=weapon.definition.supertypes,
        keywords=weapon.definition.keywords,
        functional_text="",
        type_text="Weapon attack proxy",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
        is_proxy=True,
        proxy_source_id=weapon.instance_id,
    )


# ---------------------------------------------------------------------------
# AbilityContext construction helper
# ---------------------------------------------------------------------------


def make_ability_context(
    game,
    source_card,
    controller_index=0,
    chain_link=None,
    *,
    ask=None,
):
    """Build an AbilityContext wired to the game shell.

    If *chain_link* is not given, falls back to the active link on the
    combat chain.  If *ask* is not given, defaults to always returning
    ``["pass"]``.
    """
    return AbilityContext(
        state=game.state,
        source_card=source_card,
        controller_index=controller_index,
        chain_link=chain_link or game.state.combat_chain.active_link,
        effect_engine=game.effect_engine,
        events=game.events,
        ask=ask or (lambda d: PlayerResponse(selected_option_ids=["pass"])),
        keyword_engine=game.keyword_engine,
        combat_mgr=game.combat_mgr,
    )


def setup_draconic_chain(game, num_draconic, owner_index=0):
    """Set up a combat chain with *num_draconic* Draconic chain links.

    Returns the list of attack CardInstances added.
    """
    game.combat_mgr.open_chain(game.state)
    attacks = []
    for i in range(num_draconic):
        atk = make_draconic_ninja_attack(instance_id=i + 1, owner_index=owner_index)
        game.combat_mgr.add_chain_link(game.state, atk, 1 - owner_index)
        attacks.append(atk)
    return attacks
