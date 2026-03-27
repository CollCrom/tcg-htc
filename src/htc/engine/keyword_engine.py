"""KeywordEngine — enforcement logic for FaB keywords.

Extracted from Game to isolate keyword-specific rules (Spellvoid,
Phantasm, Piercing, Battleworn, Blade Break, Temper, Rupture, Opt,
Retrieve) from game-loop orchestration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from htc.cards.instance import CardInstance
from htc.engine.actions import ActionOption, Decision, PlayerResponse
from htc.engine.continuous import EffectDuration
from htc.enums import (
    ActionType,
    DecisionType,
    EquipmentSlot,
    Keyword,
    SuperType,
    Zone,
)
from htc.engine.events import EventType, GameEvent

if TYPE_CHECKING:
    from htc.engine.effects import EffectEngine
    from htc.engine.events import EventBus
    from htc.state.combat_state import ChainLink
    from htc.state.game_state import GameState

log = logging.getLogger(__name__)

# Type alias for the ask callback (routes decisions to player interfaces)
AskFn = Callable[[Decision], PlayerResponse]


class KeywordEngine:
    """Handles all keyword-specific enforcement logic.

    Receives a reference to the effect engine and an ask callback so it
    can query players for optional keyword activations (Spellvoid, Opt,
    Retrieve).
    """

    def __init__(
        self,
        effect_engine: EffectEngine,
        events: EventBus,
        ask_fn: AskFn,
    ) -> None:
        self.effect_engine = effect_engine
        self.events = events
        self._ask = ask_fn

    # --- Spellvoid ---

    def apply_spellvoid(self, state: GameState, player_index: int, damage: int) -> int:
        """Let the player use Spellvoid to prevent arcane damage.

        Spellvoid N (8.3): 'If you would be dealt arcane damage, you may
        destroy this to prevent N of that damage.'

        Unlike Arcane Barrier, Spellvoid is one-shot: the equipment is destroyed.
        Returns the remaining damage after prevention.
        """
        if damage <= 0:
            return 0

        player = state.players[player_index]

        # Find equipment with Spellvoid
        spellvoid_equipment: list[tuple[EquipmentSlot, CardInstance, int]] = []
        for slot, eq in player.equipment.items():
            if eq and Keyword.SPELLVOID in eq.definition.keywords:
                sv_value = eq.definition.keyword_value(Keyword.SPELLVOID)
                if sv_value > 0:
                    spellvoid_equipment.append((slot, eq, sv_value))

        if not spellvoid_equipment:
            return damage

        remaining = damage
        for slot, eq, sv_value in spellvoid_equipment:
            if remaining <= 0:
                break

            # Ask the player whether to use this Spellvoid
            prevent_amount = min(sv_value, remaining)
            options = [
                ActionOption(
                    action_id=f"spellvoid_{eq.instance_id}",
                    description=f"Destroy {eq.name} to prevent {prevent_amount} arcane damage (Spellvoid {sv_value})",
                    action_type=ActionType.ACTIVATE_ABILITY,
                ),
                ActionOption(
                    action_id="pass",
                    description=f"Don't use {eq.name}'s Spellvoid",
                    action_type=ActionType.PASS,
                ),
            ]

            decision = Decision(
                player_index=player_index,
                decision_type=DecisionType.OPTIONAL_ABILITY,
                prompt=f"Use Spellvoid on {eq.name} to prevent {prevent_amount} of {remaining} arcane damage?",
                options=options,
            )
            response = self._ask(decision)

            if response.first and response.first.startswith("spellvoid_"):
                # Destroy the equipment and prevent damage
                self.destroy_equipment(state, eq)
                remaining -= prevent_amount
                log.info(
                    f"  Spellvoid {sv_value}: {eq.name} destroyed, "
                    f"prevents {prevent_amount} arcane damage"
                )

        return remaining

    # --- Phantasm ---

    def check_phantasm(self, state: GameState) -> bool:
        """Phantasm (8.3.11): if the attack has Phantasm and is defended by a
        non-Illusionist attack action card with 6+ power, destroy the attack.

        Returns True if the attack was destroyed (skip remaining combat steps).
        """
        link = state.combat_chain.active_link
        if link is None or link.active_attack is None:
            return False

        attack_keywords = self.effect_engine.get_modified_keywords(
            state, link.active_attack
        )
        if Keyword.PHANTASM not in attack_keywords:
            return False

        for card in link.defending_cards:
            modified_power = self.effect_engine.get_modified_power(state, card)
            if (
                card.definition.is_attack_action
                and SuperType.ILLUSIONIST not in card.definition.supertypes
                and modified_power >= 6
            ):
                log.info(
                    f"  Phantasm triggered! {card.name} (power={modified_power}) "
                    f"destroys {link.active_attack.name}"
                )
                # Destroy the attack — move to graveyard, close chain
                self.events.emit(GameEvent(
                    event_type=EventType.DESTROY,
                    source=card,
                    card=link.active_attack,
                    target_player=link.active_attack.owner_index,
                ))
                # Caller (Game) handles chain closing after this returns True.
                return True

        return False

    # --- Piercing ---

    def apply_piercing(self, state: GameState, link: ChainLink) -> None:
        """Piercing N: if any defending card is equipment, attack gets +N power.

        Implemented as a temporary continuous effect that lasts until end of combat.
        Rules 8.3: 'If this is defended by an equipment, it gets +N{p}.'
        """
        if link.active_attack is None:
            return
        attack_keywords = self.effect_engine.get_modified_keywords(
            state, link.active_attack
        )
        if Keyword.PIERCING not in attack_keywords:
            return
        piercing_value = link.active_attack.definition.keyword_value(Keyword.PIERCING)
        if piercing_value <= 0:
            return

        # Check if any defending card is equipment
        has_equipment_defender = any(
            card.definition.is_equipment for card in link.defending_cards
        )
        if not has_equipment_defender:
            return

        from htc.engine.continuous import make_power_modifier

        atk_id = link.active_attack.instance_id
        effect = make_power_modifier(
            piercing_value,
            link.active_attack.owner_index,
            source_instance_id=atk_id,
            duration=EffectDuration.END_OF_COMBAT,
            target_filter=lambda c, _id=atk_id: c.instance_id == _id,
        )
        self.effect_engine.add_continuous_effect(state, effect)
        log.info(
            f"  Piercing {piercing_value}: {link.active_attack.name} gets "
            f"+{piercing_value} power (equipment defending)"
        )

    # --- Equipment degradation (Battleworn, Blade Break, Temper) ---

    def apply_equipment_degradation(self, state: GameState) -> None:
        """Apply Battleworn, Blade Break, and Temper to equipment that defended."""
        for link in state.combat_chain.chain_links:
            for card in link.defending_cards:
                if not card.definition.is_equipment:
                    continue
                keywords = self.effect_engine.get_modified_keywords(state, card)

                # Blade Break (8.3.3): destroy after defending
                if Keyword.BLADE_BREAK in keywords:
                    self.destroy_equipment(state, card)
                    log.info(f"  {card.name} destroyed (Blade Break)")
                    continue  # skip other degradation if destroyed

                # Battleworn (8.3.2): lose 1 defense counter after defending
                if Keyword.BATTLEWORN in keywords:
                    card.counters["defense"] = card.counters.get("defense", 0) - 1
                    eff_def = self.effect_engine.get_modified_defense(state, card)
                    log.info(f"  {card.name} worn (Battleworn, effective defense={eff_def})")

                # Temper: lose 1 defense counter; if effective defense <= 0, destroy
                if Keyword.TEMPER in keywords:
                    card.counters["defense"] = card.counters.get("defense", 0) - 1
                    eff_def = self.effect_engine.get_modified_defense(state, card)
                    if eff_def <= 0:
                        self.destroy_equipment(state, card)
                        log.info(f"  {card.name} destroyed (Temper, defense reached 0)")
                    else:
                        log.info(f"  {card.name} tempered (effective defense={eff_def})")

    def destroy_equipment(self, state: GameState, card: CardInstance) -> None:
        """Destroy an equipment card — remove from slot and move to graveyard."""
        owner = state.players[card.owner_index]
        for slot, eq in owner.equipment.items():
            if eq is card:
                owner.equipment[slot] = None
                break
        state.move_card(card, Zone.GRAVEYARD)
        self.events.emit(GameEvent(
            event_type=EventType.DESTROY,
            source=card,
            card=card,
            target_player=card.owner_index,
        ))

    # --- Rupture ---

    def check_rupture_active(self, state: GameState, link: ChainLink) -> bool:
        """Rupture (8.3): check if the current chain link qualifies for Rupture.

        Rupture triggers if the attack is at chain link 4 or higher.
        Returns True if Rupture bonus should apply. Per-card bonus effects
        are Phase 5; this is the infrastructure check.
        """
        if link.active_attack is None:
            return False
        attack_keywords = self.effect_engine.get_modified_keywords(
            state, link.active_attack
        )
        if Keyword.RUPTURE not in attack_keywords:
            return False
        return link.link_number >= 4

    # --- Opt ---

    def perform_opt(self, state: GameState, player_index: int, n: int) -> None:
        """Opt N: look at the top N cards of your deck, put any on the bottom.

        The player chooses which cards (if any) to move to the bottom of their
        deck, in any order. Remaining cards stay on top in their original order.
        """
        player = state.players[player_index]
        if not player.deck or n <= 0:
            return

        top_cards = player.deck[:n]
        if not top_cards:
            return

        # Build options for each card the player can send to the bottom
        options: list[ActionOption] = []
        for card in top_cards:
            options.append(ActionOption(
                action_id=f"opt_bottom_{card.instance_id}",
                description=f"Put {card.name}{card.definition.color_label} on the bottom",
                action_type=ActionType.PASS,  # generic choice
                card_instance_id=card.instance_id,
            ))
        options.append(ActionOption(
            action_id="pass",
            description="Keep all on top",
            action_type=ActionType.PASS,
        ))

        decision = Decision(
            player_index=player_index,
            decision_type=DecisionType.CHOOSE_MODE,
            prompt=f"Opt {n}: choose cards to put on the bottom of your deck",
            options=options,
            min_selections=1,
            max_selections=len(options),
        )
        response = self._ask(decision)

        # Move selected cards to bottom
        cards_to_bottom: list[CardInstance] = []
        for opt_id in response.selected_option_ids:
            if opt_id == "pass":
                continue
            if opt_id.startswith("opt_bottom_"):
                instance_id = int(opt_id.replace("opt_bottom_", ""))
                card = next((c for c in top_cards if c.instance_id == instance_id), None)
                if card:
                    cards_to_bottom.append(card)

        for card in cards_to_bottom:
            player.deck.remove(card)
            player.deck.append(card)

        if cards_to_bottom:
            names = ", ".join(c.name for c in cards_to_bottom)
            log.info(f"  Opt {n}: Player {player_index} puts {len(cards_to_bottom)} card(s) on bottom")
        else:
            log.info(f"  Opt {n}: Player {player_index} keeps all on top")

    # --- Retrieve ---

    def perform_retrieve(
        self, state: GameState, player_index: int, card_filter=None
    ) -> CardInstance | None:
        """Retrieve: return a card from your graveyard to hand.

        Infrastructure for the Retrieve keyword. Specific card effects (Phase 5)
        will specify which cards are valid targets via card_filter.
        If card_filter is None, any card in graveyard is a valid target.

        Returns the retrieved card, or None if the player chose not to retrieve.
        """
        player = state.players[player_index]
        if not player.graveyard:
            return None

        valid_targets = [
            c for c in player.graveyard
            if card_filter is None or card_filter(c)
        ]
        if not valid_targets:
            return None

        options: list[ActionOption] = []
        for card in valid_targets:
            options.append(ActionOption(
                action_id=f"retrieve_{card.instance_id}",
                description=f"Retrieve {card.name}{card.definition.color_label}",
                action_type=ActionType.PASS,
                card_instance_id=card.instance_id,
            ))
        options.append(ActionOption(
            action_id="pass",
            description="Don't retrieve",
            action_type=ActionType.PASS,
        ))

        decision = Decision(
            player_index=player_index,
            decision_type=DecisionType.CHOOSE_TARGET,
            prompt="Choose a card to retrieve from your graveyard",
            options=options,
        )
        response = self._ask(decision)

        if response.first and response.first.startswith("retrieve_"):
            instance_id = int(response.first.replace("retrieve_", ""))
            card = next((c for c in valid_targets if c.instance_id == instance_id), None)
            if card:
                player.graveyard.remove(card)
                card.zone = Zone.HAND
                player.hand.append(card)
                log.info(f"  Retrieve: Player {player_index} returns {card.name} to hand")
                return card

        return None
