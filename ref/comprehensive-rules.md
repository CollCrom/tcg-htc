# Flesh and Blood Comprehensive Rules

Source: Official FaB Comprehensive Rules document (provided 2026-03-19)

---

## 1 Game Concepts

### 1.0 General
1.0.1 The rules in this document apply to any game of Flesh and Blood.
1.0.1a If an effect directly contradicts a rule contained in this document, the effect supersedes that rule.
1.0.1b If a tournament rule contradicts a rule contained in this document or an effect, the tournament rule supersedes that rule or that effect.
1.0.2 A restriction is a rule or effect that states something cannot happen. A requirement is a rule or effect that states that something should happen if possible. An allowance is a rule or effect that states something can happen. A restriction takes precedence over any requirement or allowance, and a requirement takes precedence over any allowance, subject to [1.0.1a].
1.0.2a A restriction that states that "only" something can happen is functionally equivalent to a restriction that states everything else cannot happen.
1.0.2b A restriction or requirement does not retroactively change the game state.

### 1.1 Players
1.1.1 A player is a person participating in the game.
1.1.1a To participate, a person must have a hero, a card-pool, a way to represent any tokens and counters that could be created by effects in their card-pool, a way to generate uniform random values for effects in their card-pool, a play-space for zones, and a method to record life totals.
1.1.2 A player's hero is a hero-card.[1.3.2a]
1.1.2a This document distinguishes the player as the person participating in the game and the hero as the hero card of a player.
1.1.2b A player plays the game as their hero. Card text makes no distinction between the player and their hero, identifying both identically. The term "you" refers to the player (and their hero) that is the controller of the object, or the owner of the object if there is no controller. The term "opponent" refers to the player's opponent (and their hero).
1.1.3 A player's card-pool is a collection of deck-cards and arena-cards. A card can only be included in a player's card-pool if the card's supertypes are a subset of their hero's supertypes.
1.1.3a If an effect allows a player to start the game with one or more cards with supertypes that are not a subset of their hero's supertypes, those cards may be included in the player's card-pool as long as they start the game as specified by the effect.
1.1.3b A hybrid card may be included in a player's card-pool if either of the hybrid card's supertype sets is a subset of their hero's supertypes.
1.1.4 In a game, a party comprises players who win the game together.
1.1.4a A player is always considered to be in a party with themselves, including when they are the only player in that party.
1.1.5 In a game, a player's opponents include all other players who are not in their party.
1.1.6 Clockwise order is the order of players starting from the given player and progressing clockwise among the players when viewed from above. The next player in clockwise order is the player to the left of the given player.

### 1.2 Objects
1.2.1 An object is an element of the game with properties and located in a zone or a player's inventory. Cards, attacks, macros, and layers are objects.
1.2.1a The owner of an object is the same as the card, macro, or layer that represents it, otherwise it has no owner.
1.2.1b The controller of an object is the same as the card, macro, or layer that represents it. An object does not have a controller if it is not in the arena or on the stack.
1.2.2 An object has one or more object identities that can be referred to.
1.2.2a An object has the object identity "object."
1.2.2b An object with a name property and/or moniker has the object identity of that name and/or moniker.
1.2.2c A card has the object identity of its traits, types, and subtypes, except for the subtype attack.
1.2.2d An attack-card, attack-proxy, or attack-layer has the object identity "attack."
1.2.2e A card has the object identity "card."
1.2.2f A permanent has the object identity "permanent."
1.2.2g An activated-layer has the object identity "activated ability."
1.2.2h A triggered-layer has the object identity "triggered effect."
1.2.3 Last known information about an object is a snapshot of the state of an object immediately before it ceased to exist.
1.2.3a If a rule or effect requires information about a specific object that no longer exists, instead it uses last known information about that object to fulfil that requirement.
1.2.3b Last known information about an object includes all parameters, history, and effects applicable to that object at the time it still existed.
1.2.3c Last known information about an object is immutable - it cannot be altered.
1.2.3d Last known information about an object is not an object itself - it is not a legal target for rules and effects.
1.2.4 Card and macro objects are the source of abilities, effects, non-card layers, and attack-proxies.

### 1.3 Cards
1.3.1 A card is an object represented by an official Flesh and Blood card.
1.3.1a The owner of a card is the player who started the game with that card as their hero or as part of their card-pool, or the player instructed to create it or otherwise put it into the game.
1.3.1b A card does not have a controller unless it is in the arena or on the stack. The controller of a card is its owner as it enters the arena or the player who played that card.
1.3.2 There are 4 categories of cards: hero-, token-, deck-, and arena-cards.
1.3.2a A hero-card is any card with the type hero. A hero-card starts the game as a player's hero.
1.3.2b A token-card is any card with the type token. A token-card is not considered part of a player's card-pool.
1.3.2c A deck-card is any card with one of the following types: Action, Attack Reaction, Block, Defense Reaction, Instant, Mentor, and Resource. A deck-card may start the game in a player's deck.
1.3.2d An arena-card is any non-hero- non-token- non-deck-card. An arena-card cannot start the game in a player's deck.
1.3.3 A permanent is a card in the arena that remains there indefinitely, or until they are destroyed, banished, or otherwise removed by an effect or game rule. Hero-cards, arena-cards, and token-cards are permanents while they are in the arena. Deck-cards become permanents when they are put into the arena (but not the combat chain) and they have one of the following subtypes: Affliction, Ally, Ash, Aura, Construct, Figment, Invocation, Item, and Landmark.
1.3.3a If a permanent leaves the arena, it is no longer considered a permanent.
1.3.3b A permanent has one of two different states: untapped and tapped.
1.3.4 A card is distinct from another card if one or more of its faces has a name and/or pitch value the other card does not have.

