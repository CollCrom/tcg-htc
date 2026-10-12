# Coding standards

Judgement calls for the reviewer. Anything a tool could check belongs in a check, not here.

## Use the glossary's words

Name things in code, tests and issues with the terms in `GLOSSARY.md`: List, Decklist, Deck, Game, Match, Seat, Agent, View, Intent. Don't drift to the words it marks _Avoid_, such as "pool" for a List, "action" or "move" for an Intent, "player" for a Seat, or "match" for a single Game. Where upstream's engine uses a different name (its `player` fields, its `GameIntent` type), translate at the boundary instead of letting the upstream name spread through our code.

## Test through the seams

Tests go through the public seams named in the spec, such as List loading and `runGame`, and check behaviour a caller can see. Don't test internal helpers, the shape of the Game loop or the exact wording of rendered text. If something can only be tested by reaching inside, the seam is wrong; raise it instead of working around it.

## Keep the Agent's view honest

Anything handed to an Agent must be derived from its own Seat's View, never from the full game state, even when the full state is in scope and would be convenient. This covers the rendered text, the legal Intents and anything carried between decisions.
