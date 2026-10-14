# Upstream entry points and gotchas

What a coding agent can't learn quickly by reading fyendal's engine. Upstream paths are relative to `vendor/fyendal.net/`, at the commit AGENTS.md pins; `packages/runner/...` paths are ours, from the repo root. Recheck this file after a submodule bump.

## Gotchas

- **Always pass `scripts` to `createGame`.** `GameConfig.scripts` is optional, and leaving it out fails silently: cards lose their scripted effects, and some random precon mirrors (`precon-sly`, `precon-sgb`, `precon-sdo`) then run 5,000 steps to turn 2,300 or so with no winner. Import `scripts` and `cardData` from `@fyendal/cards`.
- **The Fabrary text parser is in the server app**, which our workspace doesn't include: `parseDecklistText` and `validateDeck` in `apps/server/src/decks.ts`. `apps/server/src/fabrary.ts` is an HTTP client for Fabrary's API. `packages/runner/src/list/loadList.ts` ports the parser and the List size and copy limits (`MAX_POOL_SIZE`, `MAX_COPIES` live only in `decks.ts`).
- **`validateDeck` doesn't check bans or benched heroes.** Upstream's server calls `formatLegalityIssues(cardData, pool, format)` (`packages/cards/src/formatLegality.ts`) separately, so our code must call it too. `validateArena` and `validatePresentation` do call it.
- **Off-hands and quivers are a subtype, not a card type.** Bastion of Duty (`TCC029`) has `cardType: "equipment"` and subtype `off-hand`, but goes in the weapon zone; upstream's own comment names an action card with the off-hand subtype. Use `isWeaponZoneCard` (`packages/cards/src/equipment.ts`), which covers weapons, off-hands and quivers. Upstream's `weaponSelectionError` (`packages/cards/src/presentation.ts`) accepts a lone off-hand or no weapon at all, so requiring a real weapon is our choice (`pickDecklist`).
- **Until the Game is over, `legalIntents` always includes `concede` and a draw Intent** (`offer-draw`, `withdraw-draw`, or `accept-draw` and `decline-draw`). Filter them out with `kind !== "concede" && !kind.endsWith("-draw")`, the same filter upstream's bot uses (`packages/bot/src/evaluation.ts`). After the filter the list can be empty: a `choose-name` decision enumerates nothing, because the client submits a free-form card name.
- **Pitch order multiplies Intents.** The same card paid with the same cards appears once for each legal pitch order. Sort `pitchInstanceIds` to compare Intents without order (`packages/runner/src/measure.ts`).
- **There's no fatigue.** Random Games can stalemate with empty decks (`packages/cards/src/__tests__/fullmatch.test.ts`). Cap the number of steps.
- **The seed is a 32-bit int.** `createGame` stores `seed | 0` as the rng state.
- **`@fyendal/*` only resolves from a workspace package.** Put a throwaway probe in `packages/runner/src` and run it with `pnpm --dir packages/runner exec tsx src/probe.ts` (tsx isn't installed at the root). From `docs/` it fails with `ERR_MODULE_NOT_FOUND`. A scratchpad `.ts` loads as CommonJS and happens to resolve, but an ESM one (`.mts`, top-level `await`) fails.

## Entry points

`packages/runner/src/game.ts` is the working example. Upstream's own loop is `evaluateBotMatch` in `packages/bot/src/evaluation.ts`.

| Need | Call | Where |
|---|---|---|
| Create a Game | `createGame({ decklists, cards: cardData, scripts, seed, startPlayer })` | `packages/engine/src/index.ts`; `GameConfig` in `runtimeState.ts` |
| Which Seat acts | `state.pendingDecision?.player ?? state.priorityPlayer` | |
| Legal Intents | `legalIntents(state, seat)`. It reads the full state; there is no View-based version. Every Intent it returns applies unchanged. | `index.ts`, implemented in `legal.ts` |
| A Seat's View | `projectStateFor(state, seat)` returns a `GameView` with the opponent's hidden cards masked (`hidden: true`, `cardId: ""`). | `index.ts`, `project.ts` |
| Apply an Intent | `applyIntent(state, seat, intent)` doesn't mutate its input, and doesn't throw on an illegal Intent (an unknown card id or a card script can still throw). It returns `{ ok: true, state, events }`, or `{ ok: false, error }` with a message such as `"card not found"` or `"game is over"`. | `index.ts` |
| Game over and winner | `state.phase === "game-over"`. `state.winner` is the winning Seat, or `null` for a draw, which only `accept-draw` produces. When both heroes hit 0 life at once, Seat 1 wins (`checkWin` checks Seat 0 first). | `win.ts` |
| Replay projection | `projectStateForReplay(state)` gives a full-information `GameView` with every card revealed and the game id defaulting to `"game"`. Compare two of them with `JSON.stringify` to check a replay reproduces. | `index.ts`, `project.ts` |
| Seeded rng | `rngNext({ rngState })` returns a number in [0, 1) and advances `rngState`. | `packages/engine/src/rng.ts` |
| Present a Decklist | `validatePresentation(pool, { weaponIds, equipment, deck }, format)` returns `{ ok: true, decklist }` or `{ ok: false, error }`. It runs `validateArena` (legality, weapon setup, equipment slots) first. Silver Age needs exactly 40 deck cards (`EXACT_DECK_SIZE`). | `packages/cards/src/catalog.ts`, `presentation.ts` |
| Look up cards | `cardData` (keyed by printing id), `findPrinting(name, pitch?)`, `normalizeCardName`, `isImplemented(card)` | `packages/cards/src/catalog.ts`, `index.ts` |
| Precons | `precon(id)`, `preconsForFormat(format)` | `packages/cards/src/catalog.ts` |

`@fyendal/cards` exports only `.` and `./client`. Most of `presentation.ts` is reachable through it (`weaponSelectionError`, `MIN_DECK_SIZE`, `EXACT_DECK_SIZE`), but `functional.ts` (`functionalKey`) isn't. A subpath import fails with `ERR_PACKAGE_PATH_NOT_EXPORTED`; import such modules relatively into `vendor/fyendal.net/` (`../../../vendor/fyendal.net/packages/cards/src/functional.ts` from `packages/runner/src`).
