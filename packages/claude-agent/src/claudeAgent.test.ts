// The Claude Agent, driven through whole Games with the Claude Code call faked.
import { BRAVO_LIST_FILE, fixtureList, IRA_LIST_FILE, pickDecklist, randomAgent, runGame } from "@tcg-htc/runner";
import { describe, expect, it } from "vitest";
import type { CallResult } from "./claudeCode.js";
import { claudeAgent } from "./claudeAgent.js";
import { fakeClaudeCode, type RecordedCall } from "./fakeClaudeCode.js";

const SEED = 21;
const decklists = [pickDecklist(fixtureList(IRA_LIST_FILE), SEED), pickDecklist(fixtureList(BRAVO_LIST_FILE), SEED)] as const;
const GAME_TIMEOUT = 30_000;

const usage = { model: "claude-opus-4-1", inputTokens: 100, cachedTokens: 2000, outputTokens: 40, costUsd: 0.01, latencyMs: 1500 };

/** A scripted answer: the Intent number, with reasoning and Plan notes. */
const answer = (intent: unknown, planNotes = "keep pressure on", reasoning = "the first listed Intent looks fine"): CallResult => ({
  kind: "answer",
  output: { intent, reasoning, planNotes },
  turns: 2,
  usage,
});

/** How many Intents a decision message lists. */
function listedIntents({ message }: RecordedCall): number {
  const lines = message.split("\n");
  return lines.slice(lines.indexOf("Legal Intents:") + 1).filter((line) => /^\d+\. /.test(line)).length;
}

/** Answers a different listed Intent each call, so the Game moves along. */
const varied = (request: RecordedCall, index: number): CallResult => answer(1 + (index % listedIntents(request)));

describe("claudeAgent", () => {
  it(
    "plays a complete Game against the random Agent, one call per decision",
    async () => {
      const fake = fakeClaudeCode(varied);
      const agent = claudeAgent({ seat: 0, decklist: decklists[0], model: "opus", effort: "medium" }, fake);

      const result = await runGame({ decklists, seed: SEED, startingSeat: 0, agents: [agent, randomAgent] });

      expect(result.outcome, JSON.stringify(result.outcome === "error" ? result.detail : "")).toMatch(/^(win|draw)$/);
      const own = result.decisions.filter(({ seat }) => seat === 0);
      expect(own.length).toBeGreaterThan(0);
      expect(fake.calls).toHaveLength(own.length);
      for (const call of fake.calls) expect(call.config).toEqual({ model: "opus", effort: "medium" });
    },
    GAME_TIMEOUT,
  );
});
