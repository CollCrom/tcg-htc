"""Equipment and weapon ability implementations.

Registers ability handlers and triggered effects for equipment and weapons
used in both the Cindra Blue and Arakni Marionette decklists.

Card texts verified against data/cards.tsv functional_text field.

Equipment abilities implemented:
- Mask of Momentum (Head) — once per turn, draw on 3rd+ consecutive chain link hit
- Flick Knives (Arms) — once per turn attack reaction: dagger deals 1 damage
- Blood Splattered Vest (Chest) — on dagger hit: gain resource, add stain counter
- Fyendal's Spring Tunic (Chest) — energy counter at start of turn, spend 3 for resource
- Tide Flippers (Legs) — attack reaction: destroy to grant go again to <=2 power attack
- Blacktek Whisperers (Legs) — attack reaction: destroy to grant on-hit go again
- Dragonscaler Flight Path (Legs) — instant: cost 3 minus Draconic links, destroy to grant go again + weapon untap
- Mask of Deceit (Head) — on defend: become Agent of Chaos (random or choice if marked)

Weapon abilities implemented:
- Kunai of Retribution — destroy when combat chain closes (registered on activation)
- Hunter's Klaive — Mark keyword on hit (handled by game.py _handle_hit_mark_keyword)
- Claw of Vynserakai — no additional ability needed (Spellvoid 1 is keyword-driven)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from htc.cards.abilities._helpers import (
    draw_card,
    get_player_name,
    grant_keyword,
    grant_power_bonus,
    is_dagger_attack,
    make_instance_id_filter,
    move_card,
    require_active_attack,
    require_chain_link,
)
from htc.engine.abilities import AbilityContext, AbilityRegistry
from htc.engine.continuous import EffectDuration, make_keyword_grant
from htc.engine.events import EventType, GameEvent, TriggeredEffect
from htc.enums import ActionType, CardType, Keyword, SubType, SuperType, Zone

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from htc.cards.instance import CardInstance
    from htc.engine.effects import EffectEngine
    from htc.engine.events import EventBus
    from htc.state.game_state import GameState

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pname(state: "GameState", player_index: int) -> str:
    """Short hero name for logging (standalone helper). Delegates to get_player_name."""
    return get_player_name(state, player_index)


def _pname_from_player_state(player_state, player_index: int) -> str:
    """Short hero name from a PlayerState (no full GameState needed)."""
    if player_state.hero:
        return player_state.hero.definition.name.split(",")[0]
    return f"Player {player_index}"




def _destroy_equipment(state: GameState, card: CardInstance) -> None:
    """Move equipment to its owner's graveyard and clear the slot."""
    player = state.players[card.owner_index]
    # Remove from equipment slots
    for slot, eq in list(player.equipment.items()):
        if eq is not None and eq.instance_id == card.instance_id:
            player.equipment[slot] = None
            break
    card.zone = Zone.GRAVEYARD
    player.graveyard.append(card)
    log.info(f"  Equipment destroyed: {card.name}")


# ---------------------------------------------------------------------------
# Mask of Momentum (Head, Ninja)
# ---------------------------------------------------------------------------
# "Once per Turn Effect — When an attack action card you control is the
#  third or higher chain link in a row to hit, draw a card."
#
# Implemented as a TriggeredEffect on HIT. Checks:
# 1. Source is an attack action card controlled by this player
# 2. This is chain link 3+ in the combat chain
# 3. All prior chain links in this combat chain were hits
# 4. Once per turn flag
# ---------------------------------------------------------------------------


