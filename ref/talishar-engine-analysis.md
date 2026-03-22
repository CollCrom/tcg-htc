# Talishar Engine Analysis

Source: https://github.com/Talishar/Talishar (open-source FaB game engine, PHP)
Analyzed: 2026-03-20

---

## Overview

Talishar is the primary free-to-play Flesh and Blood online game engine. Written in PHP with a React/TypeScript frontend. Game state is persisted to flat text files (not a database). The engine is single-threaded, request-response — each player action triggers a full game state parse → process → write cycle.

## Architecture

```
User Action → ProcessInput.php → GameLogic/CardLogic → WriteGamestate.php
→ GetNextTurn.php → Frontend → React Components
```

### Key Files
- `GetNextTurn.php` — Main API endpoint; serializes and returns current game state
- `ProcessInput.php` — Validates user input, routes to game logic by mode number
- `GameLogic.php` — Massive switch statement (`DecisionQueueStaticEffect`) handling all game decisions (~4,000 lines)
- `CoreLogic.php` — Central game logic functions (~4,300 lines): combat, damage, turn structure, card manipulation
- `ParseGamestate.php` — Reads game state from flat file
- `WriteGamestate.php` — Persists game state to flat file
- `Constants.php` — All game constants, zone piece counts, class state indices

### Card System
- `CardDictionaries/` — Card definitions organized by set
- `CardLogic.php` — Card-specific ability implementations
- `CharacterAbilities.php`, `ItemAbilities.php`, `AuraAbilities.php` — Type-specific abilities
- `WeaponLogic.php` — Weapon mechanics

## Game State Representation

State is persisted as a newline-delimited text file. Each line is a space-separated array. Cards are stored as arrays where each card occupies N "pieces" (slots) — e.g., a character card uses 15 pieces to store its ID, status, counters, power, defense, frozen state, etc.

### Per-Player Zones (parallel p1/p2 variables)

| Zone | Variable | Pieces per Card |
|------|----------|----------------|
| Hand | `p[1-2]Hand` | 1 |
| Deck | `p[1-2]Deck` | 1 |
| Character/Equipment | `p[1-2]CharEquip` | 15 |
| Arsenal | `p[1-2]Arsenal` | 7 |
| Items | `p[1-2]Items` | 14 |
| Auras | `p[1-2]Auras` | 14 |
| Allies | — | 15 |
| Discard (Graveyard) | `p[1-2]Discard` | 3 |
| Pitch | `p[1-2]Pitch` | 1 |
| Banish | `p[1-2]Banish` | 3 |
| Soul | `p[1-2]Soul` | 1 |
| Inventory | `p[1-2]Inventory` | 1 |

### Shared State

| Variable | Purpose |
|----------|---------|
| `playerHealths` | Both players' health totals |
| `currentPlayer` | Active player ID (1 or 2) |
| `mainPlayer` / `defPlayer` | Perspective players |
| `currentTurn` | Turn number |
| `turn` | Turn phase details |
| `firstPlayer` | Initial player determination |
| `winner` | Game conclusion tracking |
| `actionPoints` | Current action resource |
| `combatChain` | Sequential combat cards played (12 pieces per entry) |
| `combatChainState` | Combat chain status data (48 indices) |
| `chainLinks` | Array of individual attack sequences (10 pieces per link) |
| `landmarks` | Landmark permanents (3 pieces) |
| `currentTurnEffects` | Effects active this turn (4 pieces: effect ID, player, target UID, uses) |
| `currentTurnEffectsFromCombat` | Combat-triggered effects |
| `nextTurnEffects` | Delayed effects (5 pieces: adds turn delay) |
| `decisionQueue` | Pending decision points (5 pieces) |
| `layers` | Effect resolution layers (7 pieces: card type/layer, player, parameters, target) |
| `layerPriority` | Effect ordering |
| `events` | Game event log (2 pieces: type and value) |
| `EffectContext` | Current effect resolution context |
| `permanentUniqueIDCounter` | Unique ID generator for permanents |

### Class State Tracking ($CS_* — 117+ indices per player)

Tracks per-turn statistics:
- `$CS_NumActionsPlayed` — Non-attack actions played
- `$CS_DamageTaken`, `$CS_DamageDealt` — Hero damage
- `$CS_NumAttacks`, `$CS_NumAttackCards` — Attack counts
- `$CS_NumChardsDrawn` — Cards drawn this turn
- `$CS_NumAuras` — Auras created/played
- `$CS_NumBoosted`, `$CS_NumCharged` — Ability counters
- `$CS_LastAttack` — Last attack card ID
- `$CS_HealthLost`, `$CS_HealthGained` — Hero life changes
- `$CS_Transcended` — Class-specific tracking

### Combat Chain State ($CCS_* — 48 indices)

Tracks current attack resolution:
- `$CCS_WeaponIndex` — Active weapon
- `$CCS_DamageDealt` — Link damage total
- `$CCS_AttackTarget` — Target designation
- `$CCS_LinkTotalPower` — Combined power value
- `$CCS_AttackUniqueID` — Attack identifier
- `$CCS_IsBoosted` — Boost status
- `$CCS_HitThisLink` — Hit occurred this link
- `$CCS_AttackCost` — Base attack cost

