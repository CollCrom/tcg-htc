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
from htc.engine.cost import (
    build_pitch_decision,
    calculate_play_cost,
    can_pay_action_cost,
    can_pay_resource_cost,
    pay_action_cost,
    pay_resource_cost,
    pitch_card,
)
from htc.engine.stack import StackManager
from htc.enums import (
    ActionType,
    CombatStep,
    DecisionType,
    EquipmentSlot,
    Phase,
    SubType,
    Zone,
)
from htc.player.interface import PlayerInterface
from htc.state.combat_state import ChainLink
from htc.state.game_state import GameState
from htc.state.player_state import PlayerState

log = logging.getLogger(__name__)

MAX_TURNS = 200  # safety valve


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
        self.combat_mgr = CombatManager()

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
        tp.turn_counters.reset()

        # Start Phase (4.2) — no priority
        self.state.phase = Phase.START
        # TODO: start-of-turn triggers

        # Action Phase (4.3)
        self.state.phase = Phase.ACTION
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

    def _run_action_phase(self) -> None:
        """Action phase priority loop (rules 4.3)."""
        consecutive_passes = 0

        while not self.state.game_over:
            if self.state.combat_chain.is_open:
                self._run_combat()
                if self.state.game_over:
                    break
                # After combat closes, turn player gets priority again
                consecutive_passes = 0
                continue

            # Turn player gets priority
            tp_index = self.state.turn_player_index
            decision = self._build_action_decision(tp_index)

            if not decision.options:
                break

            response = self._ask(decision)
            action_id = response.first

            if action_id is None or action_id == "pass":
                consecutive_passes += 1
                # In a 2-player game, if both pass with empty stack and closed chain, action phase ends
                if consecutive_passes >= 2 and self.stack_mgr.is_empty(self.state):
                    break
                continue

            consecutive_passes = 0
            self._execute_action(tp_index, action_id)

    def _build_action_decision(self, player_index: int) -> Decision:
        """Build the list of legal actions for the active player."""
        options: list[ActionOption] = []
        player = self.state.players[player_index]
        is_turn_player = player_index == self.state.turn_player_index

        if is_turn_player and self.stack_mgr.is_empty(self.state):
            # Can play action cards from hand and arsenal
            for card in player.hand + player.arsenal:
                if self._can_play_card(player_index, card):
                    color_str = f" ({card.definition.color.value})" if card.definition.color else ""
                    options.append(ActionOption(
                        action_id=f"play_{card.instance_id}",
                        description=f"Play {card.name}{color_str}",
                        action_type=ActionType.PLAY_CARD,
                        card_instance_id=card.instance_id,
                    ))

        # Always can pass
        options.append(ActionOption(
            action_id="pass",
            description="Pass",
            action_type=ActionType.PASS,
        ))

        return Decision(
            player_index=player_index,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Choose an action",
            options=options,
        )

    def _can_play_card(self, player_index: int, card: CardInstance) -> bool:
        """Check if a player can legally play this card."""
        defn = card.definition

        # Must be a playable type
        if not (defn.is_action or defn.is_instant or defn.is_attack_reaction or defn.is_defense_reaction):
            return False

        # Resource cards and blocks can't be played
        from htc.enums import CardType as CT
        if defn.types & {CT.RESOURCE, CT.BLOCK}:
            return False

        # Action cards need action points
        if not can_pay_action_cost(self.state, player_index, card):
            return False

        # Must be able to pay resource cost
        if not can_pay_resource_cost(self.state, player_index, card):
            return False

        return True

    def _execute_action(self, player_index: int, action_id: str) -> None:
        """Execute a chosen action."""
        if action_id.startswith("play_"):
            instance_id = int(action_id.split("_", 1)[1])
            card = self.state.find_card(instance_id)
            if card:
                self._play_card(player_index, card)

    def _play_card(self, player_index: int, card: CardInstance) -> None:
        """Play a card from hand/arsenal onto the stack."""
        player = self.state.players[player_index]

        # Remove from current zone
        if card in player.hand:
            player.hand.remove(card)
        elif card in player.arsenal:
            player.arsenal.remove(card)

        # Pay action point cost
        pay_action_cost(self.state, player_index, card)

        # Pay resource cost (pitch cards as needed)
        resource_cost = calculate_play_cost(self.state, card)
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

        # Deduct resource cost
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

        # For attack cards: open combat chain and resolve immediately
        if card.definition.is_attack:
            self._resolve_attack(player_index, card)
        else:
            # Non-attack: put on stack, resolve immediately (simplified)
            card.zone = Zone.GRAVEYARD
            player.graveyard.append(card)
            if card.definition.has_go_again:
                self.state.action_points[player_index] += 1

    # --- Combat ---

    def _resolve_attack(self, attacker_index: int, attack_card: CardInstance) -> None:
        """Simplified attack resolution: open chain -> defend -> damage -> close."""
        defender_index = 1 - attacker_index

        # Open combat chain
        if not self.state.combat_chain.is_open:
            self.combat_mgr.open_chain(self.state)

        # Add chain link
        link = self.combat_mgr.add_chain_link(self.state, attack_card, defender_index)
        self.state.combat_step = CombatStep.ATTACK

        color_str = f" ({attack_card.definition.color.value})" if attack_card.definition.color else ""
        log.info(f"  Attack: {attack_card.name}{color_str} (power={attack_card.base_power})")

        # Defend step
        self.state.combat_step = CombatStep.DEFEND
        self._defend_step(defender_index, link)

        # Reaction step (simplified: just pass for now)
        self.state.combat_step = CombatStep.REACTION

        # Damage step
        self.state.combat_step = CombatStep.DAMAGE
        damage = self.combat_mgr.resolve_damage(self.state, link)
        if damage > 0:
            log.info(f"  Hit for {damage} damage!")
        else:
            log.info(f"  Blocked!")

        # Resolution step
        self.state.combat_step = CombatStep.RESOLUTION
        if link.has_go_again:
            self.state.action_points[attacker_index] += 1

        # Close chain (simplified: close after each attack for now)
        self.state.combat_step = CombatStep.CLOSE
        self.combat_mgr.close_chain(self.state)
        self.state.combat_step = None

        self._check_game_over()

    def _run_combat(self) -> None:
        """Full combat resolution when chain is open. For now this is unused
        since _resolve_attack handles the full flow inline."""
        pass

    def _defend_step(self, defender_index: int, link: ChainLink) -> None:
        """Let the defender choose cards to defend with."""
        player = self.state.players[defender_index]
        options: list[ActionOption] = []

        # Cards from hand
        for card in player.hand:
            if card.base_defense is not None:
                color_str = f" ({card.definition.color.value})" if card.definition.color else ""
                options.append(ActionOption(
                    action_id=f"defend_{card.instance_id}",
                    description=f"Defend with {card.name}{color_str} (defense={card.base_defense})",
                    action_type=ActionType.DEFEND_WITH,
                    card_instance_id=card.instance_id,
                ))

        # Equipment
        for slot, eq in player.equipment.items():
            if eq and eq.base_defense is not None and eq.base_defense > 0:
                options.append(ActionOption(
                    action_id=f"defend_{eq.instance_id}",
                    description=f"Defend with {eq.name} (defense={eq.base_defense})",
                    action_type=ActionType.DEFEND_WITH,
                    card_instance_id=eq.instance_id,
                ))

        # Always can pass (choose not to defend)
        options.append(ActionOption(
            action_id="pass",
            description="Don't defend",
            action_type=ActionType.PASS,
        ))

        decision = Decision(
            player_index=defender_index,
            decision_type=DecisionType.CHOOSE_DEFENDERS,
            prompt=f"Defend against {link.active_attack.name if link.active_attack else 'attack'} (power={self.combat_mgr.get_attack_power(self.state, link)})",
            options=options,
            min_selections=1,
            max_selections=len(options),
        )

        response = self._ask(decision)

        for opt_id in response.selected_option_ids:
            if opt_id == "pass":
                continue
            instance_id = int(opt_id.replace("defend_", ""))
            card = player.find_card(instance_id)
            if card:
                # Remove from hand (if from hand)
                if card in player.hand:
                    player.hand.remove(card)
                    player.turn_counters.num_cards_defended_from_hand += 1
                self.combat_mgr.add_defender(self.state, link, card)
                def_color = f" ({card.definition.color.value})" if card.definition.color else ""
                log.info(f"  Defended with: {card.name}{def_color} (defense={card.base_defense})")

    # --- End Phase ---

    def _run_end_phase(self) -> None:
        """End phase procedure (rules 4.4)."""
        tp = self.state.turn_player

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
            options.append(ActionOption(
                action_id="pass",
                description="Don't arsenal",
                action_type=ActionType.PASS,
            ))
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

        # 4.4.3c: Pitch zone -> bottom of deck (any order, simplified: random for now)
        if tp.pitch:
            self.state.rng.shuffle(tp.pitch)
            for card in tp.pitch:
                card.zone = Zone.DECK
            tp.deck.extend(tp.pitch)
            tp.pitch.clear()

        # 4.4.3d: Untap all permanents
        for eq in tp.equipment.values():
            if eq:
                eq.is_tapped = False
        for w in tp.weapons:
            w.is_tapped = False

        # 4.4.3e: Lose all action points and resource points
        self.state.action_points[tp.index] = 0
        self.state.resource_points[tp.index] = 0

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
        """Draw cards from deck to hand."""
        for _ in range(count):
            if not player.deck:
                break
            card = player.deck.pop(0)
            card.zone = Zone.HAND
            player.hand.append(card)
            player.turn_counters.num_cards_drawn += 1

    def _check_game_over(self) -> None:
        """Check if any player's life has reached 0."""
        for ps in self.state.players:
            if ps.life_total <= 0:
                self.state.winner = 1 - ps.index
                self.state.game_over = True
                log.info(f"Player {ps.index} defeated! Player {1 - ps.index} wins!")
                return

    def _ask(self, decision: Decision) -> PlayerResponse:
        """Route a decision to the appropriate player interface."""
        return self.interfaces[decision.player_index].decide(self.state, decision)