@dataclass
class MaskOfMomentumTrigger(TriggeredEffect):
    """Mask of Momentum — draw on 3rd+ consecutive chain link hit."""

    controller_index: int = 0
    one_shot: bool = False  # persists all game
    _used_this_turn: bool = False
    _state_getter: object = None
    _effect_engine: object = None
    _event_bus: EventBus | None = None

    def condition(self, event: GameEvent) -> bool:
        # Reset once-per-turn flag at start of turn
        if event.event_type == EventType.START_OF_TURN:
            if event.target_player == self.controller_index:
                self._used_this_turn = False
            return False

        if event.event_type != EventType.HIT:
            return False

        if self._used_this_turn:
            return False

        if event.source is None:
            return False

        # Must be our attack
        if event.source.owner_index != self.controller_index:
            return False

        # Must be an attack action card (not weapon proxy)
        if CardType.ACTION not in event.source.definition.types:
            return False
        state = self._get_state()
        source_subtypes = (
            self._effect_engine.get_modified_subtypes(state, event.source)
            if self._effect_engine is not None and state is not None
            else event.source.definition.subtypes
        )
        if SubType.ATTACK not in source_subtypes:
            return False

        if state is None:
            return False

        # Check: chain link 3+ and all prior links were hits
        chain = state.combat_chain
        if chain.num_chain_links < 3:
            return False

        # All prior chain links must have been hits
        for link in chain.chain_links[:-1]:
            if not link.hit:
                return False

        return True

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        """Draw a card for the controller."""
        state = self._get_state()
        if state is None:
            return None

        self._used_this_turn = True

        player = state.players[self.controller_index]
        if player.deck:
            log.info(
                f"  Mask of Momentum: {_pname(state, self.controller_index)} draws a card "
                f"(3rd+ consecutive hit)"
            )
            return GameEvent(
                event_type=EventType.DRAW_CARD,
                target_player=self.controller_index,
            )
        return None

    def _get_state(self) -> GameState | None:
        if self._state_getter and callable(self._state_getter):
            return self._state_getter()
        return None


# ---------------------------------------------------------------------------
# Flick Knives (Arms, Assassin/Ninja)
# ---------------------------------------------------------------------------
# "Once per Turn Attack Reaction — 0: Target dagger you control that isn't
#  on the active chain link deals 1 damage to target hero. If damage is
#  dealt this way, the dagger has hit. Destroy the dagger."
#
# Implemented as attack_reaction_effect. The engine handles the "once per
# turn" and cost=0 aspects. We deal 1 damage from an off-chain dagger and
# destroy it. Simplified: we find any non-active-link weapon dagger and
# use it as the source.
# ---------------------------------------------------------------------------


@require_chain_link
def _flick_knives(ctx: AbilityContext) -> None:
    """Flick Knives attack reaction: off-chain dagger deals 1 damage."""
    link = ctx.chain_link

    player = ctx.state.players[ctx.controller_index]
    target_index = 1 - ctx.controller_index

    # Mark as activated this turn (once-per-turn enforcement)
    from htc.enums import EquipmentSlot
    flick = player.equipment.get(EquipmentSlot.ARMS)
    if flick is not None and flick.name == "Flick Knives":
        flick.activated_this_turn = True

    # Find a dagger weapon not on the active chain link
    active_attack_id = link.active_attack.instance_id if link.active_attack else None
    source_id = link.attack_source.instance_id if link.attack_source else None

    dagger = None
    for weapon in player.weapons:
        if SubType.DAGGER in ctx.effect_engine.get_modified_subtypes(ctx.state, weapon):
            # Not the weapon currently attacking
            if weapon.instance_id != source_id and weapon.instance_id != active_attack_id:
                dagger = weapon
                break

    if dagger is None:
        log.info("  Flick Knives: No off-chain dagger available")
        return

    # Deal 1 damage via DEAL_DAMAGE event (so prevention/replacement can apply)
    damage_event = ctx.events.emit(GameEvent(
        event_type=EventType.DEAL_DAMAGE,
        source=dagger,
        target_player=target_index,
        amount=1,
        data={"chain_link": link, "is_combat": False},
    ))

    actual_damage = damage_event.amount if not damage_event.cancelled else 0
    if actual_damage > 0:
        # Card text: "the dagger has hit" — mark the chain link as a hit.
        # This preserves Mask of Momentum's consecutive hit streak even when
        # the main attack on this chain link was blocked.
        link.hit = True

        # Emit HIT event — card text says "the dagger has hit"
        ctx.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=dagger,
            target_player=target_index,
            amount=actual_damage,
            data={"chain_link": link},
        ))
        log.info(f"  Flick Knives: Dagger deals {actual_damage} damage to {ctx.player_name(target_index)}")

        # Dispatch the dagger's on_hit ability (if any). Card text says
        # "the dagger has hit", so on-hit effects like Kiss of Death's
        # "they lose 1{h}" should trigger from the flicked dagger.
        if ctx.ability_registry is not None:
            on_hit_handler = ctx.ability_registry.lookup("on_hit", dagger.name)
            if on_hit_handler is not None:
                from htc.engine.abilities import AbilityContext as _AC
                on_hit_ctx = _AC(
                    state=ctx.state,
                    source_card=dagger,
                    controller_index=ctx.controller_index,
                    chain_link=link,
                    effect_engine=ctx.effect_engine,
                    events=ctx.events,
                    ask=ctx.ask,
                    keyword_engine=ctx.keyword_engine,
                    combat_mgr=ctx.combat_mgr,
                    ability_registry=ctx.ability_registry,
                )
                on_hit_handler(on_hit_ctx)
                log.info(f"  Flick Knives: Triggered {dagger.name} on_hit ability")
    else:
        log.info(f"  Flick Knives: Damage was prevented")

    # Destroy the dagger (move to graveyard)
    if dagger in player.weapons:
        player.weapons.remove(dagger)
    dagger.zone = Zone.GRAVEYARD
    player.graveyard.append(dagger)
    log.info(f"  Flick Knives: Destroyed {dagger.name}")


