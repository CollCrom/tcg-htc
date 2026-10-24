// The Game file: one JSON document per Game, self-contained, rewritten after
// every decision so a crash or a pause loses nothing. A Run resumes a Game from
// it (the replay's Intents and each Seat's last Plan notes, in the Decision
// records), and the report reads its outcome and measurements.
import type { Decklist } from "@fyendal/shared";
import type { AgentMeasurements, DecisionRecord, GameMeasurements, GameOutcome, Replay, Seat } from "@tcg-htc/runner";
import { mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import type { DecklistBuild } from "./buildDecklist.js";
import type { ClaudeConfig } from "./claudeCode.js";

export interface GameFile {
  /** `playing` until the Game's outcome is known. */
  status: "playing" | "complete";
  setup: GameFileSetup;
  /** Each Seat's Decklist build, Seat 0 first, before any play record. A
   * failed build is the last: the Game ended there. */
  decklistDecisions: readonly DecklistDecisionRecord[];
  /** Each Seat's play system prompt, identical for every decision of the
   * Game. Absent when a Decklist build failed and the Game never started. */
  systemPrompts?: readonly [string, string];
  /** The setup and every Intent applied so far: `replayGame` takes it.
   * Absent when a Decklist build failed and the Game never started. */
  replay?: Replay;
  /** Known once the Game is complete. */
  outcome?: GameOutcome;
  /** Known once the Game is complete. */
  turns?: number;
  measurements: GameFileMeasurements;
  /** One record per decision, in order. The last record of each Seat holds
   * its latest Plan notes. */
  decisions: readonly DecisionRecord[];
}

export interface GameFileSetup {
  seed: number;
  startingSeat: Seat;
  /** The name of the List in each Seat. */
  lists: readonly [string, string];
  /** The hero of the List in each Seat. */
  heroes: readonly [string, string];
  /** What each Seat built. Absent when a build failed and the Game never started. */
  decklists?: readonly [Decklist, Decklist];
  /** Each Seat's Claude Agent config. */
  configs: readonly [ClaudeConfig, ClaudeConfig];
}

/** The Decision record of a Seat's Decklist build: its own kind, with the
 * build's system prompt (not the play prompt) and message, so the Game file
 * stays self-contained. */
export interface DecklistDecisionRecord extends DecklistBuild {
  kind: "decklist";
  seat: Seat;
}

/** The runner's measurements plus what the Agents reported, totalled. */
export interface GameFileMeasurements extends GameMeasurements {
  /** Over the play records. */
  perSeat: readonly [AgentTotals, AgentTotals];
  totals: AgentTotals;
  /** Over the Decklist builds; its `decisions` counts builds. */
  builds: AgentTotals;
}

/** Agent measurements summed over Decision records. */
export interface AgentTotals {
  decisions: number;
  inputTokens: number;
  cachedTokens: number;
  outputTokens: number;
  latencyMs: number;
  costUsd: number;
  retries: number;
  /** Decisions whose first answer was invalid. */
  invalidFirstAnswers: number;
  /** Decisions whose Plan notes were cut. */
  notesCut: number;
}

/** The Game file's name within its Run directory: the seed and the hero in
 * Seat 0, which takes the first turn. */
export function gameFileName(seed: number, firstHero: string): string {
  return `game-${gameId(seed, firstHero)}.json`;
}

/** What a progress line calls the Game: `<seed>-<hero>-first`. */
export function gameId(seed: number, firstHero: string): string {
  return `${seed}-${heroSlug(firstHero)}-first`;
}

/** "Ira, Crimson Haze" becomes "ira". */
export function heroSlug(heroName: string): string {
  return (heroName.split(",")[0] ?? heroName)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/** Sums the Agent measurements of `records`, play or build. */
export function agentTotals(records: readonly { decision: { measurements?: AgentMeasurements } }[]): AgentTotals {
  const totals: AgentTotals = {
    decisions: 0,
    inputTokens: 0,
    cachedTokens: 0,
    outputTokens: 0,
    latencyMs: 0,
    costUsd: 0,
    retries: 0,
    invalidFirstAnswers: 0,
    notesCut: 0,
  };
  for (const { decision } of records) {
    totals.decisions++;
    const measured = decision.measurements;
    if (!measured) continue;
    totals.inputTokens += measured.inputTokens ?? 0;
    totals.cachedTokens += measured.cachedTokens ?? 0;
    totals.outputTokens += measured.outputTokens ?? 0;
    totals.latencyMs += measured.latencyMs ?? 0;
    totals.costUsd += measured.costUsd ?? 0;
    totals.retries += measured.retries ?? 0;
    if (measured.firstAnswerInvalid) totals.invalidFirstAnswers++;
    if (measured.notesCut) totals.notesCut++;
  }
  return totals;
}

/** Writes the whole file atomically: to `<path>.tmp`, then renamed over
 * `path`, so a reader (or a crash) never sees a partial document. */
export function writeGameFile(path: string, file: GameFile): void {
  mkdirSync(dirname(path), { recursive: true });
  const temp = `${path}.tmp`;
  writeFileSync(temp, JSON.stringify(file));
  renameSync(temp, path);
}

export function readGameFile(path: string): GameFile {
  return JSON.parse(readFileSync(path, "utf8")) as GameFile;
}
