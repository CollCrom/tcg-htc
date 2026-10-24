// The Agent-honesty test: across a whole Game between two fake-backed Claude
// Agents, both Decklist builds included, no card of the opponent's Decklist
// reaches an Agent in a system prompt or a message unless a View it was shown
// at or before that call held it. The build call sees nothing of the opponent
// but the hero's name.
import { cardData, scripts } from "@fyendal/cards";
import { applyIntent, createGame, projectStateFor, projectStateForReplay } from "@fyendal/engine";
import type { CardView, Decklist } from "@fyendal/shared";
import { BRAVO_LIST_FILE, fixtureList, IRA_LIST_FILE, opponentOf, type List, type Seat } from "@tcg-htc/runner";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { DECKLIST_SCHEMA } from "./buildDecklist.js";
import type { CallResult } from "./claudeCode.js";
import { fakeClaudeCode, type RecordedCall } from "./fakeClaudeCode.js";
import { playGame } from "./playGame.js";
import { legalPresentation } from "./scriptedBuild.js";

const SEED = 21;
const lists = [fixtureList(BRAVO_LIST_FILE), fixtureList(IRA_LIST_FILE)] as const;
const usage = { model: "claude-opus-4-1", inputTokens: 100, cachedTokens: 2000, outputTokens: 40, costUsd: 0.01, latencyMs: 1500 };

function listedIntents({ message }: RecordedCall): number {
  const lines = message.split("\n");
  return lines.slice(lines.indexOf("Legal Intents:") + 1).filter((line) => /^\d+\. /.test(line)).length;
}

/** Builds legally for the Seat the system prompt names; plays a different listed Intent each call. */
const script = (request: RecordedCall, index: number): CallResult =>
  request.schema === DECKLIST_SCHEMA
    ? { kind: "answer", output: { ...legalPresentation(request.systemPrompt.includes("You are Seat 0.") ? lists[0] : lists[1]), reasoning: "built" }, turns: 2, usage }
    : { kind: "answer", output: { intent: 1 + (index % listedIntents(request)), reasoning: "fine", planNotes: "press on" }, turns: 2, usage };

/** Every card name a List holds, hero included. */
function namesOf(list: List): Set<string> {
  return new Set([list.hero.name, ...[...list.weapons, ...list.equipment, ...list.deck].map((card) => card.name)]);
}

function nameOf(card: CardView): string {
  return cardData[card.cardId]?.name ?? card.name ?? card.cardId;
}

let runDir: string | undefined;
afterAll(() => {
  if (runDir) rmSync(runDir, { recursive: true, force: true });
});

describe("honesty", () => {
  it(
    "never sends either Claude Agent a card of the opponent's Decklist it has not seen, in the builds, the system prompts or any message",
    async () => {
      runDir = mkdtempSync(join(tmpdir(), "tcg-htc-honesty-"));
      const fake = fakeClaudeCode(script);

      const played = await playGame({ seed: SEED, lists, configs: [{ model: "opus", effort: "medium" }, { model: "opus", effort: "medium" }], call: fake, runDir });

      const { result, file } = played;
      expect(result.outcome, JSON.stringify(result.outcome === "error" ? result.detail : "")).toMatch(/^(win|draw)$/);
      if (!("replay" in result)) throw new Error("the Game never started");
      expect(fake.calls).toHaveLength(2 + result.decisions.length);

      // The builds: nothing of the opponent but the hero's name. Cards both Lists hold are the Agent's own knowledge.
      for (const seat of [0, 1] as const) {
        const call = fake.calls[seat]!;
        const opponent = lists[opponentOf(seat)];
        const own = namesOf(lists[seat]);
        expect(call.schema).toBe(DECKLIST_SCHEMA);
        expect(call.message).toContain(opponent.hero.name);
        expect(call.systemPrompt).not.toContain(opponent.hero.name);
        for (const text of [call.systemPrompt, call.message]) {
          expect(text).not.toContain(opponent.name);
          for (const name of namesOf(opponent)) {
            if (name === opponent.hero.name || own.has(name)) continue;
            expect(text, `Seat ${seat}'s build call names ${name}`).not.toContain(name);
          }
        }
      }

      // The play: at every decision, every card of the opponent's Decklist that this Seat's View does not show.
      const { decklists } = result.replay;
      let state = createGame({ decklists: [decklists[0], decklists[1]], cards: cardData, scripts, seed: SEED, startPlayer: 0 }); // glossary: upstream
      let secretsChecked = 0;
      result.decisions.forEach((record, step) => {
        const seat: Seat = record.seat;
        const call = fake.calls[2 + step]!;
        const view = projectStateFor(state, seat);
        const shown = JSON.stringify(view);
        const visibleNames = new Set([...shown.matchAll(/"cardId":"([^"]+)"/g)].map(([, id]) => cardData[id!]?.name));
        const own = namesOf(lists[seat]);
        const opponent = projectStateForReplay(state).players[opponentOf(seat)];
        const opponentNames = [
          ...[...opponent.hand, ...(opponent.deck ?? []), ...opponent.arsenal, ...opponent.graveyard, ...opponent.banish].map(nameOf),
          ...decklistNames(decklists[opponentOf(seat)]),
        ];
        const secrets = new Set(opponentNames.filter((name) => !visibleNames.has(name) && !shown.includes(name) && !own.has(name)));
        expect(call.systemPrompt).toBe(file.systemPrompts![seat]);
        for (const secret of secrets) {
          expect(call.systemPrompt, `step ${step}: Seat ${seat}'s system prompt names ${secret}`).not.toContain(secret);
          expect(call.message, `step ${step}: Seat ${seat}'s message names ${secret}`).not.toContain(secret);
        }
        secretsChecked += secrets.size;
        if (!("intent" in record.decision)) throw new Error(`step ${step}: no Intent`);
        const applied = applyIntent(state, seat, record.decision.intent);
        if (!applied.ok) throw new Error(`step ${step}: ${applied.error}`);
        state = applied.state;
      });
      expect(secretsChecked).toBeGreaterThan(0);
    },
    90_000,
  );
});

/** Every card name of a Decklist but the hero's, so a card in a zone the
 * projection does not list still counts. */
function decklistNames(decklist: Decklist): string[] {
  const ids = [...decklist.weaponIds, ...Object.values(decklist.equipment).filter((id): id is string => !!id), ...decklist.deck];
  return ids.map((id) => cardData[id]?.name ?? id);
}