# ---------------------------------------------------------------------------
# Blood Splattered Vest (Chest, Assassin/Ninja)
# ---------------------------------------------------------------------------
# "Whenever a dagger you control hits, you may gain {r} and put a stain
#  counter on this. Then if there are 3 or more stain counters on this,
#  destroy it."
#
# Implemented as a TriggeredEffect on HIT. Checks if source is a dagger
# controlled by the equipment owner. Always opts in (for random players
# gaining a resource is worth it). Tracks stain counters on the card.
# ---------------------------------------------------------------------------


@dataclass
class BloodSplatteredVestTrigger(TriggeredEffect):
    """Blood Splattered Vest — gain resource on dagger hit, stain counters."""

    controller_index: int = 0
    one_shot: bool = False
    _state_getter: object = None
    _effect_engine: object = None
    _equipment_instance_id: int = 0

    def condition(self, event: GameEvent) -> bool:
        if event.event_type != EventType.HIT:
            return False
        if event.source is None:
            return False

        # Must be our dagger hitting
        if event.source.owner_index != self.controller_index:
            return False

        # Check if it's a dagger attack
        chain_link = event.data.get("chain_link")
        state = self._get_state()
        if not is_dagger_attack(
            event.source, chain_link,
            effect_engine=self._effect_engine, state=state,
        ):
            return False

        # Equipment must still be in play
        if state is None:
            return False

        player = state.players[self.controller_index]
        from htc.enums import EquipmentSlot
        chest_eq = player.equipment.get(EquipmentSlot.CHEST)
        if chest_eq is None or chest_eq.instance_id != self._equipment_instance_id:
            return False

        return True

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        """Gain 1 resource, add stain counter, check for destruction."""
        state = self._get_state()
        if state is None:
            return None

        player = state.players[self.controller_index]
        from htc.enums import EquipmentSlot
        vest = player.equipment.get(EquipmentSlot.CHEST)
        if vest is None or vest.instance_id != self._equipment_instance_id:
            return None

        # Gain 1 resource
        state.resource_points[self.controller_index] = (
            state.resource_points.get(self.controller_index, 0) + 1
        )
        log.info(f"  Blood Splattered Vest: {_pname(state, self.controller_index)} gains 1 resource")

        # Add stain counter
        vest.counters["stain"] = vest.counters.get("stain", 0) + 1
        stain_count = vest.counters["stain"]
        log.info(f"  Blood Splattered Vest: {stain_count} stain counter(s)")

        # Destroy if 3+ stain counters
        if stain_count >= 3:
            _destroy_equipment(state, vest)

        return None

    def _get_state(self) -> GameState | None:
        if self._state_getter and callable(self._state_getter):
            return self._state_getter()
        return None


# ---------------------------------------------------------------------------
# Fyendal's Spring Tunic (Chest, Generic)
# ---------------------------------------------------------------------------
# "At the start of your turn, if this has fewer than 3 energy counters,
#  you may put an energy counter on it.
#  Instant — Remove 3 energy counters from this: Gain {r}"
#
# Implemented as a TriggeredEffect on START_OF_TURN (auto-add counter).
# The instant activation to spend 3 counters is deferred — the random
# player has no way to activate equipment instants yet. For now we just
# accumulate counters and auto-spend when we hit 3.
# ---------------------------------------------------------------------------


