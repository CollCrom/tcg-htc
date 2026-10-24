# @tcg-htc/claude-agent

The Claude Agent: Claude plays a Seat through Claude Code in print mode, on the developer's subscription (ADR-0002).

## The Claude Agent

`claudeAgent(config, call, options?)` in `src/claudeAgent.ts` makes a runner `Agent` for one Seat: `config` is `{ seat, decklist, model, effort }`, `call` a `ClaudeCodeCall` (the real one or `fakeClaudeCode`), `options` the results directory and, for a resumed Game, the Plan notes to start from. The returned Agent also exposes `seat`, `config`, `systemPrompt` and the current `planNotes`.

Every decision is one fresh call. The system prompt is built once in the factory and is byte-identical for the whole Game: the primer (`prompts/primer.md`), the Seat and its objective, a key to the card-text symbols, the answer format, and the Seat's own Decklist with full card text. The message is `renderDecision`'s text followed by the Seat's Plan notes under `PLAN_NOTES_HEADING`. The answer must match `ANSWER_SCHEMA`: `intent` (the number of a listed Intent), `reasoning` and `planNotes`, nothing else.

| What comes back | What the Agent does |
|---|---|
| a listed number | the Decision's Intent is `renderDecision(...).intents[n - 1]`; notes over `PLAN_NOTES_LIMIT` (2,000) characters are cut and `notesCut` recorded |
| a number out of range, or none | one retry whose message appends the problem; a second failure is a `DecisionFailure` with cause `invalid-answer` |
| `refusal`, `timeout`, `failure` | one retry with the same message, then a `DecisionFailure` with that cause |
| `rate-limit` | a `DecisionFailure` with cause `rate-limit` at once, so the Run can pause |

A failure's `detail` starts "Seat N's Claude Agent (model, effort): ". Every Decision carries `measurements`: the model Claude Code reported, the effort, tokens, latency and cost summed over the decision's calls, `retries`, `firstAnswerInvalid` and `notesCut`.

`src/claudeAgent.test.ts` drives all of this through whole Games against the random Agent with `fakeClaudeCode`, and holds the honesty test: with a Claude Agent in both Seats, no opponent hidden card appears in any system prompt or message sent.

## Playing a Game, and the Game file

`playGame({ seed, lists, configs, call, runDir, decklistPicker?, onDecision?, clock? })` in `src/playGame.ts` plays one Game between two Claude Agents: `lists` are the two Lists by Seat (Seat 0 takes the first turn), `configs` each Seat's `{ model, effort }`, `call` the Claude Code call both Agents share, `runDir` the Run's directory (the Game file, the system prompt files and Claude Code's `cwd/` all go there). Each Decklist comes from `decklistPicker(list, seed)`, `pickDecklist` by default. It returns `{ result, file, path, agents }`: the runner's `GameResult`, the final `GameFile` and where it was written. `onDecision(record, progress, { file, path })` is called after every decision, once the file holds it; `progressLine(id, record, progress)` renders the Run's one line per decision from the same arguments.

The Game file (`src/gameFile.ts`) is one JSON document, `<runDir>/game-<seed>-<hero of Seat 0>-first.json` (`gameFileName`), rewritten after every decision by writing `<path>.tmp` and renaming it over the old file, so a crash leaves a whole document. Its shape:

| Field | Holds |
|---|---|
| `status` | `playing`, then `complete` once the outcome is known |
| `setup` | `seed`, `startingSeat`, `lists` (names), `heroes`, `decklists`, `configs` by Seat |
| `systemPrompts` | each Seat's system prompt, once |
| `replay` | the runner's `Replay`: setup plus every Intent applied so far, `replayGame` takes it |
| `outcome`, `turns` | the `GameOutcome` (cause included for an Agent's failure) and turn count, once complete |
| `measurements` | the runner's `GameMeasurements` plus `perSeat` and `totals`: `AgentTotals` (decisions, tokens, latency, cost, retries, invalid first answers, notes cut) |
| `decisions` | every `DecisionRecord` in order; each Seat's last record holds its latest Plan notes |

A Run resumes a Game from `replay.intents` and the Plan notes in `decisions`. `readGameFile(path)` reads one back.

## The single-Game script

`pnpm game:claude` (root script, `src/gameClaude.ts`) plays one Game through the real call and prints a progress line per decision, the outcome, the token and cost totals and the Game file's path; it exits non-zero on a stall or an error. Flags, parsed by `parseGameClaudeArgs` in `src/gameClaudeArgs.ts`: `--seed` (1), `--first ira|bravo` (the hero in Seat 0; ira), `--model0`/`--model1` (opus), `--effort0`/`--effort1` (medium), `--results` (the results directory, relative to where pnpm was run; `results`, gitignored). The Run directory is `<results>/<UTC timestamp>-game-<seed>-<first>-first/`.

## The Run and the suite script

`runSuite({ config, runDir, call, onDecision?, onGame?, now?, upstreamCommit? })` in `src/run.ts` plays the Phase 2 suite into `runDir`: for each seed in `config.seeds`, one Game with each of `config.lists` in Seat 0 (`planGames`), `config.concurrency` Games at a time through a few workers that each claim the next pending Game, every Game through `playGame` with `config.maxSteps` as its decision cap. `<runDir>/manifest.json` (`Manifest`) holds the Run's `status` (`running`, `paused`, `complete`), `config`, `startedAt`, `updatedAt` and one `ManifestGame` per Game: `id`, `seed`, `first` (the hero in Seat 0), `status` (`pending`, `playing`, `complete`, `failed`), `outcome`, `file`, `steps`, `startedAt`, `finishedAt`. It is rewritten (tmp + rename) on every Game status change, and `onGame(game, manifest)` is called once it holds the change. A Game that stalls or errors is `failed` with the outcome kept; a `playGame` exception (a missing `claude` binary, say) is `failed` with an `error` outcome whose detail is the message. When no Game is pending the Run writes `<runDir>/report.md` (`renderReport` in `src/report.ts`, the shape of `docs/phase1-report.md`; `exitCriteria` gives the verdicts) and marks itself `complete`.

`pnpm suite:claude` (root script, `src/suiteClaude.ts`) plays it through the real call under `results/<UTC timestamp>-suite/`, printing one line per decision and per Game status change, then the report path; it exits non-zero when an exit criterion fails. Flags, parsed by `parseSuiteClaudeArgs` in `src/suiteClaudeArgs.ts`: `--model0`/`--model1` (opus), `--effort0`/`--effort1` (medium), `--concurrency` (2), `--seeds` (`1-5`; ranges and comma lists), `--results` (`results`). `--resume <runDir>` is reserved for #177 and rejected for now.

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
