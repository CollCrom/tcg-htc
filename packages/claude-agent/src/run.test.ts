// runSuite, driven with fake-backed Claude Agents: the manifest it keeps, the
// concurrency it honours, the decision cap, and what an exception does.
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { DECKLIST_SCHEMA } from "./buildDecklist.js";
import type { CallResult, ClaudeConfig } from "./claudeCode.js";
import { fakeClaudeCode, type FakeScript, type RecordedCall } from "./fakeClaudeCode.js";
import { heroList } from "./heroLists.js";
import { readManifest, runSuite, type Manifest, type ManifestGame, type RunConfig } from "./run.js";
import { legalPresentation } from "./scriptedBuild.js";
import { listedEntries } from "./scriptedPlay.js";

const RUN_TIMEOUT = 120_000;
const configs: readonly [ClaudeConfig, ClaudeConfig] = [
  { model: "opus", effort: "medium" },
  { model: "sonnet", effort: "low" },
];
const usage = { model: "claude-opus-4-1", inputTokens: 100, cachedTokens: 2000, outputTokens: 40, costUsd: 0.01, latencyMs: 1500 };
const answer = (intent: unknown): CallResult => ({ kind: "answer", output: { intent, reasoning: "fine", planNotes: "" }, turns: 2, usage });

/** The numbered Intent entries a decision message lists, without their numbers. */
const entriesOf = ({ message }: RecordedCall): string[] => listedEntries(message);

const lists = [heroList("ira"), heroList("bravo")];

/** Builds legally for the List the build's system prompt describes (it names
 * no other hero), and leaves every play decision to `play`. */
const building =
  (play: (request: RecordedCall, index: number) => CallResult): ((request: RecordedCall, index: number) => CallResult) =>
  (request, index) => {
    if (request.schema !== DECKLIST_SCHEMA) return play(request, index);
    const list = lists.find(({ hero }) => request.systemPrompt.includes(hero.name));
    if (!list) throw new Error("the build's system prompt names no known hero");
    return { kind: "answer", output: { ...legalPresentation(list), reasoning: "built" }, turns: 2, usage };
  };

/** Answers a different listed Intent each call, so Games move along and end. */
const varied: FakeScript = building((request, index) => answer(1 + (index % entriesOf(request).length)));

/** Passes whenever it can, so the Game never ends and runs into the cap. */
const passing: FakeScript = building((request) => {
  const index = entriesOf(request).findIndex((entry) => entry.startsWith("pass"));
  return answer(index >= 0 ? index + 1 : 1);
});

const tempDirs: string[] = [];
function tempRunDir(): string {
  const dir = mkdtempSync(join(tmpdir(), "tcg-htc-suite-"));
  tempDirs.push(dir);
  return dir;
}
afterAll(() => {
  for (const dir of tempDirs) rmSync(dir, { recursive: true, force: true });
});

const config = (overrides: Partial<RunConfig> = {}): RunConfig => ({
  seeds: [1, 2],
  lists: ["ira", "bravo"],
  configs,
  concurrency: 2,
  maxSteps: 600,
  ...overrides,
});

/** A clock that ticks one second per call, so timestamps are deterministic. */
function ticking(): () => Date {
  let seconds = 0;
  return () => new Date(Date.UTC(2026, 9, 24, 12, 0, seconds++));
}

