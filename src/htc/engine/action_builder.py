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
from htc.enums import ActionType, CardType, DecisionType, Keyword

if TYPE_CHECKING:
    from htc.engine.effects import EffectEngine
    from htc.state.game_state import GameState

log = logging.getLogger(__name__)


class ActionBuilder:
    """Builds Decision objects describing the legal actions available to a player.

    Stateless — all context comes via method parameters.
    """

    def __init__(self, effect_engine: EffectEngine) -> None:
        self.effect_engine = effect_engine

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
                    color_str = card.definition.color_label
                    options.append(ActionOption(
                        action_id=f"play_{card.instance_id}",
                        description=f"Play {card.name}{color_str}",
                        action_type=ActionType.PLAY_CARD,
                        card_instance_id=card.instance_id,
                    ))

            # Weapon activations (1.4.3): untapped weapons
            for weapon in player.weapons:
                if self._can_activate_weapon(state, player_index, weapon):
                    if weapon.definition.arcane and weapon.definition.arcane > 0:
                        desc = f"Activate {weapon.name} (arcane={weapon.definition.arcane})"
                    else:
                        desc = f"Attack with {weapon.name} (power={weapon.base_power or 0})"
                    options.append(ActionOption(
                        action_id=f"activate_{weapon.instance_id}",
                        description=desc,
                        action_type=ActionType.ACTIVATE_ABILITY,
                        card_instance_id=weapon.instance_id,
                    ))

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
                    options.append(ActionOption(
                        action_id=f"play_{card.instance_id}",
                        description=f"Play {card.name}{card.definition.color_label} (instant)",
                        action_type=ActionType.PLAY_CARD,
                        card_instance_id=card.instance_id,
                    ))

    def build_combat_priority_decision(
        self, state: GameState, player_index: int, allow_actions: bool = False
    ) -> Decision:
        """Build a priority decision during combat (instants only, unless allow_actions)."""
        options: list[ActionOption] = []
        player = state.players[player_index]

        if allow_actions:
            for card in player.hand + player.arsenal:
                if self.can_play_card(state, player_index, card):
                    color_str = card.definition.color_label
                    options.append(ActionOption(
                        action_id=f"play_{card.instance_id}",
                        description=f"Play {card.name}{color_str}",
                        action_type=ActionType.PLAY_CARD,
                        card_instance_id=card.instance_id,
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
                    color_str = card.definition.color_label
                    options.append(ActionOption(
                        action_id=f"play_{card.instance_id}",
                        description=f"Play {card.name}{color_str} (attack reaction)",
                        action_type=ActionType.PLAY_CARD,
                        card_instance_id=card.instance_id,
                    ))

            # Defense reactions: only defender can play (7.4.2b)
            if card.definition.is_defense_reaction and priority_player == defender_index:
                if can_pay_resource_cost(state, priority_player, card, self.effect_engine):
                    color_str = card.definition.color_label
                    options.append(ActionOption(
                        action_id=f"play_{card.instance_id}",
                        description=f"Play {card.name}{color_str} (defense reaction)",
                        action_type=ActionType.PLAY_CARD,
                        card_instance_id=card.instance_id,
                    ))

        # Instants: either player can play
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
                    color_str = card.definition.color_label
                    options.append(ActionOption(
                        action_id=f"play_{card.instance_id}",
                        description=f"Play {card.name}{color_str}",
                        action_type=ActionType.PLAY_CARD,
                        card_instance_id=card.instance_id,
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
        if cost > 0:
            available = state.resource_points[player_index]
            player = state.players[player_index]
            for c in player.hand:
                if c.pitch is not None:
                    available += c.pitch
            if available < cost:
                return False
        return True
