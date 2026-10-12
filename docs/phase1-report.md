# Phase 1 report: headless runner on fyendal's engine

Spec #115, ticket #122. Verdict: **pass**. All 100 Games ended in a win, and every replay reproduced exactly.

## Setup

- **Engine:** fyendal.net at upstream commit `22e9ed8b952efaa746ce4f0f8d5c975a703ab683`, vendored at `vendor/fyendal.net`.
- **Lists:** `packages/runner/lists/ira-crimson-haze.txt` (Ira, Crimson Haze) and `packages/runner/lists/bravo-flattering-showman.txt` (Bravo, Flattering Showman), both Silver Age.
- **Seeds:** 1 to 50. Each seed is used for its Game and, through `pickDecklist(list, seed)`, for both Decklists.
- **Seat orders:** each seed is played twice, once with Ira in Seat 0 and once with Bravo in Seat 0. Seat 0 starts every Game, so each List goes first once per seed. That makes 100 Games.
- **Agents:** the seeded random Agent in both Seats. It never concedes or offers a draw.
- **Replay check:** each Game's replay is played from a fresh Game with `replayGame`, and its final replay projection is compared with the original's.
- **Command:** `pnpm suite`, run on Node 24.21.0 in WSL with 16 cores. The suite is single-threaded.

## Results

| Outcome | Games |
| --- | --- |
| Win | 100 (Ira 30, Bravo 70) |
| Draw | 0 |
| Stall | 0 |
| Error | 0 |

Throughput: **1.56 Games per second** (64.2 s spent playing, replays excluded).

| Measurement | Average | Maximum |
| --- | --- | --- |
| Decisions per Game | 249.8 | 452 |
| Turns per Game | 13.2 | 22 |
| Intents per decision (raw) | 4.6 | 41 |
| Intents per decision (reordering removed) | 4.5 | 32 |
| Tokens per decision (characters ÷ 4) | 487.9 | 2,466 |

Replays: 100 of 100 reproduce exactly. Two full runs gave identical outcomes and measurements; only the timing differed (1.57 and 1.56 Games per second).

## Exit criteria

| Criterion | Verdict |
| --- | --- |
| All 100 Games end in a win or draw, with no stalls and no errors | Pass |
| Every Game's replay reproduces exactly | Pass |
| Games per second is reported (no target) | Pass: 1.56 |

## Failures and issues filed

None. No Game stalled or errored, and no replay diverged, so no `engine-rules`, `rules-question` or bug issues came out of this run.

## Decisions

- **Weapon setups need a real weapon.** `pickDecklist` only picks weapon setups that hold at least one weapon. Upstream would also accept a lone off-hand, but a hero with no weapon isn't a setup anyone would bring.
- **Seat orders aren't mirror Games.** The suite's `startingSeat` is always Seat 0, and the two seat orders swap which List sits in Seat 0. Each seed's two Games use the same two Decklists, but the engine's shuffles and each random Agent's choices are seeded by Seat, not by List, so the two Games aren't mirrors of each other.
- **The hidden-information test reaches the renderer directly.** `runGame` exposes only token counts, but the Agent-honesty standard needs the rendered text checked for the opponent's hidden cards, so that test calls `renderDecision` itself. This is a recorded deviation from testing through the seams.

## Notes for the Claude-player phase

- At about 250 decisions per Game and about 490 tokens per decision, one Game rendered for Claude Agents costs roughly 120,000 tokens of View plus Intents across both Seats, before any Plan notes or reasoning. Random play is a rough proxy: it makes many more cheap passes than a real player would, and Games may run longer or shorter.
- Removing pitch reorderings barely moves the average (4.6 to 4.5) but cuts the worst decision from 41 to 32 Intents.
- Bravo won 70 of 100 Games between random Agents. That says little about the matchup, since neither Seat plays with intent.
- At 1.56 Games per second, throughput does not need engine work for Phase 1.