@dataclass
class SpringTunicTrigger(TriggeredEffect):
    """Fyendal's Spring Tunic — energy counter at start of turn."""

    controller_index: int = 0
    one_shot: bool = False
    _state_getter: object = None
    _equipment_instance_id: int = 0

    def condition(self, event: GameEvent) -> bool:
        if event.event_type != EventType.START_OF_TURN:
            return False
        if event.target_player != self.controller_index:
            return False

        state = self._get_state()
        if state is None:
            return False

        # Equipment must still be equipped
        player = state.players[self.controller_index]
        from htc.enums import EquipmentSlot
        chest_eq = player.equipment.get(EquipmentSlot.CHEST)
        if chest_eq is None or chest_eq.instance_id != self._equipment_instance_id:
            return False

        # Must have fewer than 3 energy counters
        energy = chest_eq.counters.get("energy", 0)
        return energy < 3

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        """Add an energy counter at the start of turn (if fewer than 3).

        The player chooses when to spend 3 counters for 1 resource via the
        instant activation registered as an equipment_instant_effect.
        """
        state = self._get_state()
        if state is None:
            return None

        player = state.players[self.controller_index]
        from htc.enums import EquipmentSlot
        tunic = player.equipment.get(EquipmentSlot.CHEST)
        if tunic is None or tunic.instance_id != self._equipment_instance_id:
            return None

        tunic.counters["energy"] = tunic.counters.get("energy", 0) + 1
        energy = tunic.counters["energy"]
        log.info(
            f"  {_pname(state, self.controller_index)}'s Spring Tunic: adds energy counter ({energy}/3)"
        )

        return None

    def _get_state(self) -> GameState | None:
        if self._state_getter and callable(self._state_getter):
            return self._state_getter()
        return None


# ---------------------------------------------------------------------------
# Tide Flippers (Legs, Ninja)
# ---------------------------------------------------------------------------
# "Attack Reaction — Destroy Tide Flippers: Target attack action card with
#  2 or less base power gains go again."
#
# Implemented as attack_reaction_effect. Destroys the equipment and grants
# Go Again to the current attack if it qualifies.
# ---------------------------------------------------------------------------


@require_active_attack
def _tide_flippers(ctx: AbilityContext) -> None:
    """Tide Flippers: destroy self (cost), then grant go again to low-power attack.

    Destruction is the activation COST per card text ("Destroy Tide Flippers:"),
    so it happens first, unconditionally once activation begins.  Preconditions
    (attack action card with base power <= 2) are checked by the ActionBuilder
    before this handler is offered.
    """
    link = ctx.chain_link
    attack = link.active_attack

    # --- Cost: Destroy Tide Flippers ---
    player = ctx.state.players[ctx.controller_index]
    from htc.enums import EquipmentSlot
    legs_eq = player.equipment.get(EquipmentSlot.LEGS)
    if legs_eq is not None and legs_eq.name == "Tide Flippers":
        _destroy_equipment(ctx.state, legs_eq)

    # --- Effect: Grant Go Again ---
    grant_keyword(ctx, attack, Keyword.GO_AGAIN, "Tide Flippers")


# ---------------------------------------------------------------------------
# Blacktek Whisperers (Legs, Assassin)
# ---------------------------------------------------------------------------
# "Attack Reaction — Destroy Blacktek Whisperers: Target Assassin attack
#  action card gains 'When this hits a hero, it gains go again.'"
#
# Implemented as attack_reaction_effect. Destroys equipment and registers
# a one-shot HIT trigger for Go Again on the target attack.
# ---------------------------------------------------------------------------


