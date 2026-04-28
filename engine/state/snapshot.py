"""Per-player game-state snapshots with hidden-zone redaction.

External agents (driven over the JSONL stdio protocol) see the game from
one seat. They get full visibility of zones they own that contain hidden
cards (their hand, face-down arsenal, face-down banished cards) and only
public information about the opponent's equivalents.

The shape returned by :func:`snapshot_for` is::

    {
        "you": {<full player view>},
        "opponent": {<redacted player view>},
        "combat_chain": {<chain links + active attack>},
        "turn": {<turn number, phase, active player>},
    }

This module is pure data transformation. It does not know about JSONL or
any transport — :class:`engine.player.stdio_player.StdioPlayer` calls it
and embeds the result in each ``decision`` message.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from engine.cards.instance import CardInstance
from engine.enums import EquipmentSlot
from engine.state.game_state import GameState

if TYPE_CHECKING:
    from engine.rules.effects import EffectEngine
    from engine.state.player_state import PlayerState


# ---------------------------------------------------------------------------
# Card serialization
# ---------------------------------------------------------------------------


_FACE_DOWN: dict = {"face_down": True}


def _card_dict(card: CardInstance, ee: EffectEngine, state: GameState) -> dict:
    """Serialize a card to a dict with both base and effect-modified values.

    Modified values are computed via the effect engine so the agent sees
    the actual game-relevant numbers (e.g. modified power on an active
    attack, modified defense on defenders, modified cost on a cost-reduced
    card in hand).
    """
    defn = card._effective_definition
    out: dict = {
        "instance_id": card.instance_id,
        "name": defn.name,
        "zone": card.zone.value,
        "color": defn.color.value if defn.color is not None else None,
        "pitch": defn.pitch,
        "cost": defn.cost,
        "power": defn.power,
        "defense": defn.defense,
        "health": defn.health,
        "intellect": defn.intellect,
        "arcane": defn.arcane,
        "types": sorted(t.value for t in defn.types),
        "subtypes": sorted(s.value for s in defn.subtypes),
        "supertypes": sorted(s.value for s in defn.supertypes),
        "keywords": sorted(k.value for k in defn.keywords),
        "type_text": defn.type_text,
        "functional_text": defn.functional_text,
        "is_tapped": card.is_tapped,
        "activated_this_turn": card.activated_this_turn,
        "face_up": card.face_up,
        "counters": dict(card.counters),
        "is_proxy": card.is_proxy,
    }
    # Effect-modified values — only present when the base value exists.
    if defn.power is not None:
        out["modified_power"] = ee.get_modified_power(state, card)
    if defn.defense is not None:
        out["modified_defense"] = ee.get_modified_defense(state, card)
    if defn.cost is not None:
        out["modified_cost"] = ee.get_modified_cost(state, card)
    out["modified_subtypes"] = sorted(s.value for s in ee.get_modified_subtypes(state, card))
    out["modified_keywords"] = sorted(k.value for k in ee.get_modified_keywords(state, card))
    out["modified_supertypes"] = sorted(s.value for s in ee.get_modified_supertypes(state, card))
    return out


def _cards(cards: list[CardInstance], ee: EffectEngine, state: GameState) -> list[dict]:
    return [_card_dict(c, ee, state) for c in cards]


# ---------------------------------------------------------------------------
# Player views
# ---------------------------------------------------------------------------


def _equipment_dict(
    eq_map: dict[EquipmentSlot, CardInstance | None],
    ee: EffectEngine,
    state: GameState,
) -> dict:
    return {
        slot.value: (_card_dict(card, ee, state) if card is not None else None)
        for slot, card in eq_map.items()
    }


def _own_view(player: PlayerState, ee: EffectEngine, state: GameState) -> dict:
    """Full visibility view of a player's own seat."""
    return {
        "index": player.index,
        "life": player.life_total,
        "is_marked": player.is_marked,
        "action_points": state.action_points.get(player.index, 0),
        "resource_points": state.resource_points.get(player.index, 0),
        "hero": _card_dict(player.hero, ee, state) if player.hero is not None else None,
        "weapons": _cards(player.weapons, ee, state),
        "equipment": _equipment_dict(player.equipment, ee, state),
        "permanents": _cards(player.permanents, ee, state),
        "hand": _cards(player.hand, ee, state),
        "arsenal": _cards(player.arsenal, ee, state),
        "pitch": _cards(player.pitch, ee, state),
        "graveyard": _cards(player.graveyard, ee, state),
        "banished": _cards(player.banished, ee, state),
        "soul": _cards(player.soul, ee, state),
        "deck_size": len(player.deck),
        "turn_counters": asdict(player.turn_counters),
    }


