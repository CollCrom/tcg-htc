// buildDecklist: before a Game, a Claude Agent builds its Decklist from its
// List in one Claude Code call, knowing only the opponent's hero. The answer
// goes through upstream's presentation validation; an invalid build is asked
// again once with the problem, then fails the way a play decision does.
import { cardData, validatePresentation } from "@fyendal/cards";
import type { Decklist, PresentedDeck } from "@fyendal/shared";
import {
  describeCardData,
  EQUIPMENT_SLOTS,
  toUpstreamList,
  type AgentMeasurements,
  type DecisionFailure,
  type List,
  type ListCard,
  type Seat,
} from "@tcg-htc/runner";
import { ask, failed, field } from "./ask.js";
import type { ClaudeCodeCall, ClaudeConfig } from "./claudeCode.js";
import { CARD_SYMBOLS_SECTION, primer } from "./prompt.js";

/** What a build answer must look like: printing ids from the List, and why. */
export const DECKLIST_SCHEMA = {
  type: "object",
  properties: {
    weaponIds: {
      type: "array",
      items: { type: "string" },
      description: "Printing ids of the weapon-zone cards you present: at most 2, at least one of them a weapon.",
    },
    equipment: {
      type: "object",
      properties: {
        head: { type: "string", description: "Printing id of your head equipment, if any." },
        chest: { type: "string", description: "Printing id of your chest equipment, if any." },
        arms: { type: "string", description: "Printing id of your arms equipment, if any." },
        legs: { type: "string", description: "Printing id of your legs equipment, if any." },
      },
      additionalProperties: false,
    },
    deck: {
      type: "array",
      items: { type: "string" },
      description: "Printing ids of the 40 cards in your deck, one entry per copy, no more copies of a card than your List holds.",
    },
    reasoning: { type: "string", description: "Why this build against this opponent, in a few sentences." },
  },
  required: ["weaponIds", "equipment", "deck", "reasoning"],
  additionalProperties: false,
} as const;

export interface BuildDecklistOptions {
  seat: Seat;
  list: List;
  /** The opponent's hero name: all the Agent learns of the opponent. */
  opponentHero: string;
  config: ClaudeConfig;
  call: ClaudeCodeCall;
  /** Where the call writes the system prompt file and runs Claude Code. */
  resultsDir: string;
}

/** A valid build: the ids as answered, the Decklist upstream made of them,
 * the reasoning and the call's measurements. */
export interface DecklistChoice {
  presented: PresentedDeck;
  decklist: Decklist;
  reasoning: string;
  measurements: AgentMeasurements;
}

/** What a build came to; a failure ends the Game before it starts. */
export type DecklistDecision = DecklistChoice | DecisionFailure;

/** The build's call, with what was sent, so a Game file can keep it. */
export interface DecklistBuild {
  systemPrompt: string;
  message: string;
  decision: DecklistDecision;
}

export async function buildDecklist({ seat, list, opponentHero, config, call, resultsDir }: BuildDecklistOptions): Promise<DecklistBuild> {
  const systemPrompt = buildDecklistSystemPrompt(seat, list);
  const message = buildDecklistMessage(opponentHero);
  const upstreamList = toUpstreamList(list);
  const asked = await ask({
    call,
    who: `Seat ${seat}'s Claude Agent (${config.model}, ${config.effort})`,
    systemPrompt,
    message,
    schema: DECKLIST_SCHEMA,
    config,
    resultsDir,
    read: (output) => {
      const presented = readPresentation(output);
      const result = validatePresentation(upstreamList, presented, list.format);
      if (!result.ok) return { ok: false, problem: `Your build is not legal: ${result.error}` };
      // Upstream accepts empty weapon zones; a Game here starts with a weapon.
      if (!presented.weaponIds.some((id) => cardData[id]?.cardType === "weapon")) {
        return { ok: false, problem: "Your build is not legal: weaponIds must hold at least one weapon (an off-hand alone is not enough)" };
      }
      return { ok: true, value: { presented, decklist: result.decklist, reasoning: text(field(output, "reasoning")) } };
    },
  });
  if (failed(asked)) return { systemPrompt, message, decision: asked };
  return { systemPrompt, message, decision: { ...asked.value, measurements: asked.measurements } };
}

const text = (value: unknown): string => (typeof value === "string" ? value : "");
const ids = (value: unknown): string[] => (Array.isArray(value) ? value.map((id) => text(id)) : []);

/** The answer's ids as upstream's validator takes them. Anything that isn't a
 * string id is dropped and fails validation as missing. */
function readPresentation(output: unknown): PresentedDeck {
  const equipment: PresentedDeck["equipment"] = {};
  const answered = field(output, "equipment");
  for (const slot of EQUIPMENT_SLOTS) {
    const id = field(answered, slot);
    if (typeof id === "string" && id) equipment[slot] = id;
  }
  return { weaponIds: ids(field(output, "weaponIds")), equipment, deck: ids(field(output, "deck")) };
}

/** The message: the opponent's hero, and nothing else about the opponent. */
export function buildDecklistMessage(opponentHero: string): string {
  return `Your opponent's hero is ${opponentHero}. Build your Decklist for this Game from your List.`;
}

/** The system prompt for a build: primer, Seat and task, card symbols, answer
 * format, and the whole List with printing ids and card text. */
export function buildDecklistSystemPrompt(seat: Seat, list: List): string {
  return [
    primer(),
    "## You",
    `You are Seat ${seat}. Before the Game, you build your Decklist from your List, as a player would, to win the Game.`,
    CARD_SYMBOLS_SECTION,
    "## How to answer",
    [
      "Answer with a JSON object of exactly four fields, naming cards by the printing id in square brackets before each card of your List.",
      "`weaponIds`: the printing ids of the weapon-zone cards you present, at most 2, at least one of them a weapon (an off-hand alone is not enough).",
      "`equipment`: one printing id per slot you fill, under `head`, `chest`, `arms` and `legs`; a piece fits only the slot(s) listed for it.",
      "`deck`: the printing ids of exactly 40 cards for your deck, one entry per copy, with no more copies of a card than your List holds.",
      "`reasoning`: why this build against this opponent, in a few sentences.",
    ].join("\n"),
    "## Your List",
    describeList(list),
  ].join("\n\n");
}

/** The List with printing ids and full card text: hero, weapon-zone cards,
 * equipment with the slots each piece fits, and the main-deck cards with
 * their copies. */
export function describeList(list: List): string {
  const describe = (cardId: string): string => {
    const data = cardData[cardId];
    return data ? describeCardData(data) : `${cardId}: no card data`;
  };
  const copies = (card: ListCard): string => (card.count === 1 ? "" : `${card.count} copies: `);
  return [
    `Hero: ${describe(list.hero.cardId)}`,
    "Weapon-zone cards:",
    ...list.weapons.map((card) => `- [${card.cardId}] ${copies(card)}${describe(card.cardId)}`),
    "Equipment:",
    ...list.equipment.map((piece) => `- [${piece.cardId}] ${piece.slots.join(" or ")}: ${copies(piece)}${describe(piece.cardId)}`),
    `Main-deck cards (${list.deck.reduce((total, card) => total + card.count, 0)} in the List; your deck takes 40):`,
    ...list.deck.map((card) => `- [${card.cardId}] ${copies(card)}${describe(card.cardId)}`),
  ].join("\n");
}
