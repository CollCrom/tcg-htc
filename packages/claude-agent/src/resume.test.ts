// A Run pauses on a rate limit and resumes: driven through runSuite and
// resumeSuite with fake-backed Claude Agents whose answers are a pure function
// of the request, so a Run paused and resumed can be checked, Game file by
// Game file, against the same Run played without interruption.
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { DECKLIST_SCHEMA } from "./buildDecklist.js";
import type { CallResult, ClaudeConfig } from "./claudeCode.js";
import { fakeClaudeCode, type RecordedCall } from "./fakeClaudeCode.js";
import { readGameFile, type GameFile } from "./gameFile.js";
import { heroList } from "./heroLists.js";
import { readManifest, resumeSuite, runSuite, type Manifest, type RunConfig, type RunResult } from "./run.js";
import { scriptedAnswer } from "./scriptedPlay.js";

const RUN_TIMEOUT = 180_000;
const lists = [heroList("ira"), heroList("bravo")];
const configs: readonly [ClaudeConfig, ClaudeConfig] = [
  { model: "opus", effort: "medium" },
  { model: "sonnet", effort: "low" },
];
const config = (overrides: Partial<RunConfig> = {}): RunConfig => ({ seeds: [1, 2], lists: ["ira", "bravo"], configs, concurrency: 2, maxSteps: 600, ...overrides });

const pure = (request: RecordedCall): CallResult => scriptedAnswer(lists, request);
/** `pure`, but a rate limit at call `at` (0-based) of this fake. */
const rateLimitedAt = (at: number) => (request: RecordedCall, index: number): CallResult =>
  index === at ? { kind: "rate-limit", detail: "You've hit your limit · resets 3pm" } : pure(request);

const tempDirs: string[] = [];
function tempRunDir(): string {
  const dir = mkdtempSync(join(tmpdir(), "tcg-htc-resume-"));
  tempDirs.push(dir);
  return dir;
}
afterAll(() => {
  for (const dir of tempDirs) rmSync(dir, { recursive: true, force: true });
});

/** What a Game file holds that doesn't depend on when, or in how many
 * sittings, the Game was played: everything but the measurements, without
 * the rate-limit records a pause leaves behind. */
function settled(file: GameFile) {
  const { measurements: _measurements, decisions, decklistDecisions, ...rest } = file;
  const kept = <T extends { decision: object }>(records: readonly T[]) => records.filter(({ decision }) => !("cause" in decision && decision.cause === "rate-limit"));
  return { ...rest, decisions: kept(decisions), decklistDecisions: kept(decklistDecisions) };
}

/** The Game files of a Run, by id, read from disk. */
function filesOf(runDir: string, manifest: Manifest): Record<string, GameFile> {
  return Object.fromEntries(manifest.games.map((game) => [game.id, readGameFile(join(runDir, game.file))]));
}

let whole: Promise<RunResult> | undefined;
/** The two-seed Run played without interruption, for comparison. */
function uninterrupted(): Promise<RunResult> {
  whole ??= runSuite({ config: config(), runDir: tempRunDir(), call: fakeClaudeCode(pure) });
  return whole;
}