### 1.4 Attacks
1.4.1 An attack is an object on the stack or combat chain that represents an act of combat. Attack-cards, attack-layers, and attack-proxies are attacks.
1.4.1a The owner of an attack is the same as the owner of the card or activated ability that represents it.
1.4.1b The controller of an attack is the same as the controller of the object that represents it.
1.4.2 An attack-card is a card with the subtype attack that is on the stack or that is attacking on the combat chain.
1.4.2a A card with the subtype attack is only considered an attack if it is on the stack or if it was put onto the combat chain as an attack.
1.4.3 An attack-proxy is a non-card object with the attack ability that represents the attack of another object (attack-source).
1.4.3a An attack-proxy is a separate object that acts as an extension of its attack-source. It can only be referenced by effects using the object identity "attack," but is considered to inherit the properties of its attack-source in addition to any existing properties it has, with the exception of the activated and resolution abilities of its attack-source.
1.4.3b An attack-source is an object that is represented by an attack-proxy.
1.4.3c An attack-proxy exists as long as its attack-source exists, and as long as the attack-source is on the same chain link (if the attack-proxy is on the combat chain).
1.4.3d Effects that apply to the attack-source do not directly apply to its attack-proxy. If an effect applies to an attack-source and modifies its properties, the modified properties of the object are inherited by the attack-proxy.
1.4.3e Effects that reference or apply specifically to an attack-proxy do not reference or apply to its attack-source.
1.4.4 An attack-layer is a layer with the attack effect that represents an attack with no properties on the stack.
1.4.4a An attack-layer is not an extension of its attack-source.
1.4.4b An attack-layer is considered a separate object from its attack-source for an effect that applies specifically to attacks.
1.4.5 An attack-target is the target of an attack that is declared when the attack is put onto the stack. If a player plays or activates an attack, or adds a triggered-layer to the stack with an attack effect, the player must declare an attackable object controlled by an opponent as the attack-target.
1.4.5a An object is attackable if it is a living object, or if it is made attackable by an effect.
1.4.5b An attack-target remains the target of the attack until the combat chain closes.
1.4.5c If an effect modifies an attack to have multiple targets, all targets must be separate and legal to declare.
1.4.6 An attack cannot be played or activated if a rule or effect would prevent the player from attacking with that card or ability.

### 1.5 Macros
1.5.1 A macro is a non-card object in the arena.
1.5.1a A macro has no owner.
1.5.1b The controller of a macro is determined by the tournament rule that created it.
1.5.2 A macro cannot be and is not considered part of a player's card-pool.
1.5.3 If a macro leaves the arena, it is removed from the game.

### 1.6 Layers
1.6.1 A layer is an object on the stack that is yet to be resolved. Card-layers, activated-layers, and triggered-layers are layers.
1.6.1a The owner of a card-layer is the player who owns the card. The owner of an activated-layer is the player who activated the activated ability. The owner of a triggered-layer is the player who controlled the source of the triggered effect when the triggered-layer was created.
1.6.1b The controller of a layer is the player that put it on the stack.
1.6.2 There are 3 categories of layers: card-, activated-, and triggered-layers.
1.6.2a A card-layer is a layer represented by a card on the stack.
1.6.2b An activated-layer is a layer created by an activated ability.
1.6.2c A triggered-layer is a layer created by a triggered effect.

### 1.7 Abilities
1.7.1 An ability is a property of an object that influences the game by generating effects or by creating a layer on the stack that resolves and generates effects.
1.7.1a The source of an ability is the card or token that has that ability.
1.7.1b The controller of an activated-layer is the player who activated its source.
1.7.2 If an object has an ability as a property, it is considered a card with that ability.
1.7.3 There are three categories of abilities: activated abilities, resolution abilities, and static abilities.
1.7.3a Activated abilities can be activated by a player to put an activated-layer on the stack.
1.7.3b Resolution abilities generate effects when a layer with the ability resolves on the stack.
1.7.3c Static abilities simply generate effects.
1.7.4 An activated ability can only be activated when it is functional. A resolution or static ability only generates its effects when it is functional. An ability is functional when its source is public and in the arena; otherwise, it is non-functional, with the following exceptions: [1.7.4a–1.7.4j — see full document for exceptions]
1.7.5 A modal ability is a choice of modes, where each mode is a base ability the source could have.
1.7.6 A connected ability pair is a pair of abilities where the parameters and/or events of one connected ability (leading ability) are specifically referred to by the effect(s) of the other connected ability (following ability).
1.7.7 The abilities of an object can be modified.

### 1.8 Effects
1.8.1 An effect is generated by an ability or another effect, and can change the game state by producing events or applying changes to objects or the game itself.
1.8.1a The source of an effect is the same as the source of the ability or effect that generated it, unless otherwise specified.
1.8.1b The controller of an effect is the same as the controller of the ability or effect that generated it unless otherwise specified.
1.8.2 If the abilities of an object directly generate an effect, the object is considered an object with that effect.
1.8.3 An optional effect is an effect that the player may choose to be generated (contains "may").
1.8.4 A conditional effect is an effect that is dependent on a condition to be met. [Various subformats: "while," "otherwise," "unless," "if...X, Y, Z"]
1.8.5 A targeted effect is an effect where the target parameters are declared as the layer is put onto the stack. Always contains "target [DESCRIPTION]."
1.8.5a Only public objects in the arena or on the stack are targetable unless otherwise specified.
1.8.5b The same legal target cannot be declared more than once for any one instance of the target phrase.
1.8.5c An effect that does not use the term "target" is not a targeted effect.
1.8.5d If the targeted effect can only be applied to certain objects, otherwise legal targets are restricted.
1.8.5e If a targeted effect is optional, the player may choose not to select a target.
1.8.5f If an effect modifies the target of a targeted effect, only legal targets may be selected.
1.8.6 If the parameters of an effect are undetermined at the time the effect is generated, the player instructed by the effect determines the parameters.
1.8.7 If an effect refers to the value of a property, it infers the existence of the property as well as its value.
1.8.7a If an effect requires the value of a numeric property from a specific object without that property, then zero is used.
1.8.8 If an effect instructs a player to perform an action "as though" the game state or rules were modified, rules and effects consider the modified game state for the applicable effect only.
1.8.9 An effect fails if (A) it is a targeted effect and all declared targets are no longer legal or have ceased to exist, (B) the effect requires additional parameters and there are no legal parameters, or (C) if all the events it creates fail to occur.
1.8.10 If an effect specifies "your next attack" it refers to the next attack that comes under the player's control.
1.8.10a If an object has already been played/activated and then its properties change to become an attack, the effect does not apply.

