# @tcg-htc/claude-agent

The Claude Agent: Claude plays a Seat through Claude Code in print mode, on the developer's subscription (ADR-0002).

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
