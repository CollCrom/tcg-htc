# Talishar Card Definition System

Source: https://github.com/Talishar/Talishar
Analyzed: 2026-03-20

---

## How Cards Are Defined

Talishar uses a **distributed, function-based** approach rather than a single card data file. Card properties are split across multiple lookup functions, and card behavior is implemented via switch statements in separate ability files.

### Card ID Format

Cards are referenced by **lowercase string IDs with underscores**, often with color suffixes:
- `"head_jab_red"`, `"head_jab_yellow"`, `"head_jab_blue"` — color variants (different pitch)
- `"dawnblade"` — weapons, equipment (no color suffix)
- `"bravo_showstopper"` — heroes (name with underscores)
- `"aether_ashwing"` — tokens

### Property Lookup Functions (in CardDictionary.php + GeneratedCardDictionaries.php)

Each property is a separate function that takes a card ID and returns the value:

| Function | Returns | Example |
|----------|---------|---------|
| `CardType($cardID)` | Type code string | `"A"` (Action), `"I"` (Instant), `"W"` (Weapon), etc. |
| `CardCost($cardID)` | Integer cost | `3` |
| `PitchValue($cardID)` | Integer pitch value | `1` (red), `2` (yellow), `3` (blue) |
| `PowerValue($cardID)` | Integer power | `6` |
| `BlockValue($cardID)` | Integer defense | `3` |
| `CardClass($cardID)` | Class string | `"WARRIOR"`, `"NINJA"`, `"BRUTE"`, etc. |
| `CardTalent($cardID)` | Talent string | `"EARTH"`, `"LIGHTNING"`, `"SHADOW"`, etc. |
| `CardSubType($cardID)` | Subtype string | `"Ally"`, `"Item"`, `"Dagger"`, `"Sword"`, etc. |
| `CardSet($cardID)` | 3-letter set code | `"WTR"`, `"ARC"`, `"MON"`, etc. |

### Type Code Legend

| Code | Type |
|------|------|
| `"A"` | Action (attack action if has power) |
| `"AA"` | Attack Action (explicit) |
| `"AR"` | Attack Reaction |
| `"B"` | Block |
| `"C"` | Character/Hero |
| `"D"` | Character (alternate/dark) |
| `"DR"` | Defense Reaction |
| `"E"` | Equipment |
| `"I"` | Instant |
| `"M"` | Mentor |
| `"R"` | Resource |
| `"T"` | Token |
| `"W"` | Weapon |
| `"Event"` | Special Event card |
| `"Companion"` | Companion card |
| `"Macro"` | Macro/Rule card |

### Generated Card Data

`GeneratedCode/GeneratedCardDictionaries.php` contains auto-generated lookup tables derived from the **FaB Cube open-source dataset**. These are giant PHP match statements mapping card IDs to property values.

Example pattern (power values):
```
"adrenaline_rush_red" => 4
"adrenaline_rush_yellow" => 3
"adrenaline_rush_blue" => 2
"aftershock_red" => 8
"aftershock_yellow" => 7
"aftershock_blue" => 6
```

Key pattern: **Red > Yellow > Blue** for power, **Red < Yellow < Blue** for pitch. Typically red=1 pitch, yellow=2 pitch, blue=3 pitch.

---

## How Card Behavior Is Defined

Card behavior is split across multiple files by **ability timing**:

| File | When It Fires | Purpose |
|------|---------------|---------|
| `CardDictionaries/PlayAbilities.php` | When card is played | On-play effects |
| `CardDictionaries/HitEffects.php` | When attack hits | On-hit triggers |
| `CardDictionaries/ActivatedAbilities.php` | When ability is activated | Weapon attacks, equipment/item abilities |
| `CardDictionaries/CurrentEffects.php` | During combat/turn | Ongoing effect modifiers |
| `CardDictionaries/{Set}Shared.php` | Various | Set-specific shared logic |

Each file contains functions organized by class/set, using switch statements on card IDs.

### Activated Abilities Structure

Each class implements 3 functions for activated abilities:

```php
// Cost to activate
function WTRAbilityCost($cardID) {
    switch($cardID) {
        case "dawnblade": return 1;
        case "anothos": return 3;
        case "romping_club": return 2;
    }
}

// Type of ability (determines timing rules)
function WTRAbilityType($cardID) {
    switch($cardID) {
        case "dawnblade": return "AA";  // Attack Action
        case "energy_potion_blue": return "I";  // Instant
    }
}

// Whether the ability grants go again
function WTRAbilityHasGoAgain($cardID) {
    switch($cardID) {
        case "bravo_showstopper": return true;
        case "tectonic_plating": return true;
        default: return false;
    }
}
```

### Play Abilities (On-Play Effects)

When a card is played, its play ability function runs. Effects use a **decision queue** pattern for anything requiring player input:

