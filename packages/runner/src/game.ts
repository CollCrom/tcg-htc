// runGame: plays one Game between two Agents and records its replay.
import { cardData, scripts } from "@fyendal/cards";
import {
  applyIntent,
  createGame,
  legalIntents as engineLegalIntents,
  projectStateFor,
  projectStateForReplay,
  rngNext,
  type GameState,
} from "@fyendal/engine";
import type { Decklist, GameView } from "@fyendal/shared";
import { isDecisionFailure, type Agent, type Decision, type DecisionFailureCause, type Intent, type Rng, type Seat } from "./agent.js";
import { measureDecision, summarise, type DecisionMeasurement, type GameMeasurements } from "./measure.js";
import { renderDecision } from "./render.js";

/** Steps after which a Game is abandoned. */
export const MAX_STEPS = 5_000;

export interface GameSetup {
  decklists: readonly [Decklist, Decklist];
  /** A 32-bit integer. */
  seed: number;
  /** The Seat that takes the first turn. */
  startingSeat: Seat;
}

export interface RunGameOptions extends GameSetup {
  agents: readonly [Agent, Agent];
  /** Milliseconds from an arbitrary origin, for timing the Game. Defaults to
   * `performance.now`; inject a fixed clock to compare results exactly. */
  clock?: () => number;
  /** Called with each Decision record as soon as it is complete: after its
   * Intent is applied, or at once for a failure or an Intent the engine
   * rejects. A Run writes its Game file and prints its progress line here. */
  onDecision?: (record: DecisionRecord, progress: DecisionProgress) => void;
  /** Steps after which the Game is abandoned as a stall. `MAX_STEPS` by
   * default; a Run between Claude Agents sets a lower cap. */
  maxSteps?: number;
}

/** Where a Game stands after one decision. */
export interface DecisionProgress {
  /** The decision's index: the number of Intents applied before it. */
  step: number;
  /** The turn the decision was made in. */
  turn: number;
  /** Every Intent applied so far, this decision's included when it was. */
  intents: readonly Intent[];
  /** The Intents behind the numbered entries of the record's `rendered` text
   * (`renderDecision`'s `intents`), so a chosen Intent resolves to its entry. */
  listed: readonly Intent[];
}

/** How a Game ended. A stall or an error is returned rather than thrown, with
 * what's needed to reproduce it: the seed, and the step at which it happened. */
export type GameOutcome =
  | { outcome: "win"; winner: Seat }
  | { outcome: "draw" }
  | GameFailure<"stall">
  | GameError;

/** Whether a Game went wrong: a stall or an error rather than a win or a draw. */
export function isFailure(outcome: GameOutcome): outcome is GameFailure<"stall"> | GameError {
  return outcome.outcome === "stall" || outcome.outcome === "error";
}

/** A Game that went wrong at `step` (the number of Intents applied before it).
 * A stall exceeded the step cap or left the acting Seat without a legal Intent;
 * an error is an Intent the engine rejected, with the engine's message, or an
 * Agent's failure Decision, with its detail. */
export interface GameFailure<Kind extends "stall" | "error"> {
  outcome: Kind;
  seed: number;
  step: number;
  detail: string;
}

/** An error outcome. When an Agent's failure Decision ended the Game, `cause`
 * says why, so a Run can tell a rate limit from the rest. */
export type GameError = GameFailure<"error"> & { cause?: DecisionFailureCause };

/** The saved account of one decision of a Game. */
export interface DecisionRecord {
  seat: Seat;
  /** The View and legal Intents as rendered for the Agent. */
  rendered: string;
  /** Every legal Intent offered. The numbered entries of `rendered` are the
   * `intents` of `renderDecision`: the same list with pitch orderings collapsed. */
  intents: readonly Intent[];
  decision: Decision;
}

/** Everything needed to play a Game again: its setup and the Intents applied,
 * in order. Each Intent was applied by the Seat acting at that step. */
export interface Replay extends GameSetup {
  intents: Intent[];
}

/** The engine's full-information projection of a Game, every card revealed. */
export type ReplayProjection = GameView;

export type GameResult = GameOutcome & {
  turns: number;
  steps: number;
  replay: Replay;
  /** The replay projection of the final state; `replayGame(replay)` reproduces it. */
  finalProjection: ReplayProjection;
  measurements: GameMeasurements;
  /** One record per decision, in order. */
  decisions: DecisionRecord[];
};

