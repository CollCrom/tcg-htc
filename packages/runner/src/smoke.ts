// Proves the workspace wiring: create a Game from an upstream precon and print
// Seat 0's legal Intents.
import { cardData, preconsForFormat, scripts } from "@fyendal/cards";
import { createGame, legalIntents } from "@fyendal/engine";
import { presentPrecon } from "./precons.js";

const SEED = 1;
const SEAT = 0;

const chosen = preconsForFormat("silver-age")[0];
if (!chosen) throw new Error("upstream has no legal Silver Age precon");
const decklist = presentPrecon(chosen);
const state = createGame({
  decklists: [decklist, decklist],
  cards: cardData,
  scripts,
  seed: SEED,
  startPlayer: SEAT,
});

const intents = legalIntents(state, SEAT);
console.log(`${chosen.id} (${chosen.name}) mirror, seed ${SEED}, phase ${state.phase}`);
console.log(`Seat ${SEAT} has ${intents.length} legal Intents:`);
for (const intent of intents) console.log(`  ${JSON.stringify(intent)}`);
