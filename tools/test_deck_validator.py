"""Tests for deck validation: Legendary and Specialization constraints."""
from engine.cards.card import CardDefinition
from engine.cards.card_db import CardDatabase
from engine.decks.deck_list import DeckEntry, DeckList
from tools.deck_validator import validate_deck
from engine.enums import CardType, Keyword, SubType


def _make_db_with_cards(*cards: CardDefinition) -> CardDatabase:
    """Create a CardDatabase populated with the given card definitions."""
    db = CardDatabase()
    for card in cards:
        db._by_id[card.unique_id] = card
        db._by_name.setdefault(card.name, []).append(card)
    return db


def _make_defn(
    name: str,
    keywords: frozenset[Keyword] = frozenset(),
    functional_text: str = "",
    types: frozenset[CardType] = frozenset({CardType.ACTION}),
    subtypes: frozenset[SubType] = frozenset(),
) -> CardDefinition:
    return CardDefinition(
        unique_id=f"test-{name}",
        name=name,
        color=None,
        pitch=None,
        cost=1,
        power=3,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=types,
        subtypes=subtypes,
        supertypes=frozenset(),
        keywords=keywords,
        functional_text=functional_text,
        type_text="",
    )


def _make_hero_defn(name: str) -> CardDefinition:
    return CardDefinition(
        unique_id=f"hero-{name}",
        name=name,
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=None,
        health=20,
        intellect=4,
        arcane=None,
        types=frozenset({CardType.HERO}),
        subtypes=frozenset(),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )


def test_legendary_single_copy_valid():
    """Legendary card with 1 copy is valid."""
    card = _make_defn("Crown of Providence", keywords=frozenset({Keyword.LEGENDARY}))
    hero = _make_hero_defn("Bravo")
    db = _make_db_with_cards(card, hero)

    deck = DeckList(
        hero_name="Bravo",
        cards=[DeckEntry(name="Crown of Providence", count=1)],
    )
    errors = validate_deck(deck, db)
    assert len(errors) == 0


def test_legendary_multiple_copies_invalid():
    """Legendary card with >1 copy is invalid."""
    card = _make_defn("Crown of Providence", keywords=frozenset({Keyword.LEGENDARY}))
    hero = _make_hero_defn("Bravo")
    db = _make_db_with_cards(card, hero)

    deck = DeckList(
        hero_name="Bravo",
        cards=[DeckEntry(name="Crown of Providence", count=3)],
    )
    errors = validate_deck(deck, db)
    assert len(errors) == 1
    assert "Legendary" in errors[0].message


def test_non_legendary_multiple_copies_valid():
    """Non-legendary card with 3 copies is fine."""
    card = _make_defn("Pummel")
    hero = _make_hero_defn("Bravo")
    db = _make_db_with_cards(card, hero)

    deck = DeckList(
        hero_name="Bravo",
        cards=[DeckEntry(name="Pummel", count=3)],
    )
    errors = validate_deck(deck, db)
    assert len(errors) == 0


def test_specialization_matching_hero_valid():
    """Specialization card with matching hero is valid."""
    card = _make_defn(
        "Cindra's Fury",
        keywords=frozenset({Keyword.SPECIALIZATION}),
        functional_text="Specialization (Cindra)",
    )
    hero = _make_hero_defn("Cindra")
    db = _make_db_with_cards(card, hero)

    deck = DeckList(
        hero_name="Cindra",
        cards=[DeckEntry(name="Cindra's Fury", count=3)],
    )
    errors = validate_deck(deck, db)
    assert len(errors) == 0


def test_specialization_wrong_hero_flagged():
    """Specialization card with non-matching hero is flagged."""
    card = _make_defn(
        "Cindra's Fury",
        keywords=frozenset({Keyword.SPECIALIZATION}),
        functional_text="Specialization (Cindra)",
    )
    hero = _make_hero_defn("Bravo")
    db = _make_db_with_cards(card, hero)

    deck = DeckList(
        hero_name="Bravo",
        cards=[DeckEntry(name="Cindra's Fury", count=3)],
    )
    errors = validate_deck(deck, db)
    assert len(errors) == 1
    assert "Specialization" in errors[0].message


def test_legendary_weapon():
    """Legendary weapon with duplicate is flagged."""
    weapon = _make_defn(
        "Dawnblade",
        keywords=frozenset({Keyword.LEGENDARY}),
        types=frozenset({CardType.WEAPON}),
        subtypes=frozenset({SubType.SWORD}),
    )
    hero = _make_hero_defn("Dorinthea")
    db = _make_db_with_cards(weapon, hero)

    deck = DeckList(
        hero_name="Dorinthea",
        weapons=["Dawnblade", "Dawnblade"],
    )
    errors = validate_deck(deck, db)
    assert len(errors) == 1
    assert "weapon" in errors[0].message.lower()


def test_legendary_equipment():
    """Legendary equipment with duplicate is flagged."""
    equip = _make_defn(
        "Crown of Providence",
        keywords=frozenset({Keyword.LEGENDARY}),
        types=frozenset({CardType.EQUIPMENT}),
        subtypes=frozenset({SubType.HEAD}),
    )
    hero = _make_hero_defn("Bravo")
    db = _make_db_with_cards(equip, hero)

    deck = DeckList(
        hero_name="Bravo",
        equipment=["Crown of Providence", "Crown of Providence"],
    )
    errors = validate_deck(deck, db)
    assert len(errors) == 1
    assert "equipment" in errors[0].message.lower()
