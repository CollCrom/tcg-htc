"""Tests for inherent vs conditional keyword parsing in card_db.py."""

from __future__ import annotations

import pytest

from htc.cards.card_db import _is_keyword_inherent, _parse_keywords
from htc.enums import Keyword


# ---------------------------------------------------------------------------
# _is_keyword_inherent — unit tests
# ---------------------------------------------------------------------------


class TestIsKeywordInherent:
    """Test the heuristic that distinguishes inherent from conditional keywords."""

    def test_standalone_go_again(self):
        """**Go again** on its own line is inherent (e.g. Surging Strike)."""
        assert _is_keyword_inherent(Keyword.GO_AGAIN, "**Go again**") is True

    def test_conditional_gets_go_again(self):
        """'this gets **go again**' is conditional (e.g. Enflame)."""
        text = (
            "When this attacks, if you control 2 or more Draconic chain links, "
            "this gets **go again**, 3 or more, your attacks are Draconic "
            "this combat chain, 4 or more, this gets +2{p}."
        )
        assert _is_keyword_inherent(Keyword.GO_AGAIN, text) is False

    def test_conditional_gains_dominate(self):
        """'gains **dominate**' is conditional (e.g. Consuming Aftermath)."""
        text = (
            "As an additional cost to play Consuming Aftermath, you may banish "
            "a card from your hand. If a Shadow card is banished this way, "
            "Consuming Aftermath gains **dominate**."
        )
        assert _is_keyword_inherent(Keyword.DOMINATE, text) is False

    def test_standalone_dominate_multiline(self):
        """**Dominate** at start of multiline text is inherent (e.g. Herald of Erudition)."""
        text = (
            "**Dominate**\n\n"
            "If Herald of Erudition hits, put it into your hero's soul "
            "and draw 2 cards.\n\n"
            "**Phantasm**"
        )
        assert _is_keyword_inherent(Keyword.DOMINATE, text) is True
        assert _is_keyword_inherent(Keyword.PHANTASM, text) is True

    def test_combo_at_start_of_ability(self):
        """**Combo** starting ability text is inherent (e.g. Aspect of Tiger)."""
        text = (
            "**Combo** - When this attacks, if a red attack action card was "
            "the last attack this combat chain, this gets **go again** and "
            "create a Crouching Tiger in your banished zone."
        )
        assert _is_keyword_inherent(Keyword.COMBO, text) is True
        # Go Again in the same text is conditional (preceded by "gets")
        assert _is_keyword_inherent(Keyword.GO_AGAIN, text) is False

    def test_standalone_arcane_barrier_with_number(self):
        """**Arcane Barrier 1** standalone is inherent (e.g. Aether Ashwing)."""
        assert _is_keyword_inherent(Keyword.ARCANE_BARRIER, "**Arcane Barrier 1**") is True

    def test_standalone_ward_with_number(self):
        """**Ward 10** at end of multiline text is inherent."""
        text = (
            "You may remove three +1{p} counters from among auras you control "
            "rather than pay 10,000 Year Reunion's {r} cost.\n\n"
            "**Ward 10**"
        )
        assert _is_keyword_inherent(Keyword.WARD, text) is True

    def test_conditional_if_gets_go_again(self):
        """'If ... this gets **go again**' is conditional (e.g. Aggressive Pounce)."""
        text = "If you've intimidated an opponent this turn, this gets **go again**."
        assert _is_keyword_inherent(Keyword.GO_AGAIN, text) is False

    def test_no_bold_keyword_in_text_trusts_data(self):
        """If keyword doesn't appear bold in text, trust card_keywords."""
        # Hero cards often have keywords like Contract without bold text
        text = "Some ability text with no bold keywords."
        assert _is_keyword_inherent(Keyword.CONTRACT, text) is True

    def test_empty_text_trusts_data(self):
        """Empty functional text means trust card_keywords."""
        assert _is_keyword_inherent(Keyword.GO_AGAIN, "") is True

    def test_both_inherent_and_conditional_occurrences(self):
        """If keyword appears both standalone and conditionally, it's inherent."""
        text = (
            "**Go again**\n\n"
            "At the start of your turn, destroy this, then your dagger "
            "attacks get **go again** this turn."
        )
        assert _is_keyword_inherent(Keyword.GO_AGAIN, text) is True

    def test_stalkers_steps_arcane_barrier_inherent(self):
        """Stalker's Steps: **Arcane Barrier 1** on its own line is inherent."""
        text = (
            "**Attack Reaction** - Destroy this: Target attack with stealth "
            "gets **go again**\n\n"
            "**Arcane Barrier 1**"
        )
        assert _is_keyword_inherent(Keyword.ARCANE_BARRIER, text) is True

    def test_stalkers_steps_go_again_conditional(self):
        """Stalker's Steps: 'gets **go again**' is conditional."""
        text = (
            "**Attack Reaction** - Destroy this: Target attack with stealth "
            "gets **go again**\n\n"
            "**Arcane Barrier 1**"
        )
        # Go Again is NOT a keyword on Stalker's Steps in the data, but if it
        # were, the parsing would correctly identify it as conditional.
        assert _is_keyword_inherent(Keyword.GO_AGAIN, text) is False

    def test_combo_with_conditional_dominate(self):
        """Break Tide: Combo is inherent, Dominate is conditional."""
        text = (
            '**Combo** - If Rushing River or Flood of Force was the last '
            'attack this combat chain, Break Tide gains +3{p}, **dominate**, '
            'and "If Break Tide hits, banish the top card of your deck."'
        )
        assert _is_keyword_inherent(Keyword.COMBO, text) is True
        assert _is_keyword_inherent(Keyword.DOMINATE, text) is False

    # -- Bug fix: "with" prefix was too broad (Bug 1) -------------------

    def test_with_prefix_not_conditional(self):
        """'attack with X, **intimidate**' — 'with' is not a keyword-granting verb."""
        text = (
            "**Rhinar Specialization**\n\n"
            "As an additional cost to play Alpha Rampage, discard a random card.\n\n"
            "When you attack with Alpha Rampage, **intimidate**."
        )
        assert _is_keyword_inherent(Keyword.INTIMIDATE, text) is True

    def test_attack_with_does_not_strip_keyword(self):
        """Generic pattern: 'When you attack with <name>, **keyword**' is inherent."""
        text = "When you attack with Wrecking Ball, **intimidate**."
        assert _is_keyword_inherent(Keyword.INTIMIDATE, text) is True

    # -- Bug fix: sentence-level context instead of line-level (Bug 2) --

    def test_gets_in_earlier_clause_does_not_strip_later_keyword(self):
        """'...gets +1{p}. **Go again**' — Go Again is a new sentence, inherent."""
        text = (
            "The next attack action card you play this turn gets +1{p}. "
            "**Go again**"
        )
        assert _is_keyword_inherent(Keyword.GO_AGAIN, text) is True

    def test_gets_same_sentence_still_conditional(self):
        """'this gets **go again**' in the same sentence is still conditional."""
        text = "This gets **go again**."
        assert _is_keyword_inherent(Keyword.GO_AGAIN, text) is False

    def test_multi_clause_line_with_keyword_at_end(self):
        """Multiple sentences on one line; keyword at end after period boundary."""
        text = "Draw a card. Create a token. **Dominate**"
        assert _is_keyword_inherent(Keyword.DOMINATE, text) is True

    def test_gains_in_prior_sentence_does_not_strip(self):
        """'gains X. **Keyword**' — keyword is in a new sentence, inherent."""
        text = "This gains +2{p}. **Go again**"
        assert _is_keyword_inherent(Keyword.GO_AGAIN, text) is True


