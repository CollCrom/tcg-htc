"""Tests for parameterized keyword parsing (e.g. 'Arcane Barrier 2')."""

from pathlib import Path

from htc.cards.card_db import CardDatabase, _parse_keywords
from htc.enums import Keyword
from tests.conftest import make_card

DATA_DIR = Path(__file__).parent.parent / "data"


def test_parse_keyword_with_number():
    """'Arcane Barrier 2' should parse as ARCANE_BARRIER with value 2."""
    kw, vals = _parse_keywords("Arcane Barrier 2")
    assert Keyword.ARCANE_BARRIER in kw
    assert vals[Keyword.ARCANE_BARRIER] == 2


def test_parse_keyword_without_number():
    """'Temper' should parse as TEMPER with no value."""
    kw, vals = _parse_keywords("Temper")
    assert Keyword.TEMPER in kw
    assert Keyword.TEMPER not in vals


def test_parse_multiple_keywords_mixed():
    """Multiple keywords, some with values, some without."""
    kw, vals = _parse_keywords("Ward 10, Go again, Blade Break")
    assert Keyword.WARD in kw
    assert vals[Keyword.WARD] == 10
    assert Keyword.GO_AGAIN in kw
    assert Keyword.BLADE_BREAK in kw
    assert Keyword.GO_AGAIN not in vals
    assert Keyword.BLADE_BREAK not in vals


def test_parse_empty_string():
    """Empty string should return empty sets."""
    kw, vals = _parse_keywords("")
    assert len(kw) == 0
    assert len(vals) == 0


def test_keyword_value_accessor():
    """CardDefinition.keyword_value() returns the param or default."""
    from htc.cards.card import CardDefinition
    from htc.enums import CardType, SubType

    defn = CardDefinition(
        unique_id="test-ab",
        name="Test Barrier",
        color=None,
        pitch=None,
        cost=0,
        power=None,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.EQUIPMENT}),
        subtypes=frozenset({SubType.CHEST}),
        supertypes=frozenset(),
        keywords=frozenset({Keyword.ARCANE_BARRIER}),
        functional_text="",
        type_text="",
        keyword_values={Keyword.ARCANE_BARRIER: 2},
    )
    assert defn.keyword_value(Keyword.ARCANE_BARRIER) == 2
    assert defn.keyword_value(Keyword.WARD) == 0
    assert defn.keyword_value(Keyword.WARD, default=5) == 5


def test_real_csv_arcane_barrier_values():
    """Cards loaded from CSV should have Arcane Barrier values parsed."""
    db = CardDatabase.load(DATA_DIR / "cards.csv")
    ab_cards = [c for c in db.all_cards if Keyword.ARCANE_BARRIER in c.keywords]
    assert len(ab_cards) > 0, "Should find cards with Arcane Barrier"
    for card in ab_cards:
        val = card.keyword_value(Keyword.ARCANE_BARRIER)
        assert val >= 1, f"{card.name} should have Arcane Barrier >= 1, got {val}"


def test_card_instance_keyword_values_delegation():
    """CardInstance.keyword_values should delegate to definition."""
    from htc.cards.card import CardDefinition
    from htc.cards.instance import CardInstance
    from htc.enums import CardType, Zone

    defn = CardDefinition(
        unique_id="test-ward",
        name="Test Ward",
        color=None,
        pitch=None,
        cost=0,
        power=None,
        defense=2,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.EQUIPMENT}),
        subtypes=frozenset(),
        supertypes=frozenset(),
        keywords=frozenset({Keyword.WARD}),
        functional_text="",
        type_text="",
        keyword_values={Keyword.WARD: 3},
    )
    inst = CardInstance(instance_id=1, definition=defn, owner_index=0, zone=Zone.ARMS)
    assert inst.keyword_values == {Keyword.WARD: 3}
