import { describe, expect, it } from "vitest";
import { classify, type ProcessRun } from "./claudeCode.js";

/** A print-mode JSON result as Claude Code 2.1 prints it, with the fields the
 * call reads. */
const resultJson = (overrides: Record<string, unknown> = {}) =>
  JSON.stringify({
    type: "result",
    subtype: "success",
    is_error: false,
    duration_ms: 4200,
    duration_api_ms: 3900,
    num_turns: 1,
    result: '{"n":7}',
    session_id: "0000",
    total_cost_usd: 0.0123,
    usage: {
      input_tokens: 12,
      cache_creation_input_tokens: 300,
      cache_read_input_tokens: 2000,
      output_tokens: 45,
    },
    modelUsage: {
      "claude-haiku-4-5-20251001": { inputTokens: 12, outputTokens: 45, cacheReadInputTokens: 2000, cacheCreationInputTokens: 300, costUSD: 0.0123 },
    },
    structured_output: { n: 7 },
    ...overrides,
  });

const run = (overrides: Partial<ProcessRun> = {}): ProcessRun => ({
  exitCode: 0,
  stdout: resultJson(),
  stderr: "",
  timedOut: false,
  latencyMs: 4321,
  ...overrides,
});

describe("classify", () => {
  it("reads an answer's structured output and usage", () => {
    expect(classify(run())).toEqual({
      kind: "answer",
      output: { n: 7 },
      turns: 1,
      usage: {
        model: "claude-haiku-4-5-20251001",
        inputTokens: 312,
        cachedTokens: 2000,
        outputTokens: 45,
        costUsd: 0.0123,
        latencyMs: 4321,
      },
    });
  });

  it("falls back to the result text when there is no structured output but it is JSON", () => {
    const stdout = resultJson({ structured_output: undefined, result: '{"n":3}' });
    expect(classify(run({ stdout }))).toMatchObject({ kind: "answer", output: { n: 3 } });
  });

  it("reports a timeout", () => {
    expect(classify(run({ timedOut: true, exitCode: null, stdout: "" }))).toEqual({
      kind: "timeout",
      detail: "claude gave no result within 4321 ms and was killed",
    });
  });

  it("reports a rate limit from the result text", () => {
    const stdout = resultJson({
      is_error: true,
      subtype: "success",
      structured_output: undefined,
      result: "You've hit your limit · resets 3pm (Europe/London)",
    });
    expect(classify(run({ stdout, exitCode: 1 }))).toEqual({
      kind: "rate-limit",
      detail: "You've hit your limit · resets 3pm (Europe/London)",
    });
  });

  it("reports a rate limit from stderr when there is no result", () => {
    expect(classify(run({ stdout: "", stderr: "Error: usage limit reached", exitCode: 1 }))).toEqual({
      kind: "rate-limit",
      detail: "Error: usage limit reached",
    });
  });

  it("reports a refusal when the model answered in prose instead of the schema", () => {
    const stdout = resultJson({ structured_output: undefined, result: "I can't help with that." });
    expect(classify(run({ stdout }))).toEqual({ kind: "refusal", detail: "I can't help with that." });
  });

  it("reports a failure with the message on a non-zero exit", () => {
    expect(classify(run({ stdout: "", stderr: "Not logged in · run /login", exitCode: 1 }))).toEqual({
      kind: "failure",
      detail: "claude exited 1 without a JSON result: Not logged in · run /login",
    });
  });

  it("reports a failure when the result is an error", () => {
    const stdout = resultJson({
      is_error: true,
      subtype: "error_max_turns",
      structured_output: undefined,
      result: "Reached max turns (2)",
    });
    expect(classify(run({ stdout, exitCode: 1 }))).toEqual({
      kind: "failure",
      detail: "claude exited 1 (error_max_turns): Reached max turns (2)",
    });
  });

  it("reports a failure when stdout is not a result", () => {
    expect(classify(run({ stdout: "garbage", exitCode: 0 }))).toEqual({
      kind: "failure",
      detail: "claude exited 0 without a JSON result: garbage",
    });
  });
});
