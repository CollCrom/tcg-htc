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
import type { Agent, Intent, Rng, Seat } from "./agent.js";

/** Steps after which a Game is abandoned. */
export const MAX_STEPS = 5_000;

export interface GameSetup {
  decklists: readonly [Decklist, Decklist];
  /** A 32-bit integer. */
  seed: number;
  startPlayer: Seat;
}

export interface RunGameOptions extends GameSetup {
  agents: readonly [Agent, Agent];
}

export type GameOutcome = { outcome: "win"; winner: Seat } | { outcome: "draw" };

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
};

export function runGame({ decklists, seed, startPlayer, agents }: RunGameOptions): GameResult {
  let state = newGame({ decklists, seed, startPlayer });
  const rngs = [seatRng(seed, 0), seatRng(seed, 1)] as const;
  const intents: Intent[] = [];
  let steps = 0;
  for (; state.phase !== "game-over"; steps++) {
    if (steps >= MAX_STEPS) throw new Error(`seed ${seed}: Game exceeded ${MAX_STEPS} steps`);
    const seat = actingSeat(state);
    const legal = legalIntents(state, seat);
    if (legal.length === 0) throw new Error(`seed ${seed}, step ${steps}: Seat ${seat} has no legal Intent`);
    const intent = agents[seat](projectStateFor(state, seat), legal, rngs[seat]);
    const applied = applyIntent(state, seat, intent);
    if (!applied.ok) throw new Error(`seed ${seed}, step ${steps}: engine rejected ${intent.kind}: ${applied.error}`);
    state = applied.state;
    intents.push(intent);
  }
  return {
    ...outcomeOf(state),
    turns: state.turn,
    steps,
    replay: { decklists, seed, startPlayer, intents },
    finalProjection: projectStateForReplay(state),
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

function newGame({ decklists, seed, startPlayer }: GameSetup): GameState {
  return createGame({ decklists: [decklists[0], decklists[1]], cards: cardData, scripts, seed, startPlayer });
}

/** The pending decision's Seat if there is one, otherwise the Seat with priority. */
function actingSeat(state: GameState): Seat {
  return (state.pendingDecision?.player ?? state.priorityPlayer) === 1 ? 1 : 0;
}

/** The engine's legal Intents for a Seat, without concede and draw offers. */
function legalIntents(state: GameState, seat: Seat): Intent[] {
  return engineLegalIntents(state, seat).filter(
    (intent) => intent.kind !== "concede" && !intent.kind.endsWith("-draw"),
  );
}

/** An rng seeded from the Game seed and the Seat. */
function seatRng(seed: number, seat: Seat): Rng {
  const carrier = { rngState: (seed ^ Math.imul(seat + 1, 0x9e3779b9)) | 0 };
  return () => rngNext(carrier);
}

function outcomeOf(state: GameState): GameOutcome {
  return state.winner === 0 || state.winner === 1 ? { outcome: "win", winner: state.winner } : { outcome: "draw" };
}
