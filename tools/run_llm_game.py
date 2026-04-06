"""Run a game with the LLM player vs a RandomPlayer.

Usage:
    ANTHROPIC_API_KEY=... .venv/bin/python -m tools.run_llm_game [--seed N] [--llm-hero cindra|arakni]

The LLM player plays the first hero (default: Cindra Blue).
The RandomPlayer plays the second hero (default: Arakni).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from htc.cards.card_db import CardDatabase
from htc.engine.game import Game
from htc.player.llm_player import LLMPlayer
from htc.player.random_player import RandomPlayer

# Reuse the test helper for parsing markdown decklists
sys.path.insert(0, str(Path(__file__).parent.parent / "tests"))
from integration.test_full_game import parse_markdown_decklist

DATA_DIR = Path(__file__).parent.parent / "data"
REF_DIR = Path(__file__).parent.parent / "ref"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LLM player vs RandomPlayer")
    parser.add_argument("--seed", type=int, default=42, help="Game seed")
    parser.add_argument(
        "--llm-hero",
        choices=["cindra", "arakni"],
        default="cindra",
        help="Which hero the LLM plays (default: cindra)",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Claude model for the LLM player",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show LLM reasoning")
    args = parser.parse_args()

    # Logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")
    # Quiet down noisy loggers unless verbose
    if not args.verbose:
        logging.getLogger("htc.engine").setLevel(logging.WARNING)
        logging.getLogger("htc.player.llm_player").setLevel(logging.INFO)
        logging.getLogger("httpx").setLevel(logging.WARNING)

    # Load card database
    db = CardDatabase.load(DATA_DIR / "cards.tsv")

    # Load decklists
    cindra_text = (REF_DIR / "decklist-cindra-blue.md").read_text()
    arakni_text = (REF_DIR / "decklist-arakni.md").read_text()
    cindra_deck = parse_markdown_decklist(cindra_text)
    arakni_deck = parse_markdown_decklist(arakni_text)

    # Set up players
    if args.llm_hero == "cindra":
        llm_player = LLMPlayer(model=args.model, hero_name="Cindra, Dracai of Retribution")
        random_player = RandomPlayer(seed=args.seed + 1)
        deck1, deck2 = cindra_deck, arakni_deck
        hero1, hero2 = "Cindra (LLM)", "Arakni (Random)"
    else:
        llm_player = LLMPlayer(model=args.model, hero_name="Arakni, Marionette")
        random_player = RandomPlayer(seed=args.seed + 1)
        deck1, deck2 = arakni_deck, cindra_deck
        hero1, hero2 = "Arakni (LLM)", "Cindra (Random)"

    print(f"\n{'='*60}")
    print(f"  {hero1}  vs  {hero2}")
    print(f"  Seed: {args.seed} | Model: {args.model}")
    print(f"{'='*60}\n")

    # Run game
    game = Game(db, deck1, deck2, llm_player, random_player, seed=args.seed)
    result = game.play()

    # Print result
    print(f"\n{'='*60}")
    if result.winner is not None:
        winner_name = hero1 if result.winner == 0 else hero2
        print(f"  Winner: {winner_name}")
    else:
        print("  Result: Draw")
    print(f"  Turns: {result.turns}")
    print(f"  Final life: {hero1} {result.final_life[0]} | {hero2} {result.final_life[1]}")
    print(f"  LLM decisions: {len(llm_player.transcript)}")
    print(f"{'='*60}\n")

    # Post-game analysis
    print("Running post-game analysis...")
    try:
        from htc.player.analyst import analyze_game

        analysis = analyze_game(
            transcript=llm_player.transcript,
            winner=result.winner,
            my_index=0,
            my_hero=hero1.split(" (")[0],
            opp_hero=hero2.split(" (")[0],
            my_life=result.final_life[0],
            opp_life=result.final_life[1],
            my_deck_size=len(game.state.players[0].deck),
            opp_deck_size=len(game.state.players[1].deck),
            total_turns=result.turns,
            model=args.model,
        )
        print("\n--- Post-Game Analysis ---")
        print(analysis)
        print("\n(Analysis also written to memory/playtester.md)")
    except Exception as e:
        print(f"Analysis failed: {e}")


if __name__ == "__main__":
    main()