@require_active_attack
def _blacktek_whisperers(ctx: AbilityContext) -> None:
    """Blacktek Whisperers: destroy self (cost), grant on-hit go again to Assassin attack.

    Destruction is the activation COST per card text ("Destroy Blacktek Whisperers:"),
    so it happens first.  Preconditions (Assassin attack action card) are checked by
    the ActionBuilder before this handler is offered.
    """
    link = ctx.chain_link
    attack = link.active_attack

    # --- Cost: Destroy Blacktek Whisperers ---
    player = ctx.state.players[ctx.controller_index]
    from htc.enums import EquipmentSlot
    legs_eq = player.equipment.get(EquipmentSlot.LEGS)
    if legs_eq is not None and legs_eq.name == "Blacktek Whisperers":
        _destroy_equipment(ctx.state, legs_eq)

    # --- Effect: Register one-shot HIT trigger for Go Again ---
    atk_id = attack.instance_id
    hit_trigger = _BlacktekGoAgainOnHit(
        controller_index=ctx.controller_index,
        attack_instance_id=atk_id,
        _effect_engine=ctx.effect_engine,
        _state_getter=lambda: ctx.state,
        one_shot=True,
    )
    ctx.events.register_trigger(hit_trigger)
    log.info(f"  Blacktek Whisperers: {attack.name} gains 'when this hits, go again'")


@dataclass
class _BlacktekGoAgainOnHit(TriggeredEffect):
    """One-shot: when the target attack hits, grant Go Again."""

    controller_index: int = 0
    attack_instance_id: int = 0
    one_shot: bool = True
    _effect_engine: object = None
    _state_getter: object = None

    def condition(self, event: GameEvent) -> bool:
        if event.event_type != EventType.HIT:
            return False
        if event.source is None:
            return False
        return event.source.instance_id == self.attack_instance_id

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        if self._effect_engine is None:
            return None
        state = self._get_state()
        if state is None:
            return None

        go_again_effect = make_keyword_grant(
            frozenset({Keyword.GO_AGAIN}),
            self.controller_index,
            source_instance_id=None,
            duration=EffectDuration.END_OF_COMBAT,
            target_filter=make_instance_id_filter(self.attack_instance_id),
        )
        self._effect_engine.add_continuous_effect(state, go_again_effect)
        log.info("  Blacktek Whisperers: attack gets Go Again on hit")
        return None

    def _get_state(self):
        if self._state_getter and callable(self._state_getter):
            return self._state_getter()
        return None


# ---------------------------------------------------------------------------
# Dragonscaler Flight Path (Legs, Draconic)
# ---------------------------------------------------------------------------
# "Instant — {r}{r}{r}, destroy this: Target Draconic attack gets go again.
#  If it's a weapon or ally attack, you may attack with it an additional
#  time this turn. This ability costs {r} less to activate for each Draconic
#  chain link you control."
#
# Simplified: The instant activation is not yet supported by the engine's
# priority system for equipment. Deferred — registered as a placeholder
# attack_reaction_effect that would need the player to choose when to
# activate. For now, this is noted as not yet activatable.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Stalker's Steps (Legs, Assassin)
# ---------------------------------------------------------------------------
# "Attack Reaction - Destroy this: Target attack with stealth gets go again.
#  Arcane Barrier 1"
#
# Implemented as attack_reaction_effect. Destroys the equipment and grants
# Go Again to the current attack if it has the Stealth keyword.
# Arcane Barrier 1 is handled by the keyword system.
# ---------------------------------------------------------------------------


@require_active_attack
def _stalkers_steps(ctx: AbilityContext) -> None:
    """Stalker's Steps: destroy self (cost), grant go again to stealth attack.

    Destruction is the activation COST per card text ("Destroy this:"),
    so it happens first.  Preconditions (attack with Stealth) are checked by
    the ActionBuilder before this handler is offered.
    """
    link = ctx.chain_link
    attack = link.active_attack

    # --- Cost: Destroy Stalker's Steps ---
    player = ctx.state.players[ctx.controller_index]
    from htc.enums import EquipmentSlot
    legs_eq = player.equipment.get(EquipmentSlot.LEGS)
    if legs_eq is not None and legs_eq.name == "Stalker's Steps":
        _destroy_equipment(ctx.state, legs_eq)

    # --- Effect: Grant Go Again ---
    grant_keyword(ctx, attack, Keyword.GO_AGAIN, "Stalker's Steps")


