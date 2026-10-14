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
  const config: Parameters<typeof createGame>[0] = {
    decklists: [preconDecklist("precon-sbr"), preconDecklist("precon-sly")],
    cards: cardData,
    scripts,
    seed: 1,
    startPlayer: 0, // glossary: upstream
  };
  const newGame = (seed = 1) => createGame({ ...config, seed });
  const upstreamSource = (path: string) => readFileSync(join(repoRoot, "vendor/fyendal.net", path), "utf8");

  it("createGame starts a Game without scripts instead of rejecting the config", () => {
    // "Always pass `scripts` to `createGame`": leaving it out fails silently.
    const { scripts: _, ...withoutScripts } = config;
    expect(createGame(withoutScripts).phase).not.toBe("game-over");
  });

  it("only upstream's server app holds the List size and copy limits and skips the ban check", () => {
    // "The Fabrary text parser is in the server app": `MAX_POOL_SIZE`, `MAX_COPIES` live only in `decks.ts`.
    const decks = upstreamSource("apps/server/src/decks.ts");
    expect(decks).toMatch(/const MAX_POOL_SIZE\b/);
    expect(decks).toMatch(/const MAX_COPIES\b/);
    expect("MAX_POOL_SIZE" in cards || "MAX_COPIES" in cards).toBe(false);
    // "`validateDeck` doesn't check bans or benched heroes": `validateArena` does.
    expect(decks).not.toContain("formatLegalityIssues");
    expect(upstreamSource("packages/cards/src/presentation.ts")).toContain("formatLegalityIssues(");
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
    // Same bullet: upstream's bot filters them out the same way.
    expect(upstreamSource("packages/bot/src/evaluation.ts")).toContain(
      'intent.kind !== "concede" && !intent.kind.endsWith("-draw")',
    );

    const conceded = applyIntent(state, 0, { kind: "concede" });
    if (!conceded.ok) throw new Error(conceded.error);
    expect(conceded.state.phase).toBe("game-over");
    expect(legalIntents(conceded.state, 0)).toEqual([]);
    expect(legalIntents(conceded.state, 1)).toEqual([]);
    // Entry points, "Apply an Intent": a finished Game rejects Intents with "game is over".
    expect(applyIntent(conceded.state, 1, { kind: "concede" })).toEqual({ ok: false, error: "game is over" });
  });

  it("applies every legal Intent unchanged, without mutating its input", () => {
    // Entry points, "Legal Intents": every Intent it returns applies unchanged.
    // Entry points, "Apply an Intent": `applyIntent` doesn't mutate its input.
    const state = newGame();
    const before = JSON.stringify(state);
    for (const seat of [0, 1]) {
      for (const intent of legalIntents(state, seat)) {
        expect(applyIntent(state, seat, intent), `Seat ${seat} ${intent.kind}`).toMatchObject({ ok: true });
      }
    }
    expect(JSON.stringify(state)).toBe(before);
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