```php
// Simple: just add a continuous effect for this turn
case "savage_sash":
    AddCurrentTurnEffect($cardID, $currentPlayer);
    return "";

// Complex: search opponent's arsenal, let player choose, banish it
case "send_packing_yellow":
    if (IsHeroAttackTarget()) {
        AddDecisionQueue("MULTIZONEINDICES", $currentPlayer, "THEIRARS");
        AddDecisionQueue("CHOOSEMULTIZONE", $currentPlayer, "<-", 1);
        AddDecisionQueue("MZBANISH", $currentPlayer, "CC," . $cardID, 1);
        AddDecisionQueue("MZREMOVE", $currentPlayer, "-", 1);
        AddDecisionQueue("ADDCURRENTTURNEFFECT", $currentPlayer, $cardID, 1);
    }

// Dice roll with resource conversion
case "reckless_charge_blue":
    $roll = GetDieRoll($currentPlayer);
    GainActionPoints(intval($roll / 2), $currentPlayer);
    if (GetClassState($currentPlayer, $CS_HighestRoll) == 6) Draw($currentPlayer);
    return "Rolled $roll and gained " . intval($roll/2) . " action points";

// Token creation based on revealed cards
case "cast_bones_red":
    $deck = new Deck($currentPlayer);
    if ($deck->Reveal(6)) {
        $cards = explode(",", $deck->Top(remove: true, amount: 6));
        $numSixes = 0;
        foreach ($cards as $c) {
            if (ModifiedPowerValue($c) >= 6) ++$numSixes;
        }
        PlayAura("might", $currentPlayer, $numSixes);
    }
```

### Hit Effects (On-Hit Triggers)

```php
// Dawnblade: increment counter on hit
case "dawnblade":
    AddCharacterCounter($cardID, $currentPlayer);
    return "";

// Draw a card on hit
case "whelming_gustwave":
    Draw($currentPlayer);
    return "";

// Steal opponent's item or deal damage
case "pay_up_red":
    if (HasGold($defPlayer)) StealGold($defPlayer);
    else DealDamage(1, $defPlayer);
    return "";
```

### Combat Effect Modifiers

```php
// Power modifier based on color variant
function WTREffectPowerModifier($cardID) {
    switch($cardID) {
        case "sloggism_red": return 6;
        case "sloggism_yellow": return 5;
        case "sloggism_blue": return 4;
        case "pummel_red": return 4;
        case "pummel_yellow": return 3;
        case "pummel_blue": return 2;
    }
}
```

---

## Decision Queue Pattern (for player choices)

When an effect requires player input (choose a target, decide to use an optional ability, etc.), Talishar pushes entries onto a decision queue rather than blocking:

```php
AddDecisionQueue("MULTIZONEINDICES", $player, "THEIRARS");      // Find valid targets
AddDecisionQueue("SETDQCONTEXT", $player, "Choose a card");     // Set UI prompt
AddDecisionQueue("CHOOSEMULTIZONE", $player, "<-", 1);          // Player selects
AddDecisionQueue("MZBANISH", $player, "CC," . $cardID, 1);      // Execute effect
```

Queue operations include:
- `FINDINDICES` — Find valid targets in zones
- `MULTIZONEINDICES` — Search across multiple zones
- `CHOOSEMULTIZONE` / `MAYCHOOSEMULTIZONE` — Mandatory/optional player selection
- `MZBANISH`, `MZDESTROY`, `MZADDCOUNTER` — Zone manipulation effects
- `ADDCURRENTTURNEFFECT` — Register a continuous effect
- `SETDQCONTEXT` — Set the UI prompt text
- `BUTTONINPUT` — Present button choices to player
- `PASSPARAMETER` — Pass data between queue entries
- `SHUFFLEDECK` — Shuffle player's deck

The 4th parameter (`1`) typically means "skip this step if the previous step returned no result."

---

## Key Takeaways for Our Engine

1. **Card properties are pure data** — cost, power, defense, pitch, class, talent, subtype are all just lookups. We should model these as a dataclass/schema.

2. **Card behavior is timing-based** — on-play, on-hit, on-activate, during-combat are separate concerns. Our card ability system should reflect these timing hooks.

3. **The decision queue is the key pattern** — separates "what choices exist" from "how the player makes them." Essential for both human play and AI simulation.

4. **Effects are identified by card ID** — `AddCurrentTurnEffect($cardID, $player)` registers the card as having an active effect. Separate functions check what that effect does during combat/resolution.

5. **Color variants are distinct cards** — `head_jab_red`, `head_jab_yellow`, `head_jab_blue` are three separate entries with different power/pitch values but shared ability logic.

6. **Generated data from FaB Cube** — The open-source FaB Cube dataset provides base card properties. We should look into this as a data source: https://github.com/the-fab-cube

7. **Per-class organization** — Abilities are grouped by class (Warrior, Ninja, etc.) in the code. Each class has its own functions for costs, types, go-again, play abilities, hit effects, etc.
