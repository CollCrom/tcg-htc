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
    from engine.rules.events import EventBus
    from engine.state.player_state import PlayerState


# ---------------------------------------------------------------------------
# Card serialization
# ---------------------------------------------------------------------------


_FACE_DOWN: dict = {"face_down": True}


def _card_dict(
    card: CardInstance,
    ee: EffectEngine,
    state: GameState,
    *,
    cold: bool = False,
) -> dict:
    """Serialize a card to a dict.

    Two modes:

    * **Hot** (default, ``cold=False``): full serialization including
      ``functional_text`` / ``type_text`` and per-instance flags. Used for
      cards the agent actively reasons about (hand, arsenal, equipment,
      permanents, hero, weapons, pitch zone, combat chain).
    * **Cold** (``cold=True``): drops the rules-text blob and dead-state
      flags that are meaningless in inert zones (graveyard, banished
      face-up). All strategic fields — name, types, subtypes, supertypes,
      keywords, color, pitch, cost, power, defense — are preserved. The
      ``functional_text`` of a card sitting in graveyard/banished is
      ~75% of its serialized weight; stripping it shrinks cold-zone
      payloads dramatically without losing info needed for card-counting,
      type-aware recursion (e.g. Codex of Frailty), or play-around math.

    Effect-modified values (``modified_power``, ``modified_keywords``,
    etc.) are emitted **only when they differ from the base value**.
    Most cards aren't being continuously modified most of the time, so
    omitting redundant duplicates trims another ~40-60 bytes per card
    across the snapshot. Consumers should treat a missing ``modified_X``
    as "modified equals base."
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
    }
    if not cold:
        # Rules-text and per-instance state — only matter for active cards.
        out["type_text"] = defn.type_text
        out["functional_text"] = defn.functional_text
        out["is_tapped"] = card.is_tapped
        out["activated_this_turn"] = card.activated_this_turn
        out["face_up"] = card.face_up
        out["counters"] = dict(card.counters)
        out["is_proxy"] = card.is_proxy

    # Effect-modified values — only when (a) the base exists and (b) the
    # modified value actually differs. Consumers infer "modified == base"
    # from absence. Continuous effects rarely apply to cold-zone cards but
    # we still let the effect engine answer to be consistent.
    if defn.power is not None:
        modified_power = ee.get_modified_power(state, card)
        if modified_power != defn.power:
            out["modified_power"] = modified_power
    if defn.defense is not None:
        modified_defense = ee.get_modified_defense(state, card)
        if modified_defense != defn.defense:
            out["modified_defense"] = modified_defense
    if defn.cost is not None:
        modified_cost = ee.get_modified_cost(state, card)
        if modified_cost != defn.cost:
            out["modified_cost"] = modified_cost
    base_subtypes = sorted(s.value for s in defn.subtypes)
    modified_subtypes = sorted(s.value for s in ee.get_modified_subtypes(state, card))
    if modified_subtypes != base_subtypes:
        out["modified_subtypes"] = modified_subtypes
    base_keywords = sorted(k.value for k in defn.keywords)
    modified_keywords = sorted(k.value for k in ee.get_modified_keywords(state, card))
    if modified_keywords != base_keywords:
        out["modified_keywords"] = modified_keywords
    base_supertypes = sorted(s.value for s in defn.supertypes)
    modified_supertypes = sorted(s.value for s in ee.get_modified_supertypes(state, card))
    if modified_supertypes != base_supertypes:
        out["modified_supertypes"] = modified_supertypes
    return out


def _cards(
    cards: list[CardInstance],
    ee: EffectEngine,
    state: GameState,
    *,
    cold: bool = False,
) -> list[dict]:
    return [_card_dict(c, ee, state, cold=cold) for c in cards]


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
    """Full visibility view of a player's own seat.

    Hot zones (hand, arsenal, pitch, permanents, equipment, weapons, hero,
    soul) keep full card text — the agent is reasoning about plays from
    these. Cold zones (graveyard, banished) drop functional/type text and
    dead-state flags but keep all strategic fields (name, types,
    subtypes, supertypes, keywords, stats) needed for card-counting,
    type-aware recursion, and play-arounds.
    """
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
        "graveyard": _cards(player.graveyard, ee, state, cold=True),
        "banished": _cards(player.banished, ee, state, cold=True),
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
        "graveyard": _cards(player.graveyard, ee, state, cold=True),
        "banished_face_up": _cards(banished_face_up, ee, state, cold=True),
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
    events: EventBus | None = None,
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
        "active_effects": _active_effects_view(events),
    }


def _active_effects_view(events: EventBus | None) -> list[dict]:
    """Public-information description of registered replacement effects.

    Many continuous effects already surface as ``modified_*`` values on
    the cards they target, so the agent can see them. Replacement
    effects (most importantly damage prevention from cards like Shelter
    from the Storm) don't show up that way — they intercept events at
    resolution time, leaving the opponent to wonder why their 4-damage
    attack only dealt 3.

    This view enumerates registered replacement effects and asks each
    to ``describe()`` itself. Effects that return ``None`` (the default)
    are kept hidden — appropriate for purely-internal replacements.

    The activations behind these effects are public actions in real FaB
    (the card moved publicly to the graveyard, its text is printed), so
    no info-leak concern: both seats see the same list.

    Returns an empty list when no event bus is provided (legacy callers
    of ``snapshot_for`` that haven't been updated to pass it).
    """
    if events is None:
        return []
    out: list[dict] = []
    for effect in events.iter_replacement_effects():
        try:
            described = effect.describe()
        except Exception:  # noqa: BLE001 — never break snapshots over a description
            described = None
        if described:
            out.append(described)
    return out