@require_active_attack
def _dragonscaler_flight_path(ctx: AbilityContext) -> None:
    """Dragonscaler Flight Path instant: grant go again to Draconic attack.

    Cost (3 - Draconic chain links) is paid by the game engine before this
    handler is called.  This handler:
    1. Validates the active attack is Draconic
    2. Destroys the equipment
    3. Grants Go Again to the active attack
    4. If it's a weapon attack (proxy), untaps the weapon for additional attack
    """
    link = ctx.chain_link

    attack = link.active_attack
    # Must be a Draconic attack — check via effect engine for modified supertypes
    supertypes = ctx.effect_engine.get_modified_supertypes(ctx.state, attack)
    if SuperType.DRACONIC not in supertypes:
        log.info(f"  Dragonscaler Flight Path: no effect — {attack.name} is not Draconic")
        return

    # Must be our attack
    if attack.owner_index != ctx.controller_index:
        return

    # Destroy Dragonscaler Flight Path
    _destroy_equipment(ctx.state, ctx.source_card)

    # Grant Go Again to the active Draconic attack
    grant_keyword(ctx, attack, Keyword.GO_AGAIN, "Dragonscaler Flight Path")

    # If it's a weapon attack (proxy), untap the source weapon for additional attack
    if attack.is_proxy and link.attack_source is not None:
        weapon = link.attack_source
        weapon.is_tapped = False
        log.info(
            f"  Dragonscaler Flight Path: Untapped {weapon.name} "
            f"for additional attack this turn"
        )


# ---------------------------------------------------------------------------
# Mask of Deceit (Head, Assassin)
# ---------------------------------------------------------------------------
# "Arakni Specialization. When this defends, become a random Agent of Chaos.
#  If the attacking hero is marked, instead choose the Agent of Chaos.
#  Blade Break"
#
# Implemented as a TriggeredEffect on DEFEND_DECLARED. When Mask of Deceit
# is the defending card, the controller becomes an Agent of Chaos. If the
# attacking hero is marked, the player chooses which form; otherwise random.
# Blade Break is handled by the keyword engine (destroyed after defending).
# ---------------------------------------------------------------------------


@dataclass
class MaskOfDeceitTrigger(TriggeredEffect):
    """Mask of Deceit — become Agent of Chaos when this defends."""

    controller_index: int = 0
    one_shot: bool = False  # persists all game
    _equipment_instance_id: int = 0
    _state_getter: object = None
    _game: object = None  # Game reference for _become_agent_of_chaos and _ask

    def condition(self, event: GameEvent) -> bool:
        if event.event_type != EventType.DEFEND_DECLARED:
            return False
        if event.source is None:
            return False
        # Must be this specific Mask of Deceit defending
        return event.source.instance_id == self._equipment_instance_id

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        """Become an Agent of Chaos — random or player choice."""
        state = self._get_state()
        if state is None or self._game is None:
            return None

        player = state.players[self.controller_index]
        if not player.demi_heroes:
            log.info("  Mask of Deceit: No Demi-Heroes available")
            return None

        chain_link = triggering_event.data.get("chain_link")
        if chain_link is None:
            return None

        # Determine attacking player
        attacker_index = 1 - self.controller_index
        attacker = state.players[attacker_index]

        if attacker.is_marked:
            # Marked: player chooses which Agent of Chaos
            from htc.engine.actions import ActionOption, Decision
            from htc.enums import DecisionType

            options = []
            for dh in player.demi_heroes:
                options.append(ActionOption(
                    action_id=f"agent_{dh.instance_id}",
                    description=f"Become {dh.name}",
                    action_type=ActionType.ACTIVATE_ABILITY,
                    card_instance_id=dh.instance_id,
                ))

            decision = Decision(
                player_index=self.controller_index,
                decision_type=DecisionType.CHOOSE_AGENT,
                prompt="Choose which Agent of Chaos to become (attacker is marked)",
                options=options,
                min_selections=1,
                max_selections=1,
            )
            response = self._game._ask(decision)

            chosen = None
            if response.first:
                chosen_id = int(response.first.replace("agent_", ""))
                for dh in player.demi_heroes:
                    if dh.instance_id == chosen_id:
                        chosen = dh
                        break

            if chosen is None:
                # Fallback to first if response was invalid
                chosen = player.demi_heroes[0]

            log.info(f"  Mask of Deceit: {_pname(state, self.controller_index)} chooses {chosen.name}")
        else:
            # Not marked: random selection
            chosen = state.rng.choice(player.demi_heroes)
            log.info(
                f"  Mask of Deceit: {_pname(state, self.controller_index)} randomly becomes "
                f"{chosen.name}"
            )

        self._game._become_agent_of_chaos(self.controller_index, chosen)
        return None

    def _get_state(self):
        if self._state_getter and callable(self._state_getter):
            return self._state_getter()
        return None


