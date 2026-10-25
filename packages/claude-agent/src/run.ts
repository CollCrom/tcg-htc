// A Run: the Phase 2 suite played into one results directory. Its manifest
// says which Games it holds and where each stands; it is rewritten on every
// change so a pause or a crash can be picked up from it. A rate limit pauses
// the Run: no new Game starts, each Game in flight stops after its current
// decision, and the manifest says how to resume. When every Game is done the
// Run writes its report and marks itself complete.
import { isFailure, type DecisionProgress, type DecisionRecord, type GameOutcome, type List } from "@tcg-htc/runner";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { ClaudeCodeCall, ClaudeConfig } from "./claudeCode.js";
import type { Hero } from "./gameClaudeArgs.js";
import { gameFileName, gameId, heroSlug, readGameFile, type GameFile } from "./gameFile.js";
import { heroList } from "./heroLists.js";
import { CLAUDE_MAX_DECISIONS, outcomeOf, playGame, type WrittenGameFile } from "./playGame.js";
import { renderReport, upstreamCommit } from "./report.js";
import { writeAtomically } from "./writeAtomically.js";

/** The Run's config, as the manifest keeps it. */
export interface RunConfig {
  /** Each seed is played once with each List in Seat 0. */
  seeds: number[];
  /** The two Lists, by hero. */
  lists: readonly [Hero, Hero];
  /** Each Seat's Claude Agent config, whichever List sits there. */
  configs: readonly [ClaudeConfig, ClaudeConfig];
  /** Games played at once. */
  concurrency: number;
  /** The decision cap per Game. */
  maxSteps: number;
}

export const DEFAULT_SEEDS = [1, 2, 3, 4, 5];
export const DEFAULT_CONCURRENCY = 2;

export type RunStatus = "running" | "paused" | "complete";
/** `playing` covers a Game in flight and, in a paused Run, one stopped between
 * decisions that resumes from its Game file. */
export type GameStatus = "pending" | "playing" | "complete" | "failed";

/** One Game of the Run. `failed` keeps the stall or error outcome. */
export interface ManifestGame {
  id: string;
  seed: number;
  /** The hero in Seat 0, as a slug. */
  first: string;
  status: GameStatus;
  outcome?: GameOutcome;
  /** The Game file's name within the Run directory. */
  file: string;
  /** Intents applied, once the Game is done or the Run paused. */
  steps?: number;
  startedAt?: string;
  finishedAt?: string;
}

export interface Manifest {
  status: RunStatus;
  config: RunConfig;
  startedAt: string;
  updatedAt: string;
  games: ManifestGame[];
  /** When the Run paused on a rate limit; cleared on resume. */
  pausedAt?: string;
  /** The command that resumes a paused Run. */
  resumeHint?: string;
  /** What the rate limit said. */
  pauseDetail?: string;
}

/** How a paused Run is resumed. */
export function resumeHint(runDir: string): string {
  return `pnpm suite:claude --resume ${runDir}`;
}

export const MANIFEST_FILE = "manifest.json";
export const REPORT_FILE = "report.md";

export interface RunSuiteOptions {
  config: RunConfig;
  /** The Run's directory: the manifest, the Game files and the report go here. */
  runDir: string;
  call: ClaudeCodeCall;
  /** Called after every decision of every Game, once its Game file holds it. */
  onDecision?: (record: DecisionRecord, progress: DecisionProgress, context: DecisionContext) => void;
  /** Called on every Game status change, once the manifest holds it. */
  onGame?: (game: ManifestGame, manifest: Manifest) => void;
  /** The wall clock, for the manifest's timestamps. */
  now?: () => Date;
  /** The upstream commit the report names; read from the submodule by default. */
  upstreamCommit?: string;
}

export interface DecisionContext {
  game: ManifestGame;
  written: WrittenGameFile;
  manifest: Manifest;
}

/** Everything but `config`, which a resumed Run reads from its manifest. */
export type ResumeSuiteOptions = Omit<RunSuiteOptions, "config">;

export interface RunResult {
  manifest: Manifest;
  /** Each Game's file, by Game id, for the Games that have one. */
  gameFiles: Record<string, GameFile>;
  /** The report, once the Run is complete; absent when it paused. */
  report?: string;
  reportPath?: string;
}

/** The Run's Games, all pending: each seed with each List in Seat 0, the
 * first List first. */
export function planGames(config: RunConfig): ManifestGame[] {
  const heroes = config.lists.map((hero) => heroList(hero).hero.name);
  return config.seeds.flatMap((seed) =>
    heroes.map((firstHero) => ({
      id: gameId(seed, firstHero),
      seed,
      first: heroSlug(firstHero),
      status: "pending" as const,
      file: gameFileName(seed, firstHero),
    })),
  );
}

/** Plays the Run: `concurrency` Games at a time until none is pending, then
 * writes the report and marks the Run complete. A Game that stalls, errors or
 * throws is `failed` with its outcome; the Run goes on. A rate limit pauses
 * the Run instead (see `play`). */
export async function runSuite(options: RunSuiteOptions): Promise<RunResult> {
  const { config, runDir, now = () => new Date() } = options;
  mkdirSync(runDir, { recursive: true });
  const startedAt = now().toISOString();
  const manifest: Manifest = { status: "running", config, startedAt, updatedAt: startedAt, games: planGames(config) };
  return play(manifest, options);
}

