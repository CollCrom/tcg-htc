// The Claude Agent: occupies a Seat and makes every decision by one fresh
// Claude Code call (ADR-0002). It is shown a system prompt that is the same
// for the whole Game (primer, Seat, answer format, its own Decklist) and a
// message that changes per decision (the rendered decision, its Plan notes),
// and answers with one Intent number, its reasoning and new Plan notes.
import { cardData } from "@fyendal/cards";
import type { Decklist } from "@fyendal/shared";
import {
  describeCardData,
  EQUIPMENT_SLOTS,
  renderDecision,
  type Agent,
  type AgentMeasurements,
  type Decision,
  type DecisionFailureCause,
  type Seat,
} from "@tcg-htc/runner";
import { readFileSync } from "node:fs";
import type { CallResult, ClaudeCodeCall, ClaudeConfig } from "./claudeCode.js";

/** The rules primer every Claude Agent reads, owner-reviewed: see prompts/README.md. */
export const PRIMER_FILE = new URL("../prompts/primer.md", import.meta.url);

/** Plan notes longer than this are cut, and the cut recorded on the Decision. */
export const PLAN_NOTES_LIMIT = 2_000;

/** Calls made for one decision after the first: one retry. */
export const MAX_RETRIES = 1;

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
  const who = `Seat ${seat}'s Claude Agent (${model}, ${effort})`;
  let planNotes = options.planNotes ?? "";

  const agent: Agent = async (view, legalIntents) => {
    const rendered = renderDecision(view, seat, legalIntents);
    const count = rendered.intents.length;
    const message = buildMessage(rendered.text, planNotes);
    const measurements: AgentMeasurements = {
      effort,
      inputTokens: 0,
      cachedTokens: 0,
      outputTokens: 0,
      latencyMs: 0,
      retries: 0,
      firstAnswerInvalid: false,
      notesCut: false,
      costUsd: 0,
    };
    const fail = (cause: DecisionFailureCause, detail: string): Decision => ({ cause, detail: `${who}: ${detail}`, measurements });

    let problem: string | undefined;
    for (let attempt = 0; ; attempt++) {
      const result = await call({
        systemPrompt,
        message: problem ? `${message}\n\n${PROBLEM_HEADING}\n${problem}` : message,
        schema: ANSWER_SCHEMA,
        config: callConfig,
        resultsDir,
      });
      measurements.retries = attempt;
      if (result.kind === "answer") {
        const { usage } = result;
        measurements.model = usage.model;
        measurements.inputTokens! += usage.inputTokens;
        measurements.cachedTokens! += usage.cachedTokens;
        measurements.outputTokens! += usage.outputTokens;
        measurements.latencyMs! += usage.latencyMs;
        measurements.costUsd! += usage.costUsd;
      }
      const outcome = readAnswer(result, count);
      if (outcome.kind === "choice") {
        if (outcome.planNotes.length > PLAN_NOTES_LIMIT) measurements.notesCut = true;
        planNotes = outcome.planNotes.slice(0, PLAN_NOTES_LIMIT);
        return { intent: rendered.intents[outcome.intent - 1]!, reasoning: outcome.reasoning, planNotes, measurements };
      }
      if (outcome.kind === "rate-limit") return fail("rate-limit", outcome.detail);
      if (outcome.kind === "invalid-answer" && attempt === 0) measurements.firstAnswerInvalid = true;
      if (attempt >= MAX_RETRIES) return fail(outcome.kind, outcome.detail);
      problem = outcome.kind === "invalid-answer" ? outcome.detail : undefined;
    }
  };

  return Object.defineProperties(agent, {
    seat: { value: seat, enumerable: true },
    config: { value: callConfig, enumerable: true },
    systemPrompt: { value: systemPrompt, enumerable: true },
    planNotes: { get: () => planNotes, enumerable: true },
  }) as ClaudeAgent;
}

const PROBLEM_HEADING = "Your previous answer was not accepted. Answer again, fixing this problem:";

/** What one call came to: a usable choice, an answer that names no listed
 * Intent, or the call's own failure. */
type AnswerOutcome =
  | { kind: "choice"; intent: number; reasoning: string; planNotes: string }
  | { kind: "invalid-answer" | "rate-limit" | "refusal" | "timeout" | "failure"; detail: string };

function readAnswer(result: CallResult, count: number): AnswerOutcome {
  if (result.kind !== "answer") return result;
  const output = result.output;
  const field = (name: string): unknown => (output && typeof output === "object" ? (output as Record<string, unknown>)[name] : undefined);
  const intent = field("intent");
  const text = (value: unknown): string => (typeof value === "string" ? value : "");
  if (typeof intent !== "number" || !Number.isInteger(intent)) {
    return { kind: "invalid-answer", detail: `Your answer named no Intent number (got ${JSON.stringify(intent)}); answer with one of 1 to ${count}` };
  }
  if (intent < 1 || intent > count) {
    return { kind: "invalid-answer", detail: `Your answer named Intent ${intent} but only 1 to ${count} are listed` };
  }
  return { kind: "choice", intent, reasoning: text(field("reasoning")), planNotes: text(field("planNotes")) };
}

/** The per-decision message: the rendered decision, then the Plan notes. */
export function buildMessage(rendered: string, planNotes: string): string {
  return `${rendered}\n\n${PLAN_NOTES_HEADING}\n${planNotes}`;
}

/** The system prompt for a Seat: primer, Seat and objective, card symbols,
 * answer format, and the Seat's own Decklist with full card text. */
export function buildSystemPrompt(seat: Seat, decklist: Decklist): string {
  return [
    readFileSync(PRIMER_FILE, "utf8").trimEnd(),
    "## You",
    `You are Seat ${seat}. Your objective is to win the Game.`,
    "## Card text symbols",
    "{p} power, {r} resource, {h} life, {d} defense, {t} tap.",
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
  const describe = (cardId: string): string => {
    const data = cardData[cardId];
    return data ? describeCardData(data) : `${cardId}: no card data`;
  };
  const counts = new Map<string, number>();
  for (const cardId of decklist.deck) counts.set(cardId, (counts.get(cardId) ?? 0) + 1);
  return [
    `Hero: ${describe(decklist.heroId)}`,
    "Weapons:",
    ...decklist.weaponIds.map((cardId) => `- ${describe(cardId)}`),
    "Equipment:",
    ...EQUIPMENT_SLOTS.flatMap((slot) => {
      const cardId = decklist.equipment[slot];
      return cardId ? [`- ${slot}: ${describe(cardId)}`] : [];
    }),
    `Deck (${decklist.deck.length} cards):`,
    ...[...counts].map(([cardId, count]) => `- ${count}x ${describe(cardId)}`),
  ].join("\n");
}
