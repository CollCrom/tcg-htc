# Coding standards

Judgement calls for the reviewer. Anything a tool could check belongs in a check, not here.

## Use the glossary's words

Name things in code, tests and issues with the terms in `GLOSSARY.md`. `pnpm check:glossary` catches names using its _Avoid_ words, except those qualified "(for …)", which are wrong in only one sense: "match" for a single Game, "deck" for a whole List, "state" for a View. Those need your eye. Where upstream's engine uses a different name, translate at the boundary instead of letting the upstream name spread through our code; end a line with `// glossary: upstream` only where upstream forces its name, such as a field we pass to it.

## Test through the seams

Tests go through the public seams named in the spec, such as List loading and `runGame`, and check behaviour a caller can see. Don't test internal helpers, the shape of the Game loop or the exact wording of rendered text. If something can only be tested by reaching inside, the seam is wrong; raise it instead of working around it.

## Keep the Agent's view honest

Anything handed to an Agent must be derived from its own Seat's View, never from the full game state, even when the full state is in scope and would be convenient. This covers the rendered text, the legal Intents and anything carried between decisions.
