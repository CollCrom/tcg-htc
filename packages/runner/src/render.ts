// The text rendering of one decision: a Seat's View, the log of the current and
// previous turn, a reference for the opponent's visible cards, and the legal
// Intents in plain language, numbered. It is the contract a Claude Agent reads
// a decision from (render.test.ts pins one rendering), and the text whose size
// measure.ts estimates. It reads only the View, never the state.
import { cardData } from "@fyendal/cards";
import type { CardCostSelection, CardView, PlayerView } from "@fyendal/shared";
import { opponentOf, type Intent, type Seat, type View } from "./agent.js";
import { nameWithColour } from "./cards.js";

/** One rendered decision. `intents[i]` is the engine Intent behind numbered
 * entry `i + 1` of `text`: Intents that differ only in pitch order share one
 * entry, which stands for the first ordering the engine listed. */
export interface RenderedDecision {
  text: string;
  intents: Intent[];
}

/** The log lines of the current turn and the turn before it. The engine logs
 * one line at the start of every turn: its structured entry carries a
 * `turn-start` event, and its text starts "— Turn N:". The last two such lines
 * are the turn boundaries; a log without them (a legacy View, or a Game in its
 * first turn) is shown whole. The engine also appends a hidden `⟦CARDID⟧` tag
 * per card named in a line, for its client; those go. */
function recentTurns(view: View): string[] {
  const isTurnStart = (index: number): boolean => {
    const entry = view.logEntries?.[index];
    return entry && "event" in entry ? entry.event?.kind === "turn-start" : /^— Turn \d+:/.test(view.log[index] ?? "");
  };
  const starts = view.log.map((_, index) => index).filter(isTurnStart);
  const from = starts.at(-2) ?? 0;
  return view.log.slice(from).map((line) => line.replace(/⟦[^⟧]*⟧/g, ""));
}

/** One reference line per distinct opponent card the View shows (the hero
 * included): its name with colour, type, printed cost, pitch, attack, defense
 * and rules text. The Seat's own cards belong in its system prompt. */
function opponentReference(view: View, seat: Seat): string[] {
  const opponent = view.players[opponentOf(seat)];
  const visible = cardsOf(view).filter((card) => card.owner === opponent.seat && !card.hidden && card.cardId);
  const cardIds = new Set([opponent.heroCardId, ...visible.map((card) => card.cardId)]);
  return [...cardIds].map((cardId) => {
    const data = cardData[cardId];
    if (!data) return `${visible.find((card) => card.cardId === cardId)?.name ?? cardId}: no card data`;
    const type = [...(data.classes ?? []), data.cardType].join(" ") + (data.subtypes?.length ? ` - ${data.subtypes.join(", ")}` : "");
    const stats = [
      ["cost", data.cost],
      ["pitch", data.pitch],
      ["attack", data.attack],
      ["defense", data.defense],
      ["life", data.life],
      ["intellect", data.intellect],
    ].flatMap(([label, value]) => (value === undefined ? [] : [`${label} ${value}`]));
    const statsLine = stats.length > 0 ? ` ${stats.join(", ").replace(/^./, (first) => first.toUpperCase())}.` : "";
    const text = data.text.trim().replace(/\.?\s*\n\s*/g, ". ");
    return `${nameWithColour(data.name, data.pitch)}: ${type}.${statsLine}${text ? ` ${text}` : ""}`;
  });
}

