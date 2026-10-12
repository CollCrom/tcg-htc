// Card facts shared by List loading, Decklist presentation and rendering.
import type { EquipmentSlot } from "@fyendal/shared";

/** The equipment slots, one piece each in a Decklist. Upstream keeps its own
 * list private (cards/src/presentation.ts). */
export const EQUIPMENT_SLOTS: readonly EquipmentSlot[] = ["head", "chest", "arms", "legs"];

export type Colour = "red" | "yellow" | "blue" | "purple";

const COLOURS: Record<number, Colour> = { 1: "red", 2: "yellow", 3: "blue", 4: "purple" };

/** A card's colour from its pitch value, or null if it has none. */
export function colourOf(pitch: number | undefined): Colour | null {
  return pitch === undefined ? null : (COLOURS[pitch] ?? null);
}

/** A card's name with its colour, such as "Flying Kick (red)", or just its name if it has none. */
export function nameWithColour(name: string, pitch: number | undefined): string {
  const colour = colourOf(pitch);
  return colour ? `${name} (${colour})` : name;
}
