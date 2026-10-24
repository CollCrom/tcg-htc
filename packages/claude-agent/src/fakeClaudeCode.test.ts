import { describe, expect, it } from "vitest";
import type { CallRequest, CallResult } from "./claudeCode.js";
import { fakeClaudeCode } from "./fakeClaudeCode.js";

const request = (message: string): CallRequest => ({
  systemPrompt: "You are Seat 0.",
  message,
  schema: { type: "object" },
  config: { model: "opus", effort: "medium" },
  resultsDir: "/nowhere",
});

const answer = (n: number): CallResult => ({
  kind: "answer",
  output: { n },
  turns: 1,
  usage: { model: "fake", inputTokens: 1, cachedTokens: 0, outputTokens: 1, costUsd: 0, latencyMs: 1 },
});

describe("fakeClaudeCode", () => {
  it("returns the scripted results in order and records every call", async () => {
    const call = fakeClaudeCode([answer(1), { kind: "rate-limit", detail: "You've hit your limit" }]);

    expect(await call(request("first"))).toEqual(answer(1));
    expect(await call(request("second"))).toEqual({ kind: "rate-limit", detail: "You've hit your limit" });
    expect(call.calls).toEqual([
      { systemPrompt: "You are Seat 0.", message: "first", schema: { type: "object" }, config: { model: "opus", effort: "medium" } },
      { systemPrompt: "You are Seat 0.", message: "second", schema: { type: "object" }, config: { model: "opus", effort: "medium" } },
    ]);
  });

  it("answers from a function of the request and the call index", async () => {
    const call = fakeClaudeCode((request, index) => (request.message === "second" ? { kind: "refusal", detail: "no" } : answer(index)));
    expect(await call(request("first"))).toEqual(answer(0));
    expect(await call(request("second"))).toEqual({ kind: "refusal", detail: "no" });
    expect(await call(request("third"))).toEqual(answer(2));
    expect(call.calls.map(({ message }) => message)).toEqual(["first", "second", "third"]);
  });

  it("throws when the script is exhausted", async () => {
    const call = fakeClaudeCode([answer(1)]);
    await call(request("first"));

    await expect(call(request("second"))).rejects.toThrow("fakeClaudeCode has no result left for call 2");
  });
});
