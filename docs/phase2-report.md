# Phase 2 report: Claude Agents play Ira vs Bravo through Claude Code

Spec #167, ticket #176. Verdict: **pass**. All 10 Games ended in a win or draw, and no Game ended on an Agent's fault.

## Setup

- **Engine:** fyendal.net at upstream commit `22e9ed8b952efaa746ce4f0f8d5c975a703ab683`, vendored at `vendor/fyendal.net`.
- **Lists:** `packages/runner/lists/ira-crimson-haze.txt` (Ira, Crimson Haze) and `packages/runner/lists/bravo-flattering-showman.txt` (Bravo, Flattering Showman).
- **Agents:** Claude Agents through Claude Code in print mode (ADR-0002): Seat 0 opus at medium, Seat 1 opus at medium. Each Seat's config stays with the Seat whichever List sits there. Every decision is one fresh call.
- **Seeds:** 1 to 5.
- **Seat orders:** each seed is played twice, once with Ira in Seat 0 and once with Bravo in Seat 0. Seat 0 starts every Game, so each List goes first once per seed. That makes 10 Games.
- **Decision cap:** 1000 decisions per Game; a Game over it ends as a stall.
- **Concurrency:** 2 Games at a time; decisions within a Game are sequential.
- **Run directory:** `results/2026-11-02T13-28-20Z-suite` (gitignored), started 2026-11-02T13:28:20Z, completed 2026-11-03T00:26:38Z: three sittings across three usage windows, about 11 hours wall clock, 8.2 hours of call latency.
- **Command:** `pnpm suite:claude --model0 opus --effort0 medium --model1 opus --effort1 medium --seeds 1-5 --concurrency 2`.

## Results

| Outcome | Games |
| --- | --- |
| Win | 10 (Ira 9, Bravo 1) |
| Draw | 0 |
| Stall | 0 |
| Error | 0 |

| Game | Seed | Seat order | Outcome | Winner | Decisions | Turns | Models (Seat 0 / Seat 1) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `1-ira-first` | 1 | Ira (Seat 0) vs Bravo (Seat 1) | Seat 0 wins | Ira (Seat 0) | 404 | 21 | `claude-opus-5-5` / `claude-opus-5-5` |
| `1-bravo-first` | 1 | Bravo (Seat 0) vs Ira (Seat 1) | Seat 1 wins | Ira (Seat 1) | 445 | 26 | `claude-opus-5-5` / `claude-opus-5-5` |
| `2-ira-first` | 2 | Ira (Seat 0) vs Bravo (Seat 1) | Seat 0 wins | Ira (Seat 0) | 397 | 19 | `claude-opus-5-5` / `claude-opus-5-5` |
| `2-bravo-first` | 2 | Bravo (Seat 0) vs Ira (Seat 1) | Seat 0 wins | Bravo (Seat 0) | 269 | 13 | `claude-opus-5-5` / `claude-opus-5-5` |
| `3-ira-first` | 3 | Ira (Seat 0) vs Bravo (Seat 1) | Seat 0 wins | Ira (Seat 0) | 438 | 23 | `claude-opus-5-5` / `claude-opus-5-5` |
| `3-bravo-first` | 3 | Bravo (Seat 0) vs Ira (Seat 1) | Seat 1 wins | Ira (Seat 1) | 367 | 20 | `claude-opus-5-5` / `claude-opus-5-5` |
| `4-ira-first` | 4 | Ira (Seat 0) vs Bravo (Seat 1) | Seat 0 wins | Ira (Seat 0) | 358 | 19 | `claude-opus-5-5` / `claude-opus-5-5` |
| `4-bravo-first` | 4 | Bravo (Seat 0) vs Ira (Seat 1) | Seat 1 wins | Ira (Seat 1) | 325 | 16 | `claude-opus-5-5` / `claude-opus-5-5` |
| `5-ira-first` | 5 | Ira (Seat 0) vs Bravo (Seat 1) | Seat 0 wins | Ira (Seat 0) | 375 | 19 | `claude-opus-5-5` / `claude-opus-5-5` |
| `5-bravo-first` | 5 | Bravo (Seat 0) vs Ira (Seat 1) | Seat 1 wins | Ira (Seat 1) | 329 | 18 | `claude-opus-5-5` / `claude-opus-5-5` |

## Measurements

| Measurement | Average | Maximum |
| --- | --- | --- |
| Decisions per Game | 370.7 | 445 |
| Turns per Game | 19.4 | 26 |
| Input tokens per Game | 1,504,884.4 | 1,888,253 |
| Input tokens per decision | 4,059.6 | 10,522 |
| Cached tokens per Game | 1,806,902.5 | 2,186,262 |
| Cached tokens per decision | 4,874.3 | 10,421 |
| Output tokens per Game | 237,792.0 | 282,052 |
| Output tokens per decision | 641.5 | 4,339 |
| Latency per Game (s) | 2,954.4 | 3,433.6 |
| Latency per decision (s) | 8.0 | 47.8 |
| Cost estimate per Game ($) | 17.15 | 21.18 |

| Total | Value |
| --- | --- |
| Decisions | 3,707 |
| Cost estimate ($) | 171.53 |
| Retries | 52 |
| Invalid first answers | 0 |
| Plan notes cut | 0 |

### Models reported

| Seat | Config | Models Claude Code reported |
| --- | --- | --- |
| 0 | opus at medium | `claude-opus-5-5` |
| 1 | opus at medium | `claude-opus-5-5` |

## Exit criteria

| Criterion | Verdict |
| --- | --- |
| All 10 Games end in a win or draw, with no stalls and no errors | Pass |
| No Game ended on an Agent's fault (an error outcome with a Decision failure cause) | Pass |

