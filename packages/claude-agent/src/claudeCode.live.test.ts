// The one real Claude Code call. Opt in with TCG_HTC_LIVE_CLAUDE=1 on a machine
// whose `claude` is logged in; it spends the subscription, so CI never sets it.
//
//   TCG_HTC_LIVE_CLAUDE=1 pnpm --dir packages/claude-agent exec vitest run src/claudeCode.live.test.ts
//
// It checks the wire format: that the flags are accepted, that structured
// output comes back within the turn cap, and which fields the result carries.

import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { classify, MAX_TURNS, runClaudeCode } from "./claudeCode.js";

const live = process.env.TCG_HTC_LIVE_CLAUDE === "1";
const resultsDir = mkdtempSync(join(tmpdir(), "claude-code-live-"));
afterAll(() => rmSync(resultsDir, { recursive: true, force: true }));

/** The keys and value types of a JSON result, to record the shape without its
 * contents. Values are kept only for the fields that classify the result. */
function shapeOf(value: unknown, path = ""): string[] {
  if (!value || typeof value !== "object") return [`${path}: ${typeof value}`];
  const kept = new Set(["type", "subtype", "is_error", "num_turns"]);
  return Object.entries(value).flatMap(([key, child]) => {
    const here = path ? `${path}.${key}` : key;
    if (child && typeof child === "object") return shapeOf(child, here);
    return [`${here}: ${kept.has(key) ? JSON.stringify(child) : typeof child}`];
  });
}

describe.skipIf(!live)("claude -p, live", () => {
  it(
    "answers a tiny schema within the turn cap and reports usage",
    async () => {
      const run = await runClaudeCode({
        systemPrompt: "You answer arithmetic questions. Reply only with the structured output asked for.",
        message: "What is 3 + 4? Give the answer as n.",
        schema: { type: "object", properties: { n: { type: "integer" } }, required: ["n"] },
        config: { model: "haiku", effort: "low" },
        resultsDir,
      });
      console.log(`exit ${run.exitCode}, ${run.latencyMs} ms, stderr: ${JSON.stringify(run.stderr)}`);
      console.log(shapeOf(JSON.parse(run.stdout)).join("\n"));

      const result = classify(run);
      expect(result.kind).toBe("answer");
      if (result.kind !== "answer") return;
      expect(result.output).toEqual({ n: 7 });
      // The live result carries num_turns; two turns (the answer, then the StructuredOutput tool) must suffice.
      expect(result.turns).toBeDefined();
      expect(result.turns).toBeLessThanOrEqual(MAX_TURNS);
      for (const field of ["inputTokens", "cachedTokens", "outputTokens", "costUsd", "latencyMs"] as const) {
        expect(typeof result.usage[field]).toBe("number");
      }
      expect(result.usage.model).toMatch(/haiku/);
    },
    5.5 * 60_000,
  );
});
