// The Agent builds its Decklist: driven through playGame with the Claude Code
// call faked, asserting on the calls the fake records and the Game file.
import { cardData, validatePresentation } from "@fyendal/cards";
import { BRAVO_LIST_FILE, fixtureList, IRA_LIST_FILE, toUpstreamList } from "@tcg-htc/runner";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { DECKLIST_SCHEMA } from "./buildDecklist.js";
import type { CallResult, ClaudeConfig } from "./claudeCode.js";
import { fakeClaudeCode, type RecordedCall } from "./fakeClaudeCode.js";
import { readGameFile } from "./gameFile.js";
import { playGame } from "./playGame.js";
import { legalPresentation } from "./scriptedBuild.js";

const SEED = 41;
const GAME_TIMEOUT = 60_000;
const lists = [fixtureList(IRA_LIST_FILE), fixtureList(BRAVO_LIST_FILE)] as const;
const configs: readonly [ClaudeConfig, ClaudeConfig] = [
  { model: "opus", effort: "medium" },
  { model: "sonnet", effort: "low" },
];
const usage = { model: "claude-opus-4-1", inputTokens: 100, cachedTokens: 2000, outputTokens: 40, costUsd: 0.01, latencyMs: 1500 };

/** A scripted build answer: the presentation, with reasoning. */
const built = (presented: object, reasoning = "aggressive red build"): CallResult => ({ kind: "answer", output: { ...presented, reasoning }, turns: 2, usage });

const answer = (intent: unknown): CallResult => ({
  kind: "answer",
  output: { intent, reasoning: "the listed Intent looks fine", planNotes: "keep pressure on" },
  turns: 2,
  usage,
});

function listedIntents({ message }: RecordedCall): number {
  const lines = message.split("\n");
  return lines.slice(lines.indexOf("Legal Intents:") + 1).filter((line) => /^\d+\. /.test(line)).length;
}

/** Builds legally at the first two calls, then answers a different listed Intent each call. */
const buildsThenPlays = (request: RecordedCall, index: number): CallResult =>
  index < 2 ? built(legalPresentation(lists[index as 0 | 1])) : answer(1 + (index % listedIntents(request)));

const tempDirs: string[] = [];
function tempRunDir(): string {
  const dir = mkdtempSync(join(tmpdir(), "tcg-htc-build-"));
  tempDirs.push(dir);
  return dir;
}
afterAll(() => {
  for (const dir of tempDirs) rmSync(dir, { recursive: true, force: true });
});

describe("the Agent builds its Decklist", () => {
  it(
    "makes one build call per Seat before any play call, from the List and the opponent's hero name only",
    async () => {
      const fake = fakeClaudeCode(buildsThenPlays);

      const played = await playGame({ seed: SEED, lists, configs, call: fake, runDir: tempRunDir() });

      expect(played.result.outcome, JSON.stringify(played.result.outcome === "error" ? played.result.detail : "")).toMatch(/^(win|draw)$/);
      const [ira, bravo] = fake.calls;
      expect(ira!.schema).toBe(DECKLIST_SCHEMA);
      expect(bravo!.schema).toBe(DECKLIST_SCHEMA);
      expect(ira!.config).toEqual(configs[0]);
      expect(bravo!.config).toEqual(configs[1]);
      expect(ira!.message).toContain("Bravo, Flattering Showman");
      expect(bravo!.message).toContain("Ira, Crimson Haze");
      expect(ira!.message).not.toContain(lists[1].name);
      expect(ira!.message).not.toContain("Chokeslam");
      // The whole List, with printing ids: the card text is in the system prompt.
      expect(ira!.systemPrompt).toContain("# Flesh and Blood: rules primer");
      expect(ira!.systemPrompt).toContain("You are Seat 0.");
      expect(ira!.systemPrompt).toContain("{p} power");
      for (const card of [...lists[0].weapons, ...lists[0].equipment, ...lists[0].deck]) {
        expect(ira!.systemPrompt).toContain(`[${card.cardId}]`);
        expect(ira!.systemPrompt).toContain(cardData[card.cardId]!.text.trim().split("\n")[0]);
      }
      const flyingKick = lists[0].deck.find((card) => card.name === "Flying Kick" && card.colour === "red")!;
      expect(ira!.systemPrompt).toContain(`[${flyingKick.cardId}] 2 copies: Flying Kick (red): ninja action - attack. Cost 2, pitch 1, attack 5, defense 3.`);
      const helm = lists[0].equipment.find((piece) => piece.name === "Blade Beckoner Helm")!;
      expect(ira!.systemPrompt).toContain(`[${helm.cardId}] head: Blade Beckoner Helm`);
      expect(ira!.systemPrompt).toContain("`weaponIds`");
      expect(ira!.systemPrompt).toContain("`deck`");
      expect(ira!.systemPrompt).not.toContain("Bravo");
      expect(fake.calls[2]!.schema).not.toBe(DECKLIST_SCHEMA);
    },
    GAME_TIMEOUT,
  );

  it(
    "plays the Game with the built Decklists and records both builds in the Game file before the play records",
    async () => {
      const fake = fakeClaudeCode(buildsThenPlays);

      const played = await playGame({ seed: SEED, lists, configs, call: fake, runDir: tempRunDir() });

      const file = readGameFile(played.path);
      expect(file).toEqual(played.file);
      const expected = lists.map((list) => validatePresentation(toUpstreamList(list), legalPresentation(list), list.format));
      expect(file.setup.decklists).toEqual(expected.map((result) => result.ok && result.decklist));
      expect("replay" in played.result && played.result.replay.decklists).toEqual(file.setup.decklists);
      expect(file.decklistDecisions).toHaveLength(2);
      file.decklistDecisions.forEach((record, seat) => {
        expect(record).toEqual({
          kind: "decklist",
          seat,
          systemPrompt: fake.calls[seat]!.systemPrompt,
          message: fake.calls[seat]!.message,
          decision: {
            presented: legalPresentation(lists[seat as 0 | 1]),
            decklist: file.setup.decklists![seat as 0 | 1],
            reasoning: "aggressive red build",
            measurements: {
              model: usage.model,
              effort: configs[seat as 0 | 1].effort,
              inputTokens: 100,
              cachedTokens: 2000,
              outputTokens: 40,
              latencyMs: 1500,
              retries: 0,
              firstAnswerInvalid: false,
              costUsd: 0.01,
            },
          },
        });
      });
      expect(file.decisions.length).toBe(fake.calls.length - 2);
      expect(file.measurements.builds).toEqual({
        decisions: 2,
        inputTokens: 200,
        cachedTokens: 4000,
        outputTokens: 80,
        latencyMs: 3000,
        costUsd: expect.closeTo(0.02, 6),
        retries: 0,
        invalidFirstAnswers: 0,
        notesCut: 0,
      });
      expect(file.measurements.totals.decisions).toBe(file.decisions.length);
      // The Game file's order: the builds come before the play records.
      const text = JSON.stringify(file);
      expect(text.indexOf('"decklistDecisions"')).toBeLessThan(text.indexOf('"decisions"'));
    },
    GAME_TIMEOUT,
  );
});
