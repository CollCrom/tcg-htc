// ask: one question to Claude Code, asked again once when the answer is not
// accepted or the call fails, with the model's measurements summed over the
// attempts. Both the Decklist build and every play decision go through it.
import type { AgentMeasurements, DecisionFailure, DecisionFailureCause, Seat } from "@tcg-htc/runner";
import type { CallRequest, CallResult, ClaudeCodeCall, ClaudeConfig } from "./claudeCode.js";

/** Calls made for one question after the first: one retry. */
export const MAX_RETRIES = 1;

/** Heads the problem appended to the message on a retry after an invalid answer. */
export const PROBLEM_HEADING = "Your previous answer was not accepted. Answer again, fixing this problem:";

export interface Question<T> extends Omit<CallRequest, "config"> {
  config: CallRequest["config"];
  call: ClaudeCodeCall;
  /** Reads the parsed answer into a value, or names the problem with it, which
   * the retry's message shows the model. */
  read: (output: unknown) => Read<T>;
  /** Names the Seat and the Agent, for a failure's detail. */
  who: string;
}

export type Read<T> = { ok: true; value: T } | { ok: false; problem: string };

/** The accepted answer with the measurements of every attempt, or a failure
 * in the shape the runner ends a Game with. */
export type Asked<T> = { value: T; measurements: AgentMeasurements } | DecisionFailure;

/** Whether an asked-for value, or anything built from one, is the failure. */
export function failed<T extends object>(result: T | DecisionFailure): result is DecisionFailure {
  return "cause" in result;
}

/** Asks until an answer is accepted or the retries run out. An invalid answer
 * is retried with the problem appended to the message; a refusal, timeout or
 * failure is retried with the same message; a rate limit fails at once, so the
 * Run can pause. */
export async function ask<T>({ call, read, who, ...request }: Question<T>): Promise<Asked<T>> {
  const measurements: AgentMeasurements = {
    effort: request.config.effort,
    inputTokens: 0,
    cachedTokens: 0,
    outputTokens: 0,
    latencyMs: 0,
    retries: 0,
    firstAnswerInvalid: false,
    costUsd: 0,
  };
  const fail = (cause: DecisionFailureCause, detail: string): DecisionFailure => ({ cause, detail: `${who}: ${detail}`, measurements });

  let problem: string | undefined;
  for (let attempt = 0; ; attempt++) {
    const result = await call({ ...request, message: problem ? `${request.message}\n\n${PROBLEM_HEADING}\n${problem}` : request.message });
    measurements.retries = attempt;
    if (result.kind === "answer") {
      const { usage } = result;
      measurements.model = usage.model;
      measurements.inputTokens! += usage.inputTokens;
      measurements.cachedTokens! += usage.cachedTokens;
      measurements.outputTokens! += usage.outputTokens;
      measurements.latencyMs! += usage.latencyMs;
      measurements.costUsd! += usage.costUsd;
    }
    const outcome = readResult(result, read);
    if (outcome.kind === "accepted") return { value: outcome.value, measurements };
    if (outcome.kind === "rate-limit") return fail("rate-limit", outcome.detail);
    if (outcome.kind === "invalid-answer" && attempt === 0) measurements.firstAnswerInvalid = true;
    if (attempt >= MAX_RETRIES) return fail(outcome.kind, outcome.detail);
    problem = outcome.kind === "invalid-answer" ? outcome.detail : undefined;
  }
}

type Outcome<T> = { kind: "accepted"; value: T } | { kind: DecisionFailureCause; detail: string };

function readResult<T>(result: CallResult, read: (output: unknown) => Read<T>): Outcome<T> {
  if (result.kind !== "answer") return result;
  const got = read(result.output);
  return got.ok ? { kind: "accepted", value: got.value } : { kind: "invalid-answer", detail: got.problem };
}

/** A field of a parsed answer, when the answer is an object. */
export function field(output: unknown, name: string): unknown {
  return output && typeof output === "object" ? (output as Record<string, unknown>)[name] : undefined;
}

/** A string field of a parsed answer, or "" when it is missing or not a string. */
export function textField(output: unknown, name: string): string {
  const value = field(output, name);
  return typeof value === "string" ? value : "";
}

/** How a failure's detail names a Seat's Claude Agent: `Seat 0's Claude Agent (opus, medium)`. */
export function describeAgent(seat: Seat, { model, effort }: ClaudeConfig): string {
  return `Seat ${seat}'s Claude Agent (${model}, ${effort})`;
}
