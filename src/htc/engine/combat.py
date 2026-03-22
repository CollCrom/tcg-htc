from __future__ import annotations

from htc.cards.instance import CardInstance
from htc.enums import Zone
from htc.state.combat_state import ChainLink
from htc.state.game_state import GameState


class CombatManager:
    """Manages the combat chain: open, add chain links, defend, damage, close."""

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
        damage = max(0, attack_power - total_defense)
        return damage

    def get_attack_power(self, state: GameState, link: ChainLink) -> int:
        """Get the effective power of the active attack."""
        if link.active_attack is None:
            return 0
        base = link.active_attack.base_power or 0
        # TODO: apply power modifiers from effects
        return max(0, base)

    def get_total_defense(self, state: GameState, link: ChainLink) -> int:
        """Get the total defense value of all defending cards."""
        total = 0
        for card in link.defending_cards:
            defense = card.base_defense or 0
            # TODO: apply defense modifiers from effects
            total += defense
        return total

    def resolve_damage(
        self, state: GameState, link: ChainLink
    ) -> int:
        """Apply damage to the attack target. Returns damage dealt."""
        damage = self.calculate_damage(state, link)
        if damage > 0:
            target = state.players[link.attack_target_index]
            target.life_total -= damage
            target.turn_counters.damage_taken += damage
            attacker_index = 1 - link.attack_target_index
            state.players[attacker_index].turn_counters.damage_dealt += damage
            link.damage_dealt = damage
            link.hit = True
        return damage

    def close_chain(self, state: GameState) -> None:
        """Close the combat chain. Move cards to graveyard."""
        for link in state.combat_chain.chain_links:
            # Move attack card to graveyard
            if link.active_attack:
                owner = state.players[link.active_attack.owner_index]
                link.active_attack.zone = Zone.GRAVEYARD
                owner.graveyard.append(link.active_attack)
            # Move defending cards to graveyard
            for card in link.defending_cards:
                if card.definition.is_equipment or card.definition.is_weapon:
                    # Equipment returns to its zone — simplified for now
                    pass
                else:
                    owner = state.players[card.owner_index]
                    card.zone = Zone.GRAVEYARD
                    owner.graveyard.append(card)
        state.combat_chain.reset()
