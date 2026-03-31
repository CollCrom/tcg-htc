"""Phase 7 stress tests — run many full games to find crashes and invariant violations.

Runs 100 games with different seeds for each player order (Cindra P1, Arakni P1),
validating game completion invariants, per-game state invariants, and event invariants.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from htc.cards.card_db import CardDatabase
from htc.cards.instance import CardInstance
from htc.decks.deck_list import DeckEntry, DeckList
from htc.engine.events import EventBus, EventType, GameEvent
from htc.engine.game import Game, GameResult, MAX_TURNS
from htc.enums import Color, EquipmentSlot, Zone
from htc.player.random_player import RandomPlayer
from htc.state.player_state import PlayerState

DATA_DIR = Path(__file__).parent.parent.parent / "data"
REF_DIR = Path(__file__).parent.parent.parent / "ref"

_COLOR_MAP = {
    "red": Color.RED,
    "yellow": Color.YELLOW,
    "blue": Color.BLUE,
}


# ---------------------------------------------------------------------------
# Markdown decklist parser (reused from test_full_game.py)
# ---------------------------------------------------------------------------


def parse_markdown_decklist(text: str) -> DeckList:
    """Parse a markdown decklist (ref/ format) into a DeckList."""
    hero_name = ""
    weapons: list[str] = []
    equipment: list[str] = []
    cards: list[DeckEntry] = []
    section = ""

    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("## Hero"):
            section = "hero"
            continue
        elif line.startswith("## Weapon"):
            section = "weapons"
            continue
        elif line.startswith("## Equipment"):
            section = "equipment"
            continue
        elif line.startswith("## Deck"):
            section = "deck"
            continue
        elif line.startswith("### "):
            continue
        elif line.startswith("## ") or line.startswith("# "):
            section = ""
            continue
        elif line.startswith("**"):
            continue

        if section == "hero" and not line.startswith("-"):
            hero_name = line
        elif section == "weapons" and line.startswith("-"):
            wname = _parse_equipment_line(line)
            if wname:
                weapons.append(wname)
        elif section == "equipment" and line.startswith("-"):
            ename = _parse_equipment_line(line)
            if ename:
                equipment.append(ename)
        elif section == "deck" and line.startswith("-"):
            entry = _parse_deck_card_line(line)
            if entry:
                cards.append(entry)

    return DeckList(hero_name=hero_name, weapons=weapons, equipment=equipment, cards=cards)


def _parse_equipment_line(line: str) -> str | None:
    line = line.lstrip("- ").strip()
    m = re.match(r"(\d+)x\s+", line)
    if m:
        line = line[m.end():]
    line = re.sub(r"\s*\([^)]*\)\s*$", "", line)
    return line.strip() if line.strip() else None


def _parse_deck_card_line(line: str) -> DeckEntry | None:
    line = line.lstrip("- ").strip()
    count = 1
    m = re.match(r"(\d+)x\s+", line)
    if m:
        count = int(m.group(1))
        line = line[m.end():]
    color: Color | None = None
    for color_name, color_enum in _COLOR_MAP.items():
        suffix = f"({color_name})"
        if line.lower().endswith(suffix):
            color = color_enum
            line = line[: -len(suffix)].strip()
            break
    if not line:
        return None
    return DeckEntry(name=line, color=color, count=count)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def card_db() -> CardDatabase:
    return CardDatabase.load(DATA_DIR / "cards.tsv")


@pytest.fixture(scope="module")
def cindra_deck() -> DeckList:
    text = (REF_DIR / "decklist-cindra-blue.md").read_text()
    return parse_markdown_decklist(text)


@pytest.fixture(scope="module")
def arakni_deck() -> DeckList:
    text = (REF_DIR / "decklist-arakni.md").read_text()
    return parse_markdown_decklist(text)


# ---------------------------------------------------------------------------
# Event tracker — collects event counts for post-game validation
# ---------------------------------------------------------------------------


class EventTracker:
    """Registers handlers on the EventBus to count events by type."""

    def __init__(self, event_bus: EventBus) -> None:
        self.counts: Counter[EventType] = Counter()
        self._event_bus = event_bus
        for et in EventType:
            event_bus.register_handler(et, self._make_handler(et))

    def _make_handler(self, event_type: EventType):
        def handler(event: GameEvent) -> None:
            self.counts[event_type] += 1
        return handler


# ---------------------------------------------------------------------------
# State invariant validators
# ---------------------------------------------------------------------------


def _collect_all_cards(state) -> list[CardInstance]:
    """Collect every card instance across both players' zones."""
    cards: list[CardInstance] = []
    for ps in state.players:
        if ps.hero:
            cards.append(ps.hero)
        if ps.original_hero:
            cards.append(ps.original_hero)
        cards.extend(ps.hand)
        cards.extend(ps.deck)
        cards.extend(ps.arsenal)
        cards.extend(ps.pitch)
        cards.extend(ps.graveyard)
        cards.extend(ps.banished)
        cards.extend(ps.soul)
        cards.extend(ps.weapons)
        cards.extend(ps.permanents)
        cards.extend(ps.demi_heroes)
        for eq in ps.equipment.values():
            if eq is not None:
                # Skip equipment currently on the combat chain — it will be
                # collected from link.defending_cards to avoid double-counting.
                if eq.zone == Zone.COMBAT_CHAIN:
                    continue
                cards.append(eq)
    # Combat chain cards
    for link in state.combat_chain.chain_links:
        if link.active_attack:
            cards.append(link.active_attack)
        cards.extend(link.defending_cards)
    # Stack
    for layer in state.stack:
        if layer.card:
            cards.append(layer.card)
    return cards


