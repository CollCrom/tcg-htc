// Agents: the decision-makers occupying the Seats of a Game.
import type { GameIntent, GameView } from "@fyendal/shared";

/** A Seat, numbered 0 and 1 as in the engine. */
export type Seat = 0 | 1;

/** The other Seat. */
export function opponentOf(seat: Seat): Seat {
  return seat === 0 ? 1 : 0;
}

/** A single choice an Agent makes. Upstream calls it a `GameIntent`. */
export type Intent = GameIntent;

/** What one Seat is allowed to see of the Game. */
export type View = GameView;

/** A seeded source of numbers in [0, 1). */
export type Rng = () => number;

/** What an Agent returns for one decision: the Intent it chose, with what it
 * can say about choosing it, or a failure that ends the Game. */
export type Decision = DecisionChoice | DecisionFailure;

/** The Intent an Agent chose. The random Agent gives only the Intent; a Claude
 * Agent adds its reasoning, its rewritten Plan notes and its measurements. */
export interface DecisionChoice {
  intent: Intent;
  reasoning?: string;
  planNotes?: string;
  measurements?: AgentMeasurements;
}

/** An Agent that could not decide. The runner ends the Game as an error
 * outcome with the `detail`, keeping the `cause` so a rate limit can pause a
 * Run. The `detail` names the Seat and the Agent. */
export interface DecisionFailure {
  cause: DecisionFailureCause;
  detail: string;
  measurements?: AgentMeasurements;
}

export type DecisionFailureCause = "invalid-answer" | "timeout" | "refusal" | "failure" | "rate-limit";

/** Whether a Decision is a failure rather than a chosen Intent. */
export function isDecisionFailure(decision: Decision): decision is DecisionFailure {
  return "cause" in decision;
}

/** How an Agent decided: what a Claude Agent reports about its call(s). */
export interface AgentMeasurements {
  /** The model that answered, as Claude Code reports it. */
  model?: string;
  effort?: string;
  inputTokens?: number;
  cachedTokens?: number;
  outputTokens?: number;
  latencyMs?: number;
  /** Calls made after the first. */
  retries?: number;
  firstAnswerInvalid?: boolean;
  /** The Plan notes were over the limit and cut. */
  notesCut?: boolean;
  /** Claude Code's cost estimate. */
  costUsd?: number;
}

/** Chooses one of the legal Intents from its Seat's View. It is never handed
 * the full game state. */
export type Agent = (view: View, legalIntents: readonly Intent[], rng: Rng) => Promise<Decision>;

/** Picks uniformly from the legal Intents. */
export const randomAgent: Agent = async (_view, legalIntents, rng) => {
  const intent = legalIntents[Math.floor(rng() * legalIntents.length)];
  if (!intent) throw new Error("randomAgent was offered no legal Intent");
  return { intent };
};
