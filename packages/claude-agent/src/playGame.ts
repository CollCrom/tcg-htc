// playGame: one Game between two Claude Agents, written to a Game file in the
// Run's directory after every decision. Each Agent first builds its Decklist
// from its List, knowing only the opponent's hero; the Game starts once both
// builds are valid.
import type { Decklist } from "@fyendal/shared";
import {
  isDecisionFailure,
  measureDecision,
  opponentOf,
  runGame,
  summarise,
  type DecisionMeasurement,
  type DecisionProgress,
  type DecisionRecord,
  type GameError,
  type GameMeasurements,
  type GameOutcome,
  type GameResult,
  type List,
  type Seat,
} from "@tcg-htc/runner";
import { join } from "node:path";
import { isDeepStrictEqual } from "node:util";
import { failed } from "./ask.js";
import { buildDecklist } from "./buildDecklist.js";
import { claudeAgent, type ClaudeAgent } from "./claudeAgent.js";
import type { ClaudeCodeCall, ClaudeConfig } from "./claudeCode.js";
import { agentTotals, gameFileName, writeGameFile, type DecklistDecisionRecord, type GameFile, type GameFileSetup } from "./gameFile.js";

export interface PlayGameOptions {
  seed: number;
  /** The List in each Seat. Seat 0 takes the first turn. */
  lists: readonly [List, List];
  /** Each Seat's Claude Agent config. */
  configs: readonly [ClaudeConfig, ClaudeConfig];
  /** The Claude Code call both Agents use. */
  call: ClaudeCodeCall;
  /** The Run's directory: the Game file, the system prompt files and Claude
   * Code's working directory go here. */
  runDir: string;
  /** How each Seat's Decklist comes from its List. By default each Claude
   * Agent builds its own, in one call before the Game; a test that wants no
   * build calls passes the seeded picker, and the Game file then records no
   * Decklist decisions. */
  decklistPicker?: (list: List, seed: number) => Decklist;
  /** Called after every decision, once the Game file holds it. */
  onDecision?: (record: DecisionRecord, progress: DecisionProgress, written: WrittenGameFile) => void;
  /** See `runGame`. */
  clock?: () => number;
}

export interface WrittenGameFile {
  file: GameFile;
  path: string;
}

/** A Game that never started because a Seat's Decklist build failed: the
 * error outcome at step 0, with no replay and no play records. */
export interface UnplayedGame extends GameError {
  turns: 0;
  steps: 0;
  measurements: GameMeasurements;
  decisions: readonly [];
}

export interface PlayedGame extends WrittenGameFile {
  result: GameResult | UnplayedGame;
  /** Absent when the Game never started. */
  agents?: readonly [ClaudeAgent, ClaudeAgent];
}

