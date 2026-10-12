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
  return {
    seat,
    intents: legalIntents.length,
    reorderFreeIntents: new Set(legalIntents.map((intent) => reorderFreeKey(intent, view))).size,
    tokens: estimateTokens(renderDecision(view, seat, legalIntents)),
  };
}

/** Collects decision measurements into a Game's measurements. */
export function summarise(decisions: DecisionMeasurement[], durationMs: number): GameMeasurements {
  const decisionsPerSeat: [number, number] = [0, 0];
  for (const { seat } of decisions) decisionsPerSeat[seat]++;
  return { decisionsPerSeat, decisions, durationMs };
}

/** Identifies an Intent up to the order its cards are pitched in. A scripted
 * payment's `choose` option is keyed by the cards it pitches. */
function reorderFreeKey(intent: Intent, view: View): string {
  const byId = (a: number, b: number) => a - b;
  if (intent.kind === "choose") {
    const payment = view.pendingDecision?.resourcePayment?.options.find(({ optionId }) => optionId === intent.optionId);
    if (payment) return JSON.stringify({ kind: "pay", pitchInstanceIds: [...payment.pitchInstanceIds].sort(byId) });
  }
  if ("pitchInstanceIds" in intent && intent.pitchInstanceIds)
    return JSON.stringify({ ...intent, pitchInstanceIds: [...intent.pitchInstanceIds].sort(byId) });
  return JSON.stringify(intent);
}
