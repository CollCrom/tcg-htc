// The Claude Agent, driven through whole Games with the Claude Code call faked.
import { cardData } from "@fyendal/cards";
import type { CardView } from "@fyendal/shared";
import {
  BRAVO_LIST_FILE,
  fixtureList,
  IRA_LIST_FILE,
  opponentOf,
  pickDecklist,
  randomAgent,
  renderDecision,
  replayGame,
  runGame,
  type Agent,
  type View,
} from "@tcg-htc/runner";
import { describe, expect, it } from "vitest";
import type { CallResult } from "./claudeCode.js";
import { ANSWER_SCHEMA, claudeAgent, PLAN_NOTES_HEADING, PLAN_NOTES_LIMIT } from "./claudeAgent.js";
import { fakeClaudeCode, type RecordedCall } from "./fakeClaudeCode.js";

const SEED = 21;
const decklists = [pickDecklist(fixtureList(IRA_LIST_FILE), SEED), pickDecklist(fixtureList(BRAVO_LIST_FILE), SEED)] as const;
const GAME_TIMEOUT = 30_000;

const usage = { model: "claude-opus-4-1", inputTokens: 100, cachedTokens: 2000, outputTokens: 40, costUsd: 0.01, latencyMs: 1500 };

/** A scripted answer: the Intent number, with reasoning and Plan notes. */
const answer = (intent: unknown, planNotes = "keep pressure on", reasoning = "the first listed Intent looks fine"): CallResult => ({
  kind: "answer",
  output: { intent, reasoning, planNotes },
  turns: 2,
  usage,
});

/** How many Intents a decision message lists. */
function listedIntents({ message }: RecordedCall): number {
  const lines = message.split("\n");
  return lines.slice(lines.indexOf("Legal Intents:") + 1).filter((line) => /^\d+\. /.test(line)).length;
}

/** Answers a different listed Intent each call, so the Game moves along. */
const varied = (request: RecordedCall, index: number): CallResult => answer(1 + (index % listedIntents(request)));

/** An Agent that keeps the Views it was handed, for checks that need them. */
function recordingViews(agent: Agent, views: View[]): Agent {
  return (view, legal, rng) => {
    views.push(view);
    return agent(view, legal, rng);
  };
}

/** `varied` until call `at` (0-based), where `scripted` answer instead. */
const failingAt = (at: number, ...scripted: CallResult[]) => (request: RecordedCall, index: number): CallResult =>
  index >= at && index < at + scripted.length ? scripted[index - at]! : varied(request, index);

/** A Game with a Claude Agent at Seat 0 on `script`, against the random Agent. */
async function play(script: Parameters<typeof fakeClaudeCode>[0], seat: 0 | 1 = 0) {
  const fake = fakeClaudeCode(script);
  const agent = claudeAgent({ seat, decklist: decklists[seat], model: "opus", effort: "medium" }, fake);
  const agents: [Agent, Agent] = seat === 0 ? [agent, randomAgent] : [randomAgent, agent];
  const result = await runGame({ decklists, seed: SEED, startingSeat: 0, agents });
  return { fake, agent, result, own: result.decisions.filter((record) => record.seat === seat) };
}