/** Plays one Game and returns its result with the final Game file. */
export async function playGame(options: PlayGameOptions): Promise<PlayedGame> {
  const { seed, lists, configs, call, runDir, decklistPicker, onDecision, clock = () => performance.now() } = options;
  const startingSeat: Seat = 0;
  const path = join(runDir, gameFileName(seed, lists[0].hero.name));
  const started = clock();
  const setup: GameFileSetup = {
    seed,
    startingSeat,
    lists: [lists[0].name, lists[1].name],
    heroes: [lists[0].hero.name, lists[1].hero.name],
    configs,
  };

  const builds: DecklistDecisionRecord[] = [];
  const built: Decklist[] = [];
  for (const seat of [0, 1] as const) {
    if (decklistPicker) {
      built.push(decklistPicker(lists[seat], seed));
      continue;
    }
    const build = await buildDecklist({
      seat,
      list: lists[seat],
      opponentHero: lists[opponentOf(seat)].hero.name,
      config: configs[seat],
      call,
      resultsDir: runDir,
    });
    builds.push({ kind: "decklist", seat, ...build });
    if (failed(build.decision)) {
      const outcome: GameError = { outcome: "error", seed, step: 0, detail: build.decision.detail, cause: build.decision.cause };
      const measurements = summarise([], clock() - started);
      const file: GameFile = {
        status: "complete",
        setup,
        decklistDecisions: builds,
        outcome,
        turns: 0,
        measurements: { ...measurements, ...totals([], builds) },
        decisions: [],
      };
      writeGameFile(path, file);
      return { result: { ...outcome, turns: 0, steps: 0, measurements, decisions: [] }, file, path };
    }
    built.push(build.decision.decklist);
  }
  const decklists = built as unknown as readonly [Decklist, Decklist];
  setup.decklists = decklists;

  const agents = ([0, 1] as const).map((seat) =>
    claudeAgent({ seat, decklist: decklists[seat], ...configs[seat] }, call, { resultsDir: runDir }),
  ) as unknown as readonly [ClaudeAgent, ClaudeAgent];
  const systemPrompts = [agents[0].systemPrompt, agents[1].systemPrompt] as const;
  const records: DecisionRecord[] = [];
  const measured: DecisionMeasurement[] = [];

  const result = await runGame({
    decklists,
    seed,
    startingSeat,
    agents,
    clock,
    onDecision: (record, progress) => {
      records.push(record);
      measured.push(measureDecision(record.seat, record.intents, { text: record.rendered, intents: [...progress.listed] }));
      const file: GameFile = {
        status: "playing",
        setup,
        decklistDecisions: builds,
        systemPrompts,
        replay: { decklists, seed, startingSeat, intents: [...progress.intents] },
        measurements: { ...summarise([...measured], clock() - started), ...totals(records, builds) },
        decisions: [...records],
      };
      writeGameFile(path, file);
      onDecision?.(record, progress, { file, path });
    },
  });

  const file: GameFile = {
    status: "complete",
    setup,
    decklistDecisions: builds,
    systemPrompts,
    replay: result.replay,
    outcome: outcomeOf(result),
    turns: result.turns,
    measurements: { ...result.measurements, ...totals(result.decisions, builds) },
    decisions: result.decisions,
  };
  writeGameFile(path, file);
  return { result, file, path, agents };
}

/** The one line a Run prints per decision:
 * `game <id> step <n> turn <t> seat <s>: <chosen Intent's text> (<latency> ms)`,
 * or `failed (<cause>): <detail>` in place of the Intent. */
export function progressLine(id: string, record: DecisionRecord, progress: DecisionProgress): string {
  const { decision } = record;
  const what = isDecisionFailure(decision) ? `failed (${decision.cause}): ${decision.detail}` : chosenEntry(record, progress);
  return `game ${id} step ${progress.step} turn ${progress.turn} seat ${record.seat}: ${what} (${decision.measurements?.latencyMs ?? 0} ms)`;
}

/** The text of the numbered entry the record's Intent stands behind. */
function chosenEntry(record: DecisionRecord, progress: DecisionProgress): string {
  if (isDecisionFailure(record.decision)) return "";
  const { intent } = record.decision;
  const index = progress.listed.findIndex((listed) => listed === intent || isDeepStrictEqual(listed, intent));
  const lines = record.rendered.split("\n");
  const entry = lines[lines.indexOf("Legal Intents:") + 1 + index];
  return index >= 0 && entry ? entry.replace(/^\d+\. /, "") : JSON.stringify(intent);
}

function totals(
  records: readonly DecisionRecord[],
  builds: readonly DecklistDecisionRecord[],
): Pick<GameFile["measurements"], "perSeat" | "totals" | "builds"> {
  return {
    perSeat: [agentTotals(records.filter(({ seat }) => seat === 0)), agentTotals(records.filter(({ seat }) => seat === 1))],
    totals: agentTotals(records),
    builds: agentTotals(builds),
  };
}

/** The outcome alone, without the rest of the result. */
export function outcomeOf(result: GameOutcome): GameOutcome {
  switch (result.outcome) {
    case "win":
      return { outcome: "win", winner: result.winner };
    case "draw":
      return { outcome: "draw" };
    case "stall":
      return { outcome: "stall", seed: result.seed, step: result.step, detail: result.detail };
    case "error":
      return { outcome: "error", seed: result.seed, step: result.step, detail: result.detail, ...(result.cause ? { cause: result.cause } : {}) };
  }
}