def validate_final_state(state, result: GameResult, tracker: EventTracker, seed: int) -> list[str]:
    """Validate all game-state invariants after a completed game. Returns list of violations."""
    violations: list[str] = []
    tag = f"[seed={seed}]"

    # --- Game completion invariants ---
    if result.turns <= 0:
        violations.append(f"{tag} Turn count is {result.turns}, expected > 0")

    if result.winner is not None:
        winner_life = result.final_life[result.winner]
        loser_life = result.final_life[1 - result.winner]
        if winner_life <= 0:
            violations.append(f"{tag} Winner (P{result.winner}) has life={winner_life}, expected > 0")
        if loser_life != 0:
            violations.append(f"{tag} Loser (P{1-result.winner}) has life={loser_life}, expected == 0")
    else:
        # No winner => either turn limit or simultaneous death (draw)
        both_dead = all(life == 0 for life in result.final_life)
        if not both_dead and result.turns < MAX_TURNS:
            violations.append(f"{tag} No winner and only {result.turns} turns (< {MAX_TURNS})")

    # --- Player state invariants ---
    for i, ps in enumerate(state.players):
        ptag = f"{tag} P{i}"

        if ps.life_total < 0:
            violations.append(f"{ptag} has negative life: {ps.life_total}")

        if len(ps.deck) < 0:
            violations.append(f"{ptag} has negative deck size: {len(ps.deck)}")

        # Hand size: intellect is typically 4, but with some buffer allow up to 20
        intellect = ps.hero.definition.intellect if ps.hero else 4
        max_hand = (intellect or 4) + 16  # generous buffer
        if len(ps.hand) > max_hand:
            violations.append(f"{ptag} hand size {len(ps.hand)} > {max_hand}")

        # Equipment slots have at most 1 card each
        for slot in EquipmentSlot:
            eq = ps.equipment.get(slot)
            # This is enforced by the dict structure, but check anyway
            if eq is not None and not isinstance(eq, CardInstance):
                violations.append(f"{ptag} equipment slot {slot} has non-CardInstance: {type(eq)}")

    # --- Resource invariants (final state) ---
    for i in range(2):
        rp = state.resource_points.get(i, 0)
        if rp < 0:
            violations.append(f"{tag} P{i} has negative resources: {rp}")

    # --- Card uniqueness: no duplicate instance IDs ---
    all_cards = _collect_all_cards(state)
    # Filter out proxies — they are synthetic copies and may share IDs with weapons
    non_proxy_cards = [c for c in all_cards if not c.is_proxy]
    id_counts = Counter(c.instance_id for c in non_proxy_cards)
    duplicates = {iid: cnt for iid, cnt in id_counts.items() if cnt > 1}
    if duplicates:
        # Provide names for debugging
        for iid, cnt in duplicates.items():
            names = [c.name for c in non_proxy_cards if c.instance_id == iid]
            violations.append(f"{tag} Duplicate instance_id {iid} appears {cnt} times: {names}")

    # --- Event invariants ---
    if tracker.counts[EventType.DEAL_DAMAGE] == 0:
        violations.append(f"{tag} No DEAL_DAMAGE events (game was completely passive)")

    if tracker.counts[EventType.ATTACK_DECLARED] == 0:
        violations.append(f"{tag} No ATTACK_DECLARED events (no attacks in the entire game)")

    return violations


# ---------------------------------------------------------------------------
# Helper: run a single game with validation
# ---------------------------------------------------------------------------


def run_validated_game(
    card_db: CardDatabase,
    deck1: DeckList,
    deck2: DeckList,
    seed: int,
) -> tuple[GameResult, list[str]]:
    """Run a game and validate invariants. Returns (result, violations)."""
    p1 = RandomPlayer(seed=seed)
    p2 = RandomPlayer(seed=seed + 1000)
    game = Game(card_db, deck1, deck2, p1, p2, seed=seed)

    # Attach event tracker
    tracker = EventTracker(game.events)

    result = game.play()
    violations = validate_final_state(game.state, result, tracker, seed)
    return result, violations


# ---------------------------------------------------------------------------
# Stress tests: Cindra P1, Arakni P2
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(100))
def test_cindra_vs_arakni(seed: int, card_db: CardDatabase, cindra_deck: DeckList, arakni_deck: DeckList) -> None:
    """Full game with Cindra P1, Arakni P2. Validate invariants."""
    result, violations = run_validated_game(card_db, cindra_deck, arakni_deck, seed)
    assert not violations, "\n".join(violations)


# ---------------------------------------------------------------------------
# Stress tests: Arakni P1, Cindra P2 (reversed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(100))
def test_arakni_vs_cindra(seed: int, card_db: CardDatabase, arakni_deck: DeckList, cindra_deck: DeckList) -> None:
    """Full game with Arakni P1, Cindra P2. Validate invariants."""
    result, violations = run_validated_game(card_db, arakni_deck, cindra_deck, seed)
    assert not violations, "\n".join(violations)