def _opponent_view(
    player: PlayerState,
    ee: EffectEngine,
    state: GameState,
    viewer_index: int,
) -> dict:
    """Public-only view of an opponent's seat.

    Hidden zones (hand, face-down arsenal, face-down banished cards) are
    replaced with sizes or face-down placeholders. Cards in the opponent's
    hand that have been revealed to *viewer_index* (by peek effects) appear
    under ``hand_revealed`` alongside the full ``hand_size``; the viewer
    knows ``len(hand_revealed)`` of the ``hand_size`` cards. Cards revealed
    earlier that have since left hand are silently filtered out.
    """
    arsenal_view = [
        _card_dict(c, ee, state) if c.face_up else _FACE_DOWN
        for c in player.arsenal
    ]
    banished_face_up = [c for c in player.banished if c.face_up]
    banished_face_down_count = sum(1 for c in player.banished if not c.face_up)
    revealed_ids = player.hand_revealed_to.get(viewer_index, set())
    hand_revealed = [
        _card_dict(c, ee, state) for c in player.hand if c.instance_id in revealed_ids
    ]

    return {
        "index": player.index,
        "life": player.life_total,
        "is_marked": player.is_marked,
        "action_points": state.action_points.get(player.index, 0),
        "resource_points": state.resource_points.get(player.index, 0),
        "hero": _card_dict(player.hero, ee, state) if player.hero is not None else None,
        "weapons": _cards(player.weapons, ee, state),
        "equipment": _equipment_dict(player.equipment, ee, state),
        "permanents": _cards(player.permanents, ee, state),
        "hand_size": len(player.hand),
        "hand_revealed": hand_revealed,
        "arsenal": arsenal_view,
        "pitch": _cards(player.pitch, ee, state),
        "graveyard": _cards(player.graveyard, ee, state),
        "banished_face_up": _cards(banished_face_up, ee, state),
        "banished_face_down_count": banished_face_down_count,
        "deck_size": len(player.deck),
        "turn_counters": asdict(player.turn_counters),
    }


# ---------------------------------------------------------------------------
# Combat chain view
# ---------------------------------------------------------------------------


def _combat_chain_view(state: GameState, ee: EffectEngine) -> dict:
    chain = state.combat_chain
    return {
        "is_open": chain.is_open,
        "links": [
            {
                "link_number": link.link_number,
                "active_attack": (
                    _card_dict(link.active_attack, ee, state)
                    if link.active_attack is not None else None
                ),
                "attack_source": (
                    {"instance_id": link.attack_source.instance_id, "name": link.attack_source.name}
                    if link.attack_source is not None else None
                ),
                "attack_target_index": link.attack_target_index,
                "defending_cards": _cards(link.defending_cards, ee, state),
                "damage_dealt": link.damage_dealt,
                "hit": link.hit,
                "hit_count": link.hit_count,
            }
            for link in chain.chain_links
        ],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def snapshot_for(
    state: GameState,
    viewer_index: int,
    effect_engine: EffectEngine,
) -> dict:
    """Build a per-player snapshot of the game state for *viewer_index*.

    The viewer's own seat is fully visible; the opponent's seat has
    hidden zones (hand, face-down arsenal/banished) replaced with sizes
    or face-down placeholders. Cards include both base and effect-modified
    values so an agent can reason about post-modifier game-relevant
    numbers without re-implementing the effect engine.

    .. warning::
       This function requires both player states to be built. During
       :meth:`engine.rules.game.Game._setup_game`, ``CHOOSE_EQUIPMENT``
       decisions for multi-option slots fire **before** ``state.players``
       is populated, which causes this function to raise. External
       transports must guard against this (see ``HttpBridgePlayer._encode``
       in ``tools/match_server.py`` for the pattern: emit a stripped
       ``{"phase": "pre_game_setup"}`` payload until ``len(state.players)
       == 2``). The plain ``engine.stdio`` path does **not** guard this
       and will crash on decks with multi-option equipment slots.
    """
    if viewer_index not in (0, 1):
        raise ValueError(f"viewer_index must be 0 or 1, got {viewer_index!r}")
    if len(state.players) != 2:
        raise ValueError(
            f"snapshot_for assumes a 2-player game; got {len(state.players)}. "
            "If you are calling this during _setup_game (before state.players "
            "is populated), guard the call — see this function's docstring."
        )

    you = state.players[viewer_index]
    opponent = state.players[1 - viewer_index]

    return {
        "you": _own_view(you, effect_engine, state),
        "opponent": _opponent_view(opponent, effect_engine, state, viewer_index),
        "combat_chain": _combat_chain_view(state, effect_engine),
        "turn": {
            "number": state.turn_number,
            "phase": state.phase.value,
            "combat_step": state.combat_step.value if state.combat_step is not None else None,
            "active_player_index": state.turn_player_index,
            "priority_player_index": state.priority_player_index,
        },
    }
