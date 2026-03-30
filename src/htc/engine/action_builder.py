"""ActionBuilder — constructs legal action sets for player decisions.

Extracted from Game to keep decision-building logic separate from
game-loop orchestration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from htc.cards.instance import CardInstance
from htc.engine.actions import ActionOption, Decision
from htc.engine.cost import can_pay_action_cost, can_pay_resource_cost
from htc.enums import ActionType, CardType, DecisionType, EquipmentSlot, Zone

if TYPE_CHECKING:
    from htc.engine.abilities import AbilityRegistry
    from htc.engine.effects import EffectEngine
    from htc.state.game_state import GameState

log = logging.getLogger(__name__)


class ActionBuilder:
    """Builds Decision objects describing the legal actions available to a player.

    Stateless — all context comes via method parameters.
    """

    def __init__(self, effect_engine: EffectEngine, ability_registry: AbilityRegistry | None = None) -> None:
        self.effect_engine = effect_engine
        self.ability_registry = ability_registry

    # --- Public decision builders ---

    def build_action_decision(
        self, state: GameState, player_index: int, stack_is_empty: bool
    ) -> Decision:
        """Build the list of legal actions for the active player (non-combat)."""
        options: list[ActionOption] = []
        player = state.players[player_index]
        is_turn_player = player_index == state.turn_player_index

        if is_turn_player and stack_is_empty:
            # Can play action cards from hand and arsenal (7.0.1a: only when chain is closed)
            for card in player.hand + player.arsenal:
                if self.can_play_card(state, player_index, card):
                    options.append(ActionOption.play_card(
                        card.instance_id, card.name, card.definition.color_label,
                    ))

            # Playable-from-banish cards (e.g. Trap-Door, Under the Trap-Door)
            for card in self._get_playable_from_banish(state, player_index):
                if self.can_play_card(state, player_index, card):
                    options.append(ActionOption.play_card(
                        card.instance_id, card.name, card.definition.color_label,
                    ))

            # Weapon activations (1.4.3): untapped weapons
            for weapon in player.weapons:
                if self._can_activate_weapon(state, player_index, weapon):
                    if weapon.definition.arcane and weapon.definition.arcane > 0:
                        desc = f"Activate {weapon.name} (arcane={weapon.definition.arcane})"
                    else:
                        desc = f"Attack with {weapon.name} (power={weapon.base_power or 0})"
                    options.append(ActionOption.activate(weapon.instance_id, desc))

        # Instants can be played when you have priority
        self.add_instant_options(options, state, player_index)
        options.append(self.pass_option())

        return Decision(
            player_index=player_index,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Choose an action",
            options=options,
        )

    def add_instant_options(
        self, options: list[ActionOption], state: GameState, player_index: int
    ) -> None:
        """Append playable instant options from the player's hand, deduplicating."""
        player = state.players[player_index]
        for card in player.hand:
            if card.definition.is_instant and self.can_play_instant(state, player_index, card):
                if not any(o.card_instance_id == card.instance_id for o in options):
                    options.append(ActionOption.play_card(
                        card.instance_id, card.name, card.definition.color_label, suffix="instant",
                    ))
        # Instant-discard cards (e.g. Under the Trap-Door): cards in hand with
        # a registered instant_discard_effect can be discarded to activate.
        # These coexist with normal play options (a card can be both played
        # as an attack OR discarded for its instant ability).
        if self.ability_registry:
            for card in player.hand:
                handler = self.ability_registry.lookup("instant_discard_effect", card.name)
                if handler is not None:
                    # Check no duplicate activate for this card
                    if not any(
                        o.card_instance_id == card.instance_id
                        and o.action_type == ActionType.ACTIVATE_ABILITY
                        for o in options
                    ):
                        options.append(ActionOption.activate(
                            card.instance_id,
                            f"Discard {card.name} (instant ability)",
                        ))

        # Equipment instants can be activated whenever you have priority
        if self.ability_registry:
            self._add_equipment_instant_options(options, state, player_index)

    def build_combat_priority_decision(
        self, state: GameState, player_index: int, allow_actions: bool = False
    ) -> Decision:
        """Build a priority decision during combat (instants only, unless allow_actions)."""
        options: list[ActionOption] = []
        player = state.players[player_index]

        if allow_actions:
            for card in player.hand + player.arsenal:
                if self.can_play_card(state, player_index, card):
                    options.append(ActionOption.play_card(
                        card.instance_id, card.name, card.definition.color_label,
                    ))

        # Instants
        self.add_instant_options(options, state, player_index)
        options.append(self.pass_option())

        return Decision(
            player_index=player_index,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Play an instant or pass",
            options=options,
        )

    def build_reaction_decision(
        self,
        state: GameState,
        priority_player: int,
        attacker_index: int,
        defender_index: int,
    ) -> Decision:
        """Build decision for reaction step — attack reactions for attacker,
        defense reactions for defender, instants for either."""
        options: list[ActionOption] = []
        player = state.players[priority_player]

        for card in player.hand:
            # Attack reactions: only attacker can play (7.4.2a)
            if card.definition.is_attack_reaction and priority_player == attacker_index:
                if can_pay_resource_cost(state, priority_player, card, self.effect_engine):
                    options.append(ActionOption.play_card(
                        card.instance_id, card.name, card.definition.color_label,
                        suffix="attack reaction",
                    ))

            # Defense reactions: only defender can play (7.4.2b)
            if card.definition.is_defense_reaction and priority_player == defender_index:
                if can_pay_resource_cost(state, priority_player, card, self.effect_engine):
                    options.append(ActionOption.play_card(
                        card.instance_id, card.name, card.definition.color_label,
                        suffix="defense reaction",
                    ))

        # Defense reactions from banish (e.g. traps banished by Trap-Door)
        if priority_player == defender_index:
            for card in self._get_playable_from_banish(state, priority_player):
                if card.definition.is_defense_reaction:
                    if can_pay_resource_cost(state, priority_player, card, self.effect_engine):
                        options.append(ActionOption.play_card(
                            card.instance_id, card.name, card.definition.color_label,
                            suffix="defense reaction",
                        ))

        # Equipment attack reactions: only attacker can use (e.g. Tide Flippers, Stalker's Steps)
        if priority_player == attacker_index and self.ability_registry:
            self._add_equipment_reaction_options(options, state, priority_player)

        # Instants (including equipment instants): either player can play
        self.add_instant_options(options, state, priority_player)
        options.append(self.pass_option())

        return Decision(
            player_index=priority_player,
            decision_type=DecisionType.PLAY_REACTION_OR_PASS,
            prompt="Play a reaction or pass",
            options=options,
        )

    def build_resolution_decision(
        self, state: GameState, player_index: int
    ) -> Decision:
        """Build decision for resolution step — can play attacks (if turn player)
        and instants."""
        options: list[ActionOption] = []
        player = state.players[player_index]
        is_turn_player = player_index == state.turn_player_index

        if is_turn_player:
            # Can play attack cards to continue the chain (7.6.3a)
            for card in player.hand + player.arsenal:
                if card.definition.is_attack and self.can_play_card(state, player_index, card):
                    options.append(ActionOption.play_card(
                        card.instance_id, card.name, card.definition.color_label,
                    ))

            # Playable-from-banish attack cards
            for card in self._get_playable_from_banish(state, player_index):
                if card.definition.is_attack and self.can_play_card(state, player_index, card):
                    options.append(ActionOption.play_card(
                        card.instance_id, card.name, card.definition.color_label,
                    ))

        # Instants for any player
        self.add_instant_options(options, state, player_index)
        options.append(self.pass_option())

        return Decision(
            player_index=player_index,
            decision_type=DecisionType.PLAY_OR_PASS,
            prompt="Continue combat chain or pass",
            options=options,
        )

    # --- Card legality checks ---

    def can_play_card(self, state: GameState, player_index: int, card: CardInstance) -> bool:
        """Check if a player can legally play this card as an action."""
        defn = card.definition

        # Must be a playable type
        if not (defn.is_action or defn.is_instant):
            return False

        # Resource cards and blocks can't be played from hand
        if defn.types & {CardType.RESOURCE, CardType.BLOCK}:
            return False

        # Action cards need action points
        if not can_pay_action_cost(state, player_index, card):
            return False

        # Must be able to pay resource cost
        if not can_pay_resource_cost(state, player_index, card, self.effect_engine):
            return False

        return True

    def can_play_instant(self, state: GameState, player_index: int, card: CardInstance) -> bool:
        """Check if a player can play an instant (no action point needed)."""
        if not card.definition.is_instant:
            return False
        return can_pay_resource_cost(state, player_index, card, self.effect_engine)

    # --- Helpers ---

    @staticmethod
    def pass_option(description: str = "Pass") -> ActionOption:
        """Create a pass action option."""
        return ActionOption(action_id="pass", description=description, action_type=ActionType.PASS)

    @staticmethod
    def _can_activate_weapon(state: GameState, player_index: int, weapon: CardInstance) -> bool:
        """Check if a weapon can be activated (untapped, has AP, can pay cost)."""
        if weapon.is_tapped:
            return False
        # Weapons need an action point to activate
        if state.action_points[player_index] < 1:
            return False
        # Must be able to pay resource cost
        cost = weapon.definition.cost if weapon.definition.cost is not None else weapon.definition.functional_text.count("{r}")
        # Orb-Weaver reduces Graphene Chelicera activation cost by 1
        cost = ActionBuilder._apply_weapon_cost_reduction(state, player_index, weapon, cost)
        if cost > 0:
            available = state.resource_points[player_index]
            player = state.players[player_index]
            for c in player.hand:
                if c.pitch is not None:
                    available += c.pitch
            if available < cost:
                return False
        return True

    @staticmethod
    def _apply_weapon_cost_reduction(
        state: GameState, player_index: int, weapon: CardInstance, cost: int,
    ) -> int:
        """Apply hero-based weapon activation cost reductions.

        Orb-Weaver: Graphene Chelicera costs {r} less to activate.
        """
        player = state.players[player_index]
        if (
            player.hero
            and player.hero.name == "Arakni, Orb-Weaver"
            and weapon.name == "Graphene Chelicera"
        ):
            cost = max(0, cost - 1)
        return cost

    # --- Equipment ability helpers ---

    def _add_equipment_reaction_options(
        self, options: list[ActionOption], state: GameState, player_index: int
    ) -> None:
        """Add equipment attack reaction options (e.g. Tide Flippers, Stalker's Steps).

        Equipment with registered attack_reaction_effect handlers are offered
        as activate options during the reaction step.
        """
        if not self.ability_registry:
            return
        player = state.players[player_index]
        for _slot, eq in player.equipment.items():
            if eq is None:
                continue
            handler = self.ability_registry.lookup("attack_reaction_effect", eq.name)
            if handler is None:
                continue
            # Already in options?
            if any(o.card_instance_id == eq.instance_id for o in options):
                continue
            options.append(ActionOption.activate(
                eq.instance_id, f"Activate {eq.name} (attack reaction)",
            ))

    def _add_equipment_instant_options(
        self, options: list[ActionOption], state: GameState, player_index: int
    ) -> None:
        """Add equipment instant activation options (e.g. Dragonscaler Flight Path).

        Equipment with registered equipment_instant_effect handlers are offered
        as activate options whenever the player has priority.  A cost checker
        callback may be registered on the equipment to gate affordability.
        """
        if not self.ability_registry:
            return
        player = state.players[player_index]
        for _slot, eq in player.equipment.items():
            if eq is None:
                continue
            handler = self.ability_registry.lookup("equipment_instant_effect", eq.name)
            if handler is None:
                continue
            # Already in options?
            if any(o.card_instance_id == eq.instance_id for o in options):
                continue
            # Check preconditions (e.g. Dragonscaler needs active Draconic attack)
            if not self._can_use_equipment_instant(state, player_index, eq):
                continue
            # Check affordability via the equipment cost checker (if registered)
            cost = self._get_equipment_instant_cost(state, player_index, eq)
            if cost is not None and not self._can_afford_resource_cost(state, player_index, cost):
                continue
            options.append(ActionOption.activate(
                eq.instance_id,
                f"Activate {eq.name} (instant, cost={cost if cost is not None else '?'})",
            ))

    def _get_equipment_instant_cost(
        self, state: GameState, player_index: int, equipment: CardInstance,
    ) -> int | None:
        """Get the dynamic resource cost for an equipment instant activation.

        Returns the cost in resources, or None if unknown.
        """
        # Dragonscaler Flight Path: base 3, reduced by Draconic chain link count
        if equipment.name == "Dragonscaler Flight Path":
            draconic_count = self._count_draconic_chain_links(state, player_index)
            return max(0, 3 - draconic_count)
        return None

    def _can_use_equipment_instant(
        self, state: GameState, player_index: int, equipment: CardInstance,
    ) -> bool:
        """Check additional preconditions for equipment instant activation.

        Beyond cost affordability, some equipment instants require specific
        game state (e.g. Dragonscaler needs an active Draconic attack).
        """
        if equipment.name == "Dragonscaler Flight Path":
            # Must have an active Draconic attack on the chain
            link = state.combat_chain.active_link
            if link is None or link.active_attack is None:
                return False
            atk = link.active_attack
            if atk.owner_index != player_index:
                return False
            from htc.enums import SuperType
            if SuperType.DRACONIC not in self.effect_engine.get_modified_supertypes(state, atk):
                return False
        return True

    def _count_draconic_chain_links(self, state: GameState, player_index: int) -> int:
        """Count Draconic chain links controlled by a player on the combat chain."""
        from htc.enums import SuperType
        count = 0
        if not state.combat_chain.is_open:
            return 0
        for link in state.combat_chain.chain_links:
            atk = link.active_attack
            if atk is None:
                continue
            if atk.owner_index != player_index:
                continue
            if SuperType.DRACONIC in self.effect_engine.get_modified_supertypes(state, atk):
                count += 1
        return count

    @staticmethod
    def _get_playable_from_banish(state: GameState, player_index: int) -> list[CardInstance]:
        """Get banished cards that are currently marked as playable for this player."""
        player = state.players[player_index]
        playable_ids = {iid for iid, _, _ in player.playable_from_banish}
        return [c for c in player.banished if c.instance_id in playable_ids]

    @staticmethod
    def _can_afford_resource_cost(state: GameState, player_index: int, cost: int) -> bool:
        """Check if a player can afford a given resource cost."""
        if cost <= 0:
            return True
        available = state.resource_points[player_index]
        player = state.players[player_index]
        for c in player.hand:
            if c.pitch is not None:
                available += c.pitch
        return available >= cost
