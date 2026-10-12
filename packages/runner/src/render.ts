// A first, simple text rendering of one decision: a Seat's View plus its legal
// Intents. It exists to estimate what a decision would cost a Claude Agent; the
// exact text is not a contract yet. It reads only the View, never the state.
import { cardData } from "@fyendal/cards";
import type { CardView, PlayerView } from "@fyendal/shared";
import type { Intent, Seat, View } from "./agent.js";

const LOG_LINES = 5;
const COLOURS: Record<number, string> = { 1: "red", 2: "yellow", 3: "blue" };

/** Renders a Seat's View and its legal Intents as text. */
export function renderDecision(view: View, seat: Seat, legalIntents: readonly Intent[]): string {
  const opponent: Seat = seat === 0 ? 1 : 0;
  const names = cardNames(view);
  return [
    `Turn ${view.turn}, ${view.phase} phase. Seat ${view.activePlayer}'s turn; Seat ${view.priorityPlayer} has priority. You are Seat ${seat}.`,
    ...renderPlayer(view.players[seat], "You"),
    ...renderPlayer(view.players[opponent], "Opponent"),
    ...renderCombat(view),
    ...renderDecisionPrompt(view, seat),
    ...section("Recent log", view.log.slice(-LOG_LINES)),
    "Legal Intents:",
    ...legalIntents.map((intent, i) => `${i + 1}. ${renderIntent(intent, names, view)}`),
  ].join("\n");
}

/** An estimate of the tokens a text costs: its characters divided by 4. */
export function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

function renderPlayer(player: PlayerView, who: string): string[] {
  const hero = [
    `${player.heroName}`,
    `life ${player.life}`,
    `action points ${player.actionPoints}`,
    `resources ${player.resources}`,
    ...(player.chi ? [`chi ${player.chi}`] : []),
    ...(player.heroTapped ? ["tapped"] : []),
    ...counters(player.heroCounters),
  ].join(", ");
  const faceDownArsenal = player.arsenalCount - player.arsenal.length;
  const equipment = Object.entries(player.equipment).map(([slot, card]) => `${slot}: ${card ? describeCard(card) : "none"}`);
  return [
    `== ${who} (Seat ${player.seat}): ${hero}`,
    player.hand.length > 0
      ? `Hand: ${player.hand.map(describeCard).join("; ")}`
      : `Hand: ${player.handCount} card${player.handCount === 1 ? "" : "s"}`,
    `Deck: ${player.deckCount} cards${player.visibleDeckTop ? `, top ${describeCard(player.visibleDeckTop)}` : ""}`,
    ...line(
      "Arsenal",
      [
        ...[...player.arsenal].sort((a, b) => (a.arsenalSlot ?? 0) - (b.arsenalSlot ?? 0)).map(describeCard),
        ...(faceDownArsenal > 0 ? [`${faceDownArsenal} face-down`] : []),
      ],
    ),
    ...line("Pitch, in order", player.pitch.map(describeCard)),
    ...line("Soul, in order", player.soul.map(describeCard)),
    ...line("Equipment", equipment),
    ...line("Weapons", player.weapons.map(describeCard)),
    ...line("In play", player.board.map(describeCard)),
    ...line("Graveyard", grouped(player.graveyard)),
    ...line("Banish", grouped(player.banish)),
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
  for (const player of view.players) {
    names.set(player.heroInstanceId, player.heroName);
    for (const zone of [player.hand, player.arsenal, player.pitch, player.graveyard, player.banish, player.soul, player.weapons, player.board])
      zone.forEach(add);
    Object.values(player.equipment).forEach(add);
    add(player.visibleDeckTop);
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
  const colour = data?.pitch !== undefined ? COLOURS[data.pitch] : undefined;
  return colour ? `${name} (${colour})` : name;
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
