from __future__ import annotations

import logging
from dataclasses import dataclass, field
from random import Random

from htc.cards.card import CardDefinition
from htc.cards.card_db import CardDatabase
from htc.cards.instance import CardInstance
from htc.decks.deck_list import DeckList
from htc.engine.actions import ActionOption, Decision, PlayerResponse
from htc.engine.combat import CombatManager
from htc.engine.continuous import EffectDuration
from htc.engine.cost import (
    build_pitch_decision,
    calculate_play_cost,
    can_pay_action_cost,
    can_pay_resource_cost,
    pay_action_cost,
    pay_resource_cost,
    pitch_card,
)
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
from htc.state.game_state import GameState, Layer
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
        self.events = EventBus()
        self._register_event_handlers()

    def _register_event_handlers(self) -> None:
        """Register handlers for core game events."""
        self.events.register_handler(EventType.DEAL_DAMAGE, self._handle_damage)
        self.events.register_handler(EventType.GAIN_LIFE, self._handle_gain_life)
        self.events.register_handler(EventType.DRAW_CARD, self._handle_draw_card)

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
                else:
                    self.state.move_card(card, Zone.GRAVEYARD)
            elif card.definition.is_attack_reaction:
                # Attack reaction resolves: apply effect, then graveyard
                # TODO: apply attack reaction effects
                self.state.move_card(card, Zone.GRAVEYARD)
                log.info(f"  Attack reaction: {card.name}{card.definition.color_label}")
            elif card.definition.is_permanent_when_resolved:
                # Permanent subtypes (auras, items, allies, etc.) enter the arena (1.3.3)
                card.zone = Zone.PERMANENT
                player.permanents.append(card)
                log.info(f"  Permanent: {card.name}{card.definition.color_label} enters the arena")
            else:
                # Non-attack, non-reaction, non-permanent: resolve effect, then graveyard
                self.state.move_card(card, Zone.GRAVEYARD)

            # Go again from resolved layer
            if layer.has_go_again and not card.definition.is_attack:
                self.state.action_points[layer.controller_index] += 1

    def _build_action_decision(self, player_index: int) -> Decision:
        """Build the list of legal actions for the active player (non-combat)."""
        options: list[ActionOption] = []
        player = self.state.players[player_index]
        is_turn_player = player_index == self.state.turn_player_index

        if is_turn_player and self.stack_mgr.is_empty(self.state):
            # Can play action cards from hand and arsenal (7.0.1a: only when chain is closed)
            for card in player.hand + player.arsenal:
                if self._can_play_card(player_index, card):
                    color_str = card.definition.color_label
                    options.append(ActionOption(
                        action_id=f"play_{card.instance_id}",
                        description=f"Play {card.name}{color_str}",
                        action_type=ActionType.PLAY_CARD,
                        card_instance_id=card.instance_id,
                    ))

            # Weapon activations (1.4.3): untapped weapons with attack ability
            for weapon in player.weapons:
                if self._can_activate_weapon(player_index, weapon):
                    options.append(ActionOption(
                        action_id=f"activate_{weapon.instance_id}",
                        description=f"Attack with {weapon.name} (power={weapon.base_power or 0})",
                        action_type=ActionType.ACTIVATE_ABILITY,
                        card_instance_id=weapon.instance_id,
                    ))

        # Instants can be played when you have priority
        self._add_instant_options(options, player_index)
        options.append(self._pass_option())

        return Decision(
            player_index=player_index,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Choose an action",
            options=options,
        )

    def _add_instant_options(self, options: list[ActionOption], player_index: int) -> None:
        """Append playable instant options from the player's hand, deduplicating."""
        player = self.state.players[player_index]
        for card in player.hand:
            if card.definition.is_instant and self._can_play_instant(player_index, card):
                if not any(o.card_instance_id == card.instance_id for o in options):
                    options.append(ActionOption(
                        action_id=f"play_{card.instance_id}",
                        description=f"Play {card.name}{card.definition.color_label} (instant)",
                        action_type=ActionType.PLAY_CARD,
                        card_instance_id=card.instance_id,
                    ))

    @staticmethod
    def _pass_option(description: str = "Pass") -> ActionOption:
        """Create a pass action option."""
        return ActionOption(action_id="pass", description=description, action_type=ActionType.PASS)

    def _can_play_card(self, player_index: int, card: CardInstance) -> bool:
        """Check if a player can legally play this card as an action."""
        defn = card.definition

        # Must be a playable type
        if not (defn.is_action or defn.is_instant):
            return False

        # Resource cards and blocks can't be played from hand
        if defn.types & {CardType.RESOURCE, CardType.BLOCK}:
            return False

        # Action cards need action points
        if not can_pay_action_cost(self.state, player_index, card):
            return False

        # Must be able to pay resource cost
        if not can_pay_resource_cost(self.state, player_index, card, self.effect_engine):
            return False

        return True

    def _can_play_instant(self, player_index: int, card: CardInstance) -> bool:
        """Check if a player can play an instant (no action point needed)."""
        if not card.definition.is_instant:
            return False
        return can_pay_resource_cost(self.state, player_index, card, self.effect_engine)

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
        while self.state.resource_points[player_index] < resource_cost:
            pitch_decision = build_pitch_decision(
                self.state, player_index,
                resource_cost - self.state.resource_points[player_index],
            )
            if pitch_decision is None:
                break
            response = self._ask(pitch_decision)
            if response.first:
                pitch_id = int(response.first.replace("pitch_", ""))
                pitch_target = player.find_card(pitch_id)
                if pitch_target:
                    pitch_card(self.state, player_index, pitch_target)

        pay_resource_cost(self.state, player_index, resource_cost)

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

        color_str = card.definition.color_label

        # If it's an attack and combat chain is closed, open it (7.0.2a)
        if card.definition.is_attack and not self.state.combat_chain.is_open:
            self.combat_mgr.open_chain(self.state)
            log.info(f"  Play attack: {card.name}{color_str} (power={self.effect_engine.get_modified_power(self.state, card)})")
        elif card.definition.is_attack:
            log.info(f"  Chain attack: {card.name}{color_str} (power={self.effect_engine.get_modified_power(self.state, card)})")
        else:
            log.info(f"  Play: {card.name}{color_str}")

    # --- Weapon Activation (rules 1.4.3) ---

    def _can_activate_weapon(self, player_index: int, weapon: CardInstance) -> bool:
        """Check if a weapon can be activated (untapped, has AP, can pay cost)."""
        if weapon.is_tapped:
            return False
        # Weapons need an action point to activate
        if self.state.action_points[player_index] < 1:
            return False
        # Must be able to pay resource cost
        cost = self.effect_engine.get_modified_cost(self.state, weapon)
        if cost > 0:
            available = self.state.resource_points[player_index]
            player = self.state.players[player_index]
            for c in player.hand:
                if c.pitch is not None:
                    available += c.pitch
            if available < cost:
                return False
        return True

    def _activate_weapon(self, player_index: int, weapon: CardInstance) -> None:
        """Activate a weapon to create an attack proxy on the stack (rules 1.4.3).

        Sequence: Tap weapon → Pay costs → Create attack proxy → Put on stack.
        """
        player = self.state.players[player_index]

        # Tap the weapon (enforces once-per-turn)
        weapon.is_tapped = True

        # Pay action point cost
        self.state.action_points[player_index] -= 1

        # Pay resource cost
        resource_cost = self.effect_engine.get_modified_cost(self.state, weapon)
        while self.state.resource_points[player_index] < resource_cost:
            pitch_decision = build_pitch_decision(
                self.state, player_index,
                resource_cost - self.state.resource_points[player_index],
            )
            if pitch_decision is None:
                break
            response = self._ask(pitch_decision)
            if response.first:
                pitch_id = int(response.first.replace("pitch_", ""))
                pitch_target = player.find_card(pitch_id)
                if pitch_target:
                    pitch_card(self.state, player_index, pitch_target)

        pay_resource_cost(self.state, player_index, resource_cost)

        # Create attack proxy — a synthetic card with the weapon's power and keywords
        proxy = self._create_attack_proxy(weapon, player_index)

        # Put proxy on the stack
        layer = self.stack_mgr.add_card_layer(self.state, proxy, player_index)
        layer.has_go_again = weapon.definition.has_go_again

        # Update counters
        player.turn_counters.num_attacks_played += 1
        player.turn_counters.num_weapon_attacks += 1
        player.turn_counters.has_attacked = True

        # Open combat chain if needed
        if not self.state.combat_chain.is_open:
            self.combat_mgr.open_chain(self.state)

        log.info(f"  Weapon attack: {weapon.name} (power={weapon.base_power or 0})")

    def _create_attack_proxy(self, weapon: CardInstance, owner_index: int) -> CardInstance:
        """Create a transient attack card representing a weapon attack."""
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
            keywords=weapon.definition.keywords,
            functional_text="",
            type_text="Weapon attack proxy",
            keyword_values=weapon.definition.keyword_values,
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
        link.has_go_again = has_go_again

        # If this is a weapon proxy, set the weapon as attack_source
        if attack_card.is_proxy and attack_card.proxy_source_id is not None:
            link.attack_source = self.state.find_card(attack_card.proxy_source_id)

        # Emit attack declared event (7.2.4)
        self.events.emit(GameEvent(
            event_type=EventType.ATTACK_DECLARED,
            source=attack_card,
            target_player=defender_index,
            data={"chain_link": link, "attacker_index": attacker_index},
        ))

    def _attack_step(self) -> None:
        """Attack Step (7.2): Attack resolves onto combat chain.
        'Attack' event occurs. Turn player gets priority."""
        link = self.state.combat_chain.active_link
        if link is None:
            return

        # 7.2.4: "attack" event occurs — TODO: triggered effects

        # 7.2.5: Turn player gets priority
        safety = 0
        consecutive_passes = 0
        priority_player = self.state.turn_player_index

        while not self.state.game_over and safety < MAX_PRIORITY_PASSES:
            safety += 1

            if not self.stack_mgr.is_empty(self.state):
                self._resolve_stack()
                consecutive_passes = 0
                priority_player = self.state.turn_player_index
                continue

            decision = self._build_combat_priority_decision(priority_player, allow_actions=False)
            response = self._ask(decision)
            action_id = response.first

            if action_id is None or action_id == "pass":
                consecutive_passes += 1
                if consecutive_passes >= 2:
                    break
                priority_player = 1 - priority_player
                continue

            consecutive_passes = 0
            self._execute_action(priority_player, action_id)

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

        # Cards from hand with defense value (7.3.2a)
        for card in player.hand:
            if card.base_defense is not None and not card.definition.is_defense_reaction:
                color_str = card.definition.color_label
                mod_def = self.effect_engine.get_modified_defense(self.state, card)
                options.append(ActionOption(
                    action_id=f"defend_{card.instance_id}",
                    description=f"Defend with {card.name}{color_str} (defense={mod_def})",
                    action_type=ActionType.DEFEND_WITH,
                    card_instance_id=card.instance_id,
                ))

        # Equipment (public permanents) (7.3.2a) — not limited by Dominate
        for slot, eq in player.equipment.items():
            if eq and not eq.is_tapped and eq.base_defense is not None:
                mod_def = self.effect_engine.get_modified_defense(self.state, eq)
                options.append(ActionOption(
                    action_id=f"defend_{eq.instance_id}",
                    description=f"Defend with {eq.name} (defense={mod_def})",
                    action_type=ActionType.DEFEND_WITH,
                    card_instance_id=eq.instance_id,
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
                    player.hand.remove(card)
                    player.turn_counters.num_cards_defended_from_hand += 1
                    hand_cards_defended += 1
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

        safety = 0
        consecutive_passes = 0
        priority_player = self.state.turn_player_index

        while not self.state.game_over and safety < MAX_PRIORITY_PASSES:
            safety += 1

            if not self.stack_mgr.is_empty(self.state):
                self._resolve_stack()
                consecutive_passes = 0
                priority_player = self.state.turn_player_index
                self._check_game_over()
                continue

            # Priority alternates between players (7.4.2)
            decision = self._build_reaction_decision(priority_player, attacker_index, defender_index)
            response = self._ask(decision)
            action_id = response.first

            if action_id is None or action_id == "pass":
                consecutive_passes += 1
                if consecutive_passes >= 2:
                    break
                priority_player = 1 - priority_player
                continue

            consecutive_passes = 0
            self._execute_action(priority_player, action_id)

    def _build_reaction_decision(
        self, priority_player: int, attacker_index: int, defender_index: int
    ) -> Decision:
        """Build decision for reaction step — attack reactions for attacker,
        defense reactions for defender, instants for either."""
        options: list[ActionOption] = []
        player = self.state.players[priority_player]

        for card in player.hand:
            # Attack reactions: only attacker can play (7.4.2a)
            if card.definition.is_attack_reaction and priority_player == attacker_index:
                if can_pay_resource_cost(self.state, priority_player, card, self.effect_engine):
                    color_str = card.definition.color_label
                    options.append(ActionOption(
                        action_id=f"play_{card.instance_id}",
                        description=f"Play {card.name}{color_str} (attack reaction)",
                        action_type=ActionType.PLAY_CARD,
                        card_instance_id=card.instance_id,
                    ))

            # Defense reactions: only defender can play (7.4.2b)
            if card.definition.is_defense_reaction and priority_player == defender_index:
                if can_pay_resource_cost(self.state, priority_player, card, self.effect_engine):
                    color_str = card.definition.color_label
                    options.append(ActionOption(
                        action_id=f"play_{card.instance_id}",
                        description=f"Play {card.name}{color_str} (defense reaction)",
                        action_type=ActionType.PLAY_CARD,
                        card_instance_id=card.instance_id,
                    ))

        # Instants: either player can play
        self._add_instant_options(options, priority_player)
        options.append(self._pass_option())

        return Decision(
            player_index=priority_player,
            decision_type=DecisionType.PLAY_REACTION_OR_PASS,
            prompt="Play a reaction or pass",
            options=options,
        )

    def _damage_step(self) -> None:
        """Damage Step (7.5): Calculate and apply damage."""
        link = self.state.combat_chain.active_link
        if link is None:
            return

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

            actual_damage = event.amount if not event.cancelled else 0
            link.damage_dealt = actual_damage
            if actual_damage > 0:
                link.hit = True
                target = self.state.players[link.attack_target_index]
                log.info(f"  Hit for {actual_damage} damage! (P{target.index} life: {target.life_total})")

                # Emit hit event
                self.events.emit(GameEvent(
                    event_type=EventType.HIT,
                    source=link.active_attack,
                    target_player=link.attack_target_index,
                    amount=actual_damage,
                    data={"chain_link": link},
                ))
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
        # Check modified keywords dynamically (effects may have granted/removed go again)
        has_go_again = link.has_go_again
        if link.active_attack:
            attack_keywords = self.effect_engine.get_modified_keywords(self.state, link.active_attack)
            has_go_again = Keyword.GO_AGAIN in attack_keywords
        if has_go_again:
            self.state.action_points[attacker_index] += 1

        # 7.6.3: Turn player gets priority
        # 7.6.3a: Turn player may play another attack during Resolution Step
        safety = 0
        consecutive_passes = 0
        priority_player = self.state.turn_player_index

        while not self.state.game_over and safety < MAX_PRIORITY_PASSES:
            safety += 1

            if not self.stack_mgr.is_empty(self.state):
                top = self.stack_mgr.top(self.state)
                if top and top.card and top.card.definition.is_attack:
                    # New attack on stack — return True to loop back to combat steps
                    return True
                self._resolve_stack()
                consecutive_passes = 0
                priority_player = self.state.turn_player_index
                continue

            decision = self._build_resolution_decision(priority_player)
            response = self._ask(decision)
            action_id = response.first

            if action_id is None or action_id == "pass":
                consecutive_passes += 1
                if consecutive_passes >= 2:
                    # 7.6.4: both pass — move to Close Step
                    return False
                priority_player = 1 - priority_player
                continue

            consecutive_passes = 0
            self._execute_action(priority_player, action_id)

            # Check if an attack was just put on the stack
            if not self.stack_mgr.is_empty(self.state):
                top = self.stack_mgr.top(self.state)
                if top and top.card and top.card.definition.is_attack:
                    return True

        return False

    def _build_resolution_decision(self, player_index: int) -> Decision:
        """Build decision for resolution step — can play attacks (if turn player)
        and instants."""
        options: list[ActionOption] = []
        player = self.state.players[player_index]
        is_turn_player = player_index == self.state.turn_player_index

        if is_turn_player:
            # Can play attack cards to continue the chain (7.6.3a)
            for card in player.hand + player.arsenal:
                if card.definition.is_attack and self._can_play_card(player_index, card):
                    color_str = card.definition.color_label
                    options.append(ActionOption(
                        action_id=f"play_{card.instance_id}",
                        description=f"Play {card.name}{color_str}",
                        action_type=ActionType.PLAY_CARD,
                        card_instance_id=card.instance_id,
                    ))

        # Instants for any player
        self._add_instant_options(options, player_index)
        options.append(self._pass_option())

        return Decision(
            player_index=player_index,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Continue combat chain or pass",
            options=options,
        )

    def _close_step(self) -> None:
        """Close Step (7.7): Combat chain closes, cards go to graveyard."""
        # 7.7.3: "combat chain closes" event occurs
        self.events.emit(GameEvent(
            event_type=EventType.COMBAT_CHAIN_CLOSES,
        ))

        self.combat_mgr.close_chain(self.state)
        self.effect_engine.cleanup_expired_effects(self.state, EffectDuration.END_OF_COMBAT)
        log.debug("  Combat chain closed")

    def _build_combat_priority_decision(
        self, player_index: int, allow_actions: bool = False
    ) -> Decision:
        """Build a priority decision during combat (instants only, unless allow_actions)."""
        options: list[ActionOption] = []
        player = self.state.players[player_index]

        if allow_actions:
            for card in player.hand + player.arsenal:
                if self._can_play_card(player_index, card):
                    color_str = card.definition.color_label
                    options.append(ActionOption(
                        action_id=f"play_{card.instance_id}",
                        description=f"Play {card.name}{color_str}",
                        action_type=ActionType.PLAY_CARD,
                        card_instance_id=card.instance_id,
                    ))

        # Instants
        self._add_instant_options(options, player_index)
        options.append(self._pass_option())

        return Decision(
            player_index=player_index,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Play an instant or pass",
            options=options,
        )

    def _priority_loop_until_pass(self, allow_actions: bool = False) -> None:
        """Run a priority loop until both players pass with empty stack."""
        safety = 0
        consecutive_passes = 0
        priority_player = self.state.turn_player_index

        while not self.state.game_over and safety < MAX_PRIORITY_PASSES:
            safety += 1

            if not self.stack_mgr.is_empty(self.state):
                self._resolve_stack()
                consecutive_passes = 0
                priority_player = self.state.turn_player_index
                self._check_game_over()
                continue

            decision = self._build_combat_priority_decision(priority_player, allow_actions=allow_actions)
            response = self._ask(decision)
            action_id = response.first

            if action_id is None or action_id == "pass":
                consecutive_passes += 1
                if consecutive_passes >= 2:
                    break
                priority_player = 1 - priority_player
                continue

            consecutive_passes = 0
            self._execute_action(priority_player, action_id)

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

    def _ask(self, decision: Decision) -> PlayerResponse:
        """Route a decision to the appropriate player interface."""
        return self.interfaces[decision.player_index].decide(self.state, decision)