describe("claudeAgent", () => {
  it(
    "plays a complete Game against the random Agent, one call per decision",
    async () => {
      const fake = fakeClaudeCode(varied);
      const agent = claudeAgent({ seat: 0, decklist: decklists[0], model: "opus", effort: "medium" }, fake);

      const result = await runGame({ decklists, seed: SEED, startingSeat: 0, agents: [agent, randomAgent] });

      expect(result.outcome, JSON.stringify(result.outcome === "error" ? result.detail : "")).toMatch(/^(win|draw)$/);
      const own = result.decisions.filter(({ seat }) => seat === 0);
      expect(own.length).toBeGreaterThan(0);
      expect(fake.calls).toHaveLength(own.length);
      for (const call of fake.calls) expect(call.config).toEqual({ model: "opus", effort: "medium" });
    },
    GAME_TIMEOUT,
  );

  it(
    "turns a valid answer into the engine Intent behind that number of the collapsed list",
    async () => {
      const fake = fakeClaudeCode(varied);
      const views: View[] = [];
      const agent = recordingViews(claudeAgent({ seat: 1, decklist: decklists[1], model: "sonnet", effort: "low" }, fake), views);

      const result = await runGame({ decklists, seed: SEED, startingSeat: 1, agents: [randomAgent, agent] });

      const own = result.decisions.filter(({ seat }) => seat === 1);
      expect(own).toHaveLength(views.length);
      let beyondFirst = 0;
      own.forEach((record, i) => {
        const chosen = 1 + (i % listedIntents(fake.calls[i]!));
        const { intents } = renderDecision(views[i]!, 1, record.intents);
        expect(intents).toHaveLength(listedIntents(fake.calls[i]!));
        expect(record.decision).toMatchObject({ intent: intents[chosen - 1] });
        if (chosen > 1) beyondFirst++;
      });
      expect(beyondFirst).toBeGreaterThan(0);
      expect(result.replay.intents.filter((_, step) => result.decisions[step]!.seat === 1)).toEqual(own.map(({ decision }) => "intent" in decision && decision.intent));
    },
    GAME_TIMEOUT,
  );

  it(
    "sends one system prompt for the whole Game: primer, Seat, objective, answer format and its own Decklist with card text",
    async () => {
      const fake = fakeClaudeCode(varied);
      const agent = claudeAgent({ seat: 0, decklist: decklists[0], model: "opus", effort: "medium" }, fake);

      await runGame({ decklists, seed: SEED, startingSeat: 0, agents: [agent, randomAgent] });

      const prompts = new Set(fake.calls.map(({ systemPrompt }) => systemPrompt));
      expect(prompts.size).toBe(1);
      const [prompt] = [...prompts] as [string];
      expect(prompt).toBe(agent.systemPrompt);
      expect(prompt).toContain("# Flesh and Blood: rules primer");
      expect(prompt).toContain("You are Seat 0.");
      expect(prompt).toContain("win the Game");
      expect(prompt).toContain("`intent`");
      expect(prompt).toContain("`planNotes`");
      expect(prompt).toContain("{p} power");
      const flyingKick = cardData[decklists[0].deck.find((id) => cardData[id]?.name === "Flying Kick")!]!;
      expect(prompt).toContain("2x Flying Kick (red): ninja action - attack. Cost 2, pitch 1, attack 5, defense 3. " + flyingKick.text);
      expect(prompt).toContain("Hero: Ira, Crimson Haze: ninja hero. Life 20, intellect 4. Your second attack each turn gets +1{p}.");
      for (const cardId of decklists[0].weaponIds) expect(prompt).toContain(cardData[cardId]!.name);
      for (const cardId of Object.values(decklists[0].equipment)) expect(prompt).toContain(cardData[cardId!]!.name);
      expect(prompt).not.toContain("Bravo, Flattering Showman");
    },
    GAME_TIMEOUT,
  );

  it(
    "sends the rendered decision and its current Plan notes, and asks for the three-field answer",
    async () => {
      const fake = fakeClaudeCode((request, index) => answer(1 + (index % listedIntents(request)), `plan after decision ${index}`));
      const agent = claudeAgent({ seat: 0, decklist: decklists[0], model: "opus", effort: "medium" }, fake);

      const result = await runGame({ decklists, seed: SEED, startingSeat: 0, agents: [agent, randomAgent] });

      const own = result.decisions.filter(({ seat }) => seat === 0);
      expect(fake.calls.length).toBeGreaterThan(1);
      fake.calls.forEach((call, i) => {
        expect(call.message).toBe(`${own[i]!.rendered}\n\n${PLAN_NOTES_HEADING}\n${i === 0 ? "" : `plan after decision ${i - 1}`}`);
        expect(call.schema).toBe(ANSWER_SCHEMA);
      });
      expect(Object.keys(ANSWER_SCHEMA.properties)).toEqual(["intent", "reasoning", "planNotes"]);
      expect(ANSWER_SCHEMA.required).toEqual(["intent", "reasoning", "planNotes"]);
      expect(ANSWER_SCHEMA.additionalProperties).toBe(false);
      expect(agent.planNotes).toBe(`plan after decision ${fake.calls.length - 1}`);
      own.forEach((record, i) => expect(record.decision).toMatchObject({ reasoning: expect.any(String), planNotes: `plan after decision ${i}` }));
    },
    GAME_TIMEOUT,
  );

  it(
    "retries an out-of-range Intent number once, telling the model the problem, and plays on from a valid retry",
    async () => {
      const { fake, result, own } = await play(failingAt(3, answer(99), answer(1)));

      expect(result.outcome).toMatch(/^(win|draw)$/);
      expect(fake.calls).toHaveLength(own.length + 1);
      const listed = listedIntents(fake.calls[3]!);
      expect(fake.calls[4]!.message).toBe(
        `${fake.calls[3]!.message}\n\nYour previous answer was not accepted. Answer again, fixing this problem:\nYour answer named Intent 99 but only 1 to ${listed} are listed`,
      );
      expect(own[3]!.decision).toMatchObject({
        measurements: { retries: 1, firstAnswerInvalid: true, inputTokens: 200, cachedTokens: 4000, outputTokens: 80, latencyMs: 3000, costUsd: 0.02 },
      });
      expect(own[2]!.decision).toMatchObject({ measurements: { retries: 0, firstAnswerInvalid: false, inputTokens: 100 } });
    },
    GAME_TIMEOUT,
  );

  it(
    "ends the Game as an error naming the Seat and the Agent when the retry is invalid too",
    async () => {
      const { fake, result, own } = await play(failingAt(2, answer(0), answer("three")), 1);

      expect(result).toMatchObject({ outcome: "error", cause: "invalid-answer", step: result.decisions.length - 1 });
      if (result.outcome !== "error") return;
      expect(result.detail).toContain("Seat 1's Claude Agent (opus, medium)");
      expect(result.detail).toContain("no Intent number");
      expect(fake.calls).toHaveLength(4);
      expect(fake.calls[3]!.message).toContain("Your answer named Intent 0 but only 1 to");
      expect(own).toHaveLength(3);
      expect(own[2]!.decision).toEqual({
        cause: "invalid-answer",
        detail: result.detail,
        measurements: expect.objectContaining({ model: usage.model, effort: "medium", retries: 1, firstAnswerInvalid: true, inputTokens: 200 }),
      });
    },
    GAME_TIMEOUT,
  );

  it(
    "cuts Plan notes over the limit and records the cut",
    async () => {
      const long = "plan ".repeat(PLAN_NOTES_LIMIT);
      const { fake, agent, result, own } = await play(failingAt(1, answer(1, long)));

      expect(result.outcome).toMatch(/^(win|draw)$/);
      expect(own[1]!.decision).toMatchObject({ planNotes: long.slice(0, PLAN_NOTES_LIMIT), measurements: { notesCut: true } });
      expect(own[0]!.decision).toMatchObject({ measurements: { notesCut: false } });
      expect(fake.calls[2]!.message.endsWith(`${PLAN_NOTES_HEADING}\n${long.slice(0, PLAN_NOTES_LIMIT)}`)).toBe(true);
      expect(agent.planNotes).toHaveLength("keep pressure on".length);
    },
    GAME_TIMEOUT,
  );

  for (const kind of ["refusal", "timeout", "failure"] as const) {
    it(
      `retries a ${kind} once with the same message, then ends the Game as an error with that cause`,
      async () => {
        const once = await play(failingAt(2, { kind, detail: `${kind} detail` }));
        expect(once.result.outcome).toMatch(/^(win|draw)$/);
        expect(once.fake.calls[3]!.message).toBe(once.fake.calls[2]!.message);
        expect(once.own[2]!.decision).toMatchObject({ measurements: { retries: 1, firstAnswerInvalid: false, inputTokens: 100 } });

        const twice = await play(failingAt(2, { kind, detail: `${kind} detail` }, { kind, detail: `${kind} again` }));
        expect(twice.result).toMatchObject({ outcome: "error", cause: kind, detail: `Seat 0's Claude Agent (opus, medium): ${kind} again` });
        expect(twice.fake.calls).toHaveLength(4);
        expect(twice.own[2]!.decision).toMatchObject({ cause: kind, measurements: { effort: "medium", retries: 1, inputTokens: 0, latencyMs: 0 } });
      },
      GAME_TIMEOUT,
    );
  }

  it(
    "ends the Game at once with cause rate-limit, without a retry",
    async () => {
      const { fake, result, own } = await play(failingAt(1, { kind: "rate-limit", detail: "You've hit your limit" }));

      expect(result).toMatchObject({ outcome: "error", cause: "rate-limit", detail: "Seat 0's Claude Agent (opus, medium): You've hit your limit" });
      expect(fake.calls).toHaveLength(2);
      expect(own[1]!.decision).toMatchObject({ cause: "rate-limit", measurements: { retries: 0 } });
    },
    GAME_TIMEOUT,
  );

  it(
    "records every measurement on every Decision",
    async () => {
      const { own } = await play(varied);

      for (const { decision } of own) {
        expect(decision.measurements).toEqual({
          model: usage.model,
          effort: "medium",
          inputTokens: 100,
          cachedTokens: 2000,
          outputTokens: 40,
          latencyMs: 1500,
          retries: 0,
          firstAnswerInvalid: false,
          notesCut: false,
          costUsd: 0.01,
        });
      }
    },
    GAME_TIMEOUT,
  );

  it(
    "starts from the Plan notes it is given, for a resumed Game",
    async () => {
      const fake = fakeClaudeCode(varied);
      const agent = claudeAgent({ seat: 0, decklist: decklists[0], model: "opus", effort: "medium" }, fake, { planNotes: "restored plan" });

      expect(agent.planNotes).toBe("restored plan");
      await runGame({ decklists, seed: SEED, startingSeat: 0, agents: [agent, randomAgent] });

      expect(fake.calls[0]!.message.endsWith(`${PLAN_NOTES_HEADING}\nrestored plan`)).toBe(true);
      expect(agent.planNotes).toBe("keep pressure on");
    },
    GAME_TIMEOUT,
  );

  it(
    "never sends either Claude Agent an opponent's hidden card, in the system prompt or in any message",
    async () => {
      // The Agent-honesty test: the whole text each call sends, at every decision of a Game between two Claude Agents.
      const fakes = [fakeClaudeCode(varied), fakeClaudeCode(varied)] as const;
      const views: View[] = [];
      const agents = ([0, 1] as const).map((seat) =>
        recordingViews(claudeAgent({ seat, decklist: decklists[seat], model: "opus", effort: "medium" }, fakes[seat]), views),
      ) as [Agent, Agent];

      const { replay, decisions, outcome } = await runGame({ decklists, seed: SEED, startingSeat: 1, agents });

      expect(outcome).toMatch(/^(win|draw)$/);
      expect(decisions).toHaveLength(views.length);
      expect(fakes[0].calls.length + fakes[1].calls.length).toBe(decisions.length);
      const callsBySeat: [number, number] = [0, 0];
      let secretsChecked = 0;
      decisions.forEach(({ seat }, step) => {
        const view = views[step]!;
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
        // A card in the Agent's own Decklist is its own knowledge, even if the opponent holds a copy.
        const ownNames = new Set(Object.values(decklistCards(seat)).map((id) => cardData[id]?.name));
        const secrets = new Set(hidden.map(nameOf).filter((name) => !visibleNames.has(name) && !shown.includes(name) && !ownNames.has(name)));
        const call = fakes[seat].calls[callsBySeat[seat]++]!;
        for (const secret of secrets) {
          expect(call.systemPrompt).not.toContain(secret);
          expect(call.message).not.toContain(secret);
        }
        secretsChecked += secrets.size;
      });
      expect(secretsChecked).toBeGreaterThan(0);
    },
    /** Replays the Game up to every decision. */
    3 * GAME_TIMEOUT,
  );
});

/** Every printing id a Seat's Decklist holds. */
function decklistCards(seat: 0 | 1): string[] {
  const decklist = decklists[seat];
  return [decklist.heroId, ...decklist.weaponIds, ...Object.values(decklist.equipment).filter((id): id is string => !!id), ...decklist.deck];
}

function nameOf(card: CardView): string {
  return cardData[card.cardId]?.name ?? card.name ?? card.cardId;
}
