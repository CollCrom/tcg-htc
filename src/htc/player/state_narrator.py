"""Converts GameState + Decision into compact text for the LLM.

Uses abbreviated notation to minimize tokens while preserving all
information needed for informed gameplay decisions.
"""

from __future__ import annotations

from htc.cards.instance import CardInstance
from htc.engine.actions import ActionOption, Decision
from htc.enums import Color, DecisionType, EquipmentSlot, Keyword, SubType, Zone
from htc.state.combat_state import ChainLink
from htc.state.game_state import GameState
from htc.state.player_state import PlayerState

# Keywords worth surfacing in hand/option descriptions
_NOTABLE_KEYWORDS = frozenset({
    Keyword.GO_AGAIN, Keyword.STEALTH, Keyword.DOMINATE, Keyword.INTIMIDATE,
    Keyword.PIERCING, Keyword.CRUSH, Keyword.OVERPOWER, Keyword.COMBO,
    Keyword.CONTRACT, Keyword.PHANTASM, Keyword.AMBUSH, Keyword.BOOST,
    Keyword.REPRISE, Keyword.RUPTURE, Keyword.BLADE_BREAK, Keyword.BATTLEWORN,
    Keyword.TEMPER, Keyword.ARCANE_BARRIER, Keyword.SPELLVOID, Keyword.WARD,
})

_COLOR_ABBREV = {Color.RED: "R", Color.YELLOW: "Y", Color.BLUE: "B"}


def narrate(game_state: GameState, decision: Decision) -> str:
    """Build a compact textual description of the game state and decision."""
    me_idx = decision.player_index

    # During setup (equipment selection), players aren't populated yet
    if me_idx >= len(game_state.players):
        return _narrate_setup(decision)

    opp_idx = 1 - me_idx
    me = game_state.players[me_idx]
    opp = game_state.players[opp_idx]

    parts: list[str] = []

    # Header: turn, whose turn, phase, life/deck
    turn_label = "YOUR" if game_state.turn_player_index == me_idx else "OPP"
    my_deck = len(me.deck)
    opp_deck = len(opp.deck)
    header = (
        f"T{game_state.turn_number} {turn_label} {game_state.phase.value}"
        f" | HP {me.life_total} deck {my_deck}"
        f" | Opp HP {opp.life_total} deck {opp_deck}"
    )
    life_diff = me.life_total - opp.life_total
    deck_diff = my_deck - opp_deck
    if life_diff or deck_diff:
        header += (
            f" | Δlife {'+' if life_diff > 0 else ''}{life_diff}"
            f" Δdeck {'+' if deck_diff > 0 else ''}{deck_diff}"
        )
    parts.append(header)

    # Hero
    if me.hero:
        parts.append(f"Hero: {me.hero.name}")

    # Mark status
    if me.is_marked:
        parts.append("MARKED (opp gets contract bonuses)")
    if opp.is_marked:
        parts.append("Opp MARKED (you get contract bonuses)")

    # Equipment
    equip_lines = _describe_equipment(me)
    if equip_lines:
        parts.append("Equip: " + " | ".join(equip_lines))

    # Weapons
    if me.weapons:
        wlines = [f"{w.name}{'[T]' if w.is_tapped else ''}" for w in me.weapons]
        parts.append("Wpns: " + ", ".join(wlines))

    # Hand (compact inline)
    if me.hand:
        parts.append("Hand: " + " | ".join(_describe_card(c) for c in me.hand))

    # Arsenal
    if me.arsenal:
        parts.append("Arsenal: " + " | ".join(_describe_card(c) for c in me.arsenal))

    # Permanents
    my_perms = _describe_permanents(me)
    if my_perms:
        parts.append("Perms: " + " | ".join(my_perms))
    opp_perms = _describe_permanents(opp)
    if opp_perms:
        parts.append("Opp perms: " + " | ".join(opp_perms))

    # Opponent info (hand size, arsenal, equipment)
    opp_info = f"Opp: {len(opp.hand)} cards, {len(opp.arsenal)} arsenal"
    opp_eq = _describe_equipment(opp)
    if opp_eq:
        opp_info += " | " + " | ".join(opp_eq)
    parts.append(opp_info)

    # Combat chain
    cc = game_state.combat_chain
    if cc.is_open and cc.chain_links:
        parts.append(_describe_combat(cc.chain_links, me_idx))

    # Resources / action points / pitch (only if nonzero)
    res = game_state.resource_points.get(me_idx, 0)
    ap = game_state.action_points.get(me_idx, 0)
    pitch_count = len(me.pitch) if me.pitch else 0
    res_parts: list[str] = []
    if ap:
        res_parts.append(f"AP:{ap}")
    if res:
        res_parts.append(f"Res:{res}")
    if pitch_count:
        res_parts.append(f"Pitched:{pitch_count}")
    if res_parts:
        parts.append(" ".join(res_parts))

    # Decision prompt and options
    parts.append("")
    parts.append(f"DECIDE {decision.decision_type.value}: {decision.prompt}")
    if decision.max_selections > 1:
        parts.append(f"Select {decision.min_selections}-{decision.max_selections}.")
    for opt in decision.options:
        parts.append(f"  [{opt.action_id}] {opt.description}"
                     + _option_card_details(opt, game_state))

    return "\n".join(parts)


