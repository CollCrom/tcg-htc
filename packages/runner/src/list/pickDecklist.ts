// pickDecklist: what a Seat presents for one Game, picked from its List.
import { cardData, EXACT_DECK_SIZE, MIN_DECK_SIZE, validateArena, validatePresentation } from "@fyendal/cards";
import { rngNext } from "@fyendal/engine";
import type { Decklist, PresentedArena } from "@fyendal/shared";
import { EQUIPMENT_SLOTS } from "../cards.js";
import { toUpstreamList, type List } from "./loadList.js";

/**
 * Pick a Decklist from a List, seeded and pure: the same List and seed always
 * give the same Decklist. It samples the Deck's cards from the List's main-deck
 * cards, one equipment piece for each slot the List has a piece for, and a
 * weapon setup from the setups that hold at least one weapon (off-hands are
 * optional) and that upstream accepts. Throws if the List has no such setup.
 */
export function pickDecklist(list: List, seed: number): Decklist {
  const rng = { rngState: seed | 0 };
  const random = (below: number) => Math.floor(rngNext(rng) * below);
  const upstreamList = toUpstreamList(list);

  const setups = weaponSetups(upstreamList.weaponIds).filter(
    (weaponIds) => validateArena(upstreamList, { weaponIds, equipment: {} }, list.format).ok,
  );
  if (setups.length === 0) throw new Error(`${list.hero.name}'s List has no legal weapon setup with a weapon in it`);
  const weaponIds = setups[random(setups.length)]!;

  const equipment: PresentedArena["equipment"] = {};
  const unused = list.equipment.flatMap((piece) => Array<typeof piece>(piece.count).fill(piece));
  for (const slot of EQUIPMENT_SLOTS) {
    const fits = unused.filter((piece) => piece.slots.includes(slot));
    if (fits.length === 0) continue;
    const piece = fits[random(fits.length)]!;
    unused.splice(unused.indexOf(piece), 1);
    equipment[slot] = piece.cardId;
  }

  const size = EXACT_DECK_SIZE[list.format] ?? MIN_DECK_SIZE[list.format];
  const order = upstreamList.deck.map((_, index) => index);
  for (let i = order.length - 1; i > 0; i--) {
    const j = random(i + 1);
    [order[i], order[j]] = [order[j]!, order[i]!];
  }
  const deck = order
    .slice(0, size)
    .sort((a, b) => a - b)
    .map((index) => upstreamList.deck[index]!);

  const result = validatePresentation(upstreamList, { weaponIds, equipment, deck }, list.format);
  if (!result.ok) throw new Error(`picked an illegal Decklist from ${list.hero.name}'s List: ${result.error}`);
  return result.decklist;
}

/** Every one- and two-card selection of the List's weapon-zone cards that
 * holds at least one weapon, ignoring which copy is which. */
function weaponSetups(weaponIds: readonly string[]): string[][] {
  const ids = [...new Set(weaponIds)];
  const copies = (id: string) => weaponIds.filter((other) => other === id).length;
  const setups: string[][] = ids.map((id) => [id]);
  ids.forEach((id, i) => {
    if (copies(id) > 1) setups.push([id, id]);
    for (const other of ids.slice(i + 1)) setups.push([id, other]);
  });
  return setups.filter((setup) => setup.some((id) => cardData[id]?.cardType === "weapon"));
}