# ---------------------------------------------------------------------------
# Kunai of Retribution (Weapon, Draconic/Ninja, Dagger)
# ---------------------------------------------------------------------------
# "Once per Turn Action — {r}, destroy this when the combat chain closes:
#  Attack. Go again"
#
# The weapon's "destroy this when the combat chain closes" is a delayed
# triggered effect that fires on COMBAT_CHAIN_CLOSES. Registered when
# the weapon is activated. The activation and go again are handled by
# the existing weapon system.
# ---------------------------------------------------------------------------


@dataclass
class KunaiDestroyOnChainClose(TriggeredEffect):
    """One-shot: destroy Kunai of Retribution when the combat chain closes."""

    controller_index: int = 0
    weapon_instance_id: int = 0
    one_shot: bool = True
    _state_getter: object = None

    def condition(self, event: GameEvent) -> bool:
        return event.event_type == EventType.COMBAT_CHAIN_CLOSES

    def create_triggered_event(self, triggering_event: GameEvent) -> GameEvent | None:
        state = self._get_state()
        if state is None:
            return None

        player = state.players[self.controller_index]
        # Find and destroy the weapon
        for weapon in list(player.weapons):
            if weapon.instance_id == self.weapon_instance_id:
                move_card(weapon, player.weapons, player.graveyard, Zone.GRAVEYARD)
                log.info(
                    f"  Kunai of Retribution: Destroyed on combat chain close "
                    f"({_pname(state, self.controller_index)})"
                )
                break
        return None

    def _get_state(self):
        if self._state_getter and callable(self._state_getter):
            return self._state_getter()
        return None


# ---------------------------------------------------------------------------
# Hunter's Klaive (Weapon, Assassin, Dagger)
# ---------------------------------------------------------------------------
# "Once per Turn Action — {r}{r}: Attack. Go again.
#  When this hits a hero, mark them."
#
# Mark is keyword-driven via _handle_hit_mark_keyword in game.py.  The weapon
# has the Mark keyword, so the HIT handler automatically marks the target.
# No separate on_hit ability registry entry is needed — that caused duplicate
# mark logging for proxy attacks.  Piercing 1 is also keyword-driven.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Registration — Triggered Effects (equipment that uses EventBus)
# ---------------------------------------------------------------------------


def register_equipment_triggers(
    event_bus: EventBus,
    effect_engine: EffectEngine,
    state_getter: object,
    player_index: int,
    player_state,
    *,
    game: object = None,
) -> None:
    """Register equipment triggered effects for a player.

    Called during game setup after equipment is loaded. Checks which
    equipment the player has equipped and registers the appropriate
    triggered effects.

    *game* is an optional Game reference needed by triggers that call
    engine methods (e.g. Mask of Deceit uses ``_become_agent_of_chaos``
    and ``_ask``).
    """
    from htc.enums import EquipmentSlot

    # Mask of Momentum
    head_eq = player_state.equipment.get(EquipmentSlot.HEAD)
    if head_eq is not None and head_eq.name == "Mask of Momentum":
        trigger = MaskOfMomentumTrigger(
            controller_index=player_index,
            _state_getter=state_getter,
            _effect_engine=effect_engine,
            _event_bus=event_bus,
        )
        event_bus.register_trigger(trigger)
        pn = _pname_from_player_state(player_state, player_index)
        log.info(f"  Registered Mask of Momentum trigger for {pn}")

    # Blood Splattered Vest
    chest_eq = player_state.equipment.get(EquipmentSlot.CHEST)
    if chest_eq is not None and chest_eq.name == "Blood Splattered Vest":
        trigger = BloodSplatteredVestTrigger(
            controller_index=player_index,
            _state_getter=state_getter,
            _effect_engine=effect_engine,
            _equipment_instance_id=chest_eq.instance_id,
        )
        event_bus.register_trigger(trigger)
        pn = _pname_from_player_state(player_state, player_index)
        log.info(f"  Registered Blood Splattered Vest trigger for {pn}")

    # Fyendal's Spring Tunic
    if chest_eq is not None and chest_eq.name == "Fyendal's Spring Tunic":
        trigger = SpringTunicTrigger(
            controller_index=player_index,
            _state_getter=state_getter,
            _equipment_instance_id=chest_eq.instance_id,
        )
        event_bus.register_trigger(trigger)
        pn = _pname_from_player_state(player_state, player_index)
        log.info(f"  Registered Fyendal's Spring Tunic trigger for {pn}")

    # Mask of Deceit
    if head_eq is not None and head_eq.name == "Mask of Deceit":
        trigger = MaskOfDeceitTrigger(
            controller_index=player_index,
            _equipment_instance_id=head_eq.instance_id,
            _state_getter=state_getter,
            _game=game,
        )
        event_bus.register_trigger(trigger)
        pn = _pname_from_player_state(player_state, player_index)
        log.info(f"  Registered Mask of Deceit trigger for {pn}")