/** Resumes the Run in `runDir` from its manifest: `complete` and `failed`
 * Games are left alone, `pending` ones are played, and `playing` ones carry on
 * from their Game files (a Game file already complete settles its Game). The
 * Run is marked running, pauses again on another rate limit, and writes its
 * report when it completes. Throws if the Run is already complete. */
export async function resumeSuite(options: ResumeSuiteOptions): Promise<RunResult> {
  const manifest = readManifest(options.runDir);
  if (manifest.status === "complete") throw new Error(`the Run in ${options.runDir} is complete; there is nothing to resume`);
  manifest.status = "running";
  delete manifest.pausedAt;
  delete manifest.resumeHint;
  delete manifest.pauseDetail;
  return play(manifest, options);
}

async function play(manifest: Manifest, options: ResumeSuiteOptions): Promise<RunResult> {
  const { runDir, call, onDecision, onGame, now = () => new Date() } = options;
  const { config } = manifest;
  const lists = config.lists.map(heroList) as unknown as readonly [List, List];
  const save = () => {
    manifest.updatedAt = now().toISOString();
    writeManifest(runDir, manifest);
  };
  save();

  const changed = (game: ManifestGame) => {
    save();
    onGame?.(game, manifest);
  };

  /** Set by the first rate limit; every Game in flight then stops after its
   * current decision, and no Game is claimed. */
  let pausing = false;
  const shouldStop = () => pausing;
  const pause = (detail: string) => {
    if (pausing) return;
    pausing = true;
    manifest.status = "paused";
    manifest.pausedAt = now().toISOString();
    manifest.resumeHint = resumeHint(runDir);
    manifest.pauseDetail = detail;
  };

  /** The Games this process is playing right now. */
  const inFlight = new Set<string>();

  /** Claims the next Game to play, a pending one or (resuming) a playing one
   * not in flight, or nothing once none is left or the Run is pausing. */
  const claim = (): ManifestGame | undefined => {
    if (manifest.status !== "running") return undefined;
    const game = manifest.games.find(({ id, status }) => status === "pending" || (status === "playing" && !inFlight.has(id)));
    if (!game) return undefined;
    inFlight.add(game.id);
    game.status = "playing";
    game.startedAt ??= now().toISOString();
    changed(game);
    return game;
  };

  const playOne = async (game: ManifestGame): Promise<void> => {
    const first = lists.find((list) => heroSlug(list.hero.name) === game.first)!;
    const second = lists.find((list) => list !== first)!;
    const path = join(runDir, game.file);
    const saved = existsSync(path) ? readGameFile(path) : undefined;
    try {
      if (saved?.status === "complete" && saved.outcome) {
        // Written before the manifest could record it.
        settle(game, saved.outcome, saved.replay?.intents.length ?? 0);
      } else {
        const played = await playGame({
          seed: game.seed,
          lists: [first, second],
          configs: config.configs,
          call,
          runDir,
          maxSteps: config.maxSteps,
          shouldStop,
          ...(saved ? { resumeFrom: saved } : {}),
          onDecision: (record, progress, written) => onDecision?.(record, progress, { game, written, manifest }),
        });
        const { result } = played;
        if (result.outcome === "paused") {
          game.steps = result.steps;
          if (result.cause === "rate-limit") pause(result.detail);
        } else {
          settle(game, outcomeOf(result), result.steps);
        }
      }
    } catch (error) {
      const step = existsSync(path) ? (readGameFile(path).replay?.intents.length ?? 0) : 0;
      settle(game, { outcome: "error", seed: game.seed, step, detail: error instanceof Error ? error.message : String(error) }, step);
    }
    inFlight.delete(game.id);
    changed(game);
  };

  const settle = (game: ManifestGame, outcome: GameOutcome, steps: number) => {
    game.outcome = outcome;
    game.steps = steps;
    game.status = isFailure(outcome) ? "failed" : "complete";
    game.finishedAt = now().toISOString();
  };

  const worker = async (): Promise<void> => {
    for (let game = claim(); game; game = claim()) await playOne(game);
  };
  await Promise.all(Array.from({ length: Math.max(1, config.concurrency) }, worker));

  const gameFiles = readGameFiles(runDir, manifest);
  if (pausing) {
    save();
    return { manifest, gameFiles };
  }
  const report = renderReport(manifest, gameFiles, { upstreamCommit: options.upstreamCommit ?? upstreamCommit(), runDir });
  const reportPath = join(runDir, REPORT_FILE);
  writeFileSync(reportPath, report);
  manifest.status = "complete";
  save();
  return { manifest, gameFiles, report, reportPath };
}

/** The Game files of the Games that have one, by Game id. */
export function readGameFiles(runDir: string, manifest: Manifest): Record<string, GameFile> {
  const files: Record<string, GameFile> = {};
  for (const game of manifest.games) {
    const path = join(runDir, game.file);
    if (existsSync(path)) files[game.id] = readGameFile(path);
  }
  return files;
}

/** Writes the manifest atomically (see `writeAtomically`), indented. */
export function writeManifest(runDir: string, manifest: Manifest): void {
  writeAtomically(join(runDir, MANIFEST_FILE), JSON.stringify(manifest, null, 2));
}

export function readManifest(runDir: string): Manifest {
  return JSON.parse(readFileSync(join(runDir, MANIFEST_FILE), "utf8")) as Manifest;
}
