# tcg-htc

A Flesh and Blood simulator in which two AI agents play complete games using tournament-style Pools, so the games can be analysed for matchup and play insights.

## Language

### Play

**Game**:
One game of Flesh and Blood between two decklists, from setup until a winner or a draw.
_Avoid_: Match (for a single game)

**Match**:
A best-of-N series of Games between the same two decklists. Rarely needed, because Flesh and Blood is usually played best-of-one.

**Seat**:
One of the two sides in a Game, numbered 0 and 1.

**Agent**:
The decision-maker occupying a Seat. It chooses an Intent from what it is shown and never sees the full game state.
_Avoid_: Bot (reserved for upstream's scripted hero bots), AI

**View**:
What one Seat is allowed to see of the game: its own hidden cards, plus everything public.
_Avoid_: State (the full, unhidden game)

**Known information**:
Hidden cards a Seat has learned the identity or position of, such as a deck top it looked at or a card the opponent revealed from hand. It belongs to the game, not to the Agent's memory.

**Plan notes**:
An Agent's own running notes on its plan and suspicions, rewritten at every decision and limited to 500 tokens. They never hold game facts; those belong in the View or Known information.
_Avoid_: Memory, memo, scratchpad

**Decision record**:
The saved account of one decision: the View the Agent was shown, the Intents it was offered, the one it chose, its reasoning, and the Plan notes it wrote.

**Intent**:
A single choice an Agent makes when it has a decision, such as playing a card, pitching, blocking or passing.
_Avoid_: Action, move

### Decks

**Pool**:
Every card a player brings to an event: hero, weapons, equipment and deck cards. In Silver Age it holds at most 55 cards. It's what a Fabrary export describes.
_Avoid_: Deck (for the whole 55)

**Decklist**:
The cards a Seat starts a Game with, chosen from a Pool: a hero, weapons and off-hands, one equipment piece per slot, and a deck of exactly 40 cards in Silver Age.