export async function runGame(options: RunGameOptions): Promise<GameResult> {
  const { decklists, seed, startingSeat, agents, clock = () => performance.now(), onDecision, maxSteps = MAX_STEPS } = options;
  const started = clock();
  let state = newGame({ decklists, seed, startingSeat });
  const rngs = [seatRng(seed, 0), seatRng(seed, 1)] as const;
  const intents: Intent[] = [];
  const measured: DecisionMeasurement[] = [];
  const decisions: DecisionRecord[] = [];
  let steps = 0;
  let failure: GameOutcome | undefined;
  for (; state.phase !== "game-over"; steps++) {
    if (steps >= maxSteps) {
      failure = { outcome: "stall", seed, step: steps, detail: `Game exceeded ${maxSteps} steps` };
      break;
    }
    const seat = actingSeat(state);
    const legal = legalIntents(state, seat);
    if (legal.length === 0) {
      failure = { outcome: "stall", seed, step: steps, detail: `Seat ${seat} has no legal Intent` };
      break;
    }
    const view = projectStateFor(state, seat);
    const rendered = renderDecision(view, seat, legal);
    measured.push(measureDecision(seat, legal, rendered));
    const decision = await agents[seat](view, legal, rngs[seat]);
    const record: DecisionRecord = { seat, rendered: rendered.text, intents: legal, decision };
    decisions.push(record);
    const report = () => onDecision?.(record, { step: steps, turn: view.turn, intents, listed: rendered.intents });
    if (isDecisionFailure(decision)) {
      failure = { outcome: "error", seed, step: steps, detail: decision.detail, cause: decision.cause };
      report();
      break;
    }
    const { intent } = decision;
    const applied = applyIntent(state, seat, intent);
    if (!applied.ok) {
      failure = { outcome: "error", seed, step: steps, detail: `engine rejected ${intent.kind}: ${applied.error}` };
      report();
      break;
    }
    state = applied.state;
    intents.push(intent);
    report();
  }
  return {
    ...(failure ?? outcomeOf(state)),
    turns: state.turn,
    steps,
    replay: { decklists, seed, startingSeat, intents },
    finalProjection: projectStateForReplay(state),
    measurements: summarise(measured, clock() - started),
    decisions,
  };
}

/** Plays a replay's Intents from a fresh Game and returns the final replay
 * projection. Throws if the engine rejects one of them. */
export function replayGame(replay: Replay): ReplayProjection {
  let state = newGame(replay);
  replay.intents.forEach((intent, step) => {
    const seat = actingSeat(state);
    const applied = applyIntent(state, seat, intent);
    if (!applied.ok) throw new Error(`seed ${replay.seed}, step ${step}: engine rejected ${intent.kind}: ${applied.error}`);
    state = applied.state;
  });
  return projectStateForReplay(state);
}

function newGame({ decklists, seed, startingSeat }: GameSetup): GameState {
  return createGame({ decklists: [decklists[0], decklists[1]], cards: cardData, scripts, seed, startPlayer: startingSeat }); // glossary: upstream
}

/** The pending decision's Seat if there is one, otherwise the Seat with priority. */
function actingSeat(state: GameState): Seat {
  return (state.pendingDecision?.player ?? state.priorityPlayer) === 1 ? 1 : 0;
}

/** The engine's legal Intents for a Seat, without concede and draw offers. */
function legalIntents(state: GameState, seat: Seat): Intent[] {
  // Upstream has no View-based legal-Intents API, so these come from the full
  // state; they cover only this Seat's own choices, so they reveal nothing hidden.
  return engineLegalIntents(state, seat).filter(
    (intent) => intent.kind !== "concede" && !intent.kind.endsWith("-draw"),
  );
}

/** An rng seeded from the Game seed and the Seat. */
function seatRng(seed: number, seat: Seat): Rng {
  const rng = { rngState: (seed ^ Math.imul(seat + 1, 0x9e3779b9)) | 0 };
  return () => rngNext(rng);
}

function outcomeOf(state: GameState): GameOutcome {
  return state.winner === 0 || state.winner === 1 ? { outcome: "win", winner: state.winner } : { outcome: "draw" };
}
