# FaB Cube Card Dataset

Source: https://github.com/the-fab-cube/flesh-and-blood-cards
Analyzed: 2026-03-20

Open-source JSON/CSV card data for the Flesh and Blood TCG. This is what Talishar uses to generate its card dictionaries.

---

## Overview

- **Formats**: JSON and CSV, English + 4 other languages
- **Card identity**: unique by name + pitch value (color variants are separate entries)
- **Stable UUIDs**: every card, printing, set gets a permanent unique ID
- **Comprehensive**: includes all sets, all formats, legality status, errata text

## File Structure

```
json/english/
  card.json              — Full card data with nested printings (~10MB+)
  card-flattened.json    — One entry per printing (~31MB)
  card-reference.json    — Card-to-card relationships
  card-face-association.json — Double-faced card links
  keyword.json           — 89 keyword definitions
  type.json              — 117 type/subtype definitions
  ability.json           — Ability type definitions
  set.json               — Set metadata
  edition.json           — Set editions
  rarity.json            — Rarity codes
  ...legality/banned/suspended files per format

csvs/english/
  card.csv               — Tab-separated card data (more manageable size)
  card-printing.csv      — Printing details
  keyword.csv, type.csv, etc.
```

## Card Schema (from card.csv / card.json)

### Core Properties

| Field | Type | Description | Example Values |
|-------|------|-------------|----------------|
| `unique_id` | string | Stable UUID | `"W7wh8hBkTd9ntjtFfqrdz"` |
| `name` | string | Card name | `"Adrenaline Rush"` |
| `color` | string | Pitch strip color | `"Red"`, `"Yellow"`, `"Blue"`, `""` (blank) |
| `pitch` | string | Pitch value | `"1"`, `"2"`, `"3"`, `""` (blank) |
| `cost` | string | Resource cost | `"0"`, `"3"`, `"X"`, `"XX"`, `""` (blank) |
| `power` | string | Power value | `"4"`, `"*"`, `"X"`, `""` (blank) |
| `defense` | string | Defense value | `"3"`, `"*"`, `""` (blank) |
| `health` | string | Life (heroes/allies) | `"20"`, `""` (blank) |
| `intelligence` | string | Intellect (heroes) | `"4"`, `""` (blank) |
| `arcane` | string | Arcane damage | `"3"`, `"X"`, `""` (blank) |

### Classification

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `types` | array/CSV list | All types and subtypes | `"Generic, Action, Attack"` |
| `traits` | array/CSV list | Card traits | `"Agents of Chaos"` |
| `type_text` | string | Full type box text | `"Ninja Action - Attack"` |

### Keywords & Abilities

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `card_keywords` | array | Keywords the card inherently has | `"Go again"`, `"Dominate"` |
| `abilities_and_effects` | array | Types of abilities | `"Once per turn Action"` |
| `ability_and_effect_keywords` | array | Keywords in abilities/effects | `"Attack"` |
| `granted_keywords` | array | Keywords granted to other objects | `"Go again"` |
| `removed_keywords` | array | Keywords removed from objects | — |
| `interacts_with_keywords` | array | Keywords the card interacts with | `"Boost"` |

### Text

| Field | Type | Description |
|-------|------|-------------|
| `functional_text` | string | Card text in Markdown (with errata applied) |
| `functional_text_plain` | string | Card text in plain text |

### Format Legality

| Field | Type |
|-------|------|
| `blitz_legal` | boolean |
| `cc_legal` | boolean |
| `commoner_legal` | boolean |
| `ll_legal` | boolean |
| `*_banned`, `*_suspended`, `*_living_legend` | boolean + date fields per format |

---

## Real Card Examples (from card.csv)

### Hero: Arakni (Assassin)
```
name: Arakni
types: Assassin, Hero, Young
health: 20   intelligence: 4
functional_text: "Whenever you play a card with contract, you may look at the
  top card of target opponent's deck. You may put it on the bottom."
type_text: Assassin Hero - Young
```

### Weapon: Anothos (Guardian 2H Hammer)
```
name: Anothos
types: Guardian, Weapon, Hammer, 2H
abilities_and_effects: Once per turn Action
ability_and_effect_keywords: Attack
functional_text: "Once per turn Action - {r}{r}{r}: Attack
  While there are 2 or more cards with cost 3 or greater in your pitch zone,
  Anothos has +2{p}."
type_text: Guardian Weapon - Hammer (2H)
```

### Equipment: Achilles Accelerator (Mechanologist Legs)
```
name: Achilles Accelerator
cost: 0
types: Mechanologist, Equipment, Legs
card_keywords: Arcane Barrier 1
abilities_and_effects: Instant
interacts_with_keywords: Boost
functional_text: "Instant - Destroy Achilles Accelerator: Gain 1 action point.
  Activate this ability only if you have boosted this turn.
  Arcane Barrier 1"
type_text: Mechanologist Equipment - Legs
```

### Attack Action (Red): Adrenaline Rush
```
name: Adrenaline Rush
color: Red   pitch: 1   cost: 2   power: 4   defense: 2
types: Generic, Action, Attack
functional_text: "When you play this, if you have less {h} than an opposing
  hero, this gets +3{p}."
type_text: Generic Action - Attack
```