### 1.9 Events
1.9.1 An event is a change in the game state produced by the resolution of a layer, the result of an effect, a transition of turn phase or combat step, or an action taken by a player.
1.9.1a If an event comprises an instruction that involves elements outside the game, it cannot be modified by replacement effects or trigger triggered effects within the game, unless the event directly interacts with the game.
1.9.1b If an event comprises an instruction to do nothing, the event does not occur.
1.9.1c If an event comprises an instruction where failure cannot be verified by an opponent, that player may choose to fail to complete that instruction.
1.9.2 A multi-event is a collection of two or more individual events that involve performing the same or similar instructions.
1.9.2a If a triggered effect triggers from a multi-event, it does not trigger again for any of the individual events of that multi-event.
1.9.2b If a replacement effect replaces a multi-event, it does not replace any of the individual events.
1.9.2c If an event involves two or more players performing an instruction, it is a multi-event where each player performs the instruction in clockwise order starting with the turn-player.
1.9.3 A named-event is an event or collection of events named according to the keyword effect that produced it.
1.9.3a If a replacement effect modifies an event as part of a named-event, but does not modify the named-event as a whole, the named-event retains its name.
1.9.3b If a named-event cannot occur, then none of the events that comprise it occur.

### 1.10 Game State
1.10.1 A game state is a moment in the game. The game transitions between states when an event occurs. A priority state is a game state where a player would typically receive priority.
1.10.2 When the game transitions to a new priority state, the following game state actions are performed first:
1.10.2a First, if one or more heroes have died, their player loses the game (or the game ends in a draw).
1.10.2b Second, if one or more living objects in the arena have 0 life total, they are cleared simultaneously.
1.10.2c Third, continuous look effects are updated.
1.10.2d Fourth, state-based triggered effects are checked and triggered-layers added to the stack.
1.10.2e Fifth and finally, if the combat chain is open and a rule or effect has closed it, the Close Step begins.
1.10.3 If a player makes an illegal action, the game state is reversed to the legal state before that action started.

### 1.11 Priority
1.11.1 Priority describes which player may play a card, activate an ability, or pass priority.
1.11.2 Only one player can have priority at any point in time. A player with priority is the "active player."
1.11.3 The Action Phase is the only phase when players get priority. At the beginning of the action phase, during most steps of combat, and after the resolution of a layer, the turn-player gains priority.
1.11.4 The active player may pass priority to the next player.
1.11.4a If all players pass in succession without playing/activating anything and the stack is not empty, the top layer resolves. If the stack is empty, the phase or step ends.
1.11.5 If the active player plays a card or activates an ability, they regain priority after.

### 1.12 Numbers and Symbols
1.12.1 Numbers are always integers.
1.12.1a Fractions round towards zero unless specified otherwise.
1.12.1b If a rule/effect requires a player to choose a number, the number must be a non-negative integer.
1.12.2 X represents a value that starts undefined and is defined later.
1.12.2a If X is undefined, it is evaluated as zero.
1.12.2b If X is defined, it remains defined until the object ceases to exist.
1.12.2c Y and Z may also be used for additional undefined values.
1.12.3 The asterisk (*) represents a value defined by a meta-static ability or continuous effect.
1.12.3a If * is undefined, it is evaluated as zero.
1.12.3b Meta-static ability definition takes precedence over effect definition for *.
1.12.4 Symbols:
- {d} = defense value
- {i} = intellect value
- {h} = life value
- {p} = power value / physical damage
- {r} = resource value
- {c} = chi value
- {t} = tap effect
- {u} = untap effect

### 1.13 Assets
1.13.1 An asset is a point of a given type, owned by a player. Types: action points, resource points, life points, and chi points.
1.13.2 Action points are used to play action cards and activate action abilities.
1.13.2a Gained during action phase from: start of action phase, go again ability, and effects.
1.13.2b A player cannot gain action points if it is not their action phase.
1.13.3 Resource points are used to play cards and activate abilities.
1.13.3a Gained from: pitching cards and effects.
1.13.4 Life points are paid from a player's hero's life total.
1.13.5 Chi points are used to play cards and activate abilities.
1.13.5a Gained from: pitching cards during payment of costs requiring chi or resource points.
1.13.5b A chi point can be used in place of a resource point for paying resource point costs.

### 1.14 Costs
1.14.1 A cost is the requirement of payment incurred by playing a card, activating an ability, or resolving/applying an effect. Asset-costs require assets. Effect-costs require successful resolution of effects.
1.14.2 To pay an asset-cost, the player must have or gain assets of the appropriate type ≥ the cost.
1.14.2a Multiple asset types paid in order: chi points, resource points, life points, action points.
1.14.2b If the player cannot pay, the game state is reversed.
1.14.2c Chi point cost: must use chi points; may pitch cards to gain them.
1.14.2d Resource point cost: must use resource points and chi points; chi spent first.
1.14.2e Life point cost: must use life points.
1.14.2f Action point cost: must use action points.
1.14.3 To pitch a card, move it from hand to the pitch zone and gain assets.
1.14.3a A card cannot be pitched if it does not have the pitch property.
1.14.3b A player may only pitch a card if it will gain them assets they need to pay an asset-cost or if instructed by an effect.
1.14.3c Pitching a card is an event.
1.14.4 An effect-cost requires payment in the form of generating one or more effects.
1.14.4a If an effect-cost involves two or more effects, the player declares the order.
1.14.4b If any of the effects cannot be generated or resolved, the cost cannot be paid.
1.14.4c If an effect-cost is replaced and cannot be resolved, the cost is still considered paid.
1.14.5 A cost of "0" is still a cost and is paid by acknowledging the zero cost.

### 1.15 Counters
1.15.1 A counter is a physical marker placed on any public object. Counters are not objects and have no properties.
1.15.2 A counter modifies the properties and/or interacts with effects of the object it is on.
1.15.2a A counter with a numerical value and symbol modifies the corresponding property of the object.
1.15.3 When an object ceases to exist, counters on it cease to exist. When removed from an object, the counter ceases to exist.
1.15.4 Diametrically opposing counters both remain on the object (they do not cancel out).

---

## 2 Object Properties

