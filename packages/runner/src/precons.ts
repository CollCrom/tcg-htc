// Upstream precons presented as Decklists, for the smoke check and the runGame
// tests, which need Decklists but not Lists.
import { cardData, precon, validatePresentation, type Precon } from "@fyendal/cards";
import type { Decklist } from "@fyendal/shared";
import { EQUIPMENT_SLOTS } from "./cards.js";

/** Present a precon the simple way: its first 40 deck cards, its first weapon
 * and the first equipment piece for each slot, validated by upstream. */
export function presentPrecon({ id, pool: list, format }: Precon): Decklist {
  const equipment: Decklist["equipment"] = {};
  for (const slot of EQUIPMENT_SLOTS) {
    const piece = list.equipmentPool.find((cardId) => cardData[cardId]?.subtypes?.includes(slot));
    if (piece) equipment[slot] = piece;
  }
  const presented = { weaponIds: list.weaponIds.slice(0, 1), equipment, deck: list.deck.slice(0, 40) };
  const result = validatePresentation(list, presented, format);
  if (!result.ok) throw new Error(`${id} presentation is invalid: ${result.error}`);
  return result.decklist;
}

/** The Decklist of the upstream precon with this id. */
export function preconDecklist(id: string): Decklist {
  const found = precon(id);
  if (!found) throw new Error(`upstream has no precon ${id}`);
  return presentPrecon(found);
}
