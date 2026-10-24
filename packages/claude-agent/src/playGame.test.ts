// playGame, driven with fake-backed Claude Agents in both Seats: the Game file
// it writes as the Game goes, and what the file holds at the end.
import { BRAVO_LIST_FILE, fixtureList, IRA_LIST_FILE, replayGame, type DecisionRecord } from "@tcg-htc/runner";
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import type { CallResult, ClaudeConfig } from "./claudeCode.js";
import { fakeClaudeCode, type RecordedCall } from "./fakeClaudeCode.js";
import { gameFileName, readGameFile, type GameFile } from "./gameFile.js";
import { playGame, type PlayedGame } from "./playGame.js";

const SEED = 31;
const GAME_TIMEOUT = 60_000;
const lists = [fixtureList(IRA_LIST_FILE), fixtureList(BRAVO_LIST_FILE)] as const;
const configs: readonly [ClaudeConfig, ClaudeConfig] = [
  { model: "opus", effort: "medium" },
  { model: "sonnet", effort: "low" },
];
const usage = { model: "claude-opus-4-1", inputTokens: 100, cachedTokens: 2000, outputTokens: 40, costUsd: 0.01, latencyMs: 1500 };

const answer = (intent: unknown, planNotes = "keep pressure on"): CallResult => ({
  kind: "answer",
  output: { intent, reasoning: "the listed Intent looks fine", planNotes },
  turns: 2,
  usage,
});

/** How many Intents a decision message lists. */
function listedIntents({ message }: RecordedCall): number {
  const lines = message.split("\n");
  return lines.slice(lines.indexOf("Legal Intents:") + 1).filter((line) => /^\d+\. /.test(line)).length;
}

/** Answers a different listed Intent each call, so the Game moves along. */
const varied = (request: RecordedCall, index: number): CallResult => answer(1 + (index % listedIntents(request)), `plan ${index}`);

const tempDirs: string[] = [];
function tempRunDir(): string {
  const dir = mkdtempSync(join(tmpdir(), "tcg-htc-run-"));
  tempDirs.push(dir);
  return dir;
}
afterAll(() => {
  for (const dir of tempDirs) rmSync(dir, { recursive: true, force: true });
});

/** The files on disk seen from inside `onDecision`, at some steps. */
interface Snapshot {
  step: number;
  onDisk: GameFile;
  handed: GameFile;
}

let completed: Promise<{ played: PlayedGame; runDir: string; snapshots: Snapshot[] }> | undefined;
/** One complete Game, played once and shared by the tests that read its file. */
function completeGame() {
  completed ??= (async () => {
    const runDir = tempRunDir();
    const snapshots: Snapshot[] = [];
    const played = await playGame({
      seed: SEED,
      lists,
      configs,
      call: fakeClaudeCode(varied),
      runDir,
      onDecision: (_record, progress, written) => {
        if (progress.step < 2 || progress.step % 25 === 0) {
          snapshots.push({ step: progress.step, onDisk: readGameFile(written.path), handed: written.file });
        }
      },
    });
    return { played, runDir, snapshots };
  })();
  return completed;
}

