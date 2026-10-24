// The one function that talks to Claude Code: `claude -p` in print mode, on
// the developer's subscription (ADR-0002). Text and a schema in, parsed JSON
// plus usage out.

/** A Claude Code model alias. What it maps to changes by the day, so the
 * answer's `usage.model` keeps the model Claude Code reports. */
export type ModelAlias = "opus" | "sonnet" | "haiku" | "fable";

/** A Claude Code effort level. */
export type Effort = "low" | "medium" | "high" | "xhigh" | "max";

/** How a Claude Agent is configured: which model, at which effort. */
export interface ClaudeConfig {
  model: ModelAlias;
  effort: Effort;
}

/** One request to Claude Code. */
export interface CallRequest {
  /** Replaces Claude Code's default system prompt. Written to a file under
   * `resultsDir` once per distinct text, so a Game's decisions share one file
   * byte for byte and Claude Code's prompt cache is reused. */
  systemPrompt: string;
  /** The user message, sent on stdin. */
  message: string;
  /** The JSON Schema the answer must match. */
  schema: object;
  config: ClaudeConfig;
  /** The Run's results directory. The call writes the system prompt file there
   * and runs Claude Code in an empty `cwd/` beneath it. */
  resultsDir: string;
}

/** What one answer cost. `inputTokens` are the prompt tokens the model read
 * afresh (cache writes included); `cachedTokens` the ones read from cache. */
export interface Usage {
  /** The model Claude Code reports having used, as a full model id. */
  model: string;
  inputTokens: number;
  cachedTokens: number;
  outputTokens: number;
  /** Claude Code's own estimate. */
  costUsd: number;
  /** Wall-clock time of the whole process, measured by the call. */
  latencyMs: number;
}

/** What a call to Claude Code came back as. */
export type CallResult =
  | { kind: "answer"; output: unknown; usage: Usage; turns: number | undefined }
  | { kind: "rate-limit"; detail: string }
  | { kind: "refusal"; detail: string }
  | { kind: "timeout"; detail: string }
  | { kind: "failure"; detail: string };

/** The seam: tests fake it, another transport could replace it. */
export type ClaudeCodeCall = (request: CallRequest) => Promise<CallResult>;

/** What a finished (or killed) `claude` process left behind. */
export interface ProcessRun {
  exitCode: number | null;
  stdout: string;
  stderr: string;
  timedOut: boolean;
  latencyMs: number;
}

/** Text Claude Code prints when the subscription's usage window is spent. The
 * live run refines it. */
export const RATE_LIMIT_PATTERN = /hit your limit|usage limit|rate[ _-]?limit/i;

/** Turns a process run into a CallResult. Pure, so tests drive it without
 * spawning anything. */
export function classify(run: ProcessRun): CallResult {
  if (run.timedOut) {
    return { kind: "timeout", detail: `claude gave no result within ${run.latencyMs} ms and was killed` };
  }
  const parsed = parseResult(run.stdout);
  const text = typeof parsed?.result === "string" ? parsed.result : "";
  const stderr = run.stderr.trim();
  if (!parsed) {
    if (RATE_LIMIT_PATTERN.test(stderr) || RATE_LIMIT_PATTERN.test(run.stdout)) {
      return { kind: "rate-limit", detail: stderr || run.stdout.trim() };
    }
    return { kind: "failure", detail: `claude exited ${run.exitCode} without a JSON result: ${stderr || run.stdout.trim()}` };
  }
  const failed = parsed.is_error === true || run.exitCode !== 0 || (parsed.subtype !== undefined && parsed.subtype !== "success");
  if (failed) {
    if (RATE_LIMIT_PATTERN.test(text) || RATE_LIMIT_PATTERN.test(stderr)) {
      return { kind: "rate-limit", detail: text || stderr };
    }
    const subtype = typeof parsed.subtype === "string" && parsed.subtype !== "success" ? ` (${parsed.subtype})` : "";
    return { kind: "failure", detail: `claude exited ${run.exitCode}${subtype}: ${[text, stderr].filter(Boolean).join("\n")}` };
  }
  const output = "structured_output" in parsed ? parsed.structured_output : parseJson(text);
  if (output === undefined) {
    return { kind: "refusal", detail: text };
  }
  return {
    kind: "answer",
    output,
    turns: typeof parsed.num_turns === "number" ? parsed.num_turns : undefined,
    usage: usageOf(parsed, run.latencyMs),
  };
}

/** `text` parsed as a JSON object, or undefined when it isn't one. */
function parseJson(text: string): unknown {
  try {
    const value: unknown = JSON.parse(text);
    return value && typeof value === "object" ? value : undefined;
  } catch {
    return undefined;
  }
}

/** Claude Code's JSON result, loosely typed: the live test confirms the fields. */
interface ResultJson {
  type?: unknown;
  subtype?: unknown;
  is_error?: unknown;
  num_turns?: unknown;
  result?: unknown;
  total_cost_usd?: unknown;
  usage?: Record<string, unknown>;
  modelUsage?: Record<string, unknown>;
  structured_output?: unknown;
}

/** The result object in `stdout`: the whole of it, or its last non-empty line
 * when something else was printed first. */
function parseResult(stdout: string): ResultJson | undefined {
  const lines = stdout.trim().split("\n");
  for (const text of [stdout.trim(), lines[lines.length - 1] ?? ""]) {
    try {
      const value: unknown = JSON.parse(text);
      if (value && typeof value === "object" && !Array.isArray(value)) return value as ResultJson;
    } catch {
      // Not JSON; try the next candidate.
    }
  }
  return undefined;
}

function usageOf(parsed: ResultJson, latencyMs: number): Usage {
  const usage = parsed.usage ?? {};
  const models = Object.keys(parsed.modelUsage ?? {});
  return {
    model: models.length > 0 ? models.join("+") : "unknown",
    inputTokens: count(usage.input_tokens) + count(usage.cache_creation_input_tokens),
    cachedTokens: count(usage.cache_read_input_tokens),
    outputTokens: count(usage.output_tokens),
    costUsd: count(parsed.total_cost_usd),
    latencyMs,
  };
}

function count(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}
