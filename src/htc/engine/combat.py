from __future__ import annotations

from typing import TYPE_CHECKING

from htc.cards.instance import CardInstance
from htc.enums import EquipmentSlot, Zone
from htc.state.combat_state import ChainLink
from htc.state.game_state import GameState

if TYPE_CHECKING:
    from htc.engine.effects import EffectEngine


class CombatManager:
    """Manages the combat chain: open, add chain links, defend, damage, close."""

    def __init__(self, effect_engine: EffectEngine) -> None:
        self.effects = effect_engine

    def open_chain(self, state: GameState) -> None:
        state.combat_chain.is_open = True

    def add_chain_link(
        self,
        state: GameState,
        attack_card: CardInstance,
        attack_target_index: int,
    ) -> ChainLink:
        """Create a new chain link with the given attack card."""
        link = ChainLink(
            link_number=state.combat_chain.num_chain_links + 1,
            active_attack=attack_card,
            attack_target_index=attack_target_index,
            has_go_again=attack_card.definition.has_go_again,
        )
        attack_card.zone = Zone.COMBAT_CHAIN
        state.combat_chain.chain_links.append(link)
        return link

    def add_defender(self, state: GameState, link: ChainLink, card: CardInstance) -> None:
        """Add a card as a defending card on the chain link."""
        link.defending_cards.append(card)
        card.zone = Zone.COMBAT_CHAIN

    def calculate_damage(self, state: GameState, link: ChainLink) -> int:
        """Calculate damage: attack power minus total defense. Min 0."""
        attack_power = self.get_attack_power(state, link)
        total_defense = self.get_total_defense(state, link)
        return max(0, attack_power - total_defense)

    def get_attack_power(self, state: GameState, link: ChainLink) -> int:
        """Get the effective power of the active attack."""
        if link.active_attack is None:
            return 0
        return self.effects.get_modified_power(state, link.active_attack)

    def get_total_defense(self, state: GameState, link: ChainLink) -> int:
        """Get the total defense value of all defending cards."""
        total = 0
        for card in link.defending_cards:
            total += self.effects.get_modified_defense(state, card)
        return total

    def close_chain(self, state: GameState) -> None:
        """Close the combat chain. Move cards to graveyard."""
        for link in state.combat_chain.chain_links:
            if link.active_attack:
                state.move_card(link.active_attack, Zone.GRAVEYARD)
            for card in link.defending_cards:
                if card.definition.is_equipment or card.definition.is_weapon:
                    # Equipment/weapons return to their slot after combat
                    # The equipment dict still holds the reference; restore zone
                    owner = state.players[card.owner_index]
                    for slot, eq in owner.equipment.items():
                        if eq is card:
                            card.zone = Zone(slot.value)
                            break
                    else:
                        if card in owner.weapons:
                            card.zone = Zone.WEAPON_1
                else:
                    state.move_card(card, Zone.GRAVEYARD)
        state.combat_chain.reset()
