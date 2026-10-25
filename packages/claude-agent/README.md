# @tcg-htc/claude-agent

The Claude Agent: Claude plays a Seat through Claude Code in print mode, on the developer's subscription (ADR-0002).

## The Claude Agent

`claudeAgent(config, call, options?)` in `src/claudeAgent.ts` makes a runner `Agent` for one Seat: `config` is `{ seat, decklist, model, effort }`, `call` a `ClaudeCodeCall` (the real one or `fakeClaudeCode`), `options` the results directory and, for a resumed Game, the Plan notes to start from. The returned Agent also exposes `seat`, `config`, `systemPrompt` and the current `planNotes`.

Every decision is one fresh call. The system prompt is built once in the factory and is byte-identical for the whole Game: the primer (`prompts/primer.md`), the Seat and its objective, a key to the card-text symbols, the answer format, and the Seat's own Decklist with full card text. The message is the text of the `RenderedDecision` the runner hands every Agent (its fourth argument: the View rendered once by `renderDecision`, the same text the Decision record keeps) followed by the Seat's Plan notes under `PLAN_NOTES_HEADING`. The answer must match `ANSWER_SCHEMA`: `intent` (the number of a listed Intent), `reasoning` and `planNotes`, nothing else.

| What comes back | What the Agent does |
|---|---|
| a listed number | the Decision's Intent is the rendering's `intents[n - 1]`; notes over `PLAN_NOTES_LIMIT` (2,000) characters are cut and `notesCut` recorded |
| a number out of range, or none | one retry whose message appends the problem; a second failure is a `DecisionFailure` with cause `invalid-answer` |
| `refusal`, `timeout`, `failure` | one retry with the same message, then a `DecisionFailure` with that cause |
| `rate-limit` | a `DecisionFailure` with cause `rate-limit` at once; the runner pauses the Game on it and the Run pauses (see "Pausing and resuming") |

A failure's `detail` starts "Seat N's Claude Agent (model, effort): ". Every Decision carries `measurements`: the model Claude Code reported, the effort, tokens, latency and cost summed over the decision's calls, `retries`, `firstAnswerInvalid` and `notesCut`.

The retry loop is `ask` (`src/ask.ts`), shared with the Decklist build: a question with a `read` function that accepts the parsed answer or names the problem. The primer and the symbol key both prompts share are in `src/prompt.ts`.

`src/claudeAgent.test.ts` drives all of this through whole Games against the random Agent with `fakeClaudeCode`. `src/honesty.test.ts` holds the honesty test: through `playGame` with a Claude Agent in both Seats, no card of the opponent's Decklist appears in any system prompt or message sent, the builds included, unless the View shown at that decision held it.

## Building a Decklist