describe("a Run pauses on a rate limit", () => {
  it(
    "stops every in-flight Game after its current decision, marks the Run paused with the time and the resume hint, leaves the Games playing with resumable files, and writes no report",
    async () => {
      const runDir = tempRunDir();
      const statuses: { id: string; status: string; run: string }[] = [];

      const result = await runSuite({
        config: config(),
        runDir,
        call: fakeClaudeCode(rateLimitedAt(24)),
        onGame: (game, manifest) => statuses.push({ id: game.id, status: game.status, run: manifest.status }),
      });

      const { manifest } = result;
      expect(manifest.status).toBe("paused");
      expect(manifest.pausedAt).toMatch(/^\d{4}-\d{2}-\d{2}T/);
      expect(manifest.resumeHint).toBe(`pnpm suite:claude --resume ${runDir}`);
      expect(manifest.pauseDetail).toContain("You've hit your limit");
      expect(readManifest(runDir)).toEqual(manifest);
      expect(result.report).toBeUndefined();
      expect(result.reportPath).toBeUndefined();
      expect(existsSync(join(runDir, "report.md"))).toBe(false);
      expect(manifest.games.map(({ status }) => status)).toEqual(["playing", "playing", "pending", "pending"]);
      // Both in-flight Games reported stopping, with the Run already paused on disk by then.
      expect(statuses.map(({ status }) => status)).toEqual(["playing", "playing", "playing", "playing"]);
      expect(statuses.slice(2).map(({ run }) => run)).toEqual(["paused", "paused"]);

      const files = manifest.games.slice(0, 2).map((game) => ({ game, file: readGameFile(join(runDir, game.file)) }));
      const limited = files.filter(({ file }) => file.decisions.some(({ decision }) => "cause" in decision && decision.cause === "rate-limit"));
      const stopped = files.filter((entry) => !limited.includes(entry));
      expect(limited).toHaveLength(1);
      expect(stopped).toHaveLength(1);
      for (const { game, file } of files) {
        expect(file.status).toBe("paused");
        expect(file.outcome).toBeUndefined();
        expect(game.steps).toBe(file.replay!.intents.length);
        expect(game.finishedAt).toBeUndefined();
        expect(game.outcome).toBeUndefined();
        for (const seat of [0, 1] as const) {
          const own = file.decisions.filter((record) => record.seat === seat && "intent" in record.decision);
          expect(own.length, `${game.id} Seat ${seat}`).toBeGreaterThan(0);
          expect(own.at(-1)!.decision).toMatchObject({ planNotes: expect.stringMatching(/^plan \d+$/) });
        }
      }
      // The rate-limited Game's last record is the failure, with no Intent applied for it; the other stopped after a chosen Intent.
      expect(limited[0]!.file.decisions.at(-1)!.decision).toMatchObject({ cause: "rate-limit" });
      expect(limited[0]!.file.decisions).toHaveLength(limited[0]!.file.replay!.intents.length + 1);
      expect(stopped[0]!.file.decisions).toHaveLength(stopped[0]!.file.replay!.intents.length);
      expect(stopped[0]!.file.decisions.at(-1)!.decision).toHaveProperty("intent");
      // Not a complete Game: the uninterrupted Run plays each on much longer.
      const { gameFiles } = await uninterrupted();
      for (const { game, file } of files) expect(file.decisions.length).toBeLessThan(gameFiles[game.id]!.decisions.length);
      // Each Game file shows no in-flight decision: whatever it holds is between decisions.
      expect(manifest.games.slice(2).every(({ file }) => !existsSync(join(runDir, file)))).toBe(true);
    },
    RUN_TIMEOUT,
  );
});

