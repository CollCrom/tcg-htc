// A Run: the Phase 2 suite played into one results directory. Its manifest
// says which Games it holds and where each stands; it is rewritten on every
// change so a pause or a crash can be picked up from it (#177). When every
// Game is done the Run writes its report and marks itself complete.
import { isFailure, type DecisionProgress, type DecisionRecord, type GameOutcome, type List } from "@tcg-htc/runner";
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { ClaudeCodeCall, ClaudeConfig } from "./claudeCode.js";
import type { Hero } from "./gameClaudeArgs.js";
import { gameFileName, gameId, heroSlug, readGameFile, type GameFile } from "./gameFile.js";
import { heroList } from "./heroLists.js";
import { CLAUDE_MAX_DECISIONS, outcomeOf, playGame, type WrittenGameFile } from "./playGame.js";
import { renderReport, upstreamCommit } from "./report.js";

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
  /** Intents applied, once the Game is done. */
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
  /** Set when the Run paused on a rate limit (#177). */
  pausedAt?: string;
  /** How to resume a paused Run (#177). */
  resumeHint?: string;
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

export interface RunResult {
  manifest: Manifest;
  /** Each finished Game's file, by Game id. */
  gameFiles: Record<string, GameFile>;
  report: string;
  reportPath: string;
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
 * throws is `failed` with its outcome; the Run goes on. */
export async function runSuite(options: RunSuiteOptions): Promise<RunResult> {
  const { config, runDir, call, onDecision, onGame, now = () => new Date() } = options;
  mkdirSync(runDir, { recursive: true });
  const startedAt = now().toISOString();
  const manifest: Manifest = { status: "running", config, startedAt, updatedAt: startedAt, games: planGames(config) };
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

  /** Claims the next pending Game, or nothing once none is left (or the Run
   * stops starting Games, when #177 pauses it). */
  const claim = (): ManifestGame | undefined => {
    if (manifest.status !== "running") return undefined;
    const game = manifest.games.find(({ status }) => status === "pending");
    if (!game) return undefined;
    game.status = "playing";
    game.startedAt = now().toISOString();
    changed(game);
    return game;
  };

  const playOne = async (game: ManifestGame): Promise<void> => {
    const first = lists.find((list) => heroSlug(list.hero.name) === game.first)!;
    const second = lists.find((list) => list !== first)!;
    try {
      const played = await playGame({
        seed: game.seed,
        lists: [first, second],
        configs: config.configs,
        call,
        runDir,
        maxSteps: config.maxSteps,
        onDecision: (record, progress, written) => onDecision?.(record, progress, { game, written, manifest }),
      });
      game.outcome = outcomeOf(played.result);
      game.steps = played.result.steps;
      game.status = isFailure(played.result) ? "failed" : "complete";
    } catch (error) {
      const path = join(runDir, game.file);
      const step = existsSync(path) ? readGameFile(path).replay.intents.length : 0;
      game.outcome = { outcome: "error", seed: game.seed, step, detail: error instanceof Error ? error.message : String(error) };
      game.steps = step;
      game.status = "failed";
    }
    game.finishedAt = now().toISOString();
    changed(game);
  };

  const worker = async (): Promise<void> => {
    for (let game = claim(); game; game = claim()) await playOne(game);
  };
  await Promise.all(Array.from({ length: Math.max(1, config.concurrency) }, worker));

  const gameFiles = readGameFiles(runDir, manifest);
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

/** Writes the manifest atomically: to `<path>.tmp`, then renamed over the old
 * one, so a reader never sees a partial document. */
export function writeManifest(runDir: string, manifest: Manifest): void {
  mkdirSync(runDir, { recursive: true });
  const path = join(runDir, MANIFEST_FILE);
  const temp = `${path}.tmp`;
  writeFileSync(temp, JSON.stringify(manifest, null, 2));
  renameSync(temp, path);
}

export function readManifest(runDir: string): Manifest {
  return JSON.parse(readFileSync(join(runDir, MANIFEST_FILE), "utf8")) as Manifest;
}
