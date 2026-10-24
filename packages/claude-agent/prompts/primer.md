# Flesh and Blood: rules primer

Two heroes duel. Your hero card sets your starting life total and your intellect. You lose when your hero's life total reaches 0 (both at once is a draw). Damage dealt to a hero lowers its life total; life can rise above the starting value. An empty deck does not lose the game: a draw from it simply fails. Most deck cards carry a colour strip giving their pitch value: red 1, yellow 2, blue 3.

## The turn

- Start phase: start-of-turn triggers resolve. Nobody acts.
- Action phase: you receive exactly 1 action point and priority. It ends when the combat chain is closed, nothing is pending and both players pass in succession.
- End phase, in order: you may put one card from hand face down into your empty arsenal; each player puts the cards they pitched this turn on the bottom of their deck in any order; all action and resource points are lost; you draw up to your intellect (holding 1 card with intellect 4, you draw 3; holding 4 or more, none). Both players start with a full hand, and at the end of the first turn the second player also refills.

A card left in hand shrinks your draw: not playing, pitching, blocking with or arsenaling it wastes a draw.

## Action points, actions and go again

Playing an action card (attack or non-attack) or activating an action ability (a weapon attack, an equipment ability) costs 1 action point on top of its resource cost. Only the turn player has action points, and you start with one, so you get one action unless it has **go again**: when a card or ability with go again resolves (for an attack, when its chain link resolves), you gain 1 action point. Chaining go again plays several cards; an action without go again is your last action of the turn. Pitching, instants, reactions and defending need no action points. Action cards and abilities can be played only when the stack is empty, and during combat only between attacks.

## Pitching and resources

Cards have a resource cost. To pay it you pitch cards from hand: each goes face up to your pitch zone and yields resource points equal to its pitch value. Excess points stay with you until the end of the turn (pitch a blue for a 2-cost and 1 floats). You may pitch only to pay a cost you are paying now. Pitched cards go to the bottom of your deck and come back many turns later; cards played or blocked with go to the graveyard. You also pitch on the opponent's turn for defense reactions and instants.

## The combat chain

Attacks happen on the combat chain. It opens with your first attack and closes when you stop attacking. Each attack is one chain link with these steps:

1. Attack: you play an attack action card from hand or arsenal, or activate a weapon. The attack has a power value.
2. Defend: the defender may declare any number of cards from hand that have a defense value (0 counts; attack reactions can block; defense reactions cannot be declared here) and any of their equipment. Declaring is free: no cost, no action point.
3. Reaction: the attacker may play attack reactions (only on their own attack); the defender may play defense reactions (a resolved one becomes a defending card). Both cost resources but no action point. Priority alternates until both pass.
4. Damage: if power exceeds the total defense, the hero takes the difference and the attack **hits**. Equal or lower: no damage, no hit, and "when this hits" effects do nothing.
5. Resolution: go again grants its action point; the attacker may start the next attack (a new link on the same chain) or pass, which closes the chain. Non-attack actions cannot be played while the chain is open.

When the chain closes, cards on it go to the graveyard; equipment stays in play. Instants can be played any time you have priority, including the opponent's turn, with no action point.

## Arsenal

At the end of your turn you may set one card from hand face down into your arsenal if it is empty. It is played later as if from hand but cannot be pitched or blocked with. It does not count against your draw, so arsenaling carries a fifth card into your next turn.

## Equipment and weapons

Equipment (head, chest, arms, legs) starts in play. Each piece may block with its defense value and stays in play afterwards unless a keyword says otherwise: **Battleworn** puts a -1 defense counter on it after it blocks; **Temper** does the same and destroys it at 0 defense; **Blade Break** destroys it after it blocks. Defense never drops below 0; a 0-defense piece stays but blocks nothing. Weapons sit in the weapon zones; a weapon's attack is an activated action ability, typically "Once per Turn Action - [cost]: Attack", costing an action point and resources but no card, and making a chain link with the weapon's power.

## Keywords you will meet

- **Dominate**: at most one card from hand may defend the attack; once one does, defense reactions cannot be played from hand either.
- **Overpower**: at most one action card may defend the attack.
- **Combo - If [card] was the last attack this combat chain**: attack order matters.
- **Crush - When this deals 4 or more damage**: needs 4 damage dealt, not just a hit.
- **Intimidate**: the target hero banishes a random card from hand face down until the beginning of the end phase.
- **Reprise**: applies if the defending hero blocked with a card from hand this link.
- **Ward N** (on a permanent): when you would be dealt damage, you may destroy it to prevent N.

Class cards (Ninja, Guardian) are legal only for heroes of that class; Generic cards for anyone. Broadly, Ninjas chain cheap go-again attacks and combos for many hits a turn; Guardians make few, heavy attacks with dominate and crush, and defend with high-defense gear.

## How you act

At each decision you see the game from your Seat and a numbered list of every legal Intent. Choose exactly one by its number. Nothing outside the list is possible: do not invent plays, requests or targets. If the only Intents are passes, passing is the correct play.
