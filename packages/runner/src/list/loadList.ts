// Read a List from Fabrary export text. The parser is ported from upstream's
// server app (apps/server/src/decks.ts: parseDecklistText and validateDeck).
import {
  cardData,
  equipmentFitsSlot,
  findPrinting,
  formatLegalityIssues,
  isImplemented,
  isWeaponZoneCard,
  MIN_DECK_SIZE,
  normalizeCardName,
} from "@fyendal/cards";
import type { CardData, DeckPool, EquipmentSlot, Format } from "@fyendal/shared";
import { colourOf, EQUIPMENT_SLOTS, nameWithColour, type Colour } from "../cards.js";

/** One line of a List: a card (a printing id) and how many copies. */
export interface ListCard {
  cardId: string;
  name: string;
  colour: Colour | null;
  count: number;
}

/** An equipment piece and the slots it can fill (more than one if Modular). */
export interface ListEquipment extends ListCard {
  slots: EquipmentSlot[];
}

/** Every card a player brings, resolved to upstream printing ids. */
export interface List {
  name: string;
  format: Format;
  hero: { cardId: string; name: string };
  /** Weapons, off-hands and quivers: everything that goes in a weapon zone. */
  weapons: ListCard[];
  equipment: ListEquipment[];
  /** Main-deck cards. */
  deck: ListCard[];
}

const PITCH_WORDS: Record<string, number> = { red: 1, yellow: 2, yel: 2, blue: 3, blu: 3, purple: 4, pur: 4 };

interface ParsedLine {
  /** 1-based line number and the text as written, for error messages. */
  lineNumber: number;
  text: string;
  count: number;
  name: string;
  pitch?: number;
}

interface ParsedText {
  name: string | null;
  format: string | null;
  lines: ParsedLine[];
  /** Lines that read as a heading the parser doesn't know, such as a card
   * written without a count ("Aspect of Tiger: Body (red)"). */
  unrecognised: { lineNumber: number; text: string }[];
}

/** Largest count one line may claim; anything near it fails the size check. */
const MAX_LINE_COUNT = 99;

/**
 * Sections don't matter: each card's own type decides whether it's the hero,
 * a weapon, equipment or a main-deck card, and a List has no sideboard, so
 * sideboard cards count as main-deck cards.
 */
function parseFabraryText(text: string): ParsedText {
  const parsed: ParsedText = { name: null, format: null, lines: [], unrecognised: [] };
  text.split(/\r?\n/).forEach((raw, index) => {
    const line = raw.trim();
    const at = { lineNumber: index + 1, text: line };
    if (!line || line.startsWith("#") || line.startsWith("//")) return;
    if (/^(arena|deck|main|sideboard|maybeboard) cards?$/i.test(line)) return;
    if (
      /^made with love at (?:the )?fabrary$/i.test(line) ||
      /^see the full deck\s*@\s*https?:\/\/(?:www\.)?fabrary\.net\/decks\//i.test(line)
    ) return;
    const header = /^([A-Za-z][A-Za-z ]*?)\s*:\s*(.*)$/.exec(line);
    if (header) {
      const heading = header[1]!.toLowerCase();
      const rest = header[2]!.trim();
      if (heading === "name") {
        parsed.name = rest;
        return;
      }
      if (heading === "format") {
        parsed.format = rest;
        return;
      }
      if (!/^(hero|heroes|sideboard|side|deck|main|weapon|equipment|arena)/.test(heading)) {
        parsed.unrecognised.push(at);
        return;
      }
      if (rest) parsed.lines.push({ ...at, count: 1, name: rest });
      return;
    }
    const card = /^(\d+)\s*x?\s+(.+?)(?:\s*\((red|yellow|yel|blue|blu|purple|pur|[1234])\))?\s*$/i.exec(line);
    if (!card) {
      parsed.lines.push({ ...at, count: 1, name: line });
      return;
    }
    const pitchWord = card[3]?.toLowerCase();
    const pitch = pitchWord ? (PITCH_WORDS[pitchWord] ?? Number(pitchWord)) : undefined;
    parsed.lines.push({
      ...at,
      count: Math.min(Number(card[1]), MAX_LINE_COUNT),
      name: card[2]!,
      ...(pitch === undefined ? {} : { pitch }),
    });
  });
  return parsed;
}

/** The formats a List can state, with upstream's limits (validateDeck's
 * MAX_POOL_SIZE and MAX_COPIES). Only Silver Age is in scope. */
const FORMATS: Record<string, { format: Format; maxCards: number; maxCopies: number }> = {
  "silver age": { format: "silver-age", maxCards: 55, maxCopies: 2 },
};

const copiesOf = (cards: ListCard[]) => cards.flatMap((card) => Array<string>(card.count).fill(card.cardId));
const countOf = (cards: ListCard[]) => cards.reduce((total, card) => total + card.count, 0);

/** The List as upstream's legality and presentation checks take it (upstream
 * calls it a DeckPool): printing ids, one entry per copy. */
