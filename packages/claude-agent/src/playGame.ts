// playGame: one Game between two Claude Agents, written to a Game file in the
// Run's directory after every decision.
import type { Decklist } from "@fyendal/shared";
import {
  measureDecision,
  pickDecklist,
  runGame,
  summarise,
  type DecisionMeasurement,
  type DecisionProgress,
  type DecisionRecord,
  type GameOutcome,
  type GameResult,
  type List,
  type Seat,
} from "@tcg-htc/runner";
import { join } from "node:path";
import { claudeAgent, type ClaudeAgent } from "./claudeAgent.js";
import type { ClaudeCodeCall, ClaudeConfig } from "./claudeCode.js";
import { agentTotals, gameFileName, writeGameFile, type GameFile, type GameFileSetup } from "./gameFile.js";

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
  /** How each Seat's Decklist comes from its List. The seeded picker by default. */
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

export interface PlayedGame extends WrittenGameFile {
  result: GameResult;
  agents: readonly [ClaudeAgent, ClaudeAgent];
}

/** Plays one Game and returns its result with the final Game file. */
export async function playGame(options: PlayGameOptions): Promise<PlayedGame> {
  const { seed, lists, configs, call, runDir, decklistPicker = pickDecklist, onDecision, clock = () => performance.now() } = options;
  const startingSeat: Seat = 0;
  const decklists = [decklistPicker(lists[0], seed), decklistPicker(lists[1], seed)] as const;
  const agents = ([0, 1] as const).map((seat) =>
    claudeAgent({ seat, decklist: decklists[seat], ...configs[seat] }, call, { resultsDir: runDir }),
  ) as unknown as readonly [ClaudeAgent, ClaudeAgent];
  const setup: GameFileSetup = {
    seed,
    startingSeat,
    lists: [lists[0].name, lists[1].name],
    heroes: [lists[0].hero.name, lists[1].hero.name],
    decklists,
    configs,
  };
  const systemPrompts = [agents[0].systemPrompt, agents[1].systemPrompt] as const;
  const path = join(runDir, gameFileName(seed, lists[0].hero.name));
  const started = clock();
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
        systemPrompts,
        replay: { decklists, seed, startingSeat, intents: [...progress.intents] },
        measurements: { ...summarise([...measured], clock() - started), ...totals(records) },
        decisions: [...records],
      };
      writeGameFile(path, file);
      onDecision?.(record, progress, { file, path });
    },
  });

  const file: GameFile = {
    status: "complete",
    setup,
    systemPrompts,
    replay: result.replay,
    outcome: outcomeOf(result),
    turns: result.turns,
    measurements: { ...result.measurements, ...totals(result.decisions) },
    decisions: result.decisions,
  };
  writeGameFile(path, file);
  return { result, file, path, agents };
}

function totals(records: readonly DecisionRecord[]): Pick<GameFile["measurements"], "perSeat" | "totals"> {
  return {
    perSeat: [agentTotals(records.filter(({ seat }) => seat === 0)), agentTotals(records.filter(({ seat }) => seat === 1))],
    totals: agentTotals(records),
  };
}

/** The outcome alone, without the rest of the result. */
export function outcomeOf(result: GameResult): GameOutcome {
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
