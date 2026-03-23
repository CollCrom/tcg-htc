# The Elephant Method

**Source:** https://articles.starcitygames.com/articles/the-elephant-method-a-case-study/
**Author:** Zvi Mowshowitz (Pro Tour Hall of Famer)
**Context:** Written about MTG but the framework is format-agnostic.

## Core Idea

Build your deck from the 75 outward, not from the 60 inward. Instead of building a maindeck and filling sideboard slots, write the ideal post-sideboard configuration for every relevant matchup, then reverse-engineer which cards go main and which go side.

## Methodology

1. **List every relevant matchup** in your expected metagame.
2. **For each matchup, write the ideal post-sideboard decklist.** Must be realistic — account for what opponents will also sideboard into, not just their Game 1 configuration.
3. **Start greedy.** List more cards than you can fit. Better to have too many candidates than miss something.
4. **Identify core cards** that appear across multiple matchup configurations — these are maindeck staples.
5. **Resolve conflicts.** When total unique cards exceed your card pool limit, make trade-offs based on metagame weight or find flexible double-duty cards.
6. **Enforce the card pool constraint.** The unique cards across all matchup lists must fit exactly. Forces you to confront every marginal inclusion.
7. **Extract the maindeck.** Select the cards that give the best Game 1 across the field. The rest become the sideboard.

## Key Principles

- **Post-sideboard decks are the real decks.** Most matches are decided in Games 2 and 3.
- **The "Do Not Want" count matters.** For each matchup, count how many cards are dead after sideboarding. If you have more dead cards than sideboard slots, you have a structural problem.
- **One more solid card is a bigger upgrade than it appears.** The marginal sideboard slot matters more than people think.
- **Beware the "romantic mistake."** Plan against the opponent's realistic post-sideboard configuration, not their pure Game 1.
- **Late changes are dangerous.** Last-minute swaps can break the constraint math.
- **Metagame prediction is the dependency.** The method is only as good as your matchup predictions.

## Application to FaB

- FaB CC uses 80-card pools (60 deck + equipment/weapons) with inventory sideboarding.
- The core insight — build from matchup configurations inward — applies directly.
- For each hero matchup, write the ideal 60 + equipment you would register if you knew that was your only opponent. Then find the single configuration that best approximates all of them.
- The "Do Not Want" discipline maps directly: how many cards are effectively blank against a given hero?