describe("playGame", () => {
  it(
    "writes the Game file after the first decision and rewrites it after every decision",
    async () => {
      const { played, runDir, snapshots } = await completeGame();

      expect(played.result.outcome, JSON.stringify(played.result.outcome === "error" ? played.result.detail : "")).toMatch(/^(win|draw)$/);
      expect(played.path).toBe(join(runDir, gameFileName(SEED, lists[0].hero.name)));
      expect(gameFileName(SEED, lists[0].hero.name)).toBe("game-31-ira-first.json");
      expect(snapshots.length).toBeGreaterThan(2);
      for (const { step, onDisk, handed } of snapshots) {
        expect(onDisk).toEqual(handed);
        expect(onDisk.status).toBe("playing");
        expect(onDisk.decisions).toHaveLength(step + 1);
        expect(onDisk.replay.intents).toHaveLength(step + 1);
        expect(onDisk.outcome).toBeUndefined();
        expect(onDisk.decisions).toEqual(played.result.decisions.slice(0, step + 1));
        expect(onDisk.measurements.decisions).toEqual(played.result.measurements.decisions.slice(0, step + 1));
        expect(onDisk.measurements.totals.decisions).toBe(step + 1);
      }
      expect(readdirSync(runDir).filter((name) => name.endsWith(".tmp"))).toEqual([]);
    },
    GAME_TIMEOUT,
  );

  it(
    "ends with a complete file: setup, both system prompts once, the replay, the outcome, measurements and every Decision record",
    async () => {
      const { played } = await completeGame();
      const { result } = played;
      const file = readGameFile(played.path);

      expect(file).toEqual(played.file);
      expect(file.status).toBe("complete");
      expect(file.setup).toEqual({
        seed: SEED,
        startingSeat: 0,
        lists: [lists[0].name, lists[1].name],
        heroes: ["Ira, Crimson Haze", "Bravo, Flattering Showman"],
        decklists: result.replay.decklists,
        configs,
      });
      expect(file.systemPrompts[0]).toBe(played.agents[0].systemPrompt);
      expect(file.systemPrompts[1]).toBe(played.agents[1].systemPrompt);
      expect(file.systemPrompts[0]).toContain("You are Seat 0.");
      expect(file.systemPrompts[1]).toContain("You are Seat 1.");
      const encodedPrompt = JSON.stringify(file.systemPrompts[0]).slice(1, -1);
      expect(readFileSync(played.path, "utf8").split(encodedPrompt)).toHaveLength(2);
      expect(file.replay).toEqual(result.replay);
      expect(file.replay.intents).toHaveLength(result.steps);
      expect(replayGame(file.replay)).toEqual(result.finalProjection);
      expect(file.outcome).toEqual(result.outcome === "win" ? { outcome: "win", winner: result.winner } : { outcome: "draw" });
      expect(file.turns).toBe(result.turns);
      expect(file.decisions).toEqual(result.decisions);
      expect(file.decisions.map(({ decision }) => "planNotes" in decision && decision.planNotes)).toEqual(result.decisions.map((_, i) => `plan ${i}`));
      expect(file.measurements).toMatchObject(result.measurements);
      const total = result.decisions.length;
      const perSeat = (seat: 0 | 1) => result.decisions.filter((record) => record.seat === seat).length;
      expect(file.measurements.totals).toEqual({
        decisions: total,
        inputTokens: 100 * total,
        cachedTokens: 2000 * total,
        outputTokens: 40 * total,
        latencyMs: 1500 * total,
        costUsd: expect.closeTo(0.01 * total, 6),
        retries: 0,
        invalidFirstAnswers: 0,
        notesCut: 0,
      });
      expect(file.measurements.perSeat.map(({ decisions }) => decisions)).toEqual([perSeat(0), perSeat(1)]);
      expect(file.measurements.perSeat[1].inputTokens).toBe(100 * perSeat(1));
    },
    GAME_TIMEOUT,
  );

  it(
    "leaves a complete file with the error outcome when an Agent fails",
    async () => {
      const runDir = tempRunDir();
      const script = (request: RecordedCall, index: number): CallResult =>
        index === 5 ? answer(99) : index === 6 ? answer("none") : varied(request, index);
      const seen: DecisionRecord[] = [];

      const played = await playGame({ seed: SEED, lists: [lists[1], lists[0]], configs, call: fakeClaudeCode(script), runDir, onDecision: (record) => seen.push(record) });

      const file = readGameFile(played.path);
      expect(played.path).toBe(join(runDir, "game-31-bravo-first.json"));
      expect(played.result).toMatchObject({ outcome: "error", cause: "invalid-answer", step: 5, steps: 5 });
      expect(file.status).toBe("complete");
      expect(file.outcome).toEqual({ outcome: "error", seed: SEED, step: 5, detail: expect.stringContaining("Claude Agent"), cause: "invalid-answer" });
      expect(file.decisions).toHaveLength(6);
      expect(file.decisions).toEqual(seen);
      expect(file.replay.intents).toHaveLength(5);
      expect(file.setup.heroes).toEqual(["Bravo, Flattering Showman", "Ira, Crimson Haze"]);
      expect(file.measurements.totals).toMatchObject({ decisions: 6, retries: 1, invalidFirstAnswers: 1, inputTokens: 700 });
      expect(existsSync(`${played.path}.tmp`)).toBe(false);
    },
    GAME_TIMEOUT,
  );
});
