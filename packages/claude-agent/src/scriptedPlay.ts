// A scripted Claude Code call whose answers are a pure function of the
// request, for tests that pause and resume a Run: a resumed Game asks the same
// questions as an uninterrupted one, so it must get the same answers. A build
// is answered legally for the List the system prompt describes; a play
// decision with a listed Intent, and Plan notes, chosen by a hash of the
// message. Not what the Agent would choose.
import type { List } from "@tcg-htc/runner";
import { DECKLIST_SCHEMA } from "./buildDecklist.js";
import type { CallResult, Usage } from "./claudeCode.js";
import type { RecordedCall } from "./fakeClaudeCode.js";
import { legalPresentation } from "./scriptedBuild.js";

export const SCRIPTED_USAGE: Usage = { model: "claude-opus-4-1", inputTokens: 100, cachedTokens: 2000, outputTokens: 40, costUsd: 0.01, latencyMs: 1500 };

/** The numbered Intent entries a decision message lists, without their numbers. */
export function listedEntries(message: string): string[] {
  const lines = message.split("\n");
  return lines
    .slice(lines.indexOf("Legal Intents:") + 1)
    .filter((line) => /^\d+\. /.test(line))
    .map((line) => line.replace(/^\d+\. /, ""));
}

/** A pure answer to a request. The system prompt of a build names the hero of
 * exactly one of `lists`. */
export function scriptedAnswer(lists: readonly List[], request: RecordedCall): CallResult {
  if (request.schema === DECKLIST_SCHEMA) {
    const list = lists.find(({ hero }) => request.systemPrompt.includes(hero.name));
    if (!list) throw new Error("the build's system prompt names no known hero");
    return { kind: "answer", output: { ...legalPresentation(list), reasoning: "built" }, turns: 2, usage: SCRIPTED_USAGE };
  }
  const entries = listedEntries(request.message);
  // Staging a defender toggles it, so a pure choice could cycle through the
  // same staging forever; anything else moves the Game along.
  const candidates = entries.map((entry, i) => (entry.startsWith("stage ") ? -1 : i + 1)).filter((n) => n > 0);
  const numbered = candidates.length > 0 ? candidates : entries.map((_, i) => i + 1);
  const seed = hash(request.message);
  return {
    kind: "answer",
    output: { intent: numbered[seed % numbered.length], reasoning: "scripted", planNotes: `plan ${seed % 97}` },
    turns: 2,
    usage: SCRIPTED_USAGE,
  };
}

/** FNV-1a over the text, as a non-negative integer. */
export function hash(text: string): number {
  let value = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    value ^= text.charCodeAt(i);
    value = Math.imul(value, 0x01000193);
  }
  return value >>> 0;
}
