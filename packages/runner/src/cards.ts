// Card facts shared by List loading, Decklist presentation and rendering.
import type { CardData, EquipmentSlot } from "@fyendal/shared";

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

/** One reference line for a card: its name with colour, type, printed cost,
 * pitch, attack, defense, life and intellect, and rules text on one line. The
 * text keeps upstream's symbols ({p} power, {r} resource, {h} life, {d}
 * defense, {t} tap); a prompt that shows it must explain them. */
export function describeCardData(data: CardData): string {
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
}
