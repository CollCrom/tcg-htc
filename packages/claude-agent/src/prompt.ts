// The pieces every Claude Agent system prompt shares, whether it builds a
// Decklist or plays: the rules primer and the key to the card text symbols.
import { readFileSync } from "node:fs";

/** The rules primer every Claude Agent reads, owner-reviewed: see prompts/README.md. */
export const PRIMER_FILE = new URL("../prompts/primer.md", import.meta.url);

/** The primer's text, without its trailing newline. */
export function primer(): string {
  return readFileSync(PRIMER_FILE, "utf8").trimEnd();
}

/** The symbols `describeCardData` leaves in card text, explained. */
export const CARD_SYMBOLS_SECTION = "## Card text symbols\n\n{p} power, {r} resource, {h} life, {d} defense, {t} tap.";