## Decision Queue Pattern

Talishar uses a **decision queue** pattern rather than a traditional stack. When game logic needs player input (choose targets, decide to use optional abilities, etc.), it pushes entries onto a decision queue. Each entry has 5 pieces and is processed by `DecisionQueueStaticEffect` — a giant switch statement in `GameLogic.php`.

The switch handles categories like:
- **Index finding**: `FINDINDICES`, `TRAPS`, `GETINDICES`, zone-specific searches
- **Card manipulation**: `ADDHAND`, `REMOVEMYHAND`, `ADDDISCARD`, `ADDBOTDECK`, etc.
- **Combat**: `DEALDAMAGE`, `TAKEDAMAGE`, `DEALARCANE`, `TAKEARCANE`, power/defense modifiers
- **Effects**: `ADDCURRENTTURNEFFECT`, `REMOVECURRENTTURNEFFECT`, character effects
- **Flow control**: `EQUALPASS`, `NOTEQUALPASS`, `NULLPASS`, `ELSE`, `NOPASS`
- **Validation**: `ALLCARDTYPEORPASS`, `ALLCARDSUBTYPEORPASS`, etc.

The `$lastResult` parameter carries forward output from previous queue entries, enabling sequential processing.

## CoreLogic.php — Key Function Groups

### Turn Structure
- `StartTurnAbilities()` — Beginning-of-turn triggers
- `StartActionPhaseAbilities()` — Action phase initialization
- `EndTurnPitchHandling()` — Pitch zone card handling at turn end
- `CanPassPhase()` — Phase progression validation

### Combat Chain
- `AddCombatChain()` — Initiates new combat chain
- `EvaluateCombatChain()` — Calculates total power and defense
- `ReEvalCombatChain()` — Re-evaluates after state changes
- `CloseCombatChain()` — Resolves and concludes combat

### Damage System
- `DealDamageAsync()` — Primary async damage calculation
- `FinalizeDamage()` — Concludes damage resolution
- `CanDamageBePrevented()` — Prevention eligibility check
- `DamageDealtAbilities()` — Triggers when damage resolves
- `AttackDamageAbilitiesTrigger()` — Damage-triggered abilities
- `PreventLethal()` — Prevents lethal damage scenarios
- `LoseHealth()`, `GainHealth()` — Health adjustments

### Defense
- `BlockingCardDefense()` — Computes defense from blocking cards
- `NumDefendedFromHand()`, `NumCardsBlocking()` — Block counting
- `NumEquipBlock()`, `HaveUnblockedEquip()` — Equipment blocking

### Card Playing
- `PlayAbility()` — Core function for playing card abilities
- `PitchAbility()` — Pitching cards for resources
- `CanPlayAsInstant()` — Instant timing check
- `DoesAttackHaveGoAgain()` — Go again evaluation
- `ResolveGoAgain()` — Processes go again effects

### Chain Link Resolution
- `ChainLinkResolvedEffects()` — Processed resolved chain effects
- `ResolutionStepEffectTriggers()` — Effect resolution triggers
- `ResolutionStepAttackTriggers()`, `ResolutionStepBlockTriggers()` — Attack/block resolution

### Win Condition
- `IsGameOver()`, `PlayerWon()` — Win condition checking

## Design Observations & Lessons

### What Talishar does that works
1. **Flat state serialization** — Simple to debug, replay, and diff game states
2. **Decision queue** — Decouples game logic from I/O; all decisions are serialized
3. **Per-turn class state tracking** — 117+ indices tracking everything that happened this turn (enables "if you've done X this turn" conditions)
4. **Combat chain state** — 48 indices tracking the current attack in detail
5. **Replay system** — Commands are logged and can be replayed deterministically
6. **Pieces pattern** — Fixed-width array slots per zone card enable efficient indexed access

### What we can improve for our Python engine
1. **Talishar is procedural PHP** — Our engine should be properly object-oriented with clear domain models
2. **The 4,000-line switch statement** is a maintenance nightmare — We should use polymorphism and a proper effect/ability system
3. **Magic numbers everywhere** ($CS_* indices, piece offsets) — We should use typed dataclasses/enums
4. **Card logic is hardcoded per card** — We should aim for a data-driven card definition system where possible
5. **No type safety** — Python with type hints and dataclasses gives us much better guarantees
6. **Talishar mixes game logic with presentation** — We should keep the engine pure with no UI concerns

### Key architectural decisions to take from Talishar
1. **Per-turn state tracking is critical** — Many FaB cards check "if you've done X this turn," so we need comprehensive per-turn counters
2. **Combat chain needs rich state** — Attack tracking, hit tracking, power/defense modifiers, target designation all need dedicated tracking
3. **Effects need timing** — Current turn effects, next turn effects, and permanent effects are separate concerns
4. **Decision queue pattern** — Worth adopting in some form; separates "what the game needs" from "how to get player input"
5. **Layers/stack** — Talishar uses a layers array with 7 pieces per entry (card type/layer, player, parameters, target) — our stack model should capture this