### 2.0 General
2.0.1 There are 13 properties an object may have: abilities, color strip, cost, defense, intellect, life, name, pitch, power, subtypes, supertypes, text box, and type.
2.0.2 Properties are determined by the true text of the card on cardvault.fabtcg.com.
2.0.3 A numeric property has a numeric value that can be modified by effects and/or counters.
2.0.3a An effect modifying a numeric property does not modify the base value unless specified.
2.0.3b Modifying the base value is not considered increasing or decreasing the value for effect purposes.
2.0.3c A numeric property cannot have a negative base or modified value (minimum 0).
2.0.3d +1 or -1 property counters modify the value but not the base value.
2.0.4 An object has gained a property if it did not have it before but currently does. Gaining/losing a property is not considered increasing/decreasing the value.
2.0.5 The source of a property is the object of which the property is an attribute.

### 2.1 Color
2.1.1 Color is a visual representation. Red color strip = red. Yellow = yellow. Blue = blue.
2.1.2a Printed pitch is typically associated with color but they are independent.

### 2.2 Cost
2.2.1 Cost determines the starting resource asset-cost to play the card or activate the ability.
2.2.2 Printed in top right corner. Defines base cost. No printed cost = no cost property (0 is valid).
2.2.4 The cost property cannot be modified. Effects that increase/reduce cost only apply during the play/activate process.
2.2.4b "Cost" refers to unmodified cost property. "Payment" refers to modified cost when actually paid.

### 2.3 Defense
2.3.1 Defense represents the value contributed to total defense in the damage step of combat.
2.3.2 Printed at bottom right. Defines base defense. No printed defense = no defense property (0 is valid).
2.3.3 Defense can be modified. "Defense" or {d} refers to modified defense.

### 2.4 Intellect
2.4.1 Intellect represents the number of cards the controlling player draws up to at end of turn.
2.4.2 Printed at bottom left. No printed intellect = no intellect property (0 is valid).
2.4.3 Intellect can be modified.

### 2.5 Life
2.5.1 Life represents the starting life total of an object.
2.5.1a A permanent with the life property is a living object.
2.5.2 Printed at bottom right. No printed life = no life property (0 is valid).
2.5.3 Life of a permanent can be modified. "Life total" refers to: base life + life gained - life lost.
2.5.3a Life total = base life + gained - lost.
2.5.3b Life gained/lost are discrete effects, permanently modifying life total.
2.5.3c If base life changes, life total is recalculated.
2.5.3e Life total cannot be negative (minimum 0).
2.5.3f If a permanent's life total reaches 0, it is cleared as a game state action.
2.5.3g If a living object ceases to exist, it is considered to have died.

### 2.6 Metatype
2.6.1 Metatypes determine whether an object may be added to a game.
2.6.5 An object cannot gain or lose metatypes.
2.6.6 Metatypes are hero-metatypes (specify hero moniker) or set-metatypes (specify valid sets).

### 2.7 Name
2.7.1 Name represents one of an object's identities and determines uniqueness.
2.7.2 Printed at top of card.
2.7.3 A personal name determines a moniker. Format: "[HONORIFIC?] [MONIKER] [LAST?] [, SUFFIX?]"
2.7.3a If an object doesn't have a personal name, it has no moniker.
2.7.3b Two objects can have different names but the same moniker. An effect referring to a moniker may refer to multiple objects.
2.7.3c A moniker is not considered a name.
2.7.4 Always considered the English language version regardless of printed language.
2.7.5 Names must be exact case-insensitive whole-word matches.

### 2.8 Pitch
2.8.1 Pitch represents assets a player gains when pitching the card. Pitch value = number of assets gained.
2.8.2 Expressed visually as 1, 2, or 3 socketed {r} or {c} symbols in top left corner.
2.8.3 Pitch can be modified.

### 2.9 Power
2.9.1 Power represents the power value used in the damage step of combat.
2.9.2 Printed at bottom left. No printed power = no power property (0 is valid).
2.9.3 Power can be modified. "Power" or {p} refers to modified power.

### 2.10 Subtypes
2.10.1 Subtypes determine additional rules applicable to the card.
2.10.5 An object can gain or lose subtypes.
2.10.6a Functional subtype keywords: (1H), (2H), Affliction, Ally, Arrow, Ash, Attack, Aura, Construct, Figment, Invocation, Item, Landmark, Off-Hand, Quiver.
2.10.6b Non-functional subtype keywords: Angel, Arms, Axe, Base, Book, Bow, Brush, Cannon, Chest, Chi, Claw, Club, Cog, Dagger, Demon, Dragon, Evo, Fiddle, Flail, Gem, Gun, Hammer, Head, Legs, Lute, Mercenary, Orb, Pistol, Pit-Fighter, Polearm, Rock, Scepter, Scroll, Scythe, Shuriken, Song, Staff, Sword, Trap, Wrench, Young.

### 2.11 Supertypes
2.11.1 Supertypes determine whether a card can be included in a player's card-pool.
2.11.5 An object can gain or lose supertypes.
2.11.6a Class supertype keywords: Adjudicator, Assassin, Bard, Brute, Guardian, Illusionist, Mechanologist, Merchant, Necromancer, Ninja, Pirate, Ranger, Runeblade, Shapeshifter, Thief, Warrior, Wizard.
2.11.6b Talent supertype keywords: Chaos, Draconic, Earth, Elemental, Ice, Light, Lightning, Mystic, Revered, Reviled, Royal, Shadow.

### 2.12 Text Box
2.12.1 Contains card text: rules text, reminder text, and flavor text.
2.12.3 Rules text defines base abilities. Reminder and flavor text do not affect the game.
2.12.3a Self-references in rules text can be interpreted as "this."
2.12.3b Name in rules text refers to existing objects with that name, or a hypothetical object when creating.

### 2.13 Traits
2.13.1 Trait represents one of an object's identities.
2.13.3 Traits are non-functional keywords.
2.13.3a Current trait keywords: Agents of Chaos.

### 2.14 Type Box
2.14.1 Format: "[METATYPES] [SUPERTYPES] [TYPE] [--- SUBTYPES]"
2.14.1a "Generic" supertypes = no supertypes.
2.14.1b Hybrid cards have supertypes in format "[SUPERTYPES-1] / [SUPERTYPES-2]."

### 2.15 Types
2.15.1 Types determine whether the card is a hero-, token-, deck-, or arena-card, and how a deck-card may be played.
2.15.5 An object can gain or lose types.
2.15.6a Type keywords: Action, Attack Reaction, Block, Companion, Defense Reaction, Demi-Hero, Equipment, Hero, Instant, Macro, Mentor, Resource, Token, Weapon.

---

## 3 Zones

