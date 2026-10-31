// A scripted stand-in for the Claude Code call, so Games run offline in tests.
import type { CallRequest, CallResult, ClaudeCodeCall } from "./claudeCode.js";

/** What the fake records of each call: everything in the request but the
 * results directory. */
export type RecordedCall = Pick<CallRequest, "systemPrompt" | "message" | "schema" | "config">;

/** A script for the fake: the results in order, or a function of each call
 * (the request and its 0-based index) when a whole Game's worth is needed. */
export type FakeScript = readonly CallResult[] | ((request: RecordedCall, index: number) => CallResult);

export interface FakeClaudeCode extends ClaudeCodeCall {
  /** Every call so far, in order. */
  calls: RecordedCall[];
}

/** A call that answers from `script`, recording what it was sent. A list is
 * returned in order and throws once it runs out. */
export function fakeClaudeCode(script: FakeScript): FakeClaudeCode {
  const remaining = typeof script === "function" ? undefined : [...script];
  const calls: RecordedCall[] = [];
  const call = async ({ systemPrompt, message, schema, config }: CallRequest): Promise<CallResult> => {
    const recorded = { systemPrompt, message, schema, config };
    calls.push(recorded);
    if (typeof script === "function") return script(recorded, calls.length - 1);
    const result = remaining!.shift();
    if (!result) throw new Error(`fakeClaudeCode has no result left for call ${calls.length}`);
    return result;
  };
  return Object.assign(call, { calls });
}
