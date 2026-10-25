// playGame, driven with fake-backed Claude Agents in both Seats: the Game file
// it writes as the Game goes, and what the file holds at the end. The Decklists
// come from the seeded picker here; the Agent's own build is tested in
// buildDecklist.test.ts.
import { BRAVO_LIST_FILE, fixtureList, IRA_LIST_FILE, pickDecklist, replayGame, type DecisionChoice, type DecisionRecord, type GameResult } from "@tcg-htc/runner";
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { DECKLIST_SCHEMA } from "./buildDecklist.js";
import { PLAN_NOTES_HEADING } from "./claudeAgent.js";
import type { CallResult, ClaudeCodeCall, ClaudeConfig } from "./claudeCode.js";
import { fakeClaudeCode, type RecordedCall } from "./fakeClaudeCode.js";
import { gameFileName, gameId, readGameFile, type GameFile } from "./gameFile.js";
import { playGame, progressLine, type PlayedGame } from "./playGame.js";
import { scriptedAnswer } from "./scriptedPlay.js";

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

let completed: Promise<{ played: PlayedGame; runDir: string; snapshots: Snapshot[]; lines: string[] }> | undefined;
/** One complete Game, played once and shared by the tests that read its file. */
function completeGame() {
  completed ??= (async () => {
    const runDir = tempRunDir();
    const snapshots: Snapshot[] = [];
    const lines: string[] = [];
    const played = await playGame({
      seed: SEED,
      lists,
      configs,
      call: fakeClaudeCode(varied),
      runDir,
      decklistPicker: pickDecklist,
      onDecision: (record, progress, written) => {
        lines.push(progressLine(gameId(SEED, lists[0].hero.name), record, progress));
        if (progress.step < 2 || progress.step % 25 === 0) {
          snapshots.push({ step: progress.step, onDisk: readGameFile(written.path), handed: written.file });
        }
      },
    });
    return { played, runDir, snapshots, lines };
  })();
  return completed;
}

/** The result of a Game that was played, which these Games all are. */
function playedResult(played: PlayedGame): GameResult {
  if (!("replay" in played.result)) throw new Error("the Game never started");
  return played.result;
}