# ---------------------------------------------------------------------------
# _parse_keywords — integration with functional_text filtering
# ---------------------------------------------------------------------------


class TestParseKeywordsWithText:
    """Test that _parse_keywords filters conditional keywords using text."""

    def test_surging_strike_keeps_go_again(self):
        keywords, values = _parse_keywords("Go again", "**Go again**")
        assert Keyword.GO_AGAIN in keywords

    def test_enflame_removes_go_again(self):
        text = (
            "When this attacks, if you control 2 or more Draconic chain links, "
            "this gets **go again**, 3 or more, your attacks are Draconic "
            "this combat chain, 4 or more, this gets +2{p}."
        )
        keywords, values = _parse_keywords("Go again", text)
        assert Keyword.GO_AGAIN not in keywords

    def test_aggressive_pounce_removes_go_again(self):
        text = "If you've intimidated an opponent this turn, this gets **go again**."
        keywords, values = _parse_keywords("Go again", text)
        assert Keyword.GO_AGAIN not in keywords

    def test_arcane_barrier_with_value_preserved(self):
        keywords, values = _parse_keywords("Arcane Barrier 1", "**Arcane Barrier 1**")
        assert Keyword.ARCANE_BARRIER in keywords
        assert values[Keyword.ARCANE_BARRIER] == 1

    def test_ward_with_value_preserved(self):
        text = "Some text.\n\n**Ward 10**"
        keywords, values = _parse_keywords("Ward 10", text)
        assert Keyword.WARD in keywords
        assert values[Keyword.WARD] == 10

    def test_conditional_keyword_value_also_removed(self):
        """If a parameterized keyword is conditional, its value is also dropped."""
        # Hypothetical: if a card had "Ward 5" as conditional
        text = "This gains **Ward 5**."
        keywords, values = _parse_keywords("Ward 5", text)
        # "This gains" triggers the conditional prefix
        assert Keyword.WARD not in keywords
        assert Keyword.WARD not in values

    def test_multiple_keywords_mixed(self):
        """Combo + Dominate where Combo is inherent, Dominate conditional."""
        text = (
            '**Combo** - If Rushing River or Flood of Force was the last '
            'attack this combat chain, Break Tide gains +3{p}, **dominate**.'
        )
        keywords, values = _parse_keywords("Combo, Dominate", text)
        assert Keyword.COMBO in keywords
        assert Keyword.DOMINATE not in keywords

    def test_no_functional_text_keeps_all(self):
        """With empty text, all keywords are kept."""
        keywords, values = _parse_keywords("Go again, Combo", "")
        assert Keyword.GO_AGAIN in keywords
        assert Keyword.COMBO in keywords


