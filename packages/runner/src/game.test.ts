import { cardData } from "@fyendal/cards";
import type { CardView } from "@fyendal/shared";
import { describe, expect, it } from "vitest";
import { randomAgent, type Agent, type Intent, type Seat, type View } from "./agent.js";
import { replayGame, runGame } from "./game.js";
import { preconDecklist } from "./precons.js";
import { renderDecision } from "./render.js";

const decklists = [preconDecklist("precon-sbr"), preconDecklist("precon-sly")] as const;
const GAME_TIMEOUT = 15_000;

describe("runGame", () => {
  it(
    "plays two random Agents on precon Decklists to a win or a draw",
    () => {
      const result = runGame({ decklists, seed: 1, startPlayer: 0, agents: [randomAgent, randomAgent] });

      expect(["win", "draw"]).toContain(result.outcome);
      if (result.outcome === "win") expect([0, 1]).toContain(result.winner);
      expect(result.turns).toBeGreaterThan(1);
      expect(result.steps).toBeGreaterThan(result.turns);
    },
    GAME_TIMEOUT,
  );

  it(
    "hands each Agent only its own Seat's View and legal Intents",
    () => {
      const offers: { seat: Seat; args: unknown[] }[] = [];
      const recording =
        (seat: Seat): Agent =>
        (...args) => {
          offers.push({ seat, args });
          return randomAgent(...args);
        };

      runGame({ decklists, seed: 2, startPlayer: 1, agents: [recording(0), recording(1)] });

      expect(offers.map(({ seat }) => seat)).toEqual(expect.arrayContaining([0, 1]));
      for (const { seat, args } of offers) {
        expect(args).toHaveLength(3);
        const [view, legal] = args as Parameters<Agent>;
        expect(view).not.toHaveProperty("rngState");
        expect(view.players[seat].deck).toBeUndefined();
        const opponent = view.players[seat === 0 ? 1 : 0];
        expect(opponent.hand).toEqual([]);
        expect(opponent.deck).toBeUndefined();
        expect(legal.length).toBeGreaterThan(0);
        for (const intent of legal) expect(intent.kind).not.toMatch(/^concede$|-draw$/);
      }
      expect(offers.some(({ seat, args }) => (args as Parameters<Agent>)[0].players[seat === 0 ? 1 : 0].handCount > 0)).toBe(true);
    },
    GAME_TIMEOUT,
  );

  it(
    "plays the same Game from the same seed",
    () => {
      const options = { decklists, seed: 3, startPlayer: 0, agents: [randomAgent, randomAgent], clock: () => 0 } as const;

      expect(runGame(options)).toEqual(runGame(options));
      expect(runGame({ ...options, seed: 4 }).replay.intents).not.toEqual(runGame(options).replay.intents);
    },
    GAME_TIMEOUT,
  );

  it(
    "records a replay that replayGame reproduces exactly",
    () => {
      const result = runGame({ decklists, seed: 5, startPlayer: 1, agents: [randomAgent, randomAgent] });

      expect(result.replay).toMatchObject({ decklists, seed: 5, startPlayer: 1 });
      expect(result.replay.intents).toHaveLength(result.steps);
      expect(result.finalProjection.phase).toBe("game-over");
      expect(replayGame(result.replay)).toEqual(result.finalProjection);
    },
    GAME_TIMEOUT,
  );

  it(
    "measures every decision: Seat, Intents offered and estimated tokens",
    () => {
      const offered: number[] = [];
      const counting: Agent = (view, legal, rng) => {
        offered.push(legal.length);
        return randomAgent(view, legal, rng);
      };
      const { measurements, steps } = runGame({ decklists, seed: 7, startPlayer: 0, agents: [counting, counting] });

      expect(measurements.decisionsPerSeat[0]).toBeGreaterThan(0);
      expect(measurements.decisionsPerSeat[1]).toBeGreaterThan(0);
      expect(measurements.decisionsPerSeat[0] + measurements.decisionsPerSeat[1]).toBe(steps);
      expect(measurements.decisions).toHaveLength(steps);
      expect(measurements.decisions.map(({ intents }) => intents)).toEqual(offered);
      for (const decision of measurements.decisions) {
        expect(decision.reorderFreeIntents).toBeGreaterThan(0);
        expect(decision.reorderFreeIntents).toBeLessThanOrEqual(decision.intents);
        expect(decision.tokens).toBeGreaterThan(0);
      }
      expect(measurements.decisions.filter(({ seat }) => seat === 1)).toHaveLength(measurements.decisionsPerSeat[1]);
      expect(measurements.durationMs).toBeGreaterThan(0);
    },
    GAME_TIMEOUT,
  );

  it(
    "counts Intents that differ only in pitch order once",
    () => {
      const { measurements } = runGame({ decklists, seed: 8, startPlayer: 1, agents: [randomAgent, randomAgent] });

      expect(measurements.decisions.some((d) => d.reorderFreeIntents < d.intents)).toBe(true);
    },
    GAME_TIMEOUT,
  );

  it(
    "estimates tokens from a rendering more compact than the raw View",
    () => {
      const sizes: number[] = [];
      const sizing: Agent = (view, legal, rng) => {
        sizes.push(JSON.stringify({ view, legal }).length / 4);
        return randomAgent(view, legal, rng);
      };
      const { measurements } = runGame({ decklists, seed: 9, startPlayer: 0, agents: [sizing, sizing] });

      measurements.decisions.forEach(({ tokens }, i) => expect(tokens).toBeLessThan(sizes[i]!));
    },
    GAME_TIMEOUT,
  );

  it(
    "renders a decision without the opponent's hidden cards",
    () => {
      const offers: { step: number; seat: Seat; view: View; legal: readonly Intent[] }[] = [];
      const recording =
        (seat: Seat): Agent =>
        (view, legal, rng) => {
          offers.push({ step: offers.length, seat, view, legal });
          return randomAgent(view, legal, rng);
        };
      const { replay } = runGame({ decklists, seed: 10, startPlayer: 0, agents: [recording(0), recording(1)] });

      let secretsChecked = 0;
      for (const { step, seat, view, legal } of offers.filter((_, i) => i % 25 === 0)) {
        // Every card revealed, at the moment of this decision.
        const full = replayGame({ ...replay, intents: replay.intents.slice(0, step) }).players[seat === 0 ? 1 : 0];
        const hidden = [
          ...full.hand,
          ...(full.deck ?? []),
          ...full.arsenal.filter((card) => card.faceDown),
          ...full.graveyard.filter((card) => card.faceDown),
          ...full.banish.filter((card) => card.faceDown),
        ];
        const shown = JSON.stringify(view);
        const visibleNames = new Set([...shown.matchAll(/"cardId":"([^"]+)"/g)].map(([, id]) => cardData[id!]?.name));
        const secrets = new Set(hidden.map(nameOf).filter((name) => !visibleNames.has(name) && !shown.includes(name)));
        const text = renderDecision(view, seat, legal);
        for (const secret of secrets) expect(text).not.toContain(secret);
        secretsChecked += secrets.size;
      }
      expect(secretsChecked).toBeGreaterThan(0);
    },
    GAME_TIMEOUT,
  );

  it(
    "tells a replay with different Intents apart",
    () => {
      const result = runGame({ decklists, seed: 6, startPlayer: 0, agents: [randomAgent, randomAgent] });
      const shortened = { ...result.replay, intents: result.replay.intents.slice(0, -1) };

      expect(replayGame(shortened)).not.toEqual(result.finalProjection);
    },
    GAME_TIMEOUT,
  );
});

function nameOf(card: CardView): string {
  return cardData[card.cardId]?.name ?? card.name ?? card.cardId;
}