export function toUpstreamList(list: List): DeckPool {
  return {
    heroId: list.hero.cardId,
    weaponIds: copiesOf(list.weapons),
    equipmentPool: copiesOf(list.equipment), // glossary: upstream
    deck: copiesOf(list.deck),
  };
}

/** A List that can't be played, with every problem found in it. */
export class ListError extends Error {
  constructor(readonly problems: string[]) {
    super(`List can't be played:\n${problems.map((problem) => `- ${problem}`).join("\n")}`);
    this.name = "ListError";
  }
}

export interface LoadListOptions {
  /** Upstream's implemented check; swappable because every card is implemented at the pin. */
  isImplemented?: (card: CardData) => boolean;
}

const describeCard = (card: CardData) => nameWithColour(card.name, card.pitch);

function listCard(card: CardData, count: number): ListCard {
  return { cardId: card.id, name: card.name, colour: colourOf(card.pitch), count };
}

/**
 * Read a List from the text Fabrary exports. Throws a ListError naming every
 * problem: lines that don't match a card, cards upstream hasn't implemented,
 * and anything that makes the List illegal in its stated format.
 */
export function loadList(fabraryExportText: string, options: LoadListOptions = {}): List {
  const implemented = options.isImplemented ?? isImplemented;
  const parsed = parseFabraryText(fabraryExportText);
  const problems = parsed.unrecognised.map(
    ({ lineNumber, text }) => `line ${lineNumber} has a heading that isn't recognised (a card needs a count): ${text}`,
  );
  const rules = FORMATS[(parsed.format ?? "").toLowerCase()];
  if (!rules) {
    const known = Object.keys(FORMATS).map((name) => `"Format: ${name}"`).join(" or ");
    problems.push(
      parsed.format ? `format not supported: ${parsed.format} (expected ${known})` : `no format stated (expected ${known})`,
    );
  }
  const heroes: List["hero"][] = [];
  const weapons: ListCard[] = [];
  const equipment: ListEquipment[] = [];
  const deck: ListCard[] = [];
  const unimplemented = new Set<string>();
  const copies = new Map<string, { card: CardData; count: number }>();

  for (const line of parsed.lines) {
    const card = findPrinting(line.name, line.pitch);
    if (!card) {
      problems.push(`line ${line.lineNumber} doesn't match a card: ${line.text}`);
      continue;
    }
    if (!implemented(card)) unimplemented.add(describeCard(card));
    if (card.cardType === "hero") {
      if (/\bwhile this is in your inventory\b/i.test(card.text)) {
        problems.push(`${card.name} is a demi-hero, which the runner doesn't support`);
      } else {
        heroes.push({ cardId: card.id, name: card.name });
      }
    } else if (isWeaponZoneCard(card)) {
      weapons.push(listCard(card, line.count));
    } else if (card.cardType === "equipment" && !card.subtypes?.includes("evo")) {
      const slots = EQUIPMENT_SLOTS.filter((slot) => equipmentFitsSlot(card, slot));
      if (slots.length === 0) problems.push(`${card.name} doesn't fit an equipment slot`);
      equipment.push({ ...listCard(card, line.count), slots });
    } else if (card.cardType === "token") {
      problems.push(`${card.name} is a token and can't be in a List`);
    } else {
      deck.push(listCard(card, line.count));
      const unlimited = card.keywords?.some((keyword) => keyword.trim().toLowerCase() === "unlimited") === true;
      if (!unlimited) {
        const key = `${normalizeCardName(card.name)}|${card.pitch ?? 0}`;
        copies.set(key, { card, count: (copies.get(key)?.count ?? 0) + line.count });
      }
    }
  }

  if (unimplemented.size > 0) problems.push(`not implemented upstream: ${[...unimplemented].join(", ")}`);
  const hero = heroes[0];
  if (!hero) problems.push("no hero");
  if (heroes.length > 1) problems.push(`more than one hero: ${heroes.map((h) => h.name).join(", ")}`);
  if (!rules || !hero) throw new ListError(problems);

  const list: List = { name: parsed.name ?? "", format: rules.format, hero, weapons, equipment, deck };
  const size = countOf([...weapons, ...equipment, ...deck]);
  if (size > rules.maxCards) problems.push(`List too large (${size} cards, at most ${rules.maxCards})`);
  const deckSize = countOf(deck);
  const minDeck = MIN_DECK_SIZE[rules.format];
  if (deckSize < minDeck) problems.push(`too few main-deck cards (${deckSize}, at least ${minDeck})`);
  for (const { card, count } of copies.values()) {
    if (count > rules.maxCopies) problems.push(`too many copies of ${describeCard(card)} (${count}, max ${rules.maxCopies})`);
  }
  for (const issue of formatLegalityIssues(cardData, toUpstreamList(list), rules.format)) problems.push(issue.message);

  if (problems.length > 0) throw new ListError(problems);
  return list;
}
