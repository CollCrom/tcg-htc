"""Run a game with the LLM player vs a RandomPlayer or another LLM.

Usage:
    ANTHROPIC_API_KEY=... .venv/bin/python -m tools.run_llm_game [--seed N] [--llm-hero cindra|arakni]
    ANTHROPIC_API_KEY=... .venv/bin/python -m tools.run_llm_game --llm-vs-llm [--seed N]

The LLM player plays the first hero (default: Cindra Blue).
The RandomPlayer (or second LLM) plays the second hero (default: Arakni).
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from htc.cards.card_db import CardDatabase
from htc.decks.deck_list import parse_markdown_decklist
from htc.engine.game import Game
from htc.player.api_client import DEFAULT_MODEL
from htc.player.llm_player import LLMPlayer
from htc.player.random_player import RandomPlayer

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
        default=DEFAULT_MODEL,
        help="Claude model for the LLM player",
    )
    parser.add_argument("--no-reasoning", action="store_true",
                        help="Disable reasoning in LLM output (saves ~30-40%% output tokens)")
    parser.add_argument("--llm-vs-llm", action="store_true",
                        help="Both players are LLM-powered (2x API cost)")
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
    reasoning = not args.no_reasoning
    if args.llm_vs_llm:
        player1 = LLMPlayer(model=args.model, hero_name="Cindra, Dracai of Retribution",
                             reasoning=reasoning)
        player2 = LLMPlayer(model=args.model, hero_name="Arakni, Marionette",
                             reasoning=reasoning)
        deck1, deck2 = cindra_deck, arakni_deck
        hero1, hero2 = "Cindra (LLM)", "Arakni (LLM)"
    elif args.llm_hero == "cindra":
        player1 = LLMPlayer(model=args.model, hero_name="Cindra, Dracai of Retribution",
                             reasoning=reasoning)
        player2 = RandomPlayer(seed=args.seed + 1)
        deck1, deck2 = cindra_deck, arakni_deck
        hero1, hero2 = "Cindra (LLM)", "Arakni (Random)"
    else:
        player1 = LLMPlayer(model=args.model, hero_name="Arakni, Marionette",
                             reasoning=reasoning)
        player2 = RandomPlayer(seed=args.seed + 1)
        deck1, deck2 = arakni_deck, cindra_deck
        hero1, hero2 = "Arakni (LLM)", "Cindra (Random)"

    print(f"\n{'='*60}")
    print(f"  {hero1}  vs  {hero2}")
    print(f"  Seed: {args.seed} | Model: {args.model}")
    print(f"{'='*60}\n")

    # Run game
    game = Game(db, deck1, deck2, player1, player2, seed=args.seed)
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
    p1_decisions = len(player1.transcript) if hasattr(player1, "transcript") else 0
    p2_decisions = len(player2.transcript) if hasattr(player2, "transcript") else 0
    print(f"  LLM decisions: {hero1} {p1_decisions} | {hero2} {p2_decisions}")
    print(f"{'='*60}\n")

    # Post-game analysis for each LLM player
    from htc.player.analyst import analyze_game

    for idx, (player, hero, opp_hero) in enumerate([
        (player1, hero1, hero2),
        (player2, hero2, hero1),
    ]):
        if not hasattr(player, "transcript"):
            continue
        print(f"Running post-game analysis for {hero}...")
        try:
            analysis = analyze_game(
                transcript=player.transcript,
                winner=result.winner,
                my_index=idx,
                my_hero=hero.split(" (")[0],
                opp_hero=opp_hero.split(" (")[0],
                my_life=result.final_life[idx],
                opp_life=result.final_life[1 - idx],
                my_deck_size=len(game.state.players[idx].deck),
                opp_deck_size=len(game.state.players[1 - idx].deck),
                total_turns=result.turns,
                model=args.model,
            )
            print(f"\n--- Post-Game Analysis ({hero}) ---")
            print(analysis)
            print("\n(Analysis also written to memory/playtester.md)")
        except Exception as e:
            print(f"Analysis failed for {hero}: {e}")


if __name__ == "__main__":
    main()