def register_weapon_triggers(
    event_bus: EventBus,
    state_getter: object,
    player_index: int,
    weapon: CardInstance,
) -> None:
    """Register a weapon's combat-chain-close trigger if applicable.

    Called when a weapon with a delayed destroy effect is activated.
    Currently handles Kunai of Retribution.
    """
    if weapon.name == "Kunai of Retribution":
        trigger = KunaiDestroyOnChainClose(
            controller_index=player_index,
            weapon_instance_id=weapon.instance_id,
            _state_getter=state_getter,
            one_shot=True,
        )
        event_bus.register_trigger(trigger)
        state = state_getter() if callable(state_getter) else None
        pn = _pname(state, player_index) if state else f"Player {player_index}"
        log.info(
            f"  Registered Kunai of Retribution destroy trigger for {pn}"
        )


# ---------------------------------------------------------------------------
# Fyendal's Spring Tunic — Instant Activation
# ---------------------------------------------------------------------------
# "Instant - Remove 3 energy counters from this: Gain {r}"
# Registered as equipment_instant_effect.  Precondition (3+ energy counters)
# is checked in ActionBuilder._can_use_equipment_instant().
# ---------------------------------------------------------------------------


def _fyendals_spring_tunic_instant(ctx: AbilityContext) -> None:
    """Fyendal's Spring Tunic instant: remove 3 energy counters, gain 1 resource.

    Preconditions (3+ energy counters) are checked by the ActionBuilder before
    this handler is offered. No resource cost — the cost is removing counters.
    """
    from htc.enums import EquipmentSlot

    player = ctx.state.players[ctx.controller_index]
    tunic = player.equipment.get(EquipmentSlot.CHEST)
    if tunic is None or tunic.instance_id != ctx.source_card.instance_id:
        log.warning("  Spring Tunic: equipment not found")
        return

    energy = tunic.counters.get("energy", 0)
    if energy < 3:
        log.warning(f"  Spring Tunic: only {energy} energy counters (need 3)")
        return

    tunic.counters["energy"] = energy - 3
    ctx.state.resource_points[ctx.controller_index] = (
        ctx.state.resource_points.get(ctx.controller_index, 0) + 1
    )
    log.info(
        f"  {ctx.player_name(ctx.controller_index)}'s Spring Tunic: removes 3 energy counters, gains 1 resource"
    )


# ---------------------------------------------------------------------------
# Registration — Ability Registry (equipment using attack_reaction_effect)
# ---------------------------------------------------------------------------


def register_equipment_abilities(registry: AbilityRegistry) -> None:
    """Register all equipment card abilities with the given registry."""

    # Attack reactions
    registry.register("attack_reaction_effect", "Flick Knives", _flick_knives)
    registry.register("attack_reaction_effect", "Tide Flippers", _tide_flippers)
    registry.register("attack_reaction_effect", "Blacktek Whisperers", _blacktek_whisperers)
    registry.register("attack_reaction_effect", "Stalker's Steps", _stalkers_steps)

    # Equipment instants
    registry.register("equipment_instant_effect", "Dragonscaler Flight Path", _dragonscaler_flight_path)
    registry.register("equipment_instant_effect", "Fyendal's Spring Tunic", _fyendals_spring_tunic_instant)

    # Hunter's Klaive mark-on-hit is handled by the Mark keyword handler
    # in game.py (_handle_hit_mark_keyword), no separate registry entry needed.