Before each Game, each Claude Agent builds its own Decklist in one call. `buildDecklist({ seat, list, opponentHero, config, call, resultsDir })` in `src/buildDecklist.ts` sends a system prompt of the primer, the Seat and its task, the symbol key, the answer format and the whole List with a printing id in square brackets before each card (hero; weapon-zone cards; equipment with the slots each piece fits; main-deck cards with their copies), and a message naming the opponent's hero and nothing else about the opponent. The answer must match `DECKLIST_SCHEMA`: `weaponIds`, `equipment` (`head`, `chest`, `arms`, `legs`), `deck` (40 printing ids, one per copy) and `reasoning`. It goes through upstream's `validatePresentation` against the List, plus a check that at least one presented card is a weapon (upstream accepts empty weapon zones). An invalid build gets one retry whose message appends the error; a second failure, or a call failure after its retry, is a `DecisionFailure` as in play, a rate limit at once. It returns `{ systemPrompt, message, decision }`, the decision a `DecklistChoice` (`presented`, upstream's `decklist`, `reasoning`, `measurements`) or the failure. The Decklist is built afresh for every Game.

`legalPresentation(list)` (`src/scriptedBuild.ts`) derives one legal presentation from a List, for scripting the fake's answer in tests.

## Playing a Game, and the Game file

`playGame({ seed, lists, configs, call, runDir, decklistPicker?, onDecision?, clock?, maxSteps?, shouldStop?, resumeFrom? })` in `src/playGame.ts` plays one Game between two Claude Agents: `lists` are the two Lists by Seat (Seat 0 takes the first turn), `configs` each Seat's `{ model, effort }`, `call` the Claude Code call both Agents share, `runDir` the Run's directory (the Game file, the system prompt files and Claude Code's `cwd/` all go there). Each Claude Agent first builds its Decklist with `buildDecklist`, told only the opponent's hero name; a test that wants no build calls passes `decklistPicker(list, seed)` (the seeded `pickDecklist`) instead, and the file then records no Decklist decisions. It returns `{ result, file, path, agents }`: the runner's `GameResult`, the final `GameFile` and where it was written. When a build fails, the Game never starts: the file is complete with the error outcome at step 0 and no play records, `result` is an `UnplayedGame` (the error outcome, or the paused one after a rate limit, with `turns: 0`, `steps: 0`, empty `decisions`, no replay) and `agents` is absent. `onDecision(record, progress, { file, path })` is called after every decision, once the file holds it; `progressLine(id, record, progress)` renders the Run's one line per decision from the same arguments.

The Game file (`src/gameFile.ts`) is one JSON document, `<runDir>/game-<seed>-<hero of Seat 0>-first.json` (`gameFileName`), rewritten after every decision by writing `<path>.tmp` and renaming it over the old file, so a crash leaves a whole document. Its shape:

| Field | Holds |
|---|---|
| `status` | `playing` while a decision is in flight, `paused` when the Game stopped between decisions and can be resumed from the file, `complete` once the outcome is known |
| `setup` | `seed`, `startingSeat`, `lists` (names), `heroes`, `configs` by Seat, and `decklists` once both builds are valid |
| `decklistDecisions` | each Seat's build as a `DecklistDecisionRecord` (`kind: "decklist"`, `seat`, the build's own `systemPrompt` and `message`, `decision`), Seat 0 first, before any play record; a failed build is the last, unless it was a rate limit, which the Seat's new build follows on resume |
| `systemPrompts` | each Seat's play system prompt, once; absent when the Game never started |
| `replay` | the runner's `Replay`: setup plus every Intent applied so far, `replayGame` takes it; absent when the Game never started |
| `outcome`, `turns` | the `GameOutcome` (cause included for an Agent's failure) and turn count, once complete |
| `measurements` | the runner's `GameMeasurements` plus `perSeat` and `totals` over the play records and `builds` over the Decklist builds: `AgentTotals` (decisions, tokens, latency, cost, retries, invalid first answers, notes cut) |
| `decisions` | every `DecisionRecord` in order; each Seat's last chosen Decision holds its latest Plan notes; a rate-limit failure record marks where the Game paused, with no Intent applied for it |

`readGameFile(path)` reads one back. See "Pausing and resuming" for how a Game is resumed from its file.

## The single-Game script

`pnpm game:claude` (root script, `src/gameClaude.ts`) plays one Game through the real call and prints a progress line per decision, the outcome, the token and cost totals and the Game file's path; it exits non-zero on a stall or an error, and with 3 when a rate limit paused the Game (a single Game has no resume; its file holds every Intent applied). Flags, parsed by `parseGameClaudeArgs` in `src/gameClaudeArgs.ts`: `--seed` (1), `--first ira|bravo` (the hero in Seat 0; ira), `--model0`/`--model1` (opus), `--effort0`/`--effort1` (medium), `--results` (the results directory, relative to where pnpm was run; `results`, gitignored). The Run directory is `<results>/<UTC timestamp>-game-<seed>-<first>-first/`.

## The Run and the suite script

`runSuite({ config, runDir, call, onDecision?, onGame?, now?, upstreamCommit? })` in `src/run.ts` plays the Phase 2 suite into `runDir`: for each seed in `config.seeds`, one Game with each of `config.lists` in Seat 0 (`planGames`), `config.concurrency` Games at a time through a few workers that each claim the next pending Game, every Game through `playGame` with `config.maxSteps` as its decision cap. `<runDir>/manifest.json` (`Manifest`) holds the Run's `status` (`running`, `paused`, `complete`), `config`, `startedAt`, `updatedAt` and one `ManifestGame` per Game: `id`, `seed`, `first` (the hero in Seat 0), `status` (`pending`, `playing`, `complete`, `failed`), `outcome`, `file`, `steps`, `startedAt`, `finishedAt`. It is rewritten (tmp + rename) on every Game status change, and `onGame(game, manifest)` is called once it holds the change. A Game that stalls or errors is `failed` with the outcome kept; a `playGame` exception (a missing `claude` binary, say) is `failed` with an `error` outcome whose detail is the message. When no Game is pending the Run writes `<runDir>/report.md` (`renderReport` in `src/report.ts`, the shape of `docs/phase1-report.md`; `exitCriteria` gives the verdicts) and marks itself `complete`.

`pnpm suite:claude` (root script, `src/suiteClaude.ts`) plays it through the real call under `results/<UTC timestamp>-suite/`, printing one line per decision and per Game status change, then the report path; it exits non-zero when an exit criterion fails, and with `PAUSED_EXIT_CODE` (3) when the Run paused. Flags, parsed by `parseSuiteClaudeArgs` in `src/suiteClaudeArgs.ts`: `--model0`/`--model1` (opus), `--effort0`/`--effort1` (medium), `--concurrency` (2), `--seeds` (`1-5`; ranges and comma lists), `--results` (`results`); or `--resume <runDir>` alone, which takes the Run's config from its manifest and rejects any other flag.

## Pausing and resuming

A ten-Game Run is about 2,500 calls, longer than a subscription usage window, so a rate limit pauses the Run instead of failing it. The pieces, from the inside out:

- `runGame` (runner) returns a new `GameOutcome` member, `paused` (`GamePause`: `seed`, `step`, `detail`, and `cause: "rate-limit"` when an Agent's Decision was a rate-limit failure). A rate-limit failure Decision is recorded with no Intent applied and pauses the Game rather than ending it as an error; `isFailure` leaves `paused` out of the failures. Its `shouldStop` option is asked before every decision and pauses the Game when it answers true; its `resume: { intents }` option applies saved Intents before the first new decision, so `steps` and the replay count from the start of the Game.
- `playGame` takes `shouldStop` and `resumeFrom` (a `GameFile`). `shouldStop` is asked before each Decklist build as well as before every decision, so a pausing Run starts no new call. A Game that pauses, in play or in a Decklist build, is written with `status: "paused"` and no outcome. Resumed, it reuses every valid build in the file and builds again only for a Seat without one (appending that record), gives each Claude Agent the Plan notes of its last chosen Decision, replays `replay.intents`, and appends the new records to the saved ones; the measurements cover every sitting.
- `runSuite` pauses on the first `paused` result with cause `rate-limit`: it stops claiming Games and makes `shouldStop` answer true, so every Game in flight returns after its current decision with its file written. Those Games stay `playing` in the manifest with their `steps`; the manifest gets `status: "paused"`, `pausedAt`, `resumeHint` (`pnpm suite:claude --resume <runDir>`) and `pauseDetail` (what the rate limit said), and no report is written: `RunResult.report` and `reportPath` are absent.
- `resumeSuite({ runDir, call, onDecision?, onGame?, now?, upstreamCommit? })` reads the manifest, marks the Run `running`, skips `complete` and `failed` Games, plays the `pending` ones and carries each `playing` one on from its Game file (a file already `complete` settles its Game without play). It pauses again the same way on another rate limit and writes the report when the Run completes. Resuming a complete Run throws.

Because the engine is deterministic, a resumed Game asks exactly the questions an uninterrupted one would from that point. `src/resume.test.ts` and the pause tests in `src/playGame.test.ts` check this with `scriptedAnswer` (`src/scriptedPlay.ts`), a fake whose answers are a pure function of the request: a Run paused once or twice reaches, Game file by Game file, the same setup, replay, outcome and Decision records as the uninterrupted Run, the only difference being the rate-limit failure records left at each pause (which `measurements.totals.decisions` counts). The three runner tests in `packages/runner/src/game.test.ts` play the Ira and Bravo fixture Decklists rather than the precons: the precon-sly Decklist holds a card whose `canPlay` is impure (#180), which makes a paused Game's live state and its replay differ cosmetically.

## The Claude Code call

`claudeCodeCall()` in `src/claudeCode.ts` is the one function that talks to Claude Code, and the seam tests fake with `fakeClaudeCode` (`src/fakeClaudeCode.ts`). A request is a system prompt, a user message, a JSON Schema, a config (`model` alias, `effort`) and the Run's results directory. The call spawns

```
claude -p --output-format json --json-schema <schema> --tools "" --strict-mcp-config --disable-slash-commands
  --setting-sources "" --no-session-persistence --system-prompt-file <resultsDir>/system-prompt-<hash>.txt
  --model <alias> --effort <level> --max-turns 2
```

with the message on stdin, in the empty directory `<resultsDir>/cwd/` (so no AGENTS.md, hooks or settings load), and with `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and `CLAUDECODE` removed from the environment. It never passes `--bare`, which ignores the subscription's credentials. A call that hasn't finished in five minutes is killed. The system prompt file is named by the text's hash and written only when missing, so a Game's decisions share one file byte for byte.

`--max-turns` is hidden from `claude --help` in 2.1.309 but documented and accepted. `--setting-sources ""` loads no settings files (the parser returns an empty list for an empty string).

The result is classified by `classify`, a pure function over the process's exit code, stdout, stderr, timeout flag and latency:

| Kind | When |
|---|---|
| `answer` | `structured_output` present (or `result` is JSON); carries `output`, `turns` and `usage` |
| `rate-limit` | the result or stderr matches `RATE_LIMIT_PATTERN` (`hit your limit`, `usage limit`, `rate limit`) |
| `refusal` | a successful result with no structured output and prose in `result` |
| `timeout` | killed after the timeout |
| `failure` | non-zero exit, `is_error`, a subtype other than `success`, or no JSON on stdout; `detail` has the message |

Usage: `inputTokens` = `usage.input_tokens + usage.cache_creation_input_tokens`, `cachedTokens` = `usage.cache_read_input_tokens`, `outputTokens` = `usage.output_tokens`, `costUsd` = `total_cost_usd`, `model` = the key(s) of `modelUsage`, `latencyMs` measured by the call.

## Live test

`src/claudeCode.live.test.ts` makes one real call (`haiku` at `low`, a one-integer schema). It is skipped unless `TCG_HTC_LIVE_CLAUDE=1`, so `pnpm check` and CI stay offline:

```bash
TCG_HTC_LIVE_CLAUDE=1 pnpm --dir packages/claude-agent exec vitest run --reporter=verbose src/claudeCode.live.test.ts
```

Observed on 2026-10-24 with Claude Code 2.1.309: exit 0 in about 1.8 s, `num_turns: 2` (the answer turn plus the `StructuredOutput` tool turn, so the cap of 2 is exactly sufficient for a first-time valid answer and leaves no room for a schema retry), `subtype: "success"`, `is_error: false`, model `claude-haiku-5-5`. Top-level fields of the JSON result: `type`, `subtype`, `is_error`, `duration_ms`, `duration_api_ms`, `num_turns`, `result` (string), `structured_output`, `stop_reason`, `terminal_reason`, `session_id`, `uuid`, `total_cost_usd`, `usage` (`input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens`, `output_tokens_details.thinking_tokens`, `cache_creation.ephemeral_{5m,1h}_input_tokens`, `iterations[]`, `service_tier`, `speed`, `inference_geo`, `server_tool_use`, `fallback_credit`), `modelUsage.<model-id>` (`inputTokens`, `outputTokens`, `cacheReadInputTokens`, `cacheCreationInputTokens`, `costUSD`, `contextWindow`, `maxOutputTokens`, `thinkingTokens`, `canonicalModel`, `provider`, `costBasis`, `webSearchRequests`), `api_error_status`, `subagent_stats`, `safety_stops`, `fast_mode_state`, `fast_mode_disabled_reason`, `ttft_ms`, `ttft_stream_ms`, `time_to_request_ms`, `first_content_frame_ms`, `queued_turn_count`, `result_index`.

The rate-limit and refusal shapes have not been observed live; `RATE_LIMIT_PATTERN` comes from the messages in the Claude Code binary (`You've hit your limit`, `usage limit reached`, `rate limit`) and should be refined when a Run first meets one.
