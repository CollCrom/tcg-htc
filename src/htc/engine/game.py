from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from random import Random

from htc.cards.card import CardDefinition
from htc.cards.card_db import CardDatabase
from htc.cards.instance import CardInstance
from htc.decks.deck_list import DeckList
from htc.engine.action_builder import ActionBuilder
from htc.engine.actions import ActionOption, Decision, PlayerResponse
from htc.engine.combat import CombatManager
from htc.engine.continuous import EffectDuration
from htc.engine.cost import (
    calculate_play_cost,
    pay_action_cost,
)
from htc.engine.cost_manager import CostManager
from htc.engine.abilities import AbilityContext, AbilityRegistry
from htc.engine.keyword_engine import KeywordEngine
from htc.engine.effects import EffectEngine
from htc.engine.stack import StackManager
from htc.enums import (
    ActionType,
    CardType,
    CombatStep,
    DecisionType,
    EquipmentSlot,
    Keyword,
    Phase,
    SubType,
    Zone,
)
from htc.engine.events import EventBus, EventType, GameEvent
from htc.player.interface import PlayerInterface
from htc.state.combat_state import ChainLink
from htc.state.game_state import GameState
from htc.state.player_state import PlayerState

log = logging.getLogger(__name__)

MAX_TURNS = 200  # safety valve
MAX_PRIORITY_PASSES = 500  # safety valve per phase


@dataclass
class GameResult:
    winner: int | None
    turns: int
    final_life: tuple[int, int]