### 3.0 General
3.0.1 There are 15 types of zones: arms, arsenal, banished, chest, combat chain, deck, graveyard, hand, head, hero, legs, permanent, pitch, stack, and weapon.
3.0.1a A zone is considered empty when it contains no objects and has no permanents equipped to it.
3.0.2 Each player has their own arms, arsenal, banished, chest, deck, graveyard, hand, head, hero, legs, and pitch zones; and two weapon zones. The stack, permanent, and combat chain zones are shared.
3.0.3 Objects are either public (visible to all) or private (not visible to all).
3.0.3a A player may look at any private object they own, or in a zone they own, unless it is in the deck zone.
3.0.4a Public zones: arms, banished, chest, combat chain, graveyard, head, hero, legs, permanent, pitch, stack, weapon.
3.0.4b Private zones: arsenal, deck, hand.
3.0.5 The arena is a collection of all arms, chest, combat chain, head, hero, legs, permanent, and weapon zones.
3.0.5a The arena is not a zone itself.
3.0.5b Arsenal, banished, deck, graveyard, hand, pitch, and stack zones are NOT part of the arena.
3.0.7 When an object moves zones, leaving and entering are simultaneous. The object is never not in a zone.
3.0.7a The object as it leaves the origin is considered the object moving for rules/effects.
3.0.7b If origin and destination are the same, no move occurs.
3.0.9 If an object enters a zone that is not in the arena and not the stack, it resets — previous existence ceases and it becomes a new object.
3.0.12 To clear an object, move it to its owner's graveyard. Tokens, macros, and non-card layers simply cease to exist.

### 3.3 Arsenal
3.3.2 Can only contain up to one deck-card owned by the player.
3.3.2a If an effect would put a card into an arsenal zone that is not empty, the effect fails.
3.3.4 Cards in arsenal may be played.

### 3.6 Combat Chain
3.6.1 The combat chain zone is public, shared by all players, has no owner.
3.6.2 Can only contain cards and attack-proxies.
3.6.4 The combat chain is "open" during combat, otherwise "closed."

### 3.7 Deck
3.7.4 A player cannot look at their own deck unless specified by a rule or effect.
3.7.5 Objects in the deck zone are face down in an ordered uniform pile.

### 3.11 Hero
3.11.2 Can contain one card with the type hero, and zero or more cards in the hero's soul.
3.11.5 A hero's soul refers to the collection of sub-objects under the hero card.

### 3.14 Pitch
3.14.1 A pitch zone is a public zone outside the arena, owned by a player.
3.14.2 Can only contain the owner's deck-cards.

### 3.15 Stack
3.15.3 The stack contains an ordered collection of layers.
3.15.4 When a layer is added to the stack, it becomes layer N+1 where N is the number of existing layers.
3.15.5 The top layer of the stack is layer N, with the highest value of N.

---

## 4 Game Structure

### 4.0 General
4.0.1 A game is preceded by the start-of-game procedure and ends when a player wins or the game is a draw.
4.0.3 A turn consists of 3 phases: Start Phase, Action Phase, and End Phase.
4.0.3b Only one player can have a turn at any point. That player is the "turn-player."

### 4.1 Starting a Game
4.1.2 Each player places their hero card face up in their hero zone.
4.1.3 A player is selected and chooses the first-turn-player (random in first game; loser of last game chooses in subsequent games).
4.1.4 Each player selects arena-cards from their card-pool for equipment zones.
4.1.5 Each player selects deck-cards for their deck.
4.1.7 Each player shuffles and presents their starting deck to an opponent.
4.1.8 Each player equips weapons and equipment. The "start of the game" event occurs.
4.1.9 Each player draws cards up to their hero's intellect. The first turn-player begins their Start Phase.

### 4.2 Start Phase
4.2.1 Players do not get priority during the Start Phase.
4.2.2 The turn starts. "Start of turn" effects end. "Start of turn" triggers occur.
4.2.3 Start Phase ends; game proceeds to Action Phase.

### 4.3 Action Phase
4.3.1 "Beginning of the action phase" event occurs and effects trigger.
4.3.2 The turn-player has 1 action point.
4.3.2a Effects that trigger when a player gains an action point do NOT trigger from this.
4.3.3 Turn-player gains priority.
4.3.4 When the stack is empty, combat chain is closed, and both players pass priority in succession, the action phase ends.

### 4.4 End Phase
4.4.1 Players do not get priority during the End Phase.
4.4.2 "Beginning of the end phase" event occurs and effects trigger.
4.4.3 End-of-turn procedure (in order):
4.4.3a All allies' life totals reset to base life (modified by counters).
4.4.3b Turn-player may put a card from hand face-down into an empty arsenal zone.
4.4.3c Each player puts all cards in their pitch zone on the bottom of their deck in any order (hidden).
4.4.3d Turn-player untaps all permanents they control.
4.4.3e All players lose all action points and resource points.
4.4.3f Turn-player draws cards until hand size = intellect. (Other players also draw on the first turn of the game.)
4.4.4 "Until end of turn" and "this turn" effects end. Next player in clockwise order becomes turn-player.

### 4.5 Ending a Game
4.5.2 A player wins if: all opponents have lost, or an effect states they win.
4.5.3 A player loses if: hero's life total reaches 0, an effect states they lose, or they concede.
4.5.4 A draw occurs if: all remaining players' heroes' life totals reach 0 simultaneously, an effect states draw, all agree to intentional draw, stalemate, or deadlock.

---

## 5 Layers, Cards, & Abilities

### 5.1 Playing Cards
5.1.1 Playing a card moves it to the stack as a card-layer. Steps: Announce, Declare Costs, Declare Modes and Targets, Check Legal Play, Calculate Asset-Costs, Pay Asset-Costs, Calculate Effect-Costs, Pay Effect-Costs, Play.
5.1.1a A player can only play cards from their hand or arsenal zones unless otherwise specified.
5.1.2 Announce: The card moves to the stack zone under the player's control.
5.1.3 Declare Method and Costs: Declare method and parameters for costs, including X values, additional costs, alternative costs.
5.1.4 Declare Modes and Targets: Declare modes and legal targets.
5.1.5 Check Legal Play: Evaluate legality before any costs are paid.
5.1.6 Calculate Asset-Costs: Starting cost → apply setting effects → apply increases → apply decreases (floor 0).
5.1.6b Action cards cost 1 action point unless played as an instant.
5.1.7 Pay Asset-Costs.
5.1.8 Calculate Effect-Costs.
5.1.9 Pay Effect-Costs.
5.1.10 Play: Card is now considered played; player regains priority.

