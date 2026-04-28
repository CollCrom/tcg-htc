"""Run a sample game with full logging output."""
import logging
from pathlib import Path

from engine._demo_deck import BRAVO_DECK_TEXT
from engine.cards.card_db import CardDatabase
from engine.decks.loader import parse_deck_list
from engine.rules.game import Game
from engine.player.random_player import RandomPlayer

DATA_DIR = Path(__file__).parent.parent / "data"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    db = CardDatabase.load(DATA_DIR / "cards.tsv")
    deck1 = parse_deck_list(BRAVO_DECK_TEXT)
    deck2 = parse_deck_list(BRAVO_DECK_TEXT)

    p1 = RandomPlayer(seed=42)
    p2 = RandomPlayer(seed=123)

    game = Game(db, deck1, deck2, p1, p2, seed=7)
    result = game.play()

    print(f"\n--- Game Over ---")
    print(f"Winner: Player {result.winner}")
    print(f"Turns: {result.turns}")
    print(f"Final life: P0={result.final_life[0]}, P1={result.final_life[1]}")


if __name__ == "__main__":
    main()
