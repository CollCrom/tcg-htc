"""Tests for keyword tag recognition: Stealth, Contract, Legendary, Specialization.

These keywords are recognized/parsed from card data but have no generic
engine mechanic (or only deckbuilding constraints). This verifies they
are correctly parsed and accessible.
"""
from engine.cards.card import CardDefinition
from engine.cards.card_db import _parse_keywords
from engine.enums import CardType, Keyword, SubType


def test_stealth_parsed():
    """Stealth keyword is recognized from CSV data."""
    keywords, values = _parse_keywords("Stealth")
    assert Keyword.STEALTH in keywords


def test_contract_parsed():
    """Contract keyword is recognized from CSV data."""
    keywords, values = _parse_keywords("Contract")
    assert Keyword.CONTRACT in keywords


def test_legendary_parsed():
    """Legendary keyword is recognized from CSV data."""
    keywords, values = _parse_keywords("Legendary")
    assert Keyword.LEGENDARY in keywords


def test_specialization_parsed():
    """Specialization keyword is recognized from CSV data."""
    keywords, values = _parse_keywords("Specialization")
    assert Keyword.SPECIALIZATION in keywords


def test_mark_parsed():
    """Mark keyword is recognized from CSV data."""
    keywords, values = _parse_keywords("Mark")
    assert Keyword.MARK in keywords


def test_ambush_parsed():
    """Ambush keyword is recognized from CSV data."""
    keywords, values = _parse_keywords("Ambush")
    assert Keyword.AMBUSH in keywords


def test_rupture_parsed():
    """Rupture keyword is recognized from CSV data."""
    keywords, values = _parse_keywords("Rupture")
    assert Keyword.RUPTURE in keywords


def test_piercing_with_value_parsed():
    """Piercing N keyword is recognized with its numeric value."""
    keywords, values = _parse_keywords("Piercing 1")
    assert Keyword.PIERCING in keywords
    assert values[Keyword.PIERCING] == 1


def test_spellvoid_with_value_parsed():
    """Spellvoid N keyword is recognized with its numeric value."""
    keywords, values = _parse_keywords("Spellvoid 2")
    assert Keyword.SPELLVOID in keywords
    assert values[Keyword.SPELLVOID] == 2


def test_opt_with_value_parsed():
    """Opt N keyword is recognized with its numeric value."""
    keywords, values = _parse_keywords("Opt 2")
    assert Keyword.OPT in keywords
    assert values[Keyword.OPT] == 2


def test_retrieve_parsed():
    """Retrieve keyword is recognized from CSV data."""
    keywords, values = _parse_keywords("Retrieve")
    assert Keyword.RETRIEVE in keywords


def test_multiple_keywords_parsed():
    """Multiple keywords including new ones are parsed correctly."""
    keywords, values = _parse_keywords("Stealth, Piercing 1, Go again")
    assert Keyword.STEALTH in keywords
    assert Keyword.PIERCING in keywords
    assert Keyword.GO_AGAIN in keywords
    assert values[Keyword.PIERCING] == 1


def test_stealth_on_card_definition():
    """Stealth keyword is accessible on CardDefinition."""
    defn = CardDefinition(
        unique_id="test-stealth",
        name="Stealthy Attack",
        color=None,
        pitch=None,
        cost=1,
        power=3,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset(),
        keywords=frozenset({Keyword.STEALTH}),
        functional_text="",
        type_text="",
    )
    assert Keyword.STEALTH in defn.keywords