# ---------------------------------------------------------------------------
# Real card data integration — load from TSV and verify
# ---------------------------------------------------------------------------


class TestRealCardKeywords:
    """Verify keyword parsing against real Fabrary dataset."""

    @pytest.fixture(scope="class")
    def db(self):
        from htc.cards.card_db import CardDatabase
        return CardDatabase.load("data/cards.tsv")

    def test_enflame_no_inherent_go_again(self, db):
        card = db.get_by_name("Enflame the Firebrand")
        assert card is not None
        assert Keyword.GO_AGAIN not in card.keywords

    def test_surging_strike_has_go_again(self, db):
        from htc.enums import Color
        card = db.get_by_name("Surging Strike", Color.RED)
        assert card is not None
        assert Keyword.GO_AGAIN in card.keywords

    def test_aggressive_pounce_no_inherent_go_again(self, db):
        card = db.get_by_name("Aggressive Pounce")
        assert card is not None
        assert Keyword.GO_AGAIN not in card.keywords

    def test_stalkers_steps_has_arcane_barrier(self, db):
        card = db.get_by_name("Stalker's Steps")
        assert card is not None
        assert Keyword.ARCANE_BARRIER in card.keywords
        assert card.keyword_values.get(Keyword.ARCANE_BARRIER) == 1

    def test_aspect_of_tiger_combo_not_go_again(self, db):
        card = db.get_by_name("Aspect of Tiger: Body")
        assert card is not None
        assert Keyword.COMBO in card.keywords
        assert Keyword.GO_AGAIN not in card.keywords

    def test_herald_of_erudition_dominate_and_phantasm(self, db):
        card = db.get_by_name("Herald of Erudition")
        assert card is not None
        assert Keyword.DOMINATE in card.keywords
        assert Keyword.PHANTASM in card.keywords

    def test_consuming_aftermath_no_inherent_dominate(self, db):
        card = db.get_by_name("Consuming Aftermath")
        assert card is not None
        assert Keyword.DOMINATE not in card.keywords

    def test_ward_10_inherent(self, db):
        card = db.get_by_name("10,000 Year Reunion")
        assert card is not None
        assert Keyword.WARD in card.keywords
        assert card.keyword_values.get(Keyword.WARD) == 10

    def test_break_tide_combo_not_dominate(self, db):
        card = db.get_by_name("Break Tide")
        assert card is not None
        assert Keyword.COMBO in card.keywords
        assert Keyword.DOMINATE not in card.keywords

    # -- Bug fix verifications: "with" prefix (Bug 1) ------------------

    def test_alpha_rampage_has_intimidate(self, db):
        """Alpha Rampage: 'attack with X, **intimidate**' — Intimidate is inherent."""
        from htc.enums import Color
        card = db.get_by_name("Alpha Rampage", Color.RED)
        assert card is not None
        assert Keyword.INTIMIDATE in card.keywords

    # -- Bug fix verifications: sentence-level context (Bug 2) ----------

    def test_anthem_of_spring_has_go_again(self, db):
        """Anthem of Spring: 'gets +1{p}. **Go again**' — Go Again is inherent."""
        card = db.get_by_name("Anthem of Spring")
        assert card is not None
        assert Keyword.GO_AGAIN in card.keywords