/** The numbered Intent entries of a rendered decision, without their numbers. */
function entriesOf(rendered: string): string[] {
  const lines = rendered.split("\n");
  return lines.slice(lines.indexOf("Legal Intents:") + 1).map((line) => line.replace(/^\d+\. /, ""));
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
        expect(onDisk.replay!.intents).toHaveLength(step + 1);
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
      const result = playedResult(played);
      const file = readGameFile(played.path);

      expect(file).toEqual(played.file);
      expect(file.status).toBe("complete");
      expect(file.decklistDecisions).toEqual([]);
      expect(file.measurements.builds.decisions).toBe(0);
      expect(file.setup).toEqual({
        seed: SEED,
        startingSeat: 0,
        lists: [lists[0].name, lists[1].name],
        heroes: ["Ira, Crimson Haze", "Bravo, Flattering Showman"],
        decklists: result.replay.decklists,
        configs,
      });
      expect(file.systemPrompts![0]).toBe(played.agents![0].systemPrompt);
      expect(file.systemPrompts![1]).toBe(played.agents![1].systemPrompt);
      expect(file.systemPrompts![0]).toContain("You are Seat 0.");
      expect(file.systemPrompts![1]).toContain("You are Seat 1.");
      const encodedPrompt = JSON.stringify(file.systemPrompts![0]).slice(1, -1);
      expect(readFileSync(played.path, "utf8").split(encodedPrompt)).toHaveLength(2);
      expect(file.replay).toEqual(result.replay);
      expect(file.replay!.intents).toHaveLength(result.steps);
      expect(replayGame(file.replay!)).toEqual(result.finalProjection);
      expect(file.outcome).toEqual(result.outcome === "win" ? { outcome: "win", winner: result.winner } : { outcome: "draw" });
      expect(file.turns).toBe(result.turns);
      expect(file.decisions).toEqual(result.decisions);
      expect(file.decisions.map(({ decision }) => "planNotes" in decision && decision.planNotes)).toEqual(result.decisions.map((_, i) => `plan ${i}`));
      const { durationMs, ...measured } = result.measurements;
      expect(file.measurements).toMatchObject(measured);
      // The file's duration covers the whole sitting, of which runGame's play is a part.
      expect(file.measurements.durationMs).toBeGreaterThanOrEqual(durationMs);
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
    "renders one progress line per decision: Game, step, turn, Seat, the chosen Intent's text and the latency",
    async () => {
      const { played, lines } = await completeGame();

      expect(lines).toHaveLength(played.result.decisions.length);
      lines.forEach((line, i) => {
        const record = played.result.decisions[i]!;
        const chosen = (record.decision as DecisionChoice).intent;
        const entries = entriesOf(record.rendered);
        const text = line.slice(line.indexOf(": ") + 2, line.lastIndexOf(" ("));
        expect(line).toMatch(new RegExp(`^game 31-ira-first step ${i} turn \\d+ seat ${record.seat}: .+ \\(1500 ms\\)$`));
        expect(entries).toContain(text);
        // The chosen entry is the one whose number the fake answered: 1 + (i % entries).
        expect(text).toBe(entries[i % entries.length]);
        expect(chosen).toBeDefined();
      });
    },
    GAME_TIMEOUT,
  );

  it(
    "counts this sitting's Decklist builds in the Game's duration, in every write as it goes and in the final file alike",
    async () => {
      // A clock the calls drive: a build takes a second, a play decision 10 ms.
      let now = 0;
      const call: ClaudeCodeCall = async (request) => {
        now += request.schema === DECKLIST_SCHEMA ? 1000 : 10;
        return scriptedAnswer(lists, request);
      };
      const written: number[] = [];

      const played = await playGame({
        seed: SEED,
        lists,
        configs,
        call,
        runDir: tempRunDir(),
        clock: () => now,
        onDecision: (_record, _progress, { file }) => written.push(file.measurements.durationMs),
      });

      const result = playedResult(played);
      expect(result.outcome).toMatch(/^(win|draw)$/);
      expect(result.measurements.durationMs).toBe(10 * result.decisions.length);
      expect(written).toEqual(result.decisions.map((_, i) => 2000 + 10 * (i + 1)));
      expect(played.file.measurements.durationMs).toBe(2000 + result.measurements.durationMs);
      expect(readGameFile(played.path).measurements.durationMs).toBe(written.at(-1));
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
      const lines: string[] = [];

      const played = await playGame({
        seed: SEED,
        lists: [lists[1], lists[0]],
        configs,
        call: fakeClaudeCode(script),
        runDir,
        decklistPicker: pickDecklist,
        onDecision: (record, progress) => {
          seen.push(record);
          lines.push(progressLine(gameId(SEED, lists[1].hero.name), record, progress));
        },
      });

      const file = readGameFile(played.path);
      expect(lines.at(-1)).toMatch(/^game 31-bravo-first step 5 turn \d+ seat [01]: failed \(invalid-answer\): Seat [01]'s Claude Agent \(\w+, \w+\): .+ \(3000 ms\)$/);
      expect(played.path).toBe(join(runDir, "game-31-bravo-first.json"));
      expect(played.result).toMatchObject({ outcome: "error", cause: "invalid-answer", step: 5, steps: 5 });
      expect(file.status).toBe("complete");
      expect(file.outcome).toEqual({ outcome: "error", seed: SEED, step: 5, detail: expect.stringContaining("Claude Agent"), cause: "invalid-answer" });
      expect(file.decisions).toHaveLength(6);
      expect(file.decisions).toEqual(seen);
      expect(file.replay!.intents).toHaveLength(5);
      expect(file.setup.heroes).toEqual(["Bravo, Flattering Showman", "Ira, Crimson Haze"]);
      expect(file.measurements.totals).toMatchObject({ decisions: 6, retries: 1, invalidFirstAnswers: 1, inputTokens: 700 });
      expect(existsSync(`${played.path}.tmp`)).toBe(false);
    },
    GAME_TIMEOUT,
  );
});

/** Pausing and resuming, with answers that are a pure function of the request,
 * so a resumed Game and an uninterrupted one get the same answers. */