describe("runSuite", () => {
  it(
    "plays each seed with each List in Seat 0 once, tracks every Game in the manifest on every change, and ends complete",
    async () => {
      const runDir = tempRunDir();
      const changes: { id: string; status: ManifestGame["status"]; run: Manifest["status"]; onDisk: Manifest }[] = [];

      const { manifest, reportPath } = await runSuite({
        config: config(),
        runDir,
        call: fakeClaudeCode(varied),
        now: ticking(),
        onGame: (game, handed) => changes.push({ id: game.id, status: game.status, run: handed.status, onDisk: readManifest(runDir) }),
      });

      expect(manifest.games.map(({ id, seed, first, file }) => ({ id, seed, first, file }))).toEqual([
        { id: "1-ira-first", seed: 1, first: "ira", file: "game-1-ira-first.json" },
        { id: "1-bravo-first", seed: 1, first: "bravo", file: "game-1-bravo-first.json" },
        { id: "2-ira-first", seed: 2, first: "ira", file: "game-2-ira-first.json" },
        { id: "2-bravo-first", seed: 2, first: "bravo", file: "game-2-bravo-first.json" },
      ]);
      expect(manifest.status).toBe("complete");
      expect(manifest.config).toEqual(config());
      expect(manifest.startedAt).toBe("2026-10-24T12:00:00.000Z");
      expect(manifest.updatedAt > manifest.startedAt).toBe(true);
      for (const game of manifest.games) {
        expect(game.status, game.id).toBe("complete");
        expect(game.outcome?.outcome, game.id).toMatch(/^(win|draw)$/);
        expect(game.steps).toBeGreaterThan(10);
        expect(game.startedAt! < game.finishedAt!).toBe(true);
        expect(existsSync(join(runDir, game.file))).toBe(true);
      }
      // Every Game went pending -> playing -> complete, each change written before onGame saw it.
      for (const game of manifest.games) {
        expect(changes.filter(({ id }) => id === game.id).map(({ status }) => status)).toEqual(["playing", "complete"]);
      }
      for (const { onDisk, id, status, run } of changes) {
        expect(onDisk.games.find((game) => game.id === id)?.status).toBe(status);
        expect(onDisk.status).toBe(run);
        expect(run).toBe("running");
      }
      expect(readManifest(runDir)).toEqual(manifest);
      expect(readdirSync(runDir).filter((name) => name.endsWith(".tmp"))).toEqual([]);
      expect(reportPath).toBe(join(runDir, "report.md"));
      expect(readFileSync(reportPath!, "utf8")).toContain("# Phase 2 report");
    },
    RUN_TIMEOUT,
  );

  /** The most Games `playing` at once, seen from inside decisions. */
  async function mostPlaying(concurrency: number): Promise<number> {
    let most = 0;
    await runSuite({
      config: config({ concurrency }),
      runDir: tempRunDir(),
      call: fakeClaudeCode(varied),
      onDecision: (_record, _progress, { manifest }) => {
        most = Math.max(most, manifest.games.filter(({ status }) => status === "playing").length);
      },
    });
    return most;
  }

  it(
    "plays at most `concurrency` Games at once: two by default, one when asked",
    async () => {
      expect(await mostPlaying(2)).toBe(2);
      expect(await mostPlaying(1)).toBe(1);
    },
    RUN_TIMEOUT,
  );

  it(
    "ends a Game over the decision cap as a stall, listed as failed with its seed and step, and still completes the Run",
    async () => {
      const runDir = tempRunDir();

      const { manifest } = await runSuite({ config: config({ seeds: [3], maxSteps: 50 }), runDir, call: fakeClaudeCode(passing) });

      expect(manifest.status).toBe("complete");
      expect(manifest.games.map(({ id, status, steps, outcome }) => ({ id, status, steps, outcome }))).toEqual([
        { id: "3-ira-first", status: "failed", steps: 50, outcome: { outcome: "stall", seed: 3, step: 50, detail: "Game exceeded 50 steps" } },
        { id: "3-bravo-first", status: "failed", steps: 50, outcome: { outcome: "stall", seed: 3, step: 50, detail: "Game exceeded 50 steps" } },
      ]);
      expect(readFileSync(join(runDir, "report.md"), "utf8")).toContain("3-bravo-first");
    },
    RUN_TIMEOUT,
  );

  it(
    "records a Game whose call throws as failed with an error outcome carrying the message, and still completes the Run",
    async () => {
      const runDir = tempRunDir();
      const call = fakeClaudeCode(() => {
        throw new Error("spawn claude ENOENT");
      });

      const { manifest, gameFiles } = await runSuite({ config: config({ seeds: [4], concurrency: 1 }), runDir, call });

      expect(manifest.status).toBe("complete");
      for (const game of manifest.games) {
        expect(game.status).toBe("failed");
        expect(game.outcome).toEqual({ outcome: "error", seed: 4, step: 0, detail: "spawn claude ENOENT" });
        expect(game.finishedAt).toBeDefined();
      }
      expect(gameFiles).toEqual({});
      expect(existsSync(join(runDir, "report.md"))).toBe(true);
    },
    RUN_TIMEOUT,
  );
});
