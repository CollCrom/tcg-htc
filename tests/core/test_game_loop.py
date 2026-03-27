"""Test a full game between two random players with simple warrior decks."""
import logging

from htc.cards.card_db import CardDatabase
from htc.decks.loader import parse_deck_list

from tests.conftest import DATA_DIR, WARRIOR_DECK, run_game


def test_game_completes():
    result = run_game()

    assert result.winner is not None or result.turns >= 200
    assert result.turns > 0


def test_card_loading():
    db = CardDatabase.load(DATA_DIR / "cards.csv")
    assert len(db) > 4000

    bravo = db.get_by_name("Bravo, Showstopper")
    assert bravo is not None
    assert bravo.is_hero
    assert bravo.health == 40


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_card_loading()
    print("Card loading: OK")
    test_game_completes()
    print("Game loop: OK")
