// The Claude Agent: occupies a Seat and makes every decision by one fresh
// Claude Code call (ADR-0002). It is shown a system prompt that is the same
// for the whole Game (primer, Seat, answer format, its own Decklist) and a
// message that changes per decision (the rendered decision, its Plan notes),
// and answers with one Intent number, its reasoning and new Plan notes.
import type { Decklist } from "@fyendal/shared";
import { describeCardId, EQUIPMENT_SLOTS, type Agent, type Seat } from "@tcg-htc/runner";
import { ask, describeAgent, failed, field, textField, type Read } from "./ask.js";
import type { ClaudeCodeCall, ClaudeConfig } from "./claudeCode.js";
import { CARD_SYMBOLS_SECTION, primer } from "./prompt.js";

export { MAX_RETRIES } from "./ask.js";
export { PRIMER_FILE } from "./prompt.js";

/** Plan notes longer than this are cut, and the cut recorded on the Decision. */
export const PLAN_NOTES_LIMIT = 2_000;

// "Answer" here is Claude Code's raw reply, before the Agent turns it into a
// Decision; that is the sense the glossary's "answer (for a Decision)" keeps.
/** What an answer must look like: the Intent number, reasoning, Plan notes. */
export const ANSWER_SCHEMA = {
  type: "object",
  properties: {
    intent: { type: "integer", description: "The number of the one legal Intent you choose, from the numbered list." },
    reasoning: { type: "string", description: "Why this Intent, in a few sentences." },
    planNotes: {
      type: "string",
      description: `Your Plan notes, rewritten for your next decision: your plan and suspicions, not game facts. Under ${PLAN_NOTES_LIMIT} characters.`,
    },
  },
  required: ["intent", "reasoning", "planNotes"],
  additionalProperties: false,
} as const;

/** The heading the message puts the Seat's Plan notes under. */
export const PLAN_NOTES_HEADING = "Your Plan notes, from your last decision:";

export interface ClaudeAgentConfig extends ClaudeConfig {
  seat: Seat;
  /** The Decklist the Seat plays, shown with full card text in the system prompt. */
  decklist: Decklist;
}

export interface ClaudeAgentOptions {
  /** Where the call writes the system prompt file and runs Claude Code. */
  resultsDir?: string;
  /** Plan notes to start from, when a Game is resumed. */
  planNotes?: string;
}

/** A Claude Agent: a runner Agent that also exposes what a Run saves and
 * restores. `planNotes` are the notes the Agent wrote at its last decision. */
export interface ClaudeAgent extends Agent {
  readonly seat: Seat;
  readonly config: ClaudeConfig;
  /** Identical for every decision of the Game. */
  readonly systemPrompt: string;
  readonly planNotes: string;
}

/** Makes the Claude Agent for a Seat. The system prompt is built here, once. */
export function claudeAgent(config: ClaudeAgentConfig, call: ClaudeCodeCall, options: ClaudeAgentOptions = {}): ClaudeAgent {
  const { seat, decklist, model, effort } = config;
  const callConfig: ClaudeConfig = { model, effort };
  const resultsDir = options.resultsDir ?? "results";
  const systemPrompt = buildSystemPrompt(seat, decklist);
  const who = describeAgent(seat, callConfig);
  let planNotes = options.planNotes ?? "";

  // The runner's rendering of the View is the message; its numbered entries map the answer back to an Intent.
  const agent: Agent = async (_view, _legalIntents, _rng, rendered) => {
    const asked = await ask({
      call,
      who,
      systemPrompt,
      message: buildMessage(rendered.text, planNotes),
      schema: ANSWER_SCHEMA,
      config: callConfig,
      resultsDir,
      read: (output) => readAnswer(output, rendered.intents.length),
    });
    if (failed(asked)) return { ...asked, measurements: { ...asked.measurements, notesCut: false } };
    const { value, measurements } = asked;
    measurements.notesCut = value.planNotes.length > PLAN_NOTES_LIMIT;
    planNotes = value.planNotes.slice(0, PLAN_NOTES_LIMIT);
    return { intent: rendered.intents[value.intent - 1]!, reasoning: value.reasoning, planNotes, measurements };
  };

  return Object.defineProperties(agent, {
    seat: { value: seat, enumerable: true },
    config: { value: callConfig, enumerable: true },
    systemPrompt: { value: systemPrompt, enumerable: true },
    planNotes: { get: () => planNotes, enumerable: true },
  }) as ClaudeAgent;
}

/** The three fields of an answer (Claude Code's raw reply, not yet a
 * Decision), once it names a listed Intent. */
interface Answer {
  intent: number;
  reasoning: string;
  planNotes: string;
}

function readAnswer(output: unknown, count: number): Read<Answer> {
  const intent = field(output, "intent");
  if (typeof intent !== "number" || !Number.isInteger(intent)) {
    return { ok: false, problem: `Your answer named no Intent number (got ${JSON.stringify(intent)}); answer with one of 1 to ${count}` };
  }
  if (intent < 1 || intent > count) {
    return { ok: false, problem: `Your answer named Intent ${intent} but only 1 to ${count} are listed` };
  }
  return { ok: true, value: { intent, reasoning: textField(output, "reasoning"), planNotes: textField(output, "planNotes") } };
}

/** The per-decision message: the rendered decision, then the Plan notes. */
export function buildMessage(rendered: string, planNotes: string): string {
  return `${rendered}\n\n${PLAN_NOTES_HEADING}\n${planNotes}`;
}

/** The system prompt for a Seat: primer, Seat and objective, card symbols,
 * answer format, and the Seat's own Decklist with full card text. */
export function buildSystemPrompt(seat: Seat, decklist: Decklist): string {
  return [
    primer(),
    "## You",
    `You are Seat ${seat}. Your objective is to win the Game.`,
    CARD_SYMBOLS_SECTION,
    "## How to answer",
    [
      "Answer with a JSON object of exactly three fields.",
      "`intent`: the number of the one legal Intent you choose, from the numbered list.",
      "`reasoning`: why this Intent, in a few sentences.",
      `\`planNotes\`: your Plan notes rewritten for your next decision, under ${PLAN_NOTES_LIMIT} characters: your plan and suspicions, not game facts, which the next decision shows you afresh.`,
    ].join("\n"),
    "## Your Decklist",
    describeDecklist(decklist),
  ].join("\n\n");
}

/** The Decklist with full card text: hero, weapons, equipment by slot, and
 * the Deck grouped by card with counts. */
function describeDecklist(decklist: Decklist): string {
  const counts = new Map<string, number>();
  for (const cardId of decklist.deck) counts.set(cardId, (counts.get(cardId) ?? 0) + 1);
  return [
    `Hero: ${describeCardId(decklist.heroId)}`,
    "Weapons:",
    ...decklist.weaponIds.map((cardId) => `- ${describeCardId(cardId)}`),
    "Equipment:",
    ...EQUIPMENT_SLOTS.flatMap((slot) => {
      const cardId = decklist.equipment[slot];
      return cardId ? [`- ${slot}: ${describeCardId(cardId)}`] : [];
    }),
    `Deck (${decklist.deck.length} cards):`,
    ...[...counts].map(([cardId, count]) => `- ${count}x ${describeCardId(cardId)}`),
  ].join("\n");
}
