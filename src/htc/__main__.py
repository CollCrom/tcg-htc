"""Run a sample game with full logging output."""
import logging
from pathlib import Path

from htc.cards.card_db import CardDatabase
from htc.decks.loader import parse_deck_list
from htc.engine.game import Game
from htc.player.random_player import RandomPlayer

DATA_DIR = Path(__file__).parent.parent.parent / "data"

WARRIOR_DECK = """\
Hero: Bravo, Showstopper
Weapons: Anothos
Equipment: Crater Fist, Helm of Isen's Peak, Tectonic Plating, Ironrot Legs
---
3x Adrenaline Rush (Red)
3x Adrenaline Rush (Yellow)
3x Adrenaline Rush (Blue)
3x Debilitate (Red)
3x Debilitate (Yellow)
3x Debilitate (Blue)
3x Pummel (Red)
3x Pummel (Yellow)
3x Pummel (Blue)
3x Cartilage Crush (Red)
3x Cartilage Crush (Yellow)
3x Cartilage Crush (Blue)
3x Disable (Red)
3x Disable (Yellow)
3x Disable (Blue)
3x Sink Below (Red)
3x Sink Below (Yellow)
3x Sink Below (Blue)
3x Sigil of Solace (Red)
3x Sigil of Solace (Blue)
"""


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    db = CardDatabase.load(DATA_DIR / "cards.csv")
    deck1 = parse_deck_list(WARRIOR_DECK)
    deck2 = parse_deck_list(WARRIOR_DECK)

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