### Non-Attack Action (Red): 10,000 Year Reunion (Aura)
```
name: 10,000 Year Reunion
color: Red   pitch: 1   cost: 8   defense: 3
types: Illusionist, Action, Aura
card_keywords: Ward 10
functional_text: "You may remove three +1{p} counters from among auras you
  control rather than pay 10,000 Year Reunion's {r} cost.
  Ward 10"
type_text: Illusionist Action - Aura
```

### Defense Reaction: Absorb in Aether
```
name: Absorb in Aether
color: Red   pitch: 1   cost: 1   defense: 4
types: Wizard, Defense Reaction
functional_text: "The next card you play this turn with an effect that deals
  arcane damage, instead deals that much arcane damage plus 2."
type_text: Wizard Defense Reaction
```

### Instant: Aetherize
```
name: Aetherize
color: Blue   pitch: 3   cost: 1
types: Wizard, Instant
card_keywords: Negate
functional_text: "Negate target instant card with cost {r} or less."
type_text: Wizard Instant
```

### Attack Reaction: Affirm Loyalty
```
name: Affirm Loyalty
color: Red   pitch: 1   cost: 0   defense: 2
types: Draconic, Warrior, Attack Reaction
functional_text: "Target dagger attack gets +2{p}. If you control 2 or more
  Draconic chain links, create a Fealty token."
type_text: Draconic Warrior Attack Reaction
```

### Token: Agility
```
name: Agility
types: Generic, Token, Aura
granted_keywords: Go again
functional_text: "At the start of your turn, destroy this, then your next
  attack this turn gets go again."
type_text: Generic Token - Aura
```

### Block: Asking for Trouble
```
name: Asking for Trouble
color: Yellow   pitch: 2   defense: 4
types: Brute, Block
functional_text: "When this defends, create a Vigor token under the
  attacking hero's control."
type_text: Brute Block
```

### Arcane Action: Aether Dart (Red)
```
name: Aether Dart
color: Red   pitch: 1   cost: 0   defense: 3   arcane: 3
types: Wizard, Action
functional_text: "Deal 3 arcane damage to any target."
type_text: Wizard Action
```

---

## All 89 Keywords

Ambush, Amp X, Arcane Barrier X, Arcane Shelter X, Attack, Awaken, Battleworn, Beat Chest, Blade Break, Blood Debt, Bond, Boost, Channel, Charge, Clash, Cloaked, Combo, Contract, Crank, Crush, Decompose, Dominate, Ephemeral, Essence, Evo Upgrade, Flow, Freeze, Fusion, Galvanize, Go again, Go Fish, Guardwell, Heave X, Heavy, Intimidate, Legendary, Mark, Material, Mirage, Modular, Negate, Opt X, Overpower, Pairs, Perched, Phantasm, Piercing X, Protect, Quell X, Reload, Reprise, Retrieve, Rune Gate, Rupture, Scrap, Solflare, Specialization, Spectra, Spellvoid X, Steal, Stealth, Surge, Suspense, Temper, The Crowd Boos, The Crowd Cheers, Tower, Transcend, Transform, Unfreeze, Unity, Universal, Unlimited, Wager, Ward X, Watery Grave

## All 117 Types

**Card types**: Action, Attack Reaction, Block, Companion, Defense Reaction, Demi-Hero, Equipment, Hero, Instant, Macro, Mentor, Resource, Token, Weapon

**Subtypes (functional)**: 1H, 2H, Affliction, Ally, Arrow, Ash, Attack, Aura, Construct, Figment, Invocation, Item, Landmark, Off-Hand, Quiver

**Subtypes (non-functional)**: Angel, Arms, Axe, Base, Book, Bow, Brush, Cannon, Chest, Chi, Claw, Club, Cog, Dagger, Demon, Dragon, Evo, Fiddle, Flail, Gem, Gun, Hammer, Head, Legs, Lute, Mercenary, Orb, Pistol, Pit-Fighter, Polearm, Rock, Scepter, Scroll, Scythe, Shuriken, Song, Staff, Sword, Trap, Wrench, Young

**Supertypes (class)**: Adjudicator, Assassin, Bard, Brute, Guardian, Illusionist, Mechanologist, Merchant, Necromancer, Ninja, Pirate, Ranger, Runeblade, Shapeshifter, Thief, Warrior, Wizard

**Supertypes (talent)**: Chaos, Draconic, Earth, Elemental, Ice, Light, Lightning, Mystic, Revered, Reviled, Royal, Shadow

**Other**: Generic, Event, High Seas, Rosetta, Placeholder Card

---

## Usage Notes for Our Engine

1. **card.csv is the best starting point** — tab-separated, one row per card (unique by name+pitch), manageable size
2. **functional_text contains errata** — always use this over printed text
3. **Types field is a flat list** — we'll need to parse it to separate supertypes, types, and subtypes
4. **Numeric fields are strings** — need to handle `""`, `"*"`, `"X"`, `"XX"` gracefully
5. **Keywords are pre-parsed** — the dataset separates inherent keywords, ability keywords, granted keywords, etc.
6. **No rules engine logic** — this is pure data. We still need to implement what each keyword/ability actually does
7. **Card text is natural language** — we'll need to parse `functional_text` or implement card behavior manually (like Talishar does)
