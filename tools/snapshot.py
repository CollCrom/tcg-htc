"""Capture game state snapshots for the board viewer.

Serializes the current GameState into a JSON-friendly dict that can be
written to a file and read by the board viewer.
"""

from __future__ import annotations

from engine.cards.instance import CardInstance
from engine.enums import EquipmentSlot
from engine.state.combat_state import ChainLink
from engine.state.game_state import GameState


def _card_info(card: CardInstance, *, visible: bool = True) -> dict:
    """Serialize a single card to a dict."""
    if not visible:
        return {"name": "???", "color": None, "face_up": False}
    defn = card._effective_definition
    return {
        "name": defn.name,
        "color": defn.color.value if defn.color else None,
        "cost": defn.cost,
        "power": defn.power,
        "defense": defn.defense,
        "face_up": card.face_up,
    }


def _equipment_info(slot: EquipmentSlot, card: CardInstance | None) -> dict | None:
    """Serialize an equipment slot."""
    if card is None:
        return None
    defn = card._effective_definition
    return {
        "slot": slot.value,
        "name": defn.name,
        "defense": defn.defense,
        "counters": dict(card.counters) if card.counters else {},
        "is_tapped": card.is_tapped,
        "activated_this_turn": card.activated_this_turn,
    }


def _chain_link_info(link: ChainLink) -> dict:
    """Serialize a combat chain link."""
    attack = link.active_attack
    return {
        "link_number": link.link_number,
        "attack": {
            "name": attack.name if attack else "???",
            "power": attack.base_power if attack else None,
            "color": attack._effective_definition.color.value
            if attack and attack._effective_definition.color
            else None,
        }
        if attack
        else None,
        "defenders": [
            {
                "name": d.name,
                "defense": d.base_defense,
                "color": d._effective_definition.color.value
                if d._effective_definition.color
                else None,
            }
            for d in link.defending_cards
        ],
        "damage_dealt": link.damage_dealt,
        "hit": link.hit,
    }


def _player_info(
    state: GameState,
    player_index: int,
    *,
    is_viewer: bool = False,
    effect_engine=None,
) -> dict:
    """Serialize a player's board state.

    If *is_viewer* is True, hand cards are shown face-up.
    Otherwise, only the count is shown普通 (card backs).
    """
    ps = state.players[player_index]
    hero = ps.hero

    # Hand — always visible for review/debugging purposes
    hand = [_card_info(c) for c in ps.hand]

    # Arsenal — always visible for review (note face_up status for reference)
    arsenal = [_card_info(c) for c in ps.arsenal]

    # Equipment
    equipment = {}
    for slot, card in ps.equipment.items():
        info = _equipment_info(slot, card)
        if info is not None:
            equipment[slot.value] = info

    # Weapons
    weapons = [
        {
            "name": w.name,
            "power": w.base_power,
            "is_tapped": w.is_tapped,
            "counters": dict(w.counters) if w.counters else {},
        }
        for w in ps.weapons
    ]

    # Permanents / tokens
    permanents = [
        {
            "name": p.name,
            "counters": dict(p.counters) if p.counters else {},
        }
        for p in ps.permanents
    ]

    # Graveyard — just names
    graveyard = [c.name for c in ps.graveyard]

    # Banished — always show name for review, with face_up flag
    banished = [{"name": c.name, "face_up": c.face_up, "color": c._effective_definition.color.value if c._effective_definition.color else None} for c in ps.banished]

    return {
        "name": hero.definition.name.split(",")[0] if hero else f"Player {player_index}",
        "hero_full": hero.definition.name if hero else None,
        "life": ps.life_total,
        "is_marked": ps.is_marked,
        "diplomacy_restriction": ps.diplomacy_restriction,
        "hand": hand,
        "hand_count": len(ps.hand),
        "arsenal": arsenal,
        "equipment": equipment,
        "weapons": weapons,
        "permanents": permanents,
        "graveyard": graveyard,
        "graveyard_count": len(ps.graveyard),
        "banished": banished,
        "deck_count": len(ps.deck),
    }


def capture_snapshot(
    state: GameState,
    description: str,
    *,
    effect_engine=None,
    viewer_index: int = 0,
) -> dict:
    """Serialize current game state into a JSON-friendly dict.

    Args:
        state: The current GameState.
        description: Human-readable description of what just happened.
        effect_engine: Optional EffectEngine for modified stats (unused for now).
        viewer_index: Which player's hand is visible (0 or 1). The turn player's
            hand is always shown; the other player's hand is hidden.

    Returns:
        A dict suitable for JSON serialization.
    """
    turn_player_idx = state.turn_player_index
    opp_idx = 1 - turn_player_idx

    # Combat chain
    chain = []
    if state.combat_chain.is_open:
        for link in state.combat_chain.chain_links:
            chain.append(_chain_link_info(link))

    # Check stack for attack cards not yet on the chain
    stack_attacks = []
    for layer in state.stack:
        card = layer.card
        if card and card.definition.is_attack:
            stack_attacks.append({
                "link_number": len(chain) + len(stack_attacks) + 1,
                "attack": {
                    "name": card.name,
                    "power": card.base_power,
                    "color": card._effective_definition.color.value
                    if card._effective_definition.color else None,
                },
                "defenders": [],
                "damage_dealt": 0,
                "hit": False,
                "on_stack": True,
            })
    chain.extend(stack_attacks)

    return {
        "description": description,
        "turn_number": state.turn_number,
        "turn_player_index": turn_player_idx,
        "phase": state.phase.value if state.phase else None,
        "combat_step": state.combat_step.value if state.combat_step else None,
        "action_points": state.action_points.get(turn_player_idx, 0),
        "resource_points": state.resource_points.get(turn_player_idx, 0),
        "game_over": state.game_over,
        "winner": state.winner,
        "turn_player": _player_info(
            state, turn_player_idx, is_viewer=True, effect_engine=effect_engine
        ),
        "opponent": _player_info(
            state, opp_idx, is_viewer=False, effect_engine=effect_engine
        ),
        "combat_chain": chain,
    }