class Game:
    """Orchestrates a complete FaB game between two players."""

    def __init__(
        self,
        db: CardDatabase,
        deck1: DeckList,
        deck2: DeckList,
        player1: PlayerInterface,
        player2: PlayerInterface,
        seed: int = 0,
    ) -> None:
        self.db = db
        self.decks = [deck1, deck2]
        self.interfaces = [player1, player2]
        self.state = GameState(rng=Random(seed))
        self.stack_mgr = StackManager()
        self.effect_engine = EffectEngine()
        self.combat_mgr = CombatManager(self.effect_engine)
        self.action_builder = ActionBuilder(self.effect_engine)
        self.cost_manager = CostManager(self.effect_engine, lambda d: self._ask(d))
        self.events = EventBus()
        self.keyword_engine = KeywordEngine(
            self.effect_engine, self.events, lambda d: self._ask(d),
        )
        self.ability_registry = AbilityRegistry()
        self._register_abilities()
        self._register_event_handlers()

    def _register_abilities(self) -> None:
        """Register card abilities with the ability registry."""
        from htc.cards.abilities import register_generic_abilities
        from htc.cards.abilities.assassin import register_assassin_abilities
        from htc.cards.abilities.ninja import register_ninja_abilities
        from htc.cards.abilities.equipment import register_equipment_abilities
        register_generic_abilities(self.ability_registry)
        register_assassin_abilities(self.ability_registry)
        register_ninja_abilities(self.ability_registry)
        register_equipment_abilities(self.ability_registry)

    def _register_hero_abilities(self) -> None:
        """Register hero abilities as triggered effects on the EventBus.

        Called after heroes are loaded during game setup. Each hero's
        ability is registered as a persistent TriggeredEffect.
        """
        from htc.cards.abilities.heroes import register_hero_abilities
        for i, player in enumerate(self.state.players):
            if player.hero:
                register_hero_abilities(
                    hero_name=player.hero.name,
                    controller_index=i,
                    event_bus=self.events,
                    effect_engine=self.effect_engine,
                    state_getter=lambda: self.state,
                    game=self,
                )

    def _register_equipment_triggers(self) -> None:
        """Register equipment triggered effects on the EventBus.

        Called after equipment is loaded during game setup. Checks each
        player's equipped items and registers appropriate triggers.
        """
        from htc.cards.abilities.equipment import register_equipment_triggers
        for i, player in enumerate(self.state.players):
            register_equipment_triggers(
                event_bus=self.events,
                effect_engine=self.effect_engine,
                state_getter=lambda: self.state,
                player_index=i,
                player_state=player,
            )

    def _apply_card_ability(
        self, card: CardInstance, player_index: int, timing: str,
        *, extra_data: dict | None = None,
    ) -> None:
        """Look up and apply a card's ability at the given timing.

        If no ability is registered for the card, does nothing (graceful
        degradation). Builds an AbilityContext and calls the handler.

        ``extra_data`` is an optional dict of contextual info (e.g.
        ``target_was_marked``) passed through to the AbilityContext.
        """
        handler = self.ability_registry.lookup(timing, card.name)
        if handler is None:
            log.debug(f"  No {timing} ability for {card.name}")
            return

        ctx = AbilityContext(
            state=self.state,
            source_card=card,
            controller_index=player_index,
            chain_link=self.state.combat_chain.active_link,
            effect_engine=self.effect_engine,
            events=self.events,
            ask=lambda d: self._ask(d),
            keyword_engine=self.keyword_engine,
            combat_mgr=self.combat_mgr,
            extra_data=extra_data or {},
        )
        handler(ctx)

    def _register_event_handlers(self) -> None:
        """Register handlers for core game events."""
        self.events.register_handler(EventType.DEAL_DAMAGE, self._handle_damage)
        self.events.register_handler(EventType.GAIN_LIFE, self._handle_gain_life)
        self.events.register_handler(EventType.DRAW_CARD, self._handle_draw_card)
        self.events.register_handler(EventType.HIT, self._handle_hit_mark_removal)

    def _handle_damage(self, event: GameEvent) -> None:
        """Apply damage to a player."""
        if event.target_player is not None and event.amount > 0:
            target = self.state.players[event.target_player]
            target.life_total = max(0, target.life_total - event.amount)
            target.turn_counters.damage_taken += event.amount
            target.turn_counters.life_lost += event.amount
            # Track damage dealt by the source's controller
            if event.source:
                attacker_index = event.source.owner_index
                self.state.players[attacker_index].turn_counters.damage_dealt += event.amount

    def _handle_gain_life(self, event: GameEvent) -> None:
        """Apply life gain to a player."""
        if event.target_player is not None and event.amount > 0:
            target = self.state.players[event.target_player]
            target.life_total += event.amount
            target.turn_counters.life_gained += event.amount
            log.info(f"  Player {event.target_player} gains {event.amount} life (life: {target.life_total})")

    def _handle_hit_mark_removal(self, event: GameEvent) -> None:
        """Remove marked condition when hero is hit by opponent's source (rules 9.3.3)."""
        if event.target_player is None:
            return
        target = self.state.players[event.target_player]
        if target.is_marked and event.source is not None:
            # Check that the source is controlled by an opponent
            source_owner = event.source.owner_index
            if source_owner != event.target_player:
                target.is_marked = False
                log.info(f"  Mark removed from Player {event.target_player} (hit by opponent)")

    def _handle_draw_card(self, event: GameEvent) -> None:
        """Draw a card for a player."""
        if event.target_player is None:
            return
        player = self.state.players[event.target_player]
        if not player.deck:
            return
        card = player.deck.pop(0)
        card.zone = Zone.HAND
        player.hand.append(card)
        player.turn_counters.num_cards_drawn += 1

    # --- Triggered Effect Processing ---

    MAX_TRIGGER_ITERATIONS = 50  # safety limit to prevent infinite loops

    def _process_pending_triggers(self) -> None:
        """Process all pending triggered effects until none remain.

        Triggered effects may cause further events which themselves trigger
        more effects. Loop until the queue is empty, with a safety limit
        to prevent infinite loops (rules 6.6.6).
        """
        iterations = 0
        while iterations < self.MAX_TRIGGER_ITERATIONS:
            pending = self.events.get_pending_triggers()
            if not pending:
                break
            iterations += 1
            for triggered_event in pending:
                log.debug(f"  Processing triggered effect: {triggered_event.event_type.name}")
                # Re-emit the triggered event through the pipeline so it
                # gets handlers, replacement effects, and may trigger further
                # effects.
                self.events.emit(triggered_event)
        if iterations >= self.MAX_TRIGGER_ITERATIONS:
            log.warning("Triggered effect processing hit safety limit")

    def play(self) -> GameResult:
        """Run a complete game to conclusion."""
        self._setup_game()
        while not self.state.game_over and self.state.turn_number < MAX_TURNS:
            self._run_turn()
        if self.state.winner is None and self.state.turn_number >= MAX_TURNS:
            log.warning("Game ended by turn limit")
        return GameResult(
            winner=self.state.winner,
            turns=self.state.turn_number,
            final_life=(self.state.players[0].life_total, self.state.players[1].life_total),
        )

    # --- Setup ---

    def _setup_game(self) -> None:
        """Start-of-game procedure (rules 4.1)."""
        for i in range(2):
            ps = self._build_player_state(i, self.decks[i])
            self.state.players.append(ps)

        # Register hero abilities as triggered effects
        self._register_hero_abilities()

        # Register equipment triggered effects
        self._register_equipment_triggers()

        # Shuffle decks
        for ps in self.state.players:
            self.state.rng.shuffle(ps.deck)

        # Randomly choose first player
        self.state.turn_player_index = self.state.rng.randint(0, 1)
        self.state.turn_number = 1

        # Draw starting hands
        for ps in self.state.players:
            intellect = ps.hero.definition.intellect if ps.hero else 4
            self._draw_cards(ps, intellect or 4)

    def _build_player_state(self, index: int, deck: DeckList) -> PlayerState:
        ps = PlayerState(index=index)

        # Hero
        hero_def = self.db.get_by_name(deck.hero_name)
        if hero_def is None:
            raise ValueError(f"Hero not found: {deck.hero_name}")
        ps.hero = self._make_instance(hero_def, index, Zone.HERO)
        ps.life_total = hero_def.health or 20

        # Weapons
        for wname in deck.weapons:
            wdef = self.db.get_by_name(wname)
            if wdef:
                ps.weapons.append(self._make_instance(wdef, index, Zone.WEAPON_1))

        # Equipment
        for ename in deck.equipment:
            edef = self.db.get_by_name(ename)
            if edef:
                card = self._make_instance(edef, index, Zone.HEAD)  # zone updated below
                slot = self._equipment_slot(edef)
                if slot and ps.equipment.get(slot) is None:
                    ps.equipment[slot] = card
                    card.zone = Zone(slot.value)

        # Deck cards
        for entry in deck.cards:
            cdef = self.db.get_by_name(entry.name, entry.color)
            if cdef is None:
                log.warning(f"Card not found: {entry.name} ({entry.color})")
                continue
            for _ in range(entry.count):
                ps.deck.append(self._make_instance(cdef, index, Zone.DECK))

        return ps

    def _make_instance(self, defn: CardDefinition, owner: int, zone: Zone) -> CardInstance:
        return CardInstance(
            instance_id=self.state.next_instance_id(),
            definition=defn,
            owner_index=owner,
            zone=zone,
        )

    def _create_fealty_token(self, controller_index: int) -> CardInstance:
        """Create a Fealty token as a permanent for the given player.

        Emits a CREATE_TOKEN event. The token is a Draconic Aura that
        can be destroyed for an effect (Cindra's hero ability).
        """
        from htc.cards.abilities.heroes import _create_fealty_token_simple
        _create_fealty_token_simple(self.state, controller_index)
        token = self.state.players[controller_index].permanents[-1]
        self.events.emit(GameEvent(
            event_type=EventType.CREATE_TOKEN,
            source=None,
            target_player=controller_index,
            card=token,
            data={"token_name": "Fealty"},
        ))
        return token

    @staticmethod
    def _equipment_slot(defn: CardDefinition) -> EquipmentSlot | None:
        if SubType.HEAD in defn.subtypes:
            return EquipmentSlot.HEAD
        if SubType.CHEST in defn.subtypes:
            return EquipmentSlot.CHEST
        if SubType.ARMS in defn.subtypes:
            return EquipmentSlot.ARMS
        if SubType.LEGS in defn.subtypes:
            return EquipmentSlot.LEGS
        return None

    # --- Turn structure ---

    def _run_turn(self) -> None:
        tp = self.state.turn_player
        log.info(f"=== Turn {self.state.turn_number} (Player {tp.index}) ===")
        # Reset turn counters for ALL players at start of each turn
        for player in self.state.players:
            player.turn_counters.reset()

        # Start Phase (4.2) — no priority
        self.state.phase = Phase.START
        self.events.emit(GameEvent(
            event_type=EventType.START_OF_TURN,
            target_player=tp.index,
        ))
        self._process_pending_triggers()

        # Action Phase (4.3)
        self.state.phase = Phase.ACTION
        self.events.emit(GameEvent(
            event_type=EventType.START_OF_ACTION_PHASE,
            target_player=tp.index,
        ))
        self.state.action_points[tp.index] = 1
        self.state.resource_points[0] = 0
        self.state.resource_points[1] = 0
        self._run_action_phase()

        # End Phase (4.4)
        self.state.phase = Phase.END
        self._run_end_phase()

        # Check for game over
        self._check_game_over()

        # Advance turn
        self.state.turn_player_index = 1 - self.state.turn_player_index
        self.state.turn_number += 1

    # --- Action Phase with Priority ---

    def _run_action_phase(self) -> None:
        """Action phase priority loop (rules 4.3).

        Turn player gains priority first. Priority alternates on pass.
        When both players pass in succession with an empty stack and
        closed combat chain, the action phase ends.
        """
        safety = 0
        consecutive_passes = 0
        priority_player = self.state.turn_player_index

        while not self.state.game_over and safety < MAX_PRIORITY_PASSES:
            safety += 1

            # If combat chain is open, run combat steps
            if self.state.combat_chain.is_open:
                self._run_combat_steps()
                if self.state.game_over:
                    break
                # After combat closes, turn player gets priority again
                consecutive_passes = 0
                priority_player = self.state.turn_player_index
                continue

            # If stack has items, resolve them
            if not self.stack_mgr.is_empty(self.state):
                self._resolve_stack()
                if self.state.game_over:
                    break
                # Turn player regains priority after resolution (1.11.5)
                consecutive_passes = 0
                priority_player = self.state.turn_player_index
                continue

            # Stack is empty, chain is closed — active player gets priority
            decision = self._build_action_decision(priority_player)

            response = self._ask(decision)
            action_id = response.first

            if action_id is None or action_id == "pass":
                consecutive_passes += 1
                if consecutive_passes >= 2:
                    # 4.3.4: both pass with empty stack and closed chain
                    break
                # Pass priority to opponent
                priority_player = 1 - priority_player
                continue

            consecutive_passes = 0
            self._execute_action(priority_player, action_id)
            # After acting, same player retains priority

    def _resolve_stack(self) -> None:
        """Resolve the top layer of the stack."""
        layer = self.stack_mgr.resolve_top(self.state)
        if layer is None:
            return

        if layer.card:
            card = layer.card
            player = self.state.players[layer.controller_index]

            if card.definition.is_attack:
                # Attack resolves: move to combat chain, begin combat
                self._begin_attack(layer.controller_index, card, layer.has_go_again)
            elif card.definition.is_defense_reaction:
                # Defense reaction resolves: becomes a defending card (7.4.2d)
                link = self.state.combat_chain.active_link
                if link:
                    self.combat_mgr.add_defender(self.state, link, card)
                    log.info(f"  Defense reaction: {card.name}{card.definition.color_label} (defense={self.effect_engine.get_modified_defense(self.state, card)})")
                    # Apply defense reaction effect (e.g. Fate Foreseen's Opt, Sink Below's cycle)
                    self._apply_card_ability(card, layer.controller_index, "defense_reaction_effect")
                else:
                    self.state.move_card(card, Zone.GRAVEYARD)
            elif card.definition.is_attack_reaction:
                # Attack reaction resolves: apply effect, then graveyard
                self._apply_card_ability(card, layer.controller_index, "attack_reaction_effect")
                self.state.move_card(card, Zone.GRAVEYARD)
                log.info(f"  Attack reaction: {card.name}{card.definition.color_label}")
            elif card.definition.is_permanent_when_resolved:
                # Permanent subtypes (auras, items, allies, etc.) enter the arena (1.3.3)
                card.zone = Zone.PERMANENT
                player.permanents.append(card)
                log.info(f"  Permanent: {card.name}{card.definition.color_label} enters the arena")
                # Apply on_play ability for permanents (e.g. Amulet of Echoes)
                self._apply_card_ability(card, layer.controller_index, "on_play")
            else:
                # Non-attack, non-reaction, non-permanent: resolve effect, then graveyard
                # Apply on_play ability before moving to graveyard
                self._apply_card_ability(card, layer.controller_index, "on_play")
                # If the card has arcane damage, deal it
                if card.definition.arcane and card.definition.arcane > 0:
                    target_index = 1 - layer.controller_index
                    self._deal_arcane_damage(card, target_index, card.definition.arcane)
                self.state.move_card(card, Zone.GRAVEYARD)

            # Go again from resolved layer
            if layer.has_go_again and not card.definition.is_attack:
                self.state.action_points[layer.controller_index] += 1

    def _build_action_decision(self, player_index: int) -> Decision:
        """Build the list of legal actions for the active player (non-combat)."""
        return self.action_builder.build_action_decision(
            self.state, player_index, self.stack_mgr.is_empty(self.state),
        )

    def _add_instant_options(self, options: list[ActionOption], player_index: int) -> None:
        """Append playable instant options from the player's hand, deduplicating."""
        self.action_builder.add_instant_options(options, self.state, player_index)

    @staticmethod
    def _pass_option(description: str = "Pass") -> ActionOption:
        """Create a pass action option."""
        return ActionBuilder.pass_option(description)

    def _can_play_card(self, player_index: int, card: CardInstance) -> bool:
        """Check if a player can legally play this card as an action."""
        return self.action_builder.can_play_card(self.state, player_index, card)

    def _can_play_instant(self, player_index: int, card: CardInstance) -> bool:
        """Check if a player can play an instant (no action point needed)."""
        return self.action_builder.can_play_instant(self.state, player_index, card)

    def _execute_action(self, player_index: int, action_id: str) -> None:
        """Execute a chosen action."""
        if action_id.startswith("play_"):
            instance_id = int(action_id.split("_", 1)[1])
            card = self.state.find_card(instance_id)
            if card:
                self._play_card(player_index, card)
        elif action_id.startswith("activate_"):
            instance_id = int(action_id.split("_", 1)[1])
            weapon = self.state.find_card(instance_id)
            if weapon:
                self._activate_weapon(player_index, weapon)

    def _play_card(self, player_index: int, card: CardInstance) -> None:
        """Play a card from hand/arsenal onto the stack (rules 5.1).

        Sequence per rules: Announce (move to stack) → Pay costs → Emit event.
        Legality is already verified before this method is called.
        """
        player = self.state.players[player_index]

        # 5.1.2: Announce — remove from zone and put on stack
        if card in player.hand:
            player.hand.remove(card)
        elif card in player.arsenal:
            player.arsenal.remove(card)

        layer = self.stack_mgr.add_card_layer(
            self.state, card, player_index,
        )

        # 5.1.5: Pay action point cost
        pay_action_cost(self.state, player_index, card)

        # 5.1.6: Pay resource cost (pitch cards as needed)
        resource_cost = calculate_play_cost(self.state, card, self.effect_engine)
        self._pitch_to_pay(player_index, resource_cost)

        # Update turn counters
        if card.definition.is_attack_action:
            player.turn_counters.num_attack_cards_played += 1
            player.turn_counters.num_attacks_played += 1
            player.turn_counters.has_attacked = True
        elif card.definition.is_non_attack_action:
            player.turn_counters.num_non_attack_actions_played += 1
        elif card.definition.is_instant:
            player.turn_counters.num_instants_played += 1
        elif card.definition.is_attack_reaction:
            pass  # counter not yet needed
        elif card.definition.is_defense_reaction:
            player.turn_counters.num_defense_reactions_played += 1

        # Emit play event
        self.events.emit(GameEvent(
            event_type=EventType.PLAY_CARD,
            source=card,
            target_player=player_index,
            card=card,
        ))
        # Process triggered effects from the play event
        self._process_pending_triggers()

        color_str = card.definition.color_label

        # If it's an attack and combat chain is closed, open it (7.0.2a)
        if card.definition.is_attack and not self.state.combat_chain.is_open:
            self.combat_mgr.open_chain(self.state)
            log.info(f"  Play attack: {card.name}{color_str} (power={self.effect_engine.get_modified_power(self.state, card)})")
        elif card.definition.is_attack:
            log.info(f"  Chain attack: {card.name}{color_str} (power={self.effect_engine.get_modified_power(self.state, card)})")
        else:
            log.info(f"  Play: {card.name}{color_str}")

    # --- Arcane Damage ---

    def _deal_arcane_damage(
        self, source: CardInstance, target_player_index: int, amount: int
    ) -> None:
        """Deal arcane damage to a player, with Arcane Barrier prevention.

        Before damage is applied, the target player may pay resources to
        activate Arcane Barrier on their equipment to prevent some or all
        of the arcane damage.
        """
        if amount <= 0:
            return

        # Check for Spellvoid on target's equipment (one-shot prevention)
        remaining = self._apply_spellvoid(target_player_index, amount)

        # Check for Arcane Barrier on target's equipment
        remaining = self._apply_arcane_barrier(target_player_index, remaining)

        if remaining > 0:
            self.events.emit(GameEvent(
                event_type=EventType.DEAL_DAMAGE,
                source=source,
                target_player=target_player_index,
                amount=remaining,
                data={"damage_type": "arcane"},
            ))
            log.info(
                f"  Arcane damage: {remaining} to Player {target_player_index} "
                f"(life: {self.state.players[target_player_index].life_total})"
            )
            self._check_game_over()
        else:
            log.info(f"  Arcane damage fully prevented by Arcane Barrier")

    def _apply_arcane_barrier(self, player_index: int, damage: int) -> int:
        """Let the player use Arcane Barrier to prevent arcane damage.

        Returns the remaining damage after prevention.
        """
        player = self.state.players[player_index]

        # Collect total Arcane Barrier value from equipment (using modified keywords)
        barrier_equipment = self.keyword_engine.get_equipment_with_keyword(
            self.state, player, Keyword.ARCANE_BARRIER,
        )
        total_barrier = sum(value for _, _, value in barrier_equipment)

        if total_barrier <= 0:
            return damage

        # Calculate how much can be prevented (limited by barrier and damage)
        max_prevent = min(total_barrier, damage)

        # Check if the player can pay any resources
        available_resources = self.state.resource_points[player_index]
        for card in player.hand:
            if card.pitch is not None:
                available_resources += card.pitch

        if available_resources <= 0:
            return damage

        # Ask the player how much to prevent (0 to max_prevent)
        max_affordable = min(max_prevent, available_resources)
        options = [
            ActionOption(
                action_id=f"barrier_{n}",
                description=f"Pay {n} resource(s) to prevent {n} arcane damage",
                action_type=ActionType.ACTIVATE_ABILITY,
            )
            for n in range(1, max_affordable + 1)
        ]
        options.append(self._pass_option("Don't use Arcane Barrier"))

        decision = Decision(
            player_index=player_index,
            decision_type=DecisionType.OPTIONAL_ABILITY,
            prompt=f"Use Arcane Barrier to prevent up to {max_affordable} of {damage} arcane damage?",
            options=options,
        )
        response = self._ask(decision)

        if response.first is None or response.first == "pass":
            return damage

        prevent_amount = int(response.first.replace("barrier_", ""))

        # Pay resources (pitch cards as needed)
        self._pitch_to_pay(player_index, prevent_amount)

        log.info(f"  Arcane Barrier: Player {player_index} prevents {prevent_amount} arcane damage")
        return damage - prevent_amount

    def _apply_spellvoid(self, player_index: int, damage: int) -> int:
        """Let the player use Spellvoid to prevent arcane damage."""
        return self.keyword_engine.apply_spellvoid(self.state, player_index, damage)

    # --- Weapon Activation (rules 1.4.3) ---

    @staticmethod
    def _weapon_activation_cost(weapon: CardInstance) -> int:
        """Get the resource cost to activate a weapon.

        Weapons store activation cost in functional text as {r} tokens
        (e.g. '{r}{r}' = 2), since the CSV 'Cost' field is for play cost.
        Falls back to the card's cost field if set.
        """
        if weapon.definition.cost is not None:
            return weapon.definition.cost
        return weapon.definition.functional_text.count("{r}")

    def _can_activate_weapon(self, player_index: int, weapon: CardInstance) -> bool:
        """Check if a weapon can be activated (untapped, has AP, can pay cost)."""
        return ActionBuilder._can_activate_weapon(self.state, player_index, weapon)

    def _activate_weapon(self, player_index: int, weapon: CardInstance) -> None:
        """Activate a weapon ability (rules 1.4.3).

        Physical weapons (power > 0): create attack proxy → combat chain.
        Arcane weapons (arcane > 0): deal arcane damage directly.
        """
        player = self.state.players[player_index]

        # Tap the weapon (enforces once-per-turn)
        weapon.is_tapped = True

        # Pay action point cost
        self.state.action_points[player_index] -= 1

        # Pay resource cost
        resource_cost = self._weapon_activation_cost(weapon)
        self._pitch_to_pay(player_index, resource_cost)

        # Update counters
        player.turn_counters.num_weapon_attacks += 1

        # Register delayed weapon triggers (e.g. Kunai of Retribution destroy)
        from htc.cards.abilities.equipment import register_weapon_triggers
        register_weapon_triggers(
            event_bus=self.events,
            state_getter=lambda: self.state,
            player_index=player_index,
            weapon=weapon,
        )

        # Branch: arcane ability vs physical attack
        if weapon.definition.arcane and weapon.definition.arcane > 0:
            self._activate_arcane_weapon(player_index, weapon)
        else:
            self._activate_attack_weapon(player_index, weapon)

    def _activate_attack_weapon(self, player_index: int, weapon: CardInstance) -> None:
        """Activate a physical weapon — create attack proxy on the stack."""
        player = self.state.players[player_index]

        proxy = self._create_attack_proxy(weapon, player_index)
        layer = self.stack_mgr.add_card_layer(self.state, proxy, player_index)
        layer.has_go_again = weapon.definition.has_go_again

        player.turn_counters.num_attacks_played += 1
        player.turn_counters.has_attacked = True

        if not self.state.combat_chain.is_open:
            self.combat_mgr.open_chain(self.state)

        log.info(f"  Weapon attack: {weapon.name} (power={weapon.base_power or 0})")

    def _activate_arcane_weapon(self, player_index: int, weapon: CardInstance) -> None:
        """Activate an arcane weapon — deal arcane damage directly (no combat chain)."""
        arcane_damage = weapon.definition.arcane or 0
        target_index = 1 - player_index

        # Go again from weapon (e.g. Surgent Aethertide)
        if weapon.definition.has_go_again:
            self.state.action_points[player_index] += 1

        log.info(f"  Arcane activation: {weapon.name} (arcane={arcane_damage})")
        self._deal_arcane_damage(weapon, target_index, arcane_damage)

    def _create_attack_proxy(self, weapon: CardInstance, owner_index: int) -> CardInstance:
        """Create a transient attack card representing a weapon attack.

        Uses modified keywords/values from the effect engine so that any
        continuous effects on the weapon are inherited by the proxy.
        """
        modified_keywords = self.effect_engine.get_modified_keywords(self.state, weapon)
        # Build keyword_values dict for modified keywords using effect-engine-aware path
        modified_kw_values = {
            kw: self.effect_engine.get_keyword_value(self.state, weapon, kw)
            for kw in modified_keywords
            if self.effect_engine.get_keyword_value(self.state, weapon, kw) > 0
        }
        proxy_def = CardDefinition(
            unique_id=f"proxy-{weapon.definition.unique_id}",
            name=f"{weapon.name} (attack)",
            color=None,
            pitch=None,
            cost=None,
            power=weapon.definition.power,
            defense=None,
            health=None,
            intellect=None,
            arcane=None,
            types=frozenset({CardType.ACTION}),
            subtypes=frozenset({SubType.ATTACK}),
            supertypes=weapon.definition.supertypes,
            keywords=modified_keywords,
            functional_text="",
            type_text="Weapon attack proxy",
            keyword_values=modified_kw_values,
        )
        proxy = CardInstance(
            instance_id=self.state.next_instance_id(),
            definition=proxy_def,
            owner_index=owner_index,
            zone=Zone.STACK,
            is_proxy=True,
            proxy_source_id=weapon.instance_id,
        )
        return proxy

    # --- Combat Steps (Section 7) ---

    def _run_combat_steps(self) -> None:
        """Run through combat chain steps for the active chain link.

        Steps: Layer -> Attack -> Defend -> Reaction -> Damage -> Resolution -> Close
        Per rules section 7.
        """
        if not self.state.combat_chain.is_open:
            return

        # Layer Step (7.1): attack is on the stack
        self.state.combat_step = CombatStep.LAYER
        self._layer_step()
        if self.state.game_over or not self.state.combat_chain.is_open:
            return

        # Attack Step (7.2): attack resolves onto combat chain
        self.state.combat_step = CombatStep.ATTACK
        self._attack_step()
        if self.state.game_over or not self.state.combat_chain.is_open:
            return

        # Defend Step (7.3): defender declares defending cards
        self.state.combat_step = CombatStep.DEFEND
        self._defend_step()
        if self.state.game_over or not self.state.combat_chain.is_open:
            return

        # Phantasm check (8.3.11): if defended by non-Illusionist attack action
        # with 6+ power, destroy the Phantasm attack
        if self._check_phantasm():
            return  # attack was destroyed, chain link is done

        # Reaction Step (7.4): attack/defense reactions
        self.state.combat_step = CombatStep.REACTION
        self._reaction_step()
        if self.state.game_over or not self.state.combat_chain.is_open:
            return

        # Damage Step (7.5): calculate and apply damage
        self.state.combat_step = CombatStep.DAMAGE
        self._damage_step()
        if self.state.game_over or not self.state.combat_chain.is_open:
            return

        # Resolution Step (7.6): go again, may continue chain
        self.state.combat_step = CombatStep.RESOLUTION
        continued = self._resolution_step()
        if self.state.game_over or not self.state.combat_chain.is_open:
            return

        if continued:
            # Attacker played another attack — loop back to combat steps
            # (the new attack is on the stack, combat chain stays open)
            return

        # Close Step (7.7): combat chain closes
        self.state.combat_step = CombatStep.CLOSE
        self._close_step()
        self.state.combat_step = None

    def _layer_step(self) -> None:
        """Layer Step (7.1): Attack is on the stack. Turn player gets priority.
        When the top layer is the attack and all pass, Layer Step ends."""
        safety = 0
        consecutive_passes = 0
        priority_player = self.state.turn_player_index

        while not self.state.game_over and safety < MAX_PRIORITY_PASSES:
            safety += 1

            # If stack is empty (attack already resolved somehow), move on
            if self.stack_mgr.is_empty(self.state):
                break

            top = self.stack_mgr.top(self.state)
            if top and top.card and top.card.definition.is_attack:
                # The attack is still on top — priority loop (7.1.2)
                decision = self._build_combat_priority_decision(priority_player, allow_actions=False)
                response = self._ask(decision)
                action_id = response.first

                if action_id is None or action_id == "pass":
                    consecutive_passes += 1
                    if consecutive_passes >= 2:
                        # Both passed — resolve the attack
                        self._resolve_stack()
                        break
                    priority_player = 1 - priority_player
                    continue

                consecutive_passes = 0
                self._execute_action(priority_player, action_id)
            else:
                # Something else on top of stack — resolve it
                self._resolve_stack()
                consecutive_passes = 0
                priority_player = self.state.turn_player_index

    def _begin_attack(self, attacker_index: int, attack_card: CardInstance, has_go_again: bool) -> None:
        """Move an attack from the stack to the combat chain as a new chain link."""
        defender_index = 1 - attacker_index
        link = self.combat_mgr.add_chain_link(self.state, attack_card, defender_index)

        # If this is a weapon proxy, set the weapon as attack_source
        if attack_card.is_proxy and attack_card.proxy_source_id is not None:
            link.attack_source = self.state.find_card(attack_card.proxy_source_id)

        # Apply on_attack ability (e.g. Pick Up the Point retrieve, Whittle from Bone)
        self._apply_card_ability(attack_card, attacker_index, "on_attack")

        # Emit attack declared event (7.2.4)
        self.events.emit(GameEvent(
            event_type=EventType.ATTACK_DECLARED,
            source=attack_card,
            target_player=defender_index,
            data={"chain_link": link, "attacker_index": attacker_index},
        ))
        # Process triggered effects from the attack event (rules 6.6)
        self._process_pending_triggers()

    def _attack_step(self) -> None:
        """Attack Step (7.2): Attack resolves onto combat chain.
        'Attack' event occurs. Turn player gets priority."""
        link = self.state.combat_chain.active_link
        if link is None:
            return

        # 7.2.5: Turn player gets priority
        self._run_priority_loop(
            lambda pp: self._build_combat_priority_decision(pp, allow_actions=False),
        )

    def _defend_step(self) -> None:
        """Defend Step (7.3): Defender declares defending cards."""
        link = self.state.combat_chain.active_link
        if link is None:
            return

        defender_index = link.attack_target_index
        player = self.state.players[defender_index]
        options: list[ActionOption] = []

        # Check Dominate (8.3.4): can't be defended by more than 1 card from hand
        attack_keywords = (
            self.effect_engine.get_modified_keywords(self.state, link.active_attack)
            if link.active_attack else frozenset()
        )
        has_dominate = Keyword.DOMINATE in attack_keywords
        has_overpower = Keyword.OVERPOWER in attack_keywords

        # Cards from hand with defense value (7.3.2a)
        for card in player.hand:
            if card.base_defense is not None and not card.definition.is_defense_reaction:
                mod_def = self.effect_engine.get_modified_defense(self.state, card)
                options.append(ActionOption.defend_with(
                    card.instance_id, f"{card.name}{card.definition.color_label}", mod_def,
                ))

        # Ambush (8.3): cards with Ambush in arsenal can defend
        for card in player.arsenal:
            card_keywords = self.effect_engine.get_modified_keywords(self.state, card)
            if (
                Keyword.AMBUSH in card_keywords
                and card.base_defense is not None
            ):
                mod_def = self.effect_engine.get_modified_defense(self.state, card)
                options.append(ActionOption.defend_with(
                    card.instance_id, f"{card.name}{card.definition.color_label}", mod_def,
                    extra="from arsenal",
                ))

        # Equipment (public permanents) (7.3.2a) — not limited by Dominate
        for slot, eq in player.equipment.items():
            if eq and not eq.is_tapped and eq.base_defense is not None:
                mod_def = self.effect_engine.get_modified_defense(self.state, eq)
                options.append(ActionOption.defend_with(
                    eq.instance_id, eq.name, mod_def,
                ))

        # Always can pass
        options.append(self._pass_option("Don't defend"))

        decision = Decision(
            player_index=defender_index,
            decision_type=DecisionType.CHOOSE_DEFENDERS,
            prompt=f"Defend against {link.active_attack.name if link.active_attack else 'attack'} "
                   f"(power={self.combat_mgr.get_attack_power(self.state, link)})",
            options=options,
            min_selections=1,
            max_selections=len(options),
        )

        response = self._ask(decision)

        hand_cards_defended = 0
        action_cards_defended = 0
        for opt_id in response.selected_option_ids:
            if opt_id == "pass":
                continue
            instance_id = int(opt_id.replace("defend_", ""))
            card = player.find_card(instance_id)
            if card:
                # Dominate (8.3.4): can't defend with more than 1 card from hand
                if card in player.hand:
                    if has_dominate and hand_cards_defended >= 1:
                        continue
                    # Overpower (8.3.9): can't defend with more than 1 action card
                    if has_overpower and card.definition.is_action and action_cards_defended >= 1:
                        continue
                    player.hand.remove(card)
                    player.turn_counters.num_cards_defended_from_hand += 1
                    hand_cards_defended += 1
                    if card.definition.is_action:
                        action_cards_defended += 1
                elif card in player.arsenal:
                    # Only Ambush cards can defend from arsenal
                    card_kws = self.effect_engine.get_modified_keywords(self.state, card)
                    if Keyword.AMBUSH not in card_kws:
                        continue
                    # Ambush: defending from arsenal counts as hand defense
                    # for Dominate/Overpower purposes
                    if has_dominate and hand_cards_defended >= 1:
                        continue
                    if has_overpower and card.definition.is_action and action_cards_defended >= 1:
                        continue
                    player.arsenal.remove(card)
                    hand_cards_defended += 1
                    if card.definition.is_action:
                        action_cards_defended += 1
                self.combat_mgr.add_defender(self.state, link, card)
                log.info(f"  Defended with: {card.name}{card.definition.color_label} (defense={self.effect_engine.get_modified_defense(self.state, card)})")

                # Emit defend event (7.0.5a)
                self.events.emit(GameEvent(
                    event_type=EventType.DEFEND_DECLARED,
                    source=card,
                    target_player=defender_index,
                    data={"chain_link": link},
                ))

        # 7.3.3: Turn player gets priority after defenders declared
        self._priority_loop_until_pass(allow_actions=False)

    def _reaction_step(self) -> None:
        """Reaction Step (7.4): Players may play attack/defense reactions."""
        link = self.state.combat_chain.active_link
        if link is None:
            return

        attacker_index = 1 - link.attack_target_index
        defender_index = link.attack_target_index

        # Priority alternates between players (7.4.2)
        self._run_priority_loop(
            lambda pp: self._build_reaction_decision(pp, attacker_index, defender_index),
            check_game_over_after_resolve=True,
        )

    def _build_reaction_decision(
        self, priority_player: int, attacker_index: int, defender_index: int
    ) -> Decision:
        """Build decision for reaction step — attack reactions for attacker,
        defense reactions for defender, instants for either."""
        return self.action_builder.build_reaction_decision(
            self.state, priority_player, attacker_index, defender_index,
        )

    def _damage_step(self) -> None:
        """Damage Step (7.5): Calculate and apply damage."""
        link = self.state.combat_chain.active_link
        if link is None:
            return

        # Piercing N (8.3): if defended by equipment, attack gets +N power
        self._apply_piercing(link)

        damage = self.combat_mgr.calculate_damage(self.state, link)
        if damage > 0:
            # Emit damage event through the event bus (enables replacement/prevention)
            event = self.events.emit(GameEvent(
                event_type=EventType.DEAL_DAMAGE,
                source=link.active_attack,
                target_player=link.attack_target_index,
                amount=damage,
                data={"chain_link": link, "is_combat": True},
            ))
            # Process triggered effects from the damage event
            self._process_pending_triggers()

            actual_damage = event.amount if not event.cancelled else 0
            link.damage_dealt = actual_damage
            if actual_damage > 0:
                link.hit = True
                target = self.state.players[link.attack_target_index]
                log.info(f"  Hit for {actual_damage} damage! (P{target.index} life: {target.life_total})")

                # Record mark state BEFORE emitting HIT event.
                # The HIT handler clears is_marked, but on_hit abilities
                # (e.g. Mark of the Black Widow, Savor Bloodshed) need
                # the pre-hit mark state.  Store it in the event data.
                target_was_marked = target.is_marked

                # Emit hit event (handler removes mark during this call)
                self.events.emit(GameEvent(
                    event_type=EventType.HIT,
                    source=link.active_attack,
                    target_player=link.attack_target_index,
                    amount=actual_damage,
                    data={
                        "chain_link": link,
                        "target_was_marked": target_was_marked,
                    },
                ))
                # Process triggered effects from the hit event
                self._process_pending_triggers()

                # Apply on_hit ability (e.g. Kiss of Death, Mark of the Black Widow)
                if link.active_attack:
                    attacker_index = 1 - link.attack_target_index
                    self._apply_card_ability(
                        link.active_attack, attacker_index, "on_hit",
                        extra_data={"target_was_marked": target_was_marked},
                    )
            else:
                log.info(f"  Blocked!")
        else:
            log.info(f"  Blocked!")

        self._check_game_over()

        # 7.5.3: Turn player gets priority after damage
        self._priority_loop_until_pass(allow_actions=False)

    def _resolution_step(self) -> bool:
        """Resolution Step (7.6): Go again, may continue combat chain.

        Returns True if the attacker played another attack (chain continues).
        """
        link = self.state.combat_chain.active_link
        if link is None:
            return False

        attacker_index = 1 - link.attack_target_index

        # 7.6.2: If attack has go again at resolution time, controller gains 1 AP
        # Always use effect engine for dynamic keyword check (effects may grant/remove go again)
        has_go_again = False
        if link.active_attack:
            attack_keywords = self.effect_engine.get_modified_keywords(self.state, link.active_attack)
            has_go_again = Keyword.GO_AGAIN in attack_keywords
        if has_go_again:
            self.state.action_points[attacker_index] += 1

        def _check_attack_on_stack() -> object:
            """If an attack is on top of the stack, signal chain continuation."""
            if self.stack_mgr.is_empty(self.state):
                return None
            top = self.stack_mgr.top(self.state)
            if top and top.card and top.card.definition.is_attack:
                return self._BREAK_TRUE
            return None  # fall through to default resolve behaviour

        # 7.6.3: Turn player gets priority
        # 7.6.3a: Turn player may play another attack during Resolution Step
        return self._run_priority_loop(
            lambda pp: self._build_resolution_decision(pp),
            on_stack_not_empty=_check_attack_on_stack,
            on_action_executed=_check_attack_on_stack,
        )

    def _build_resolution_decision(self, player_index: int) -> Decision:
        """Build decision for resolution step — can play attacks (if turn player)
        and instants."""
        return self.action_builder.build_resolution_decision(self.state, player_index)

    def _check_phantasm(self) -> bool:
        """Phantasm (8.3.11): if the attack has Phantasm and is defended by a
        non-Illusionist attack action card with 6+ power, destroy the attack.

        Returns True if the attack was destroyed (skip remaining combat steps).
        """
        triggered = self.keyword_engine.check_phantasm(self.state)
        if triggered:
            # Chain close and effect cleanup are game-loop concerns
            self.combat_mgr.close_chain(self.state)
            self.effect_engine.cleanup_expired_effects(
                self.state, EffectDuration.END_OF_COMBAT
            )
        return triggered

    def _apply_piercing(self, link: ChainLink) -> None:
        """Piercing N: if any defending card is equipment, attack gets +N power."""
        self.keyword_engine.apply_piercing(self.state, link)

    def _apply_equipment_degradation(self) -> None:
        """Apply Battleworn, Blade Break, and Temper to equipment that defended."""
        self.keyword_engine.apply_equipment_degradation(self.state)

    def _destroy_equipment(self, card: CardInstance) -> None:
        """Destroy an equipment card — remove from slot and move to graveyard."""
        self.keyword_engine.destroy_equipment(self.state, card)

    def _close_step(self) -> None:
        """Close Step (7.7): Combat chain closes, cards go to graveyard.

        Equipment degradation (Battleworn, Blade Break, Temper) is applied
        to equipment that defended during this combat chain.
        """
        # 7.7.3: "combat chain closes" event occurs
        self.events.emit(GameEvent(
            event_type=EventType.COMBAT_CHAIN_CLOSES,
        ))
        self._process_pending_triggers()

        # Apply equipment degradation before close_chain moves cards
        self._apply_equipment_degradation()

        self.combat_mgr.close_chain(self.state)
        self.effect_engine.cleanup_expired_effects(self.state, EffectDuration.END_OF_COMBAT)
        log.debug("  Combat chain closed")

    def _build_combat_priority_decision(
        self, player_index: int, allow_actions: bool = False
    ) -> Decision:
        """Build a priority decision during combat (instants only, unless allow_actions)."""
        return self.action_builder.build_combat_priority_decision(
            self.state, player_index, allow_actions=allow_actions,
        )

    # --- Shared Priority Loop ---

    _BREAK = object()       # sentinel: break out of loop, return False
    _BREAK_TRUE = object()  # sentinel: break out of loop, return True
    _CONTINUE = object()    # sentinel: skip to next iteration

    def _run_priority_loop(
        self,
        decision_builder: Callable[[int], Decision],
        *,
        check_game_over_after_resolve: bool = False,
        on_stack_not_empty: Callable[[], object] | None = None,
        on_action_executed: Callable[[], object] | None = None,
    ) -> bool:
        """Generic priority loop shared by all combat steps and sub-phases.

        Parameters
        ----------
        decision_builder:
            Called with the current priority player index; must return a Decision.
        check_game_over_after_resolve:
            If True, call _check_game_over() after each stack resolution.
        on_stack_not_empty:
            Optional hook called when the stack is non-empty *instead* of the
            default resolve-and-reset behaviour.  Return one of the sentinels
            ``_BREAK``, ``_BREAK_TRUE``, or ``_CONTINUE`` to control the loop,
            or ``None`` to fall through to the default behaviour.
        on_action_executed:
            Optional hook called after an action is executed.  Return
            ``_BREAK_TRUE`` to exit the loop returning True, or ``None``
            to continue normally.

        Returns
        -------
        bool
            True only when a hook requests early exit via ``_BREAK_TRUE``.
        """
        safety = 0
        consecutive_passes = 0
        priority_player = self.state.turn_player_index

        while not self.state.game_over and safety < MAX_PRIORITY_PASSES:
            safety += 1

            # --- Stack resolution ---
            if not self.stack_mgr.is_empty(self.state):
                if on_stack_not_empty is not None:
                    signal = on_stack_not_empty()
                    if signal is self._BREAK:
                        return False
                    if signal is self._BREAK_TRUE:
                        return True
                    if signal is self._CONTINUE:
                        continue
                    # None → fall through to default behaviour

                self._resolve_stack()
                consecutive_passes = 0
                priority_player = self.state.turn_player_index
                if check_game_over_after_resolve:
                    self._check_game_over()
                continue

            # --- Decision ---
            decision = decision_builder(priority_player)
            response = self._ask(decision)
            action_id = response.first

            if action_id is None or action_id == "pass":
                consecutive_passes += 1
                if consecutive_passes >= 2:
                    return False
                priority_player = 1 - priority_player
                continue

            consecutive_passes = 0
            self._execute_action(priority_player, action_id)

            # --- Post-action hook ---
            if on_action_executed is not None:
                signal = on_action_executed()
                if signal is self._BREAK_TRUE:
                    return True

        return False

    def _priority_loop_until_pass(self, allow_actions: bool = False) -> None:
        """Run a priority loop until both players pass with empty stack."""
        self._run_priority_loop(
            lambda pp: self._build_combat_priority_decision(pp, allow_actions=allow_actions),
            check_game_over_after_resolve=True,
        )

    # --- End Phase ---

    def _run_end_phase(self) -> None:
        """End phase procedure (rules 4.4)."""
        tp = self.state.turn_player

        self.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=tp.index,
        ))

        # Clean up continuous effects that expire at end of turn
        self.effect_engine.cleanup_expired_effects(self.state, EffectDuration.END_OF_TURN)
        self.effect_engine.cleanup_zone_effects(self.state)

        # 4.4.3b: May arsenal a card from hand
        if not tp.arsenal and tp.hand:
            options = [
                ActionOption(
                    action_id=f"arsenal_{c.instance_id}",
                    description=f"Arsenal {c.name}",
                    action_type=ActionType.ARSENAL,
                    card_instance_id=c.instance_id,
                )
                for c in tp.hand
            ]
            options.append(self._pass_option("Don't arsenal"))
            decision = Decision(
                player_index=tp.index,
                decision_type=DecisionType.CHOOSE_ARSENAL_CARD,
                prompt="Choose a card to put in arsenal (face-down)",
                options=options,
            )
            response = self._ask(decision)
            if response.first and response.first != "pass":
                instance_id = int(response.first.replace("arsenal_", ""))
                card = tp.find_card(instance_id)
                if card and card in tp.hand:
                    tp.hand.remove(card)
                    card.zone = Zone.ARSENAL
                    card.face_up = False
                    tp.arsenal.append(card)

        # 4.4.3c: ALL players' pitch zones -> bottom of deck
        # TODO: rules say player chooses order (pitch-stacking). Currently random.
        # Should be a Decision when strategic players are implemented.
        for player in self.state.players:
            if player.pitch:
                self.state.rng.shuffle(player.pitch)
                for card in player.pitch:
                    card.zone = Zone.DECK
                player.deck.extend(player.pitch)
                player.pitch.clear()

        # 4.4.3d: Untap all turn player's permanents
        for eq in tp.equipment.values():
            if eq:
                eq.is_tapped = False
        for w in tp.weapons:
            w.is_tapped = False

        # 4.4.3e: ALL players lose all action points and resource points
        for i in range(len(self.state.players)):
            self.state.action_points[i] = 0
            self.state.resource_points[i] = 0

        # 4.4.3f: Draw up to intellect
        intellect = tp.hero.definition.intellect if tp.hero else 4
        cards_to_draw = max(0, (intellect or 4) - len(tp.hand))
        self._draw_cards(tp, cards_to_draw)

        # On first turn, non-turn player also draws up
        if self.state.turn_number == 1:
            ntp = self.state.non_turn_player
            ntp_intellect = ntp.hero.definition.intellect if ntp.hero else 4
            ntp_draw = max(0, (ntp_intellect or 4) - len(ntp.hand))
            self._draw_cards(ntp, ntp_draw)

    # --- Utilities ---

    def _draw_cards(self, player: PlayerState, count: int) -> None:
        """Draw cards from deck to hand via event system."""
        for _ in range(count):
            if not player.deck:
                break
            self.events.emit(GameEvent(
                event_type=EventType.DRAW_CARD,
                target_player=player.index,
            ))

    def _check_rupture_active(self, link: ChainLink) -> bool:
        """Rupture (8.3): check if the current chain link qualifies for Rupture."""
        return self.keyword_engine.check_rupture_active(self.state, link)

    def _perform_opt(self, player_index: int, n: int) -> None:
        """Opt N: look at the top N cards of your deck, put any on the bottom."""
        self.keyword_engine.perform_opt(self.state, player_index, n)

    def _perform_retrieve(self, player_index: int, card_filter=None) -> CardInstance | None:
        """Retrieve: return a card from your graveyard to hand."""
        return self.keyword_engine.perform_retrieve(self.state, player_index, card_filter)

    def _check_game_over(self) -> None:
        """Check if any player's life has reached 0.

        If both players are at 0, the game is a draw (4.5.4).
        """
        if self.state.game_over:
            return
        dead = [ps for ps in self.state.players if ps.life_total <= 0]
        if len(dead) >= 2:
            # Both dead — draw
            self.state.winner = None
            self.state.game_over = True
            log.info("Both players defeated! Game is a draw!")
        elif len(dead) == 1:
            self.state.winner = 1 - dead[0].index
            self.state.game_over = True
            log.info(f"Player {dead[0].index} defeated! Player {1 - dead[0].index} wins!")

    def _pitch_to_pay(self, player_index: int, cost: int) -> None:
        """Pitch cards from hand to generate resources, then pay the cost."""
        self.cost_manager.pitch_to_pay(self.state, player_index, cost)

    def _ask(self, decision: Decision) -> PlayerResponse:
        """Route a decision to the appropriate player interface."""
        return self.interfaces[decision.player_index].decide(self.state, decision)
