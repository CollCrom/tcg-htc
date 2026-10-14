import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import * as cards from "@fyendal/cards";
import { cardData, isWeaponZoneCard, scripts, weaponSelectionError } from "@fyendal/cards";
import { applyIntent, createGame, legalIntents, projectStateForReplay } from "@fyendal/engine";
import { describe, expect, it } from "vitest";
import { preconDecklist } from "./precons.js";
import { missingDocPaths } from "./upstreamDoc.js";

const repoRoot = join(import.meta.dirname, "../../..");

describe("missingDocPaths", () => {
  it("names each cited path that exists rejects", () => {
    const doc =
      "See `packages/runner/src/game.ts`, `packages/engine/src/gone.ts`, `apps/server/src/gone.ts` " +
      "and `../../../vendor/fyendal.net/packages/cards/src/gone.ts`.";
    const exists = (path: string) => path.endsWith("game.ts");

    expect(missingDocPaths(doc, exists)).toEqual([
      "packages/engine/src/gone.ts",
      "apps/server/src/gone.ts",
      "vendor/fyendal.net/packages/cards/src/gone.ts",
    ]);
  });

  it("finds every path docs/upstream.md cites", () => {
    const doc = readFileSync(join(repoRoot, "docs/upstream.md"), "utf8");
    const exists = (path: string) =>
      existsSync(join(repoRoot, path)) || existsSync(join(repoRoot, "vendor/fyendal.net", path));

    expect(missingDocPaths(doc, exists)).toEqual([]);
  });
});

// Each assertion guards a claim in docs/upstream.md. When one fails, fix the
// doc line named in its comment, then the assertion.
describe("docs/upstream.md gotchas", () => {
  const decklists = [preconDecklist("precon-sbr"), preconDecklist("precon-sly")] as const;
  const newGame = (seed = 1) =>
    createGame({ decklists: [decklists[0], decklists[1]], cards: cardData, scripts, seed, startPlayer: 0 });

  it("createGame accepts a config with no scripts", () => {
    // "Always pass `scripts` to `createGame`": leaving it out fails silently.
    const state = createGame({ decklists: [decklists[0], decklists[1]], cards: cardData, seed: 1, startPlayer: 0 });
    expect(state.phase).not.toBe("game-over");
  });

  it("off-hands are an equipment subtype that goes in the weapon zone", () => {
    // "Off-hands and quivers are a subtype, not a card type."
    const bastion = cardData.TCC029;
    expect(bastion?.name).toBe("Bastion of Duty");
    expect(bastion?.cardType).toBe("equipment");
    expect(bastion?.subtypes).toContain("off-hand");
    expect(isWeaponZoneCard(bastion)).toBe(true);
    // Same bullet: `weaponSelectionError` accepts a lone off-hand or no weapon.
    expect(weaponSelectionError(cardData, [])).toBeNull();
    expect(weaponSelectionError(cardData, ["TCC029"])).toBeNull();
  });

  it("legalIntents offers concede and a draw Intent until the Game is over", () => {
    // "Until the Game is over, `legalIntents` always includes `concede` and a draw Intent."
    const state = newGame();
    const kinds = legalIntents(state, 0).map((intent) => intent.kind);
    expect(kinds).toContain("concede");
    expect(kinds.some((kind) => kind.endsWith("-draw"))).toBe(true);

    const conceded = applyIntent(state, 0, { kind: "concede" });
    if (!conceded.ok) throw new Error(conceded.error);
    expect(conceded.state.phase).toBe("game-over");
    expect(legalIntents(conceded.state, 0)).toEqual([]);
    expect(legalIntents(conceded.state, 1)).toEqual([]);
    // Entry points, "Apply an Intent": a finished Game rejects Intents with "game is over".
    expect(applyIntent(conceded.state, 1, { kind: "concede" })).toEqual({ ok: false, error: "game is over" });
  });

  it("stores the seed as a 32-bit int", () => {
    // "The seed is a 32-bit int.": `createGame` stores `seed | 0` as the rng
    // state, so seeds equal mod 2^32 give the same Game. Setup shuffles, so the
    // stored state has moved on from the seed by the time we can read it.
    const replayOf = (seed: number) => JSON.stringify(projectStateForReplay(newGame(seed)));
    expect(replayOf(2 ** 32 + 5)).toBe(replayOf(5));
    expect(replayOf(6)).not.toBe(replayOf(5));
  });

  it('projectStateForReplay defaults the game id to "game"', () => {
    // Entry points, "Replay projection".
    expect(projectStateForReplay(newGame()).gameId).toBe("game");
  });

  it("@fyendal/cards exports only . and ./client, and not functionalKey", () => {
    // The paragraph after the entry points table.
    const manifest = JSON.parse(readFileSync(join(repoRoot, "vendor/fyendal.net/packages/cards/package.json"), "utf8"));
    expect(Object.keys(manifest.exports)).toEqual([".", "./client"]);
    expect("functionalKey" in cards).toBe(false);
  });
});
