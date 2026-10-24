import { chmodSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { type CallRequest, claudeCodeCall, classify, type ProcessRun, systemPromptFile } from "./claudeCode.js";

const tempDir = mkdtempSync(join(tmpdir(), "claude-code-call-"));
afterAll(() => rmSync(tempDir, { recursive: true, force: true }));

/** A stand-in for the `claude` binary: a shell script that records what it was
 * given under `dir` and prints `stdout`. */
function fakeBinary(dir: string, stdout: string, body = ""): string {
  mkdirSync(dir, { recursive: true });
  const path = join(dir, "claude");
  writeFileSync(
    path,
    [
      "#!/usr/bin/env bash",
      `printf '%s\\n' "$@" > '${dir}/args'`,
      `pwd > '${dir}/cwd'`,
      `cat > '${dir}/stdin'`,
      `env | grep -E '^(ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN|CLAUDE_CODE_CALL_PROBE)=' > '${dir}/env' || true`,
      body,
      `printf '%s' '${stdout.replace(/'/g, "'\\''")}'`,
    ].join("\n"),
  );
  chmodSync(path, 0o755);
  return path;
}

const request = (resultsDir: string, overrides: Partial<CallRequest> = {}): CallRequest => ({
  systemPrompt: "You are Seat 0.",
  message: "Choose an Intent.\nLine two.",
  schema: { type: "object", properties: { n: { type: "integer" } }, required: ["n"] },
  config: { model: "haiku", effort: "low" },
  resultsDir,
  ...overrides,
});

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

describe("claudeCodeCall", () => {
  it("spawns claude -p with the print-mode flags, in an empty cwd, without the API key", async () => {
    const dir = join(tempDir, "spawn");
    const resultsDir = join(dir, "results");
    const binary = fakeBinary(dir, resultJson());
    process.env.ANTHROPIC_API_KEY = "sk-ant-test";
    process.env.ANTHROPIC_AUTH_TOKEN = "token-test";
    process.env.CLAUDE_CODE_CALL_PROBE = "kept";

    const result = await claudeCodeCall({ binary })(request(resultsDir));

    expect(result).toMatchObject({ kind: "answer", output: { n: 7 } });
    const args = readFileSync(join(dir, "args"), "utf8").trimEnd().split("\n");
    const promptFile = systemPromptFile(resultsDir, "You are Seat 0.");
    expect(args).toEqual([
      "-p",
      "--output-format",
      "json",
      "--json-schema",
      JSON.stringify(request(resultsDir).schema),
      "--tools",
      "",
      "--strict-mcp-config",
      "--disable-slash-commands",
      "--setting-sources",
      "",
      "--no-session-persistence",
      "--system-prompt-file",
      promptFile,
      "--model",
      "haiku",
      "--effort",
      "low",
      "--max-turns",
      "2",
    ]);
    expect(args).not.toContain("--bare");
    expect(readFileSync(promptFile, "utf8")).toBe("You are Seat 0.");
    expect(readFileSync(join(dir, "stdin"), "utf8")).toBe("Choose an Intent.\nLine two.");
    expect(readFileSync(join(dir, "cwd"), "utf8").trim()).toBe(join(resultsDir, "cwd"));
    expect(readdirSync(join(resultsDir, "cwd"))).toEqual([]);
    expect(readFileSync(join(dir, "env"), "utf8").trim()).toBe("CLAUDE_CODE_CALL_PROBE=kept");
  });

  it("kills a claude that gives no result in time and reports a timeout", async () => {
    const dir = join(tempDir, "timeout");
    const binary = fakeBinary(dir, resultJson(), "sleep 30");

    const started = Date.now();
    const result = await claudeCodeCall({ binary, timeoutMs: 300 })(request(join(dir, "results")));

    expect(result.kind).toBe("timeout");
    expect(Date.now() - started).toBeLessThan(5000);
  });

  it("writes the system prompt file once and reuses it unchanged for the same text", async () => {
    const dir = join(tempDir, "reuse");
    const resultsDir = join(dir, "results");
    const binary = fakeBinary(dir, resultJson());
    const call = claudeCodeCall({ binary });

    await call(request(resultsDir));
    const promptFile = systemPromptFile(resultsDir, "You are Seat 0.");
    const first = statSync(promptFile);
    await new Promise((resolve) => setTimeout(resolve, 20));
    await call(request(resultsDir, { message: "Another decision." }));
    await call(request(resultsDir, { systemPrompt: "You are Seat 1." }));

    expect(statSync(promptFile).mtimeMs).toBe(first.mtimeMs);
    const otherFile = systemPromptFile(resultsDir, "You are Seat 1.");
    expect(otherFile).not.toBe(promptFile);
    expect(existsSync(otherFile)).toBe(true);
    expect(readFileSync(join(dir, "args"), "utf8")).toContain(otherFile);
  });
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
