// Proves the workspace wiring: create a Game from an upstream precon and print
// Seat 0's legal Intents.
import { cardData, preconsForFormat, scripts, validatePresentation, type Precon } from "@fyendal/cards";
import { createGame, legalIntents } from "@fyendal/engine";
import type { Decklist, EquipmentSlot } from "@fyendal/shared";

const SLOTS: EquipmentSlot[] = ["head", "chest", "arms", "legs"];

/** Present a precon the simple way: its first 40 deck cards, its first weapon
 * and the first equipment piece for each slot, validated by upstream. */
function presentPrecon({ id, pool, format }: Precon): Decklist {
  const equipment: Decklist["equipment"] = {};
  for (const slot of SLOTS) {
    const piece = pool.equipmentPool.find((cardId) => cardData[cardId]?.subtypes?.includes(slot));
    if (piece) equipment[slot] = piece;
  }
  const presented = { weaponIds: pool.weaponIds.slice(0, 1), equipment, deck: pool.deck.slice(0, 40) };
  const result = validatePresentation(pool, presented, format);
  if (!result.ok) throw new Error(`${id} presentation is invalid: ${result.error}`);
  return result.decklist;
}

const chosen = preconsForFormat("silver-age")[0];
if (!chosen) throw new Error("upstream has no legal Silver Age precon");
const decklist = presentPrecon(chosen);
const state = createGame({
  decklists: [decklist, decklist],
  cards: cardData,
  scripts,
  seed: 1,
  startPlayer: 0,
});

const intents = legalIntents(state, 0);
console.log(`${chosen.id} (${chosen.name}) mirror, seed 1, phase ${state.phase}`);
console.log(`Seat 0 has ${intents.length} legal Intents:`);
for (const intent of intents) console.log(`  ${JSON.stringify(intent)}`);