describe("playGame pauses and resumes", () => {
  const PAUSE_SEED = 33;
  const pure = (request: RecordedCall): CallResult => scriptedAnswer(lists, request);
  /** `pure`, but a rate limit at call `at` (0-based; the two builds are calls 0 and 1). */
  const rateLimitedAt = (at: number) => (request: RecordedCall, index: number): CallResult =>
    index === at ? { kind: "rate-limit", detail: "You've hit your limit" } : pure(request);

  /** What a Game file holds that doesn't depend on when, or in how many
   * sittings, the Game was played: everything but the measurements, without
   * the rate-limit records a pause leaves behind. */
  function settled(file: GameFile) {
    const { measurements: _measurements, decisions, decklistDecisions, ...rest } = file;
    const kept = <T extends { decision: object }>(records: readonly T[]) =>
      records.filter(({ decision }) => !("cause" in decision && decision.cause === "rate-limit"));
    return { ...rest, decisions: kept(decisions), decklistDecisions: kept(decklistDecisions) };
  }

  /** The Plan notes the Seat's last chosen Decision left. */
  function lastNotes(file: GameFile, seat: 0 | 1): string | undefined {
    const choices = file.decisions.filter((record) => record.seat === seat && "intent" in record.decision);
    const last = choices.at(-1)?.decision;
    return last && "planNotes" in last ? last.planNotes : undefined;
  }

  let whole: Promise<PlayedGame> | undefined;
  /** The same Game played without interruption, for comparison. */
  function uninterrupted() {
    whole ??= playGame({ seed: PAUSE_SEED, lists, configs, call: fakeClaudeCode(pure), runDir: tempRunDir() });
    return whole;
  }

  it(
    "pauses on a rate limit mid-Game: a paused file with every applied Intent, the rate-limit record last and no outcome",
    async () => {
      const runDir = tempRunDir();

      const paused = await playGame({ seed: PAUSE_SEED, lists, configs, call: fakeClaudeCode(rateLimitedAt(12)), runDir });

      expect(paused.result).toMatchObject({ outcome: "paused", cause: "rate-limit", seed: PAUSE_SEED, step: 10, steps: 10, detail: expect.stringContaining("You've hit your limit") });
      const file = readGameFile(paused.path);
      expect(file).toEqual(paused.file);
      expect(file.status).toBe("paused");
      expect(file.outcome).toBeUndefined();
      expect(file.turns).toBeUndefined();
      expect(file.setup.decklists).toHaveLength(2);
      expect(file.replay!.intents).toHaveLength(10);
      expect(file.decisions).toHaveLength(11);
      expect(file.decisions.at(-1)!.decision).toMatchObject({ cause: "rate-limit" });
      expect(file.decisions.slice(0, 10).every(({ decision }) => "intent" in decision)).toBe(true);
      expect(file.measurements.totals.decisions).toBe(11);
    },
    GAME_TIMEOUT,
  );

  it(
    "resumes a paused Game from its file: no build call, each Seat's Plan notes restored, records appended, and the finished file matches the uninterrupted Game's",
    async () => {
      const runDir = tempRunDir();
      const paused = await playGame({ seed: PAUSE_SEED, lists, configs, call: fakeClaudeCode(rateLimitedAt(12)), runDir });
      const notes = [lastNotes(paused.file, 0), lastNotes(paused.file, 1)];
      expect(notes[0]).toMatch(/^plan \d+$/);
      expect(notes[1]).toMatch(/^plan \d+$/);
      const fake = fakeClaudeCode(pure);

      const resumed = await playGame({ seed: PAUSE_SEED, lists, configs, call: fake, runDir, resumeFrom: readGameFile(paused.path) });

      expect(resumed.result.outcome).toMatch(/^(win|draw)$/);
      expect(fake.calls.some(({ schema }) => schema === DECKLIST_SCHEMA)).toBe(false);
      for (const seat of [0, 1] as const) {
        const first = fake.calls.find(({ systemPrompt }) => systemPrompt === paused.file.systemPrompts![seat]);
        expect(first!.message.endsWith(`${PLAN_NOTES_HEADING}\n${notes[seat]}`)).toBe(true);
      }
      expect(resumed.path).toBe(paused.path);
      const file = readGameFile(resumed.path);
      expect(file).toEqual(resumed.file);
      expect(file.status).toBe("complete");
      expect(file.decisions.slice(0, 11)).toEqual(paused.file.decisions);
      expect(file.decklistDecisions).toEqual(paused.file.decklistDecisions);
      expect(file.systemPrompts).toEqual(paused.file.systemPrompts);
      expect(file.replay!.intents.slice(0, 10)).toEqual(paused.file.replay!.intents);
      expect(replayGame(file.replay!)).toEqual(playedResult(resumed).finalProjection);
      expect(playedResult(resumed).steps).toBe(file.replay!.intents.length);
      expect(playedResult(resumed).decisions).toHaveLength(file.decisions.length - 11);
      expect(file.measurements.decisions).toHaveLength(file.decisions.length);
      expect(file.measurements.totals.decisions).toBe(file.decisions.length);

      const { file: wholeFile } = await uninterrupted();
      expect(wholeFile.status).toBe("complete");
      expect(settled(file)).toEqual(settled(wholeFile));
      expect(file.measurements.totals.decisions).toBe(wholeFile.measurements.totals.decisions + 1);
      expect(file.measurements.durationMs).toBeGreaterThan(0);
    },
    2 * GAME_TIMEOUT,
  );

  it(
    "pauses on a rate limit in a Decklist build, and resumes with one more build call for the Seat without a valid build",
    async () => {
      const runDir = tempRunDir();

      const paused = await playGame({ seed: PAUSE_SEED, lists, configs, call: fakeClaudeCode(rateLimitedAt(1)), runDir });

      expect(paused.result).toMatchObject({ outcome: "paused", cause: "rate-limit", seed: PAUSE_SEED, step: 0, steps: 0, turns: 0, decisions: [] });
      expect(paused.file.status).toBe("paused");
      expect(paused.file.setup.decklists).toBeUndefined();
      expect(paused.file.replay).toBeUndefined();
      expect(paused.file.systemPrompts).toBeUndefined();
      expect(paused.file.decisions).toEqual([]);
      expect(paused.file.decklistDecisions.map(({ seat, decision }) => ({ seat, failed: "cause" in decision }))).toEqual([
        { seat: 0, failed: false },
        { seat: 1, failed: true },
      ]);
      expect(paused.file.measurements.builds.decisions).toBe(2);
      expect(readGameFile(paused.path)).toEqual(paused.file);

      const fake = fakeClaudeCode(pure);
      const resumed = await playGame({ seed: PAUSE_SEED, lists, configs, call: fake, runDir, resumeFrom: readGameFile(paused.path) });

      const buildCalls = fake.calls.filter(({ schema }) => schema === DECKLIST_SCHEMA);
      expect(buildCalls).toHaveLength(1);
      expect(buildCalls[0]!.systemPrompt).toContain("You are Seat 1.");
      expect(resumed.result.outcome).toMatch(/^(win|draw)$/);
      expect(resumed.file.decklistDecisions).toHaveLength(3);
      expect(resumed.file.decklistDecisions.slice(0, 2)).toEqual(paused.file.decklistDecisions);
      expect(resumed.file.decklistDecisions[2]).toMatchObject({ kind: "decklist", seat: 1, decision: { reasoning: "built" } });
      expect(resumed.file.measurements.builds.decisions).toBe(3);
      const { file: wholeFile } = await uninterrupted();
      expect(settled(resumed.file)).toEqual(settled(wholeFile));
    },
    2 * GAME_TIMEOUT,
  );

  it(
    "stops before the next decision once `shouldStop` says so, leaving a paused file the Game resumes from",
    async () => {
      const runDir = tempRunDir();
      let decisions = 0;

      const stopped = await playGame({
        seed: PAUSE_SEED,
        lists,
        configs,
        call: fakeClaudeCode(pure),
        runDir,
        shouldStop: () => decisions >= 7,
        onDecision: () => decisions++,
      });

      expect(stopped.result).toMatchObject({ outcome: "paused", seed: PAUSE_SEED, step: 7, steps: 7 });
      expect(stopped.result).not.toHaveProperty("cause");
      expect(stopped.file.status).toBe("paused");
      expect(stopped.file.decisions).toHaveLength(7);
      expect(stopped.file.replay!.intents).toHaveLength(7);

      const resumed = await playGame({ seed: PAUSE_SEED, lists, configs, call: fakeClaudeCode(pure), runDir, resumeFrom: readGameFile(stopped.path) });

      const { file: wholeFile } = await uninterrupted();
      expect(resumed.file.status).toBe("complete");
      expect(settled(resumed.file)).toEqual(settled(wholeFile));
      expect(resumed.file.measurements.totals.decisions).toBe(wholeFile.measurements.totals.decisions);
    },
    2 * GAME_TIMEOUT,
  );
});