/** Renders a Seat's View and its legal Intents as text. */
export function renderDecision(view: View, seat: Seat, legalIntents: readonly Intent[]): RenderedDecision {
  const names = namesOf(view);
  const intents = collapsePitchOrderings(legalIntents, view);
  const text = [
    `Turn ${view.turn}, ${view.phase} phase. Seat ${view.activePlayer}'s turn; Seat ${view.priorityPlayer} has priority. You are Seat ${seat}.`,
    ...renderSeat(view.players[seat], "You"),
    ...renderSeat(view.players[opponentOf(seat)], "Opponent"),
    ...renderCombat(view),
    ...renderDecisionPrompt(view, seat),
    ...section("Log, previous turn and this turn", recentTurns(view)),
    ...section("Opponent's cards you can see", opponentReference(view, seat)),
    "Legal Intents:",
    ...intents.map((intent, i) => `${i + 1}. ${renderIntent(intent, names, view, seat)}`),
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

/** What each pending decision kind asks, for a decision the engine gives no prompt. */
const DECISION_KINDS: Record<NonNullable<View["pendingDecision"]>["kind"], string> = {
  defend: "declare defending cards",
  "attack-reaction": "attack reaction window",
  "defense-reaction": "defense reaction window",
  "priority-window": "play an instant or pass",
  arsenal: "put a card in arsenal or pass",
  "choose-target": "choose one",
  "choose-name": "name a card",
  "order-triggers": "order the triggers",
  "optional-effect": "optional effect",
};

function renderDecisionPrompt(view: View, seat: Seat): string[] {
  const decision = view.pendingDecision;
  if (!decision || decision.player !== seat) return [];
  const prompt = `Decision: ${decision.prompt || DECISION_KINDS[decision.kind]}`;
  const staged = decision.stagedCards?.length ? [`Staged defenders: ${decision.stagedCards.map(describeCard).join(", ")}`] : [];
  const revealed = decision.revealedCards?.length ? [`Revealed: ${decision.revealedCards.map(describeCard).join(", ")}`] : [];
  const looked = decision.lookedCards?.length ? [`Looked at: ${decision.lookedCards.map(describeCard).join(", ")}`] : [];
  return [prompt, ...staged, ...revealed, ...looked];
}

/** Names of the cards this View shows, by instance id, plus the labels the
 * pending decision gives its options. */
interface Names {
  card(instanceId: number): string;
  option(optionId: string): string;
}

/** One Intent in plain language: what is done, to or with which cards. */
function renderIntent(intent: Intent, names: Names, view: View, seat: Seat): string {
  const list = (ids: readonly number[]) => listed(ids.map(names.card));
  const pitching = (ids: readonly number[] | undefined) => (ids && ids.length > 0 ? `, pitching ${list(ids)}` : "");
  const play = (verb: string, card: number, from: string, intent: Extract<Intent, { pitchInstanceIds: number[] }>) => {
    const details = "boost" in intent || "meldSide" in intent ? playDetails(intent, names) : [];
    return `${verb} ${names.card(card)}${from}${details.map((detail) => `, ${detail}`).join("")}${pitching(intent.pitchInstanceIds)}`;
  };
  switch (intent.kind) {
    case "play-card":
      return play("play", intent.instanceId, "", intent);
    case "play-from-arsenal":
      return play("play", intent.instanceId, " from arsenal", intent);
    case "play-from-zone":
      return play("play", intent.instanceId, ` from ${intent.zone}`, intent);
    case "activate-ability": {
      const ability = abilityOf(view, intent.sourceInstanceId, intent.abilityIndex ?? 0);
      const source = names.card(intent.sourceInstanceId);
      const verb = ability.attack ? `attack with ${source}` : `activate ${source}'s ability${ability.label ? ` (${ability.label})` : ""}`;
      const target = targetOf(intent, names);
      const alternative = intent.alternativeCostCardInstanceIds?.length
        ? [`paying its alternative cost with ${list(intent.alternativeCostCardInstanceIds)}`]
        : [];
      const cost = intent.cardCostSelection ? [cardCost(intent.cardCostSelection)] : [];
      return `${verb}${[...target, ...alternative, ...cost].map((detail) => `, ${detail}`).join("")}${pitching(intent.pitchInstanceIds)}`;
    }
    case "pass":
      return `pass${passMeaning(view, seat)}`;
    case "defend":
      return intent.instanceIds.length === 0
        ? "block with nothing"
        : `block with ${list(intent.instanceIds)}${pitching(intent.pitchInstanceIds)}`;
    case "stage-defenders":
      return `stage ${list(intent.instanceIds)} to block`;
    case "choose": {
      const payment = view.pendingDecision?.resourcePayment?.options.find(({ optionId }) => optionId === intent.optionId);
      if (payment) return `pay ${view.pendingDecision?.resourcePayment?.cost} by pitching ${list(payment.pitchInstanceIds)}`;
      if (view.pendingDecision?.kind === "arsenal") return `put ${names.option(intent.optionId)} in arsenal`;
      return `choose ${names.option(intent.optionId)}`;
    }
    case "choose-many":
      return `choose ${listed(intent.optionIds.map(names.option))}`;
    case "order-triggers":
      return `resolve the triggers in this order: ${intent.optionIds.map(names.option).join(", then ")}`;
    case "skip-runechant":
      return "skip through the Runechant trigger";
    case "close-chain":
      return "close the combat chain";
    case "concede":
      return "concede the Game";
    case "offer-draw":
      return "offer a draw";
    case "accept-draw":
      return "accept the draw offer";
    case "decline-draw":
      return "decline the draw offer";
    case "withdraw-draw":
      return "withdraw the draw offer";
    default:
      return unreachable(intent);
  }
}

/** The optional parts of a play Intent: meld side, target, boost, instant,
 * alternative cost and card cost. */
function playDetails(
  intent: Extract<Intent, { kind: "play-card" | "play-from-arsenal" | "play-from-zone" }>,
  names: Names,
): string[] {
  return [
    ...(intent.meldSide ? [intent.meldSide === "both" ? "melding both sides" : `melding the ${intent.meldSide} side`] : []),
    ...targetOf(intent, names),
    ...(intent.boost ? [intent.boostCount && intent.boostCount > 1 ? `boosted ${intent.boostCount} times` : "boosted"] : []),
    ...(intent.asInstant ? ["as an instant"] : []),
    ...(intent.alternativeCostCardInstanceIds?.length
      ? [`paying its alternative cost with ${listed(intent.alternativeCostCardInstanceIds.map(names.card))}`]
      : []),
    ...(intent.cardCostSelection ? [cardCost(intent.cardCostSelection)] : []),
  ];
}

function targetOf(intent: { targetAllyId?: number; targetCardInstanceId?: number }, names: Names): string[] {
  const target = intent.targetCardInstanceId ?? intent.targetAllyId;
  return target === undefined ? [] : [`targeting ${names.card(target)}`];
}

function cardCost(selection: CardCostSelection): string {
  const modes = selection.modes.map(({ kind, maximum }) => `${kind} up to ${maximum}`).join(" or ");
  return `its card cost (${selection.cardLabel}: ${modes})`;
}

/** What passing does here, when the rules give it a specific meaning. */
function passMeaning(view: View, seat: Seat): string {
  const decision = view.pendingDecision;
  if (decision?.kind === "arsenal") return " (put nothing in arsenal)";
  if (decision?.kind === "optional-effect") return " (decline)";
  if (!decision && view.phase === "action" && view.activePlayer === seat && view.chain.length === 0 && view.stack.length === 0)
    return " (end your turn)";
  return "";
}

/** An activated ability of a card the View shows: whether it attacks, and its
 * label when the card has several. */
function abilityOf(view: View, sourceInstanceId: number, abilityIndex: number): { attack: boolean; label?: string } {
  for (const seatView of view.players) {
    if (seatView.heroInstanceId === sourceInstanceId)
      return { attack: seatView.heroAttackAbilityIndexes?.includes(abilityIndex) ?? false, label: seatView.heroAbilityLabels?.[abilityIndex] };
  }
  const card = cardsOf(view).find((card) => card.instanceId === sourceInstanceId);
  return { attack: card?.attackAbilityIndexes?.includes(abilityIndex) ?? false, label: card?.activatedAbilityLabels?.[abilityIndex] };
}

/** "A", "A and B" or "A, B and C". */
function listed(items: readonly string[]): string {
  return items.length <= 1 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`;
}

function unreachable(value: never): never {
  throw new Error(`unknown Intent ${JSON.stringify(value)}`);
}

/** Names for Intents: a card's name with colour from the View, or "card <id>"
 * when the View doesn't show it; an option's label, card, or id. */
function namesOf(view: View): Names {
  const cards = new Map<number, string>();
  for (const seatView of view.players) cards.set(seatView.heroInstanceId, seatView.heroName);
  for (const card of cardsOf(view)) if (!card.hidden) cards.set(card.instanceId, cardName(card));
  const decision = view.pendingDecision;
  return {
    card: (instanceId) => cards.get(instanceId) ?? `card ${instanceId}`,
    option: (optionId) => {
      const index = decision?.options?.indexOf(optionId) ?? -1;
      const card = index >= 0 ? decision?.optionCards?.[index] : null;
      return decision?.optionLabels?.[index] ?? (card ? cardName(card) : optionId);
    },
  };
}

/** Every card the View shows, in any zone of either Seat, including cards
 * underneath others and the cards of the pending decision. */
function cardsOf(view: View): CardView[] {
  const cards: CardView[] = [];
  const add = (card: CardView | null | undefined) => {
    if (!card) return;
    cards.push(card);
    card.subcards?.forEach(add);
  };
  for (const seatView of view.players) {
    for (const zone of [seatView.hand, seatView.arsenal, seatView.pitch, seatView.graveyard, seatView.banish, seatView.soul, seatView.weapons, seatView.board])
      zone.forEach(add);
    Object.values(seatView.equipment).forEach(add);
    seatView.heroSubcards?.forEach(add);
    add(seatView.visibleDeckTop);
  }
  for (const link of view.chain) [link.attackingCard, ...link.defendingCards, ...link.reactions, link.targetAlly].forEach(add);
  for (const layer of view.stack) add(layer.card);
  const decision = view.pendingDecision;
  [...(decision?.optionCards ?? []), ...(decision?.revealedCards ?? []), ...(decision?.lookedCards ?? []), ...(decision?.stagedCards ?? [])].forEach(add);
  add(decision?.preStackSource?.card);
  return cards;
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
