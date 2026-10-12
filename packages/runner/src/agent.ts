// Agents: the decision-makers occupying the Seats of a Game.
import type { GameIntent, GameView } from "@fyendal/shared";

/** A Seat, numbered 0 and 1 as in the engine. */
export type Seat = 0 | 1;

/** A single choice an Agent makes. Upstream calls it a `GameIntent`. */
export type Intent = GameIntent;

/** What one Seat is allowed to see of the Game. */
export type View = GameView;

/** A seeded source of numbers in [0, 1). */
export type Rng = () => number;

/** Chooses one of the legal Intents from its Seat's View. It is never handed
 * the full game state. */
export type Agent = (view: View, legalIntents: readonly Intent[], rng: Rng) => Intent;

/** Picks uniformly from the legal Intents. */
export const randomAgent: Agent = (_view, legalIntents, rng) => {
  const intent = legalIntents[Math.floor(rng() * legalIntents.length)];
  if (!intent) throw new Error("randomAgent was offered no legal Intent");
  return intent;
};
