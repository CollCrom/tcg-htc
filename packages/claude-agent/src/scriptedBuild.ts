// A legal Decklist presentation derived from a List, for scripting the fake
// Claude Code call's answer to a build in tests. Not what the Agent would
// choose: the first real weapon upstream accepts, the first piece that fits
// each equipment slot, and the first 40 main-deck cards.
import { cardData, EXACT_DECK_SIZE, MIN_DECK_SIZE, validateArena } from "@fyendal/cards";
import type { PresentedDeck } from "@fyendal/shared";
import { EQUIPMENT_SLOTS, toUpstreamList, type List } from "@tcg-htc/runner";

export function legalPresentation(list: List): PresentedDeck {
  const upstreamList = toUpstreamList(list);
  const weaponId = [...new Set(upstreamList.weaponIds)].find(
    (id) => cardData[id]?.cardType === "weapon" && validateArena(upstreamList, { weaponIds: [id], equipment: {} }, list.format).ok,
  );
  if (!weaponId) throw new Error(`${list.hero.name}'s List has no weapon upstream accepts on its own`);
  const equipment: PresentedDeck["equipment"] = {};
  const unused = list.equipment.flatMap((piece) => Array<typeof piece>(piece.count).fill(piece));
  for (const slot of EQUIPMENT_SLOTS) {
    const piece = unused.find((candidate) => candidate.slots.includes(slot));
    if (!piece) continue;
    unused.splice(unused.indexOf(piece), 1);
    equipment[slot] = piece.cardId;
  }
  const size = EXACT_DECK_SIZE[list.format] ?? MIN_DECK_SIZE[list.format];
  return { weaponIds: [weaponId], equipment, deck: upstreamList.deck.slice(0, size) };
}
