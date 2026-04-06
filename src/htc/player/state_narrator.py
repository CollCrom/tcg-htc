"""Converts GameState + Decision into readable text for the LLM.

Keeps output concise (target under 2000 tokens) while including all
information needed to make an informed gameplay decision.
"""

from __future__ import annotations

from htc.cards.instance import CardInstance
from htc.engine.actions import ActionOption, Decision
from htc.enums import DecisionType, EquipmentSlot, Keyword, SubType, Zone
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


def narrate(game_state: GameState, decision: Decision) -> str:
    """Build a concise textual description of the game state and decision."""
    me_idx = decision.player_index
    opp_idx = 1 - me_idx
    me = game_state.players[me_idx]
    opp = game_state.players[opp_idx]

    parts: list[str] = []

    # Header: turn, phase, who is deciding
    turn_label = "Your turn" if game_state.turn_player_index == me_idx else "Opponent's turn"
    parts.append(f"Turn {game_state.turn_number} | {turn_label} | Phase: {game_state.phase.value}")

    # Life and deck
    my_deck = len(me.deck)
    opp_deck = len(opp.deck)
    parts.append(f"You: {me.life_total} life, {my_deck} cards in deck"
                 f" | Opponent: {opp.life_total} life, {opp_deck} cards in deck")
    diff = me.life_total - opp.life_total
    if diff != 0:
        parts.append(f"Life differential: {'+'if diff > 0 else ''}{diff} "
                     f"| Deck differential: {'+'if my_deck - opp_deck > 0 else ''}{my_deck - opp_deck}")

    # My hero
    if me.hero:
        parts.append(f"Your hero: {me.hero.name}")

    # Mark status
    if me.is_marked:
        parts.append("You are MARKED (opponent gets contract bonuses).")
    if opp.is_marked:
        parts.append("Opponent is MARKED (you get contract bonuses).")

    # Equipment
    equip_lines = _describe_equipment(me)
    if equip_lines:
        parts.append("Your equipment: " + " | ".join(equip_lines))

    # Weapons
    if me.weapons:
        wlines = []
        for w in me.weapons:
            extra = ""
            if w.is_tapped:
                extra = " [tapped]"
            wlines.append(f"{w.name}{extra}")
        parts.append("Your weapons: " + ", ".join(wlines))

    # Hand
    if me.hand:
        parts.append("Your hand:")
        for c in me.hand:
            parts.append(f"  - {_describe_card(c)}")
    else:
        parts.append("Your hand: (empty)")

    # Arsenal
    if me.arsenal:
        parts.append("Arsenal: " + ", ".join(_describe_card(c) for c in me.arsenal))

    # Permanents / tokens
    my_perms = _describe_permanents(me)
    if my_perms:
        parts.append("Your permanents: " + " | ".join(my_perms))
    opp_perms = _describe_permanents(opp)
    if opp_perms:
        parts.append("Opp permanents: " + " | ".join(opp_perms))

    # Opponent hand size and arsenal count (hidden information)
    parts.append(f"Opponent hand: {len(opp.hand)} cards | "
                 f"Opp arsenal: {len(opp.arsenal)} card(s)")

    # Opponent equipment (visible)
    opp_eq = _describe_equipment(opp)
    if opp_eq:
        parts.append("Opp equipment: " + " | ".join(opp_eq))

    # Combat chain
    cc = game_state.combat_chain
    if cc.is_open and cc.chain_links:
        parts.append(_describe_combat(cc.chain_links, me_idx))

    # Pitch zone
    if me.pitch:
        parts.append(f"Pitch zone: {len(me.pitch)} card(s)")

    # Resources / action points available
    res = game_state.resource_points.get(me_idx, 0)
    ap = game_state.action_points.get(me_idx, 0)
    if res or ap:
        parts.append(f"Resources: {res} | Action points: {ap}")

    # Decision prompt and options
    parts.append("")
    parts.append(f"DECISION ({decision.decision_type.value}): {decision.prompt}")
    if decision.max_selections > 1:
        parts.append(f"Select {decision.min_selections}-{decision.max_selections} options.")
    parts.append("Options:")
    for opt in decision.options:
        parts.append(f"  [{opt.action_id}] {opt.description}"
                     + _option_card_details(opt, game_state))

    return "\n".join(parts)


def _describe_card(card: CardInstance) -> str:
    """One-line description of a card for hand/arsenal listing."""
    d = card.definition
    bits: list[str] = [d.name]
    if d.color:
        bits.append(f"({d.color.value})")
    stats: list[str] = []
    if d.cost is not None:
        stats.append(f"cost {d.cost}")
    if d.power is not None:
        stats.append(f"power {d.power}")
    if d.defense is not None:
        stats.append(f"def {d.defense}")
    if d.pitch is not None:
        stats.append(f"pitch {d.pitch}")
    if stats:
        bits.append("[" + ", ".join(stats) + "]")
    kws = [kw.value for kw in d.keywords if kw in _NOTABLE_KEYWORDS]
    if kws:
        bits.append("{" + ", ".join(kws) + "}")
    return " ".join(bits)


def _describe_equipment(player: PlayerState) -> list[str]:
    """Describe equipment in each slot."""
    lines: list[str] = []
    for slot in EquipmentSlot:
        eq = player.equipment.get(slot)
        if eq is None:
            continue
        name = eq.name
        extras: list[str] = []
        # Counters
        for counter_name, count in eq.counters.items():
            extras.append(f"{count} {counter_name}")
        # Destroyed = equipment in graveyard (we still show slot if occupied)
        if eq.zone == Zone.GRAVEYARD:
            extras.append("destroyed")
        # Notable keywords
        kws = [kw.value for kw in eq.definition.keywords if kw in _NOTABLE_KEYWORDS]
        if kws:
            extras.extend(kws)
        desc = name
        if extras:
            desc += f" ({', '.join(extras)})"
        lines.append(f"{slot.value}: {desc}")
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
            desc += f" ({', '.join(extras)})"
        lines.append(desc)
    return lines


def _describe_combat(links: list[ChainLink], my_idx: int) -> str:
    """Describe the combat chain state."""
    parts: list[str] = ["Combat chain:"]
    for link in links:
        atk = link.active_attack
        if not atk:
            continue
        desc = f"  Link {link.link_number}: {atk.name}"
        if atk.base_power is not None:
            desc += f" (power {atk.base_power})"
        if link.attack_source and link.attack_source != atk:
            desc += f" via {link.attack_source.name}"
        if link.defending_cards:
            def_names = [c.name for c in link.defending_cards]
            desc += f" — blocked by: {', '.join(def_names)}"
        if link.damage_dealt > 0:
            desc += f" — dealt {link.damage_dealt} dmg"
            if link.hit:
                desc += " (HIT)"
        parts.append(desc)
    return "\n".join(parts)


def _option_card_details(opt: ActionOption, gs: GameState) -> str:
    """Add card stat details to an option if a card is referenced."""
    if opt.card_instance_id is None:
        return ""
    card = gs.find_card(opt.card_instance_id)
    if card is None:
        return ""
    d = card.definition
    extras: list[str] = []
    if d.cost is not None:
        extras.append(f"cost={d.cost}")
    if d.power is not None:
        extras.append(f"pow={d.power}")
    if d.defense is not None:
        extras.append(f"def={d.defense}")
    if d.pitch is not None:
        extras.append(f"pitch={d.pitch}")
    kws = [kw.value for kw in d.keywords if kw in _NOTABLE_KEYWORDS]
    if kws:
        extras.extend(kws)
    if extras:
        return f" — {', '.join(extras)}"
    return ""
