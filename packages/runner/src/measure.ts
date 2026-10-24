// Measurements of a Game: what it would cost a Claude Agent to play it.
import type { Intent, Seat, View } from "./agent.js";
import { estimateTokens, renderDecision } from "./render.js";

/** One decision: the Seat that made it, the Intents it was offered and the
 * estimated tokens of its rendered View plus legal Intents. */
export interface DecisionMeasurement {
  seat: Seat;
  /** Legal Intents offered. */
  intents: number;
  /** Legal Intents offered, counting Intents that differ only in pitch order once. */
  reorderFreeIntents: number;
  /** Rendered View plus legal Intents, in characters ÷ 4. */
  tokens: number;
}

export interface GameMeasurements {
  /** Decisions made by each Seat. */
  decisionsPerSeat: [number, number];
  /** Every decision, in order. */
  decisions: DecisionMeasurement[];
  /** Wall-clock time to play the Game, in milliseconds. */
  durationMs: number;
}

/** Measures one decision from what the deciding Seat was shown. */
export function measureDecision(view: View, seat: Seat, legalIntents: readonly Intent[]): DecisionMeasurement {
  const rendered = renderDecision(view, seat, legalIntents);
  return {
    seat,
    intents: legalIntents.length,
    reorderFreeIntents: rendered.intents.length,
    tokens: estimateTokens(rendered.text),
  };
}

/** Collects decision measurements into a Game's measurements. */
export function summarise(decisions: DecisionMeasurement[], durationMs: number): GameMeasurements {
  const decisionsPerSeat: [number, number] = [0, 0];
  for (const { seat } of decisions) decisionsPerSeat[seat]++;
  return { decisionsPerSeat, decisions, durationMs };
}
