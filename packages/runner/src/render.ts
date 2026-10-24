// A first, simple text rendering of one decision: a Seat's View plus its legal
// Intents. It exists to estimate what a decision would cost a Claude Agent; the
// exact text is not a contract yet. It reads only the View, never the state.
import { cardData } from "@fyendal/cards";
import type { CardView, PlayerView } from "@fyendal/shared";
import { opponentOf, type Intent, type Seat, type View } from "./agent.js";
import { nameWithColour } from "./cards.js";

const LOG_LINES = 5;

/** One rendered decision. `intents[i]` is the engine Intent behind numbered
 * entry `i + 1` of `text`: Intents that differ only in pitch order share one
 * entry, which stands for the first ordering the engine listed. */
export interface RenderedDecision {
  text: string;
  intents: Intent[];
}

/** Renders a Seat's View and its legal Intents as text. */
export function renderDecision(view: View, seat: Seat, legalIntents: readonly Intent[]): RenderedDecision {
  const names = cardNames(view);
  const intents = collapsePitchOrderings(legalIntents, view);
  const text = [
    `Turn ${view.turn}, ${view.phase} phase. Seat ${view.activePlayer}'s turn; Seat ${view.priorityPlayer} has priority. You are Seat ${seat}.`,
    ...renderSeat(view.players[seat], "You"),
    ...renderSeat(view.players[opponentOf(seat)], "Opponent"),
    ...renderCombat(view),
    ...renderDecisionPrompt(view, seat),
    ...section("Recent log", view.log.slice(-LOG_LINES)),
    "Legal Intents:",
    ...intents.map((intent, i) => `${i + 1}. ${renderIntent(intent, names, view)}`),
  ].join("\n");
  return { text, intents };
}

