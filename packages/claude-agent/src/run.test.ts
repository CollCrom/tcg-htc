// runSuite, driven with fake-backed Claude Agents: the manifest it keeps, the
// concurrency it honours, the decision cap, and what an exception does.
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import type { CallResult, ClaudeConfig } from "./claudeCode.js";
import { fakeClaudeCode, type RecordedCall } from "./fakeClaudeCode.js";
import { readManifest, runSuite, type Manifest, type ManifestGame, type RunConfig } from "./run.js";

const RUN_TIMEOUT = 120_000;
const configs: readonly [ClaudeConfig, ClaudeConfig] = [
  { model: "opus", effort: "medium" },
  { model: "sonnet", effort: "low" },
];
const usage = { model: "claude-opus-4-1", inputTokens: 100, cachedTokens: 2000, outputTokens: 40, costUsd: 0.01, latencyMs: 1500 };
const answer = (intent: unknown): CallResult => ({ kind: "answer", output: { intent, reasoning: "fine", planNotes: "" }, turns: 2, usage });

/** The numbered Intent entries a decision message lists, without their numbers. */
function entriesOf({ message }: RecordedCall): string[] {
  const lines = message.split("\n");
  return lines.slice(lines.indexOf("Legal Intents:") + 1).filter((line) => /^\d+\. /.test(line)).map((line) => line.replace(/^\d+\. /, ""));
}

/** Answers a different listed Intent each call, so Games move along and end. */
const varied = (request: RecordedCall, index: number): CallResult => answer(1 + (index % entriesOf(request).length));

/** Passes whenever it can, so the Game never ends and runs into the cap. */
const passing = (request: RecordedCall): CallResult => {
  const index = entriesOf(request).findIndex((entry) => entry.startsWith("pass"));
  return answer(index >= 0 ? index + 1 : 1);
};

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
      expect(readFileSync(reportPath, "utf8")).toContain("# Phase 2 report");
    },
    RUN_TIMEOUT,
  );
});
