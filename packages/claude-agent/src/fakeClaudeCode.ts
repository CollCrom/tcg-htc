// A scripted stand-in for the Claude Code call, so Games run offline in tests.

import type { CallRequest, CallResult, ClaudeCodeCall } from "./claudeCode.js";

/** What the fake records of each call: everything in the request but the
 * results directory. */
export type RecordedCall = Pick<CallRequest, "systemPrompt" | "message" | "schema" | "config">;

export interface FakeClaudeCode extends ClaudeCodeCall {
  /** Every call so far, in order. */
  calls: RecordedCall[];
}

/** A call that returns `results` in order, recording what it was sent, and
 * throws once the script runs out. */
export function fakeClaudeCode(results: readonly CallResult[]): FakeClaudeCode {
  const remaining = [...results];
  const calls: RecordedCall[] = [];
  const call = async ({ systemPrompt, message, schema, config }: CallRequest): Promise<CallResult> => {
    calls.push({ systemPrompt, message, schema, config });
    const result = remaining.shift();
    if (!result) throw new Error(`fakeClaudeCode has no result left for call ${calls.length}`);
    return result;
  };
  return Object.assign(call, { calls });
}