def _card_stats_and_keywords(d) -> tuple[list[str], list[str]]:
    """Extract compact stat tokens and notable keywords from a CardDefinition."""
    stats: list[str] = []
    if d.cost is not None:
        stats.append(f"{d.cost}c")
    if d.power is not None:
        stats.append(f"{d.power}p")
    if d.defense is not None:
        stats.append(f"{d.defense}d")
    if d.pitch is not None:
        stats.append(f"{d.pitch}P")
    kws = [kw.value for kw in d.keywords if kw in _NOTABLE_KEYWORDS]
    return stats, kws


def _describe_card(card: CardInstance) -> str:
    """Compact one-line card description: Name(R)[1c 4p 3d 1P]{Go again}."""
    d = card.definition
    result = d.name
    if d.color:
        result += f"({_COLOR_ABBREV.get(d.color, d.color.value)})"
    stats, kws = _card_stats_and_keywords(d)
    if stats:
        result += f"[{' '.join(stats)}]"
    if kws:
        result += "{" + ",".join(kws) + "}"
    return result


def _describe_equipment(player: PlayerState) -> list[str]:
    """Compact equipment descriptions: slot=Name(extras)."""
    lines: list[str] = []
    for slot in EquipmentSlot:
        eq = player.equipment.get(slot)
        if eq is None:
            continue
        extras: list[str] = []
        for counter_name, count in eq.counters.items():
            extras.append(f"{count} {counter_name}")
        if eq.zone == Zone.GRAVEYARD:
            extras.append("destroyed")
        kws = [kw.value for kw in eq.definition.keywords if kw in _NOTABLE_KEYWORDS]
        if kws:
            extras.extend(kws)
        name = eq.name
        if extras:
            name += f"({','.join(extras)})"
        lines.append(f"{slot.value}={name}")
    return lines


def _describe_permanents(player: PlayerState) -> list[str]:
    """Describe tokens and permanents."""
    lines: list[str] = []
    for p in player.permanents:
        extras: list[str] = []
        for cname, count in p.counters.items():
            extras.append(f"{count} {cname}")
        desc = p.name
        if extras:
            desc += f"({','.join(extras)})"
        lines.append(desc)
    return lines


def _describe_combat(links: list[ChainLink], my_idx: int) -> str:
    """Compact combat chain description."""
    parts: list[str] = ["Combat:"]
    for link in links:
        atk = link.active_attack
        if not atk:
            continue
        desc = f"  L{link.link_number}: {atk.name}"
        if atk.base_power is not None:
            desc += f"({atk.base_power}p)"
        if link.attack_source and link.attack_source != atk:
            desc += f" via {link.attack_source.name}"
        if link.defending_cards:
            def_names = [c.name for c in link.defending_cards]
            desc += f" blocked:{','.join(def_names)}"
        if link.damage_dealt > 0:
            desc += f" {link.damage_dealt}dmg"
            if link.hit:
                desc += " HIT"
        parts.append(desc)
    return "\n".join(parts)


def _option_card_details(opt: ActionOption, gs: GameState) -> str:
    """Compact card stats appended to an option line."""
    if opt.card_instance_id is None:
        return ""
    card = gs.find_card(opt.card_instance_id)
    if card is None:
        return ""
    stats, kws = _card_stats_and_keywords(card.definition)
    extras = stats + kws
    if extras:
        return f" — {' '.join(extras)}"
    return ""


def _narrate_setup(decision: Decision) -> str:
    """Narrate a pre-game decision (e.g., equipment selection)."""
    parts: list[str] = [
        "Pre-game setup",
        "",
        f"DECIDE {decision.decision_type.value}: {decision.prompt}",
        "Options:",
    ]
    for opt in decision.options:
        parts.append(f"  [{opt.action_id}] {opt.description}")
    return "\n".join(parts)
