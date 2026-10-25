import { cardData } from "@fyendal/cards";
import type { CardView } from "@fyendal/shared";
import { describe, expect, it } from "vitest";
import { opponentOf, randomAgent, type Agent, type Decision, type Intent, type Seat, type View } from "./agent.js";
import { isFailure, MAX_STEPS, replayGame, runGame, type DecisionProgress, type DecisionRecord } from "./game.js";
import { BRAVO_LIST_FILE, fixtureList, IRA_LIST_FILE } from "./list/fixtureLists.js";
import { pickDecklist } from "./list/pickDecklist.js";
import { preconDecklist } from "./precons.js";
import { renderDecision } from "./render.js";

const decklists = [preconDecklist("precon-sbr"), preconDecklist("precon-sly")] as const;
/** The Phase 2 Decklists, free of the card whose `canPlay` is impure (#180),
 * so a paused Game's live state and its replay agree. */
const iraVsBravo = [pickDecklist(fixtureList(IRA_LIST_FILE), 12), pickDecklist(fixtureList(BRAVO_LIST_FILE), 12)] as const;
const GAME_TIMEOUT = 15_000;
/** A stalled Game plays all MAX_STEPS steps, then replays them. */
const STALL_TIMEOUT = 60_000;

describe("runGame", () => {
  it(
    "plays two random Agents on precon Decklists to a win or a draw",
    async () => {
      const result = await runGame({ decklists, seed: 1, startingSeat: 0, agents: [randomAgent, randomAgent] });

      expect(["win", "draw"]).toContain(result.outcome);
      if (result.outcome === "win") expect([0, 1]).toContain(result.winner);
      expect(result.turns).toBeGreaterThan(1);
      expect(result.steps).toBeGreaterThan(result.turns);
    },
    GAME_TIMEOUT,
  );

  it(
    "hands each Agent only its own Seat's View and legal Intents",
    async () => {
      const offers: { seat: Seat; args: unknown[] }[] = [];
      const recording =
        (seat: Seat): Agent =>
        (...args) => {
          offers.push({ seat, args });
          return randomAgent(...args);
        };

      await runGame({ decklists, seed: 2, startingSeat: 1, agents: [recording(0), recording(1)] });

      expect(offers.map(({ seat }) => seat)).toEqual(expect.arrayContaining([0, 1]));
      for (const { seat, args } of offers) {
        expect(args).toHaveLength(4);
        const [view, legal, , rendered] = args as Parameters<Agent>;
        expect(view).not.toHaveProperty("rngState");
        // The rendering is of this Seat's View, with the legal Intents behind its numbered entries.
        expect(rendered.text).toContain(`You are Seat ${seat}`);
        expect(rendered.entries).toHaveLength(rendered.intents.length);
        for (const intent of rendered.intents) expect(legal).toContain(intent);
        expect(view.players[seat].deck).toBeUndefined();
        const opponent = view.players[opponentOf(seat)];
        expect(opponent.hand).toEqual([]);
        expect(opponent.deck).toBeUndefined();
        expect(legal.length).toBeGreaterThan(0);
        for (const intent of legal) expect(intent.kind).not.toMatch(/^concede$|-draw$/);
      }
      expect(offers.some(({ seat, args }) => (args as Parameters<Agent>)[0].players[opponentOf(seat)].handCount > 0)).toBe(true);
    },
    GAME_TIMEOUT,
  );

  it(
    "plays the same Game from the same seed",
    async () => {
      const options = { decklists, seed: 3, startingSeat: 0, agents: [randomAgent, randomAgent], clock: () => 0 } as const;

      expect(await runGame(options)).toEqual(await runGame(options));
      expect((await runGame({ ...options, seed: 4 })).replay.intents).not.toEqual((await runGame(options)).replay.intents);
    },
    GAME_TIMEOUT,
  );

  it(
    "records a replay that replayGame reproduces exactly",
    async () => {
      const result = await runGame({ decklists, seed: 5, startingSeat: 1, agents: [randomAgent, randomAgent] });

      expect(result.replay).toMatchObject({ decklists, seed: 5, startingSeat: 1 });
      expect(result.replay.intents).toHaveLength(result.steps);
      expect(result.finalProjection.phase).toBe("game-over");
      expect(replayGame(result.replay)).toEqual(result.finalProjection);
    },
    GAME_TIMEOUT,
  );

  it(
    "measures every decision: Seat, Intents offered and estimated tokens",
    async () => {
      const offered: number[] = [];
      const counting: Agent = (view, legal, rng, rendered) => {
        offered.push(legal.length);
        return randomAgent(view, legal, rng, rendered);
      };
      const { measurements, steps } = await runGame({ decklists, seed: 7, startingSeat: 0, agents: [counting, counting] });

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
    async () => {
      const { measurements } = await runGame({ decklists, seed: 8, startingSeat: 1, agents: [randomAgent, randomAgent] });

      expect(measurements.decisions.some((d) => d.reorderFreeIntents < d.intents)).toBe(true);
    },
    GAME_TIMEOUT,
  );

  it(
    "estimates tokens from a rendering more compact than the raw View",
    async () => {
      const sizes: number[] = [];
      const sizing: Agent = (view, legal, rng, rendered) => {
        sizes.push(JSON.stringify({ view, legal }).length / 4);
        return randomAgent(view, legal, rng, rendered);
      };
      const { measurements } = await runGame({ decklists, seed: 9, startingSeat: 0, agents: [sizing, sizing] });

      measurements.decisions.forEach(({ tokens }, i) => expect(tokens).toBeLessThan(sizes[i]!));
    },
    GAME_TIMEOUT,
  );

  it(
    "renders a decision without the opponent's hidden cards",
    async () => {
      // The Agent-honesty standard: the text in each Decision record, which is what an Agent is shown, names no hidden card.
      const offers: { step: number; seat: Seat; view: View }[] = [];
      const recording =
        (seat: Seat): Agent =>
        (view, legal, rng, rendered) => {
          offers.push({ step: offers.length, seat, view });
          return randomAgent(view, legal, rng, rendered);
        };
      const { replay, decisions } = await runGame({ decklists, seed: 10, startingSeat: 0, agents: [recording(0), recording(1)] });

      expect(decisions).toHaveLength(offers.length);
      let secretsChecked = 0;
      for (const { step, seat, view } of offers) {
        // Every card revealed, at the moment of this decision.
        const full = replayGame({ ...replay, intents: replay.intents.slice(0, step) }).players[opponentOf(seat)];
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
        const text = decisions[step]!.rendered;
        for (const secret of secrets) expect(text).not.toContain(secret);
        secretsChecked += secrets.size;
      }
      expect(secretsChecked).toBeGreaterThan(0);
    },
    /** Replays the Game up to every decision: about 7 s locally. */
    2 * GAME_TIMEOUT,
  );

  it(
    "tells a replay with different Intents apart",
    async () => {
      const result = await runGame({ decklists, seed: 6, startingSeat: 0, agents: [randomAgent, randomAgent] });
      const shortened = { ...result.replay, intents: result.replay.intents.slice(0, -1) };

      expect(replayGame(shortened)).not.toEqual(result.finalProjection);
    },
    GAME_TIMEOUT,
  );

  it(
    "reports a Game that runs past the step cap as a stall with its seed",
    async () => {
      const passing: Agent = (view, legal, rng, rendered) => {
        const pass = legal.find((intent) => intent.kind === "pass");
        return pass ? Promise.resolve({ intent: pass }) : randomAgent(view, legal, rng, rendered);
      };

      const result = await runGame({ decklists, seed: 7, startingSeat: 0, agents: [passing, passing] });

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
    "caps a Game at the steps it is given instead of the default, ending it as a stall",
    async () => {
      const passing: Agent = (view, legal, rng, rendered) => {
        const pass = legal.find((intent) => intent.kind === "pass");
        return pass ? Promise.resolve({ intent: pass }) : randomAgent(view, legal, rng, rendered);
      };

      const result = await runGame({ decklists, seed: 7, startingSeat: 0, agents: [passing, passing], maxSteps: 40 });

      expect(result).toMatchObject({ outcome: "stall", seed: 7, step: 40, steps: 40, detail: "Game exceeded 40 steps" });
      expect(result.replay.intents).toHaveLength(40);
      expect(result.decisions).toHaveLength(40);
    },
    GAME_TIMEOUT,
  );

  it(
    "reports an Intent the engine rejects as an error with its seed, step and the engine's message",
    async () => {
      let decisions = 0;
      const illegalOnFourth: Agent = (view, legal, rng, rendered) =>
        ++decisions === 4
          ? Promise.resolve({ intent: { kind: "play-card", instanceId: -1, pitchInstanceIds: [] } })
          : randomAgent(view, legal, rng, rendered);

      const result = await runGame({ decklists, seed: 8, startingSeat: 1, agents: [illegalOnFourth, illegalOnFourth] });

      expect(result).toMatchObject({ outcome: "error", seed: 8, step: 3, steps: 3 });
      if (result.outcome !== "error") return;
      expect(result.detail).toContain("card not found");
      expect(result.replay.intents).toHaveLength(3);
      expect(replayGame(result.replay)).toEqual(result.finalProjection);
    },
    GAME_TIMEOUT,
  );
  it(
    "records a Decision record per decision: Seat, rendered text, Intents offered and the Decision",
    async () => {
      const offers: { seat: Seat; view: View; legal: readonly Intent[]; decision: Decision }[] = [];
      const recording =
        (seat: Seat): Agent =>
        async (view, legal, rng, rendered) => {
          const decision: Decision = { ...(await randomAgent(view, legal, rng, rendered)), reasoning: `decision ${offers.length}`, planNotes: "keep attacking" };
          offers.push({ seat, view, legal, decision });
          return decision;
        };

      const result = await runGame({ decklists, seed: 11, startingSeat: 0, agents: [recording(0), recording(1)] });

      expect(result.outcome).toBe("win");
      expect(result.decisions).toHaveLength(result.steps);
      expect(result.decisions).toHaveLength(offers.length);
      result.decisions.forEach((record, i) => {
        const offer = offers[i]!;
        expect(record.seat).toBe(offer.seat);
        expect(record.intents).toEqual(offer.legal);
        expect(record.decision).toEqual(offer.decision);
        expect(record.rendered).toContain(`You are Seat ${offer.seat}`);
        for (const card of offer.view.players[offer.seat].hand) expect(record.rendered).toContain(nameOf(card));
      });
    },
    GAME_TIMEOUT,
  );
  it(
    "ends the Game as an error when an Agent returns a failure Decision, naming its detail and keeping its cause",
    async () => {
      let decisions = 0;
      const failure: Decision = { cause: "timeout", detail: "Seat 1's Claude Agent (opus, medium) timed out" };
      const failingOnFourth: Agent = (view, legal, rng, rendered) => (++decisions === 4 ? Promise.resolve(failure) : randomAgent(view, legal, rng, rendered));

      const result = await runGame({ decklists, seed: 12, startingSeat: 1, agents: [failingOnFourth, failingOnFourth] });

      expect(result).toMatchObject({ outcome: "error", seed: 12, step: 3, steps: 3, detail: failure.detail, cause: "timeout" });
      expect(isFailure(result)).toBe(true);
      expect(result.decisions).toHaveLength(4);
      expect(result.decisions[3]!.decision).toEqual(failure);
      expect(result.replay.intents).toHaveLength(3);
      expect(result.finalProjection.phase).not.toBe("game-over");
    },
    GAME_TIMEOUT,
  );

  it(
    "pauses the Game, not failing it, when an Agent's failure Decision is a rate limit: the record kept, no Intent applied, the replay intact",
    async () => {
      let decisions = 0;
      const failure: Decision = { cause: "rate-limit", detail: "Seat 1's Claude Agent (opus, medium): You've hit your limit" };
      const failingOnFourth: Agent = (view, legal, rng, rendered) => (++decisions === 4 ? Promise.resolve(failure) : randomAgent(view, legal, rng, rendered));

      const result = await runGame({ decklists: iraVsBravo, seed: 12, startingSeat: 1, agents: [failingOnFourth, failingOnFourth] });

      expect(result).toMatchObject({ outcome: "paused", seed: 12, step: 3, steps: 3, detail: failure.detail, cause: "rate-limit" });
      expect(isFailure(result)).toBe(false);
      expect(result.decisions).toHaveLength(4);
      expect(result.decisions[3]!.decision).toEqual(failure);
      expect(result.replay.intents).toHaveLength(3);
      expect(replayGame(result.replay)).toEqual(result.finalProjection);
    },
    GAME_TIMEOUT,
  );

  it(
    "pauses before a decision once `shouldStop` says so, with every applied Intent in the replay and no record for the decision not made",
    async () => {
      let decisions = 0;
      const counting: Agent = (view, legal, rng, rendered) => {
        decisions++;
        return randomAgent(view, legal, rng, rendered);
      };

      const result = await runGame({ decklists: iraVsBravo, seed: 13, startingSeat: 0, agents: [counting, counting], shouldStop: () => decisions >= 5 });

      expect(result).toMatchObject({ outcome: "paused", seed: 13, step: 5, steps: 5 });
      expect(result).not.toHaveProperty("cause");
      expect(isFailure(result)).toBe(false);
      expect(decisions).toBe(5);
      expect(result.decisions).toHaveLength(5);
      expect(result.replay.intents).toHaveLength(5);
      expect(result.finalProjection.phase).not.toBe("game-over");
      expect(replayGame(result.replay)).toEqual(result.finalProjection);
    },
    GAME_TIMEOUT,
  );

  it(
    "resumes from saved Intents: they are applied before the first new decision, and the result counts and replays from the start",
    async () => {
      const decklists = iraVsBravo;
      const whole = await runGame({ decklists, seed: 14, startingSeat: 1, agents: [randomAgent, randomAgent], clock: () => 0 });
      const half = Math.floor(whole.steps / 2);
      const saved = whole.replay.intents.slice(0, half);

      const resumed = await runGame({ decklists, seed: 14, startingSeat: 1, agents: [randomAgent, randomAgent], clock: () => 0, resume: { intents: saved } });

      expect(resumed.replay.intents.slice(0, half)).toEqual(saved);
      expect(resumed.steps).toBe(resumed.replay.intents.length);
      expect(resumed.steps).toBeGreaterThan(half);
      expect(resumed.decisions).toHaveLength(resumed.steps - half);
      expect(resumed.measurements.decisions).toHaveLength(resumed.steps - half);
      expect(["win", "draw"]).toContain(resumed.outcome);
      expect(replayGame(resumed.replay)).toEqual(resumed.finalProjection);
      // Stopping at once after the replay leaves exactly the saved Game.
      const stopped = await runGame({ decklists, seed: 14, startingSeat: 1, agents: [randomAgent, randomAgent], resume: { intents: saved }, shouldStop: () => true });
      expect(stopped).toMatchObject({ outcome: "paused", step: half, steps: half });
      expect(stopped.decisions).toEqual([]);
      expect(stopped.finalProjection).toEqual(replayGame({ ...whole.replay, intents: saved }));
    },
    GAME_TIMEOUT,
  );

  it(
    "reports each Decision record as it is made, with its step, its turn, the numbered Intents and the Intents applied so far",
    async () => {
      const seen: { record: DecisionRecord; progress: DecisionProgress; applied: number }[] = [];
      const views: View[] = [];
      const recording: Agent = (view, legal, rng, rendered) => {
        views.push(view);
        return randomAgent(view, legal, rng, rendered);
      };

      const result = await runGame({
        decklists,
        seed: 13,
        startingSeat: 0,
        agents: [recording, recording],
        onDecision: (record, progress) => seen.push({ record, progress, applied: progress.intents.length }),
      });

      expect(result.outcome).toBe("win");
      expect(seen).toHaveLength(result.decisions.length);
      seen.forEach(({ record, progress, applied }, i) => {
        expect(record).toBe(result.decisions[i]);
        expect(progress.step).toBe(i);
        expect(progress.turn).toBe(views[i]!.turn);
        expect(applied).toBe(i + 1);
        expect(progress.intents.slice(0, applied)).toEqual(result.replay.intents.slice(0, applied));
        expect(progress.rendered).toEqual(renderDecision(views[i]!, record.seat, record.intents));
        expect(progress.rendered.text).toBe(record.rendered);
        for (const intent of progress.rendered.intents) expect(record.intents).toContain(intent);
      });
      // The random Agent picks from the raw list, so its choice can be a pitch ordering the numbered entries fold away.
      expect(seen.some(({ record, progress }) => progress.rendered.intents.length < record.intents.length)).toBe(true);
      expect(seen.at(-1)!.progress.turn).toBe(result.turns);
    },
    GAME_TIMEOUT,
  );

  it(
    "reports a failure Decision's record too, with no Intent applied for it",
    async () => {
      let decisions = 0;
      const failure: Decision = { cause: "timeout", detail: "Seat 0's Claude Agent (opus, medium): timed out" };
      const failingOnThird: Agent = (view, legal, rng, rendered) => (++decisions === 3 ? Promise.resolve(failure) : randomAgent(view, legal, rng, rendered));
      const seen: { record: DecisionRecord; progress: DecisionProgress }[] = [];

      const result = await runGame({
        decklists,
        seed: 14,
        startingSeat: 0,
        agents: [failingOnThird, failingOnThird],
        onDecision: (record, progress) => seen.push({ record, progress: { ...progress, intents: [...progress.intents] } }),
      });

      expect(result).toMatchObject({ outcome: "error", step: 2, steps: 2 });
      expect(seen).toHaveLength(3);
      expect(seen[2]!.record.decision).toEqual(failure);
      expect(seen[2]!.progress).toMatchObject({ step: 2, intents: result.replay.intents });
      expect(seen[2]!.progress.intents).toHaveLength(2);
    },
    GAME_TIMEOUT,
  );
});

function nameOf(card: CardView): string {
  return cardData[card.cardId]?.name ?? card.name ?? card.cardId;
}