### 5.2 Activated Abilities
5.2.1 Format: "[LIMIT?] [TYPE] -- [COST]: [ABILITIES] [CONDITION?]"
5.2.2 To activate: announce → declare costs → declare modes/targets → check legal → calculate costs → pay costs → activate.
5.2.2a The activated-layer is created with the same supertypes and types as the source.

### 5.3 Resolution Abilities & Resolving Layers
5.3.1 If the stack is not empty and all players pass in succession, the top layer resolves (except the Layer Step of combat).
Resolution order: Check resolution → Static effects → Layer effects → Go again → Leave stack → Clear.
5.3.2 Check resolution: A layer fails to resolve if:
5.3.2a It is a triggered-layer with a state-trigger condition no longer met.
5.3.2b It is a defense reaction card that cannot become a defending card.
5.3.5 Go again: If the layer has go again, the controlling player gains 1 action point.
5.3.7 Clear: If the layer is still on the stack, it is cleared, then the turn-player gains priority.

### 5.4 Static Abilities
5.4.1 Static abilities generate effects without resolving a layer.
5.4.2 Functional static abilities generate static continuous effects.
5.4.3 Meta-static: generates effects applying to rules outside the game.
5.4.4 Play-static: generates effects applying to the playing of its source card.
5.4.4a Additional-cost ability: adds asset-costs/effect-costs to play the card.
5.4.4b Alternative-cost ability: replaces asset-costs/effect-costs.
5.4.5 Property-static: defines the property or value of a property (functional anywhere in and outside the game).
5.4.6 Triggered-static: generates a single triggered effect.
5.4.7 While-static: has a condition making it functional under specified circumstances.
5.4.7b Hidden triggered ability: while-static + triggered-static where while-condition specifies private/private zone.

---

## 6 Effects

### 6.1 Discrete Effects
6.1.1 Discrete effects change the game state by producing an event; have no duration.
6.1.2 Discrete effects are atomic — generated and produce events one at a time.
6.1.3 Conditional discrete effects have their condition evaluated only once, at the time the effect would be generated.

### 6.2 Continuous Effects
6.2.1 Continuous effects modify the state/properties of objects and/or game rules for their duration.
6.2.2 Layer-continuous effects are generated by layer resolution; typically have a specified duration.
6.2.2a Starts as soon as generated; ends after specified duration or when no longer applicable. If no duration specified, ends at end of turn.
6.2.2b Variable values (X) are determined when the continuous effect is generated.
6.2.2c If a layer-continuous effect starts to apply to an object, it continues to apply even if that object's properties change.
6.2.3 Static-continuous effects are generated by static abilities; never have a specified duration.
6.2.3a Starts when the static ability becomes functional; ends when it becomes non-functional.
6.2.4 If a continuous effect would only apply to a future object, it applies to the next object that meets the specification.

### 6.3 Continuous Effect Interactions
6.3.1 Continuous effects modifying rules of the game are applied before effects modifying objects. Effects modifying objects use the staging system.
6.3.2 Stage order (1–8):
1. Effects modifying copyable properties
2. Effects modifying/dependent on controller
3. Effects modifying/dependent on name, color strip, or text box
4. Effects modifying/dependent on types or subtypes
5. Effects modifying/dependent on supertypes
6. Effects modifying/dependent on abilities
7. Effects modifying/dependent on base values of numeric properties
8. Effects and counters modifying/dependent on values of numeric properties
6.3.3 Substage order (for stages 7–8):
1. Add/remove a numerical property
2. Set the value of a numerical property (independent)
3. Multiply the value (independent)
4. Divide the value (independent)
5. Add to the value (independent)
6. Subtract from the value (independent)
7. Dependent effects
6.3.4 Timestamp order: chronological order of effect generation. Turn-player decides for same-timestamp effects.
6.3.5 Continuous effects applied dynamically — all recalculated whenever effects change.
6.3.6 Continuous effects that remove a property do not remove properties added by another effect.
6.3.7 Continuous effects only prevent properties from being added/removed if they explicitly specify.

### 6.4 Replacement Effects
6.4.1 A replacement effect replaces an event with a modified event.
6.4.2 Active if an event is about to occur that can be replaced.
6.4.3 Must exist before the event to replace it.
6.4.5 A replacement effect can only replace an event once per original event.
6.4.7 Self-replacement effect: replaces a preceding effect generated by the same or a connected leading ability.
6.4.8 Identity-replacement effect: typically "As [CONDITION] [MODIFICATION]."
6.4.9 Standard-replacement effect: "(If / The next) [CONDITION], instead [MODIFICATION]."
6.4.10 Prevention effect: replaces a damage event. Shielded object loses prevention amount as damage is prevented.
6.4.10i Fixed-prevention: one-off effect; remaining prevention not used for subsequent events.
6.4.10j Shielding-prevention: acts as a shield; remaining prevention carries over.
6.4.11 Outcome-replacement effect: replaces the outcome of an event.

### 6.5 Replacement Effect Interactions
Application order per event: Self/Identity → Standard → Prevention → Event → Outcome.

### 6.6 Triggered Effects
6.6.1 Format: "[LIMIT?] (When / Whenever / At / The Nth time / The next time) [EVENT and/or STATE] [ABILITIES]"
6.6.2 Inline-triggered: can only trigger when it is generated.
6.6.3 Delayed-triggered: layer-continuous triggered effect.
6.6.4 Static-triggered: static-continuous triggered effect.
6.6.5 If a game event/state meets a triggered effect's trigger condition, the effect is triggered.
6.6.5a Effect must exist before the event/state occurs to be triggered.
6.6.5b Event-based triggered effect only triggers if event actually occurs.
6.6.5c State-based triggered effect triggers when state changes to meet the condition.
6.6.5e If trigger exceeds trigger limit, triggered-layer is not created.
6.6.6 Triggered-layers are added to the stack before the next player receives priority.
6.6.6a When adding triggered-layer to stack, player must declare parameters of all abilities.
6.6.6b If two or more triggered-layers are created, the turn-player selects a player, then each player in clockwise order adds their pending layers.