describe("a paused Run resumes", () => {
  it(
    "continues the playing and pending Games to the same final Game files as an uninterrupted Run, with no build call for a built Game, and writes the report",
    async () => {
      const runDir = tempRunDir();
      const paused = await runSuite({ config: config(), runDir, call: fakeClaudeCode(rateLimitedAt(24)) });
      expect(paused.manifest.status).toBe("paused");
      const pausedFiles = filesOf(runDir, { ...paused.manifest, games: paused.manifest.games.slice(0, 2) });
      const fake = fakeClaudeCode(pure);
      const statuses: { id: string; status: string }[] = [];

      const resumed = await resumeSuite({ runDir, call: fake, onGame: (game) => statuses.push({ id: game.id, status: game.status }) });

      const { manifest } = resumed;
      expect(manifest.status).toBe("complete");
      expect(manifest.pausedAt).toBeUndefined();
      expect(manifest.resumeHint).toBeUndefined();
      expect(manifest.pauseDetail).toBeUndefined();
      expect(manifest.config).toEqual(config());
      expect(manifest.startedAt).toBe(paused.manifest.startedAt);
      expect(readManifest(runDir)).toEqual(manifest);
      expect(resumed.reportPath).toBe(join(runDir, "report.md"));
      expect(existsSync(resumed.reportPath!)).toBe(true);
      expect(manifest.games.every(({ status }) => status === "complete")).toBe(true);
      for (const game of manifest.games) {
        expect(game.outcome?.outcome, game.id).toMatch(/^(win|draw)$/);
        expect(game.finishedAt).toBeDefined();
      }
      // The two Games that were built before the pause made no build call; the two pending ones built both Seats.
      expect(fake.calls.filter(({ schema }) => schema === DECKLIST_SCHEMA)).toHaveLength(4);
      for (const id of Object.keys(pausedFiles)) {
        expect(statuses.filter((change) => change.id === id).map(({ status }) => status)).toEqual(["playing", "complete"]);
      }

      const { gameFiles: wholeFiles, manifest: wholeManifest } = await uninterrupted();
      const files = filesOf(runDir, manifest);
      for (const game of manifest.games) {
        expect(settled(files[game.id]!), game.id).toEqual(settled(wholeFiles[game.id]!));
        expect(game.outcome, game.id).toEqual(wholeManifest.games.find((whole) => whole.id === game.id)!.outcome);
        expect(game.steps, game.id).toBe(wholeManifest.games.find((whole) => whole.id === game.id)!.steps);
      }
      for (const [id, pausedFile] of Object.entries(pausedFiles)) {
        expect(files[id]!.decisions.slice(0, pausedFile.decisions.length)).toEqual(pausedFile.decisions);
        expect(files[id]!.measurements.decisions).toHaveLength(files[id]!.decisions.length);
      }
      expect(resumed.gameFiles).toEqual(files);
    },
    RUN_TIMEOUT,
  );

  it(
    "pauses again on another rate limit and resumes again, still reaching the same final Game files and a report",
    async () => {
      const runDir = tempRunDir();
      const once = await runSuite({ config: config({ seeds: [1] }), runDir, call: fakeClaudeCode(rateLimitedAt(24)) });
      expect(once.manifest.status).toBe("paused");

      const twice = await resumeSuite({ runDir, call: fakeClaudeCode(rateLimitedAt(15)) });
      expect(twice.manifest.status).toBe("paused");
      expect(twice.manifest.resumeHint).toBe(`pnpm suite:claude --resume ${runDir}`);
      expect(twice.report).toBeUndefined();
      expect(existsSync(join(runDir, "report.md"))).toBe(false);
      const midway = filesOf(runDir, twice.manifest);
      expect(Object.values(midway).flatMap((file) => file.decisions.filter(({ decision }) => "cause" in decision && decision.cause === "rate-limit"))).toHaveLength(2);

      const done = await resumeSuite({ runDir, call: fakeClaudeCode(pure) });

      expect(done.manifest.status).toBe("complete");
      expect(done.manifest.games.map(({ status }) => status)).toEqual(["complete", "complete"]);
      expect(existsSync(join(runDir, "report.md"))).toBe(true);
      const { gameFiles: wholeFiles } = await uninterrupted();
      for (const game of done.manifest.games) expect(settled(done.gameFiles[game.id]!), game.id).toEqual(settled(wholeFiles[game.id]!));
    },
    RUN_TIMEOUT,
  );

  it(
    "pauses on a rate limit in a Decklist build and, on resume, builds only for the Seats without a valid build",
    async () => {
      const runDir = tempRunDir();

      const paused = await runSuite({ config: config({ seeds: [1], concurrency: 1 }), runDir, call: fakeClaudeCode(rateLimitedAt(1)) });

      expect(paused.manifest.status).toBe("paused");
      expect(paused.manifest.games.map(({ status, steps }) => ({ status, steps }))).toEqual([
        { status: "playing", steps: 0 },
        { status: "pending", steps: undefined },
      ]);
      const pausedFile = readGameFile(join(runDir, paused.manifest.games[0]!.file));
      expect(pausedFile.status).toBe("paused");
      expect(pausedFile.setup.decklists).toBeUndefined();
      expect(pausedFile.decklistDecisions.map(({ seat, decision }) => ({ seat, failed: "cause" in decision }))).toEqual([
        { seat: 0, failed: false },
        { seat: 1, failed: true },
      ]);

      const fake = fakeClaudeCode(pure);
      const resumed = await resumeSuite({ runDir, call: fake });

      const builds = fake.calls.filter(({ schema }) => schema === DECKLIST_SCHEMA);
      expect(builds).toHaveLength(3);
      expect(builds[0]!.systemPrompt).toContain("You are Seat 1.");
      expect(resumed.manifest.status).toBe("complete");
      const file = resumed.gameFiles[paused.manifest.games[0]!.id]!;
      expect(file.decklistDecisions.map(({ seat }) => seat)).toEqual([0, 1, 1]);
      const { gameFiles: wholeFiles } = await uninterrupted();
      for (const game of resumed.manifest.games) expect(settled(resumed.gameFiles[game.id]!), game.id).toEqual(settled(wholeFiles[game.id]!));
    },
    RUN_TIMEOUT,
  );

  it("refuses to resume a complete Run", async () => {
    const runDir = tempRunDir();
    await runSuite({ config: config({ seeds: [1], concurrency: 1 }), runDir, call: fakeClaudeCode(pure) });

    await expect(resumeSuite({ runDir, call: fakeClaudeCode(pure) })).rejects.toThrow(/complete/);
  }, RUN_TIMEOUT);
});
