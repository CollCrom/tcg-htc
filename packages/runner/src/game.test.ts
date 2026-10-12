import { describe, expect, it } from "vitest";
import { randomAgent, type Agent, type Seat } from "./agent.js";
import { MAX_STEPS, replayGame, runGame } from "./game.js";
import { preconDecklist } from "./precons.js";

const decklists = [preconDecklist("precon-sbr"), preconDecklist("precon-sly")] as const;
const GAME_TIMEOUT = 15_000;
/** A stalled Game plays all MAX_STEPS steps, then replays them. */
const STALL_TIMEOUT = 60_000;

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
      const options = { decklists, seed: 3, startPlayer: 0, agents: [randomAgent, randomAgent] } as const;

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
    "tells a replay with different Intents apart",
    () => {
      const result = runGame({ decklists, seed: 6, startPlayer: 0, agents: [randomAgent, randomAgent] });
      const shortened = { ...result.replay, intents: result.replay.intents.slice(0, -1) };

      expect(replayGame(shortened)).not.toEqual(result.finalProjection);
    },
    GAME_TIMEOUT,
  );

  it(
    "reports a Game that runs past the step cap as a stall with its seed",
    () => {
      const passing: Agent = (view, legal, rng) => legal.find((intent) => intent.kind === "pass") ?? randomAgent(view, legal, rng);

      const result = runGame({ decklists, seed: 7, startPlayer: 0, agents: [passing, passing] });

      expect(result).toMatchObject({ outcome: "stall", seed: 7, step: MAX_STEPS, steps: MAX_STEPS });
      if (result.outcome !== "stall") return;
      expect(result.detail).toMatch(/steps/);
      expect(result.replay.intents).toHaveLength(MAX_STEPS);
      expect(result.finalProjection.phase).not.toBe("game-over");
      expect(replayGame(result.replay)).toEqual(result.finalProjection);
    },
    STALL_TIMEOUT,
  );

  it(
    "reports an Intent the engine rejects as an error with its seed, step and the engine's message",
    () => {
      let decisions = 0;
      const illegalOnFourth: Agent = (view, legal, rng) =>
        ++decisions === 4 ? { kind: "play-card", instanceId: -1, pitchInstanceIds: [] } : randomAgent(view, legal, rng);

      const result = runGame({ decklists, seed: 8, startPlayer: 1, agents: [illegalOnFourth, illegalOnFourth] });

      expect(result).toMatchObject({ outcome: "error", seed: 8, step: 3, steps: 3 });
      if (result.outcome !== "error") return;
      expect(result.detail).toContain("card not found");
      expect(result.replay.intents).toHaveLength(3);
      expect(replayGame(result.replay)).toEqual(result.finalProjection);
    },
    GAME_TIMEOUT,
  );
});