---

## 7 Combat

### 7.0 General
7.0.1 Combat is a game state where the combat chain is open and attacks undergo resolution. Resolution of a chain link consists of steps: Layer, Attack, Defend, Reaction, Damage, Resolution.
7.0.1a During combat, while the combat chain is open, a player cannot play action cards/abilities except during the Resolution Step.
7.0.2a If the combat chain is closed and an attack is added to the stack, the combat chain opens and the Layer Step begins.
7.0.3 A chain link comprises an active-attack, an attack-source (if any), and any number of defending cards.
7.0.3b The active chain link is the most recent chain link being resolved.
7.0.3c Properties of a chain link = properties of its active-attack. If active-attack ceases to exist, last known information is used.
7.0.5 A defending card is a card designated as defending on a chain link for an attack-target.
7.0.5a When added as a defending card, the "defend" event occurs and triggered effects trigger.
7.0.5b If an effect would add a card as a defending card but it's already defending or cannot become a defending card, the effect fails.
7.0.5d A card can only defend on one chain link for one attack-target at a time.

### 7.1 Layer Step
7.1.1 An attack is unresolved on the stack.
7.1.2 Turn-player gains priority.
7.1.3 When top layer is the attack and all players pass, the Layer Step ends and Attack Step begins.

### 7.2 Attack Step
7.2.1 An attack resolves and becomes attacking before any defending cards are declared.
7.2.2 At least one attack target must still be legal.
7.2.3 Resolution abilities generate effects, then the attack moves onto the combat chain as a chain link.
7.2.4 The "attack" event occurs. Triggered effects trigger.
7.2.4a Controller of the active-attack and their hero become the "attacking hero."
7.2.4b Controller of the attack-target and their hero become the "defending hero."
7.2.5 Turn-player gains priority.
7.2.6 When stack is empty and all players pass, Attack Step ends and Defend Step begins.

### 7.3 Defend Step
7.3.1 Defending cards may be declared.
7.3.2 Defending cards are declared for the attack-target(s).
7.3.2a If attack-target is a hero, their controller may declare any number of non-defense-reaction cards from hand and/or public equipment permanents.
7.3.2b A card cannot be declared if it has no defense property, is already defending, or would make the current set of declared cards illegal.
7.3.3 Turn-player gains priority.

### 7.4 Reaction Step
7.4.1 Players may use reactions related to combat.
7.4.2 Turn-player gains priority.
7.4.2a Controller of the attack may play/activate attack reactions.
7.4.2b Player controlling an attacked hero may play/activate defense reactions.
7.4.2c A defense reaction card cannot be played if a rule/effect prevents defending with it.
7.4.2d When a defense reaction card resolves, it becomes a defending card on the active chain link.

### 7.5 Damage Step
7.5.1 Physical damage of the active chain link is calculated and applied.
7.5.2 Damage = attack power − sum of defending cards' defense values, if positive.
7.5.2a This is a hit-event; source of damage is the attack.
7.5.3 Turn-player gains priority.
7.5.5 Hit-event: a named-event identical to a deal {p} damage event. An attack is considered to have hit if it deals damage with a hit-event.
7.5.5b If the hit-event is modified such that no damage is dealt by the active-attack to the attack-target, it is no longer a hit-event.

### 7.6 Resolution Step
7.6.1 Active chain link resolves; attacker may gain action point from go again; attacker may continue combat chain.
7.6.2 Active chain link becomes a resolved chain link. If attack has go again, controller gains 1 action point.
7.6.3 Turn-player gains priority. If an attack is added to the stack, Resolution Step ends and Layer Step begins.
7.6.3a Turn-player may play or activate another attack during the Resolution Step.
7.6.4 When stack is empty and all players pass, Resolution Step ends and Close Step begins.

### 7.7 Close Step
7.7.1 Combat chain closes and combat ends. Players do not get priority.
7.7.2 The combat chain closes when:
7.7.2a All players pass in succession during the Resolution Step.
7.7.2b No valid attack-targets at beginning of the Attack Step.
7.7.2c Active-attack does not exist or cannot move to combat chain, or ceases to exist before damage.
7.7.2d An effect closes the combat chain.
7.7.3 "Combat chain closes" event occurs. All attacks and reactions on the stack go to graveyard.
7.7.4 Layers on the stack resolve.
7.7.5 Permanents remaining on the combat chain return to their respective zones.
7.7.6 Remaining objects on the combat chain are cleared.
7.7.7 Combat chain closes. "This combat chain" effects end. Action Phase continues.

---

## 8 Keywords

### 8.1 Type Keywords
- **Action** (8.1.1): deck-card; can only be played when stack is empty (or as instant); costs 1 action point.
- **Attack Reaction** (8.1.2): deck-card; only playable by attacker during Reaction Step; cleared on resolution.
- **Defense Reaction** (8.1.3): deck-card; only playable by defender during Reaction Step; becomes defending card on resolution.
- **Equipment** (8.1.4): arena-card; may be used as defending card during Defend Step.
- **Hero** (8.1.5): hero-card; starts game in hero zone.
- **Instant** (8.1.6): deck-card; can be played any time a player has priority.
- **Resource** (8.1.7): deck-card; cannot be played.
- **Token** (8.1.8): token-card; only exists in the arena or as sub-cards.
- **Weapon** (8.1.9): arena-card; equipped during start-of-game procedure.
- **Mentor** (8.1.10): deck-card; only for players with a "young" hero.
- **Demi-Hero** (8.1.11): arena-card; becomes the player's hero if they don't control one.
- **Block** (8.1.12): deck-card; cannot be played.
- **Companion** (8.1.14): arena-card.

### 8.2 Subtype Keywords (Functional)
- **(1H)**: must be equipped to a weapon zone.
- **(2H)**: must be equipped to two weapon zones.
- **Attack**: considered an attack only when on the stack or attacking on the combat chain.
- **Aura**: enters the arena as a permanent when resolved.
- **Item**: enters the arena as a permanent when resolved.
- **Arrow**: can only be played from arsenal while controlling a bow.
- **Ally**: life reset during End Phase; attacking ally = controller is not "attacking hero"; attacked ally = controller is "defending hero" but cannot declare defending cards or play defense reactions.
- **Landmark**: when entering arena, all other landmark permanents are cleared.
- **Off-Hand**: equipped to a weapon zone; player cannot equip more than one.
- **Affliction**: when entering arena, controller declares an opponent and it enters under that opponent's control.
- **Ash**: enters arena as permanent.
- **Invocation**: enters arena with back-face active.
- **Construct**: enters arena with back-face active.
- **Quiver**: may be equipped to weapon zone occupied by 2H bow.
- **Figment**: enters arena as permanent.