## Failures and issues filed

The final manifest holds no failure: every Game ended in a win. Along the way the Run was stopped three times, and nine Games were played on from their files with `--resume --retry-failed` rather than restarted. In order:

- **Defend staging looped** in the single Game played before the suite (step 2 of #178): upstream offers staging with replace semantics, so an Agent that wanted two blockers staged one, then the other, and never confirmed. Filed and fixed as #181 (PR #182) before the suite started.
- **The first rate limit was not recognised** (first sitting, 2026-11-02 14:55Z). Claude Code printed "You've hit your 5-hour limit · resets 12:40pm", the pattern expected "hit your limit", and six Games failed as Agent errors instead of pausing. Filed and fixed as #186 (PR #189). The second and third limits paused the Run as designed.
- **The model's safeguards flagged ordinary decisions** (`[reasoning_extraction]`), three Games in the first sitting and one more in the second. Each flag came after the one retry, each at a decision listing a single Intent (a forced pass). Filed as #187 (PR #190: a flagged call is a refusal, retried three times; one that outlasts the retries at a one-Intent decision applies that Intent and says so in its reasoning) and #192 (PR #193: the Plan notes were the one thing every message of the Seat repeated, so a flagged set of notes was refused for the rest of the Game; the question is asked once more without them). 11 decisions in three Games (`1-ira-first`, `2-ira-first`, `3-ira-first`, all for the Ira Seat) were applied this way, and one decision in `3-ira-first` was answered to the notes-free message. They are counted as ordinary decisions above.
- **A resume could not pick up a failed Game.** Filed and fixed as #188 (PR #191).

No engine stall, no rejected Intent, no invalid answer. Issues left open from the Run: #183 (apply the lone legal Intent without a call), #201 (cache writes at the 1-hour rate).

## Decisions

- **The decision cap is 1,000, up from 600** (#184). Phase 1's random Games peaked at 452 decisions; the live Games ran 269 to 445 with a mean of 371, so a 600 cap was within reach of a normal Game. A paused Run reads the cap from its manifest, so it was raised before the suite started.
- **A refused call does not end a Game that has nothing to decide.** When the safeguards flag persists through the retries, with and without the Plan notes, at a decision listing one Intent, the Agent applies it and the Decision record says so (its reasoning starts with a fixed sentence). A refusal at a decision with a choice still ends the Game with cause `refusal`. The report does not yet count the applied-without-answer decisions separately; they are found by that sentence.
- **A Run is recovered, not restarted.** `--retry-failed` plays on the Games that failed at an Agent's fault from their files. The Game files of this Run keep the failure records from the first sitting before the records of the play that followed; `measurements.totals.decisions` counts them, which is why the Results table shows one more decision than the manifest's steps for the Games that failed once.
- **The report is the generated one, with the three sections above written by hand** and the Run directory made relative.

## Notes for the next phase

- **Ira won 9 of 10.** Phase 1's random Agents had Bravo winning 70 of 100. Played with intent, the Ira List beats the Bravo List from either Seat; the one Bravo win was seed 2 going first. Both Seats cost about the same ($85 and $86), so the result is not one Seat thinking harder.
- **Half the calls had nothing to decide.** 1,765 of 3,700 decisions listed a single Intent (nearly all a forced pass): $75.55 of the $171.53 and 3.0 of the 8.2 hours of latency. The Agents use those calls to write Plan notes, and several of the safeguards flags landed on them. #183 proposes applying the lone Intent without a call.
- **Cache writes are the largest cost.** Reconciled against list prices, the $171.53 is 15.0M input tokens written to the cache at the 1-hour rate ($120), 18.1M cache reads ($3.61) and 2.4M output tokens ($47.56). Each decision's message is written and never read back. #201.
- **Blocking costs three decisions for a two-card block.** Staging was 444 of 3,700 decisions; 128 blocks used two or more cards. Cumulative staging (#181) made that possible, and an Intent that stages and confirms in one step would save two calls per such block.
- **What a Decision record holds.** The rendered View and legal Intents as the Agent saw them, the answer (the Intent, a few sentences of reasoning, the Plan notes rewritten), and the call's measurements (model, tokens, cache reads, latency, cost, retries). The Game file adds both system prompts, both Decklist builds with their reasoning, the replay, which reproduces the Game, and the outcome. That supports per-Intent-kind cost and latency, reading a Seat's Plan notes as they change turn by turn, grading reasoning against what happened next, and replaying any decision's state from the seed and step.
- **Nothing carries across Games.** Each Game starts with an empty Plan notes slate and a fresh Decklist build, so ten Games are ten independent samples, not a learning curve. Cross-Game learning is the open design question for the next phase.
- **Concessions cannot happen.** The runner filters concede and draw-offer Intents out of the legal list, so every Game plays to a kill. A Seat that is clearly lost spends calls to the end; letting an Agent concede, or ending a Game once a Seat cannot win, would save some of them. Known information is whatever the View shows: no hidden card of the opponent reached a prompt (the honesty test), and the Agents are told only the opponent's hero before building.
- **Latency.** 8.0 s per decision on average, 47.8 s at most; a Game of 370 decisions is about 50 minutes, and two at a time filled a 5-hour window with about 4 Games. A Run of ten needs three windows at this pace.
- **Safeguards.** The flags were all `reasoning_extraction`, all on the Ira Seat, and repeatable for the same message. The answer schema asks for a `reasoning` field; if flags continue with the Plan notes dropped, renaming what the model is asked for is the next thing to try.
