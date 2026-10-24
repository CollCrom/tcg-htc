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

describe("an invalid build", () => {
  const short = (list: typeof lists[number]) => {
    const presented = legalPresentation(list);
    return { ...presented, deck: presented.deck.slice(0, 39) };
  };

  it(
    "is retried once with the validation error, and a valid retry starts the Game",
    async () => {
      const fake = fakeClaudeCode((request, index) => (index === 1 ? built(short(lists[1])) : index === 2 ? built(legalPresentation(lists[1]), "fixed") : buildsThenPlays(request, index - (index > 2 ? 1 : 0))));

      const played = await playGame({ seed: SEED, lists, configs, call: fake, runDir: tempRunDir() });

      expect(played.result.outcome, JSON.stringify(played.result.outcome === "error" ? played.result.detail : "")).toMatch(/^(win|draw)$/);
      expect(fake.calls[2]!.schema).toBe(DECKLIST_SCHEMA);
      expect(fake.calls[2]!.systemPrompt).toBe(fake.calls[1]!.systemPrompt);
      expect(fake.calls[2]!.message).toBe(
        `${fake.calls[1]!.message}\n\nYour previous answer was not accepted. Answer again, fixing this problem:\nYour build is not legal: main deck must be exactly 40 cards for silver-age (39 presented)`,
      );
      const file = readGameFile(played.path);
      expect(file.decklistDecisions[1]!.decision).toMatchObject({
        reasoning: "fixed",
        measurements: { retries: 1, firstAnswerInvalid: true, inputTokens: 200, latencyMs: 3000 },
      });
      expect(file.measurements.builds).toMatchObject({ decisions: 2, retries: 1, invalidFirstAnswers: 1, inputTokens: 300 });
    },
    GAME_TIMEOUT,
  );

  it(
    "twice ends the Game as an error before any Intent, recorded in a complete Game file with no play records",
    async () => {
      const fake = fakeClaudeCode((request, index) => (index === 0 ? built(short(lists[0])) : index === 1 ? built({ ...legalPresentation(lists[0]), weaponIds: [] }) : buildsThenPlays(request, index)));

      const played = await playGame({ seed: SEED, lists, configs, call: fake, runDir: tempRunDir() });

      expect(fake.calls).toHaveLength(2);
      expect(played.result).toEqual({
        outcome: "error",
        cause: "invalid-answer",
        seed: SEED,
        step: 0,
        detail: expect.stringMatching(/^Seat 0's Claude Agent \(opus, medium\): Your build is not legal: /),
        turns: 0,
        steps: 0,
        measurements: { decisionsPerSeat: [0, 0], decisions: [], durationMs: expect.any(Number) },
        decisions: [],
      });
      expect(played.agents).toBeUndefined();
      const detail = played.result.outcome === "error" ? played.result.detail : "";
      const file = readGameFile(played.path);
      expect(file).toEqual(played.file);
      expect(file.status).toBe("complete");
      expect(file.outcome).toEqual({ outcome: "error", cause: "invalid-answer", seed: SEED, step: 0, detail });
      expect(file.setup).toEqual({ seed: SEED, startingSeat: 0, lists: [lists[0].name, lists[1].name], heroes: ["Ira, Crimson Haze", "Bravo, Flattering Showman"], configs });
      expect(file.systemPrompts).toBeUndefined();
      expect(file.replay).toBeUndefined();
      expect(file.decisions).toEqual([]);
      expect(file.decklistDecisions).toHaveLength(1);
      expect(file.decklistDecisions[0]).toMatchObject({
        kind: "decklist",
        seat: 0,
        message: fake.calls[0]!.message,
        decision: { cause: "invalid-answer", detail, measurements: { retries: 1, firstAnswerInvalid: true, inputTokens: 200 } },
      });
      expect(file.measurements.builds).toMatchObject({ decisions: 1, retries: 1, invalidFirstAnswers: 1 });
      expect(file.measurements.totals.decisions).toBe(0);
    },
    GAME_TIMEOUT,
  );

  for (const kind of ["refusal", "timeout", "failure"] as const) {
    it(
      `a ${kind} of the build call is retried once with the same message, then ends the Game with that cause`,
      async () => {
        const once = fakeClaudeCode((request, index) => (index === 0 ? { kind, detail: `${kind} detail` } : buildsThenPlays(request, index === 1 ? 0 : index - 1)));
        const recovered = await playGame({ seed: SEED, lists, configs, call: once, runDir: tempRunDir() });
        expect(recovered.result.outcome).toMatch(/^(win|draw)$/);
        expect(once.calls[1]!.message).toBe(once.calls[0]!.message);
        expect(recovered.file.decklistDecisions[0]!.decision).toMatchObject({ measurements: { retries: 1, firstAnswerInvalid: false, inputTokens: 100 } });

        const twice = fakeClaudeCode([{ kind, detail: `${kind} detail` }, { kind, detail: `${kind} again` }]);
        const failedGame = await playGame({ seed: SEED, lists, configs, call: twice, runDir: tempRunDir() });
        expect(failedGame.result).toMatchObject({ outcome: "error", cause: kind, step: 0, detail: `Seat 0's Claude Agent (opus, medium): ${kind} again` });
        expect(failedGame.file.decklistDecisions[0]!.decision).toMatchObject({ cause: kind, measurements: { retries: 1, inputTokens: 0 } });
      },
      GAME_TIMEOUT,
    );
  }

  it(
    "a rate limit pauses the Game at once, without a retry, keeping the valid build",
    async () => {
      const fake = fakeClaudeCode((request, index) => (index === 1 ? { kind: "rate-limit", detail: "You've hit your limit" } : buildsThenPlays(request, index)));

      const played = await playGame({ seed: SEED, lists, configs, call: fake, runDir: tempRunDir() });

      expect(fake.calls).toHaveLength(2);
      expect(played.result).toMatchObject({ outcome: "paused", cause: "rate-limit", step: 0, detail: "Seat 1's Claude Agent (sonnet, low): You've hit your limit" });
      expect(played.file.status).toBe("paused");
      expect(played.file.outcome).toBeUndefined();
      expect(played.file.decklistDecisions).toHaveLength(2);
      expect(played.file.decklistDecisions[0]!.decision).toMatchObject({ reasoning: "aggressive red build" });
      expect(played.file.decklistDecisions[1]!.decision).toMatchObject({ cause: "rate-limit", measurements: { retries: 0 } });
    },
    GAME_TIMEOUT,
  );
});

describe("the Decklist is built afresh", () => {
  /** Builds legally whenever asked to, from the Seat the system prompt names; plays otherwise. */
  const bySchema = (request: RecordedCall, index: number): CallResult =>
    request.schema === DECKLIST_SCHEMA
      ? built(legalPresentation(request.systemPrompt.includes("You are Seat 0.") ? lists[0] : lists[1]))
      : answer(1 + (index % listedIntents(request)));

  it(
    "for every Game: two Games with the same seed and heroes make two separate build calls each",
    async () => {
      const fake = fakeClaudeCode(bySchema);
      const first = await playGame({ seed: SEED, lists, configs, call: fake, runDir: tempRunDir() });
      const firstCalls = fake.calls.length;

      const second = await playGame({ seed: SEED, lists, configs, call: fake, runDir: tempRunDir() });

      expect(first.result.outcome).toMatch(/^(win|draw)$/);
      expect(second.result.outcome).toMatch(/^(win|draw)$/);
      expect(fake.calls.map(({ schema }, i) => (schema === DECKLIST_SCHEMA ? i : -1)).filter((i) => i >= 0)).toEqual([0, 1, firstCalls, firstCalls + 1]);
      expect(second.file.decklistDecisions).toEqual(first.file.decklistDecisions);
    },
    2 * GAME_TIMEOUT,
  );
});