/** The legal Intents with each set of pitch orderings reduced to the first one listed. */
function collapsePitchOrderings(legalIntents: readonly Intent[], view: View): Intent[] {
  const seen = new Set<string>();
  return legalIntents.filter((intent) => {
    const key = reorderFreeKey(intent, view);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
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

/** An estimate of the tokens a text costs: its characters divided by 4. */
export function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

/** One Seat's part of the View (upstream calls it a PlayerView). */
function renderSeat(seatView: PlayerView, who: string): string[] {
  const hero = [
    `${seatView.heroName}`,
    `life ${seatView.life}`,
    `action points ${seatView.actionPoints}`,
    `resources ${seatView.resources}`,
    ...(seatView.chi ? [`chi ${seatView.chi}`] : []),
    ...(seatView.heroTapped ? ["tapped"] : []),
    ...counters(seatView.heroCounters),
  ].join(", ");
  const faceDownArsenal = seatView.arsenalCount - seatView.arsenal.length;
  const equipment = Object.entries(seatView.equipment).map(([slot, card]) => `${slot}: ${card ? describeCard(card) : "none"}`);
  return [
    `== ${who} (Seat ${seatView.seat}): ${hero}`,
    seatView.hand.length > 0
      ? `Hand: ${seatView.hand.map(describeCard).join("; ")}`
      : `Hand: ${seatView.handCount} card${seatView.handCount === 1 ? "" : "s"}`,
    `Deck: ${seatView.deckCount} cards${seatView.visibleDeckTop ? `, top ${describeCard(seatView.visibleDeckTop)}` : ""}`,
    ...line(
      "Arsenal",
      [
        ...[...seatView.arsenal].sort((a, b) => (a.arsenalSlot ?? 0) - (b.arsenalSlot ?? 0)).map(describeCard),
        ...(faceDownArsenal > 0 ? [`${faceDownArsenal} face-down`] : []),
      ],
    ),
    ...line("Pitch, in order", seatView.pitch.map(describeCard)),
    ...line("Soul, in order", seatView.soul.map(describeCard)),
    ...line("Equipment", equipment),
    ...line("Weapons", seatView.weapons.map(describeCard)),
    ...line("In play", seatView.board.map(describeCard)),
    ...line("Graveyard", grouped(seatView.graveyard)),
    ...line("Banish", grouped(seatView.banish)),
  ];
}

function renderCombat(view: View): string[] {
  const chain = view.chain.map((link, i) => {
    const defenders = link.defendingCards.map(describeCard).join(", ") || "none";
    const flags = [
      link.resolved ? "resolved" : "",
      link.hit ? "hit" : "",
      link.goAgain ? "go again" : "",
      link.dominate ? "dominate" : "",
      link.overpower ? "overpower" : "",
    ].filter(Boolean);
    const reactions = link.reactions.length > 0 ? `; reactions ${link.reactions.map(describeCard).join(", ")}` : "";
    return `${i + 1}. ${describeCard(link.attackingCard)} attacks for ${link.attackValue} against ${link.defenseValue} defense (${defenders}); damage ${link.damage}${flags.length > 0 ? `; ${flags.join(", ")}` : ""}${reactions}`;
  });
  const stack = view.stack.map((layer) => `${layer.card ? describeCard(layer.card) : "?"}: ${layer.label} (Seat ${layer.seat})`);
  const ongoing = view.ongoing.map((effect) => `Seat ${effect.seat}: ${effect.label}`);
  return [...section("Combat chain", chain), ...section("Stack, top first", stack), ...section("Ongoing effects", ongoing)];
}

function renderDecisionPrompt(view: View, seat: Seat): string[] {
  const decision = view.pendingDecision;
  if (!decision || decision.player !== seat) return [];
  const prompt = `Decision: ${decision.kind}${decision.prompt ? ` - ${decision.prompt}` : ""}`;
  const staged = decision.stagedCards?.length ? [`Staged defenders: ${decision.stagedCards.map(describeCard).join(", ")}`] : [];
  const revealed = decision.revealedCards?.length ? [`Revealed: ${decision.revealedCards.map(describeCard).join(", ")}`] : [];
  const looked = decision.lookedCards?.length ? [`Looked at: ${decision.lookedCards.map(describeCard).join(", ")}`] : [];
  return [prompt, ...staged, ...revealed, ...looked];
}

function renderIntent(intent: Intent, names: ReadonlyMap<number, string>, view: View): string {
  const name = (id: number) => names.get(id) ?? `card ${id}`;
  const parts: string[] = [intent.kind];
  for (const [key, value] of Object.entries(intent)) {
    if (key === "kind" || value === undefined) continue;
    if (key === "optionId" && typeof value === "string") parts.push(optionLabel(view, value));
    else if (Array.isArray(value) && key.endsWith("InstanceIds")) parts.push(`${key} [${value.map(name).join(", ")}]`);
    else if (key === "instanceIds" && Array.isArray(value)) parts.push(`[${value.map(name).join(", ")}]`);
    else if (typeof value === "number" && /(InstanceId|instanceId|AllyId)$/.test(key)) parts.push(`${key} ${name(value)}`);
    else parts.push(`${key} ${JSON.stringify(value)}`);
  }
  return parts.join(" ");
}

function optionLabel(view: View, optionId: string): string {
  const decision = view.pendingDecision;
  const index = decision?.options?.indexOf(optionId) ?? -1;
  const card = index >= 0 ? decision?.optionCards?.[index] : null;
  return decision?.optionLabels?.[index] ?? (card ? describeCard(card) : optionId);
}

/** Names of the cards this View shows, by instance id, for naming Intents' cards. */
function cardNames(view: View): Map<number, string> {
  const names = new Map<number, string>();
  const add = (card: CardView | null | undefined) => {
    if (card && !card.hidden) names.set(card.instanceId, describeCard(card));
  };
  for (const seatView of view.players) {
    names.set(seatView.heroInstanceId, seatView.heroName);
    for (const zone of [seatView.hand, seatView.arsenal, seatView.pitch, seatView.graveyard, seatView.banish, seatView.soul, seatView.weapons, seatView.board])
      zone.forEach(add);
    Object.values(seatView.equipment).forEach(add);
    add(seatView.visibleDeckTop);
  }
  for (const link of view.chain) [link.attackingCard, ...link.defendingCards, ...link.reactions].forEach(add);
  for (const layer of view.stack) add(layer.card);
  const decision = view.pendingDecision;
  [...(decision?.optionCards ?? []), ...(decision?.revealedCards ?? []), ...(decision?.lookedCards ?? []), ...(decision?.stagedCards ?? [])].forEach(add);
  add(decision?.preStackSource?.card);
  return names;
}

/** Cards grouped by name with counts. Face-down cards are grouped by name when
 * the View shows their identity, and only counted when it hides it. */
function grouped(cards: readonly CardView[]): string[] {
  const counts = new Map<string, number>();
  let hidden = 0;
  for (const card of cards) {
    if (card.hidden) {
      hidden++;
      continue;
    }
    const key = `${cardName(card)}${card.faceDown ? " face-down" : ""}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...[...counts].map(([name, count]) => `${count}x ${name}`), ...(hidden > 0 ? [`${hidden} face-down`] : [])];
}

function describeCard(card: CardView): string {
  if (card.hidden) return "face-down card";
  const stats = [
    card.attack !== undefined ? `attack ${card.attack}` : "",
    card.defense !== undefined ? `defense ${card.defense}` : "",
    card.life !== undefined ? `life ${card.life}` : "",
    card.tapped ? "tapped" : "",
    card.faceDown ? "face-down" : "",
    ...counters(card.counters),
  ].filter(Boolean);
  return `${cardName(card)}${stats.length > 0 ? ` [${stats.join(", ")}]` : ""}`;
}

function cardName(card: CardView): string {
  const data = cardData[card.cardId];
  const name = card.name ?? data?.name ?? card.cardId;
  return nameWithColour(name, data?.pitch);
}

function counters(record: Record<string, number> | undefined): string[] {
  return Object.entries(record ?? {}).map(([name, count]) => `${count} ${name} counters`);
}

function line(label: string, items: readonly string[]): string[] {
  return items.length > 0 ? [`${label}: ${items.join("; ")}`] : [];
}

function section(label: string, lines: readonly string[]): string[] {
  return lines.length > 0 ? [`${label}:`, ...lines] : [];
}