### 8.3 Ability Keywords (Key ones for engine)
- **Attack**: static ability; a layer with this is an attack-proxy.
- **Battleworn**: "When the combat chain closes, if this defended, put a -1{d} counter on it."
- **Blade Break**: "When the combat chain closes, if this defended, destroy it."
- **Dominate**: "This can't be defended by more than one card from hand."
- **Go again**: special resolution ability; controlling player gains 1 action point.
  - 8.3.5a On non-attack layer: player gains 1 action point after all other resolution abilities resolve.
  - 8.3.5b On attack on the active chain link: player gains 1 action point at beginning of Resolution Step.
  - 8.3.5c An object cannot have more than one "go again" ability.
- **Legendary**: "You may only have 1 of this in your constructed deck."
- **Specialization**: "You may only have this in your deck if your hero is [HERO]."
- **Arcane Barrier N**: "If you would be dealt arcane damage, you may pay N{r} to prevent N of that damage."
- **Boost**: optional additional cost; banish top card of deck; if it's a Mechanologist card, this gets go again.
- **Temper**: "When the combat chain closes, if this defended, put a -1{d} counter on it, then destroy it if it has zero {d}."
- **Blood Debt**: "While in your banished zone, at the beginning of your end phase, lose 1{h}."
- **Phantasm**: "Whenever this is defended by a non-Illusionist attack action card with 6 or more {p}, destroy this."
- **Spectra**: "This can be attacked" + "When this becomes the target of an attack, destroy this."
- **Spellvoid N**: "If you would be dealt arcane damage, you may destroy this to prevent N of that damage."
- **Overpower**: "This can't be defended by more than one action card."
- **Piercing N**: "If this is defended by an equipment, it gets +N{p}."
- **Stealth**: has no rules meaning.
- **Ward N**: "If you would be dealt damage, destroy this to prevent N of that damage."
- **Ambush**: "While in your arsenal, you may defend with it."
- **Dominate**: "Can't be defended by more than one card from hand."
- **Protect**: "You may defend any hero attacked by an opponent with this."
- **Rune Gate**: play from banished zone without paying cost if you control Runechants ≥ cost.

### 8.4 Label Keywords
- **Combo**: "If [NAMES] was the last attack this combat chain, [EFFECTS]."
- **Crush**: "When this deals 4 or more damage, [EFFECTS]."
- **Reprise**: "If the defending hero has defended with a card from their hand this chain link, [EFFECTS]."
- **Channel [SUPERTYPE]**: at end phase, put flow counter on this then destroy unless you put a [SUPERTYPE] card from pitch zone on bottom of deck for each flow counter.
- **Rupture**: "If this is played at chain link 4 or higher, [EFFECTS]."
- **Surge**: "If this deals N damage, [EFFECTS]."

### 8.5 Effect Keywords (Key ones)
- **Banish**: move object to owner's banished zone.
- **Create (token)**: produce token and put in arena.
- **Deal (damage)**: object loses {h}. Three types: generic, physical ({p}), arcane.
- **Destroy**: put object into owner's graveyard.
- **Discard**: move card from hand to graveyard.
- **Draw**: move top card of deck to player's hand.
- **Gain (asset)**: increase player's or object's assets.
- **Gets (numerical property)**: modify numeric properties.
- **Intimidate**: banish a random card from hand face-down; returns at beginning of end phase.
- **Lose (asset)**: decrease player's or object's assets.
- **Put/Return**: move object to specified zone.
- **Search**: look at all cards in specified zone(s) and choose.
- **Shuffle**: put cards in zone in random order.
- **Pitch**: put card into pitch zone and gain assets equal to pitch value.
- **Clash**: reveal top card of deck; player revealing card with greatest {p} wins.
- **Negate**: clear a layer from the stack without it resolving.
- **Equip**: put object into equipment/weapon zone as a permanent.
- **Tap**: change state from untapped to tapped.
- **Untap**: change state from tapped to untapped.

### 8.6 Token Keywords (Notable tokens)
- **Runechant**: "When you play an attack action card or activate a weapon attack, destroy this and deal 1 arcane damage to target opposing hero."
- **Spectral Shield**: Ward 1 illusionist aura.
- **Frostbite**: "Cards and abilities cost you an additional {r} to play or activate." Destroyed at beginning of end phase or when you play a card/activate an ability.
- **Gold**: "Action -- {r}{r}, destroy this: Draw a card. Go again."
- **Quicken**: "When you play an attack action card or activate a weapon attack, destroy this then the attack gains go again."
- **Might**: "At the start of your turn, destroy this, then your next attack this turn gets +1{p}."
- **Vigor**: "At the start of your turn, destroy this, then gain {r}."
- **Agility**: "At the start of your turn, destroy this, then your next attack this turn gets go again."

---

## 9 Additional Rules

### 9.1 Double-Faced Cards
9.1.3 Flip-card: front-face and back-face; one face active at a time.
9.1.4 Twin-card: both faces may be active outside arena; only one face active in arena or on stack.
9.1.5 Transcend-card: back-face active after transcend, remains active even if object becomes new.

### 9.2 Split-Cards
9.2.1 A split-card has two names, typeboxes, and textboxes.
9.2.2 Considered a single card with all properties of both sides, except when on the stack.
9.2.3 When put on the stack, player chooses one side. For the remainder of its existence, it only has that side's properties.

### 9.3 Marked
9.3.1 Marked is a special condition a hero may have.
9.3.2 A hero is marked if an effect causes them to be marked.
9.3.2b Marked continues until the hero is hit by a source controlled by an opponent, or the hero ceases to exist.
9.3.3 When a marked hero is hit by a source controlled by an opponent, the marked condition is removed as part of the hit event.

### 9.4 Living Legend
9.4.1 Living legend is a status that a hero may have if listed on the official FaB living legend resource page.
