"""Tests for defense reaction ability effects.

Covers Fate Foreseen (Opt 1) and Sink Below (cycle).
Defense reactions contribute defense value via the normal combat system;
these tests verify their additional effects.
"""

from htc.enums import Color, Zone
from tests.conftest import make_card, make_game_shell, make_mock_ask
from tests.abilities.conftest import make_defense_reaction as _make_defense_reaction


# ---------------------------------------------------------------------------
# Fate Foreseen — Opt 1
# ---------------------------------------------------------------------------


def test_fate_foreseen_triggers_opt():
    """Fate Foreseen triggers Opt 1 when its defense reaction effect fires."""
    game = make_game_shell()

    # Set up deck for player 1 (the defender)
    top_card = make_card(instance_id=50, name="Top Card", owner_index=1, zone=Zone.DECK)
    bottom_card = make_card(instance_id=51, name="Bottom Card", owner_index=1, zone=Zone.DECK)
    game.state.players[1].deck = [top_card, bottom_card]

    # Mock ask: when Opt prompt appears, put the top card on bottom
    game._ask = make_mock_ask({"Opt": [f"opt_bottom_{top_card.instance_id}"]})
    # Re-wire keyword_engine's ask to the mock
    game.keyword_engine._ask = game._ask

    # Set up combat chain
    attack = make_card(instance_id=1, power=5, zone=Zone.COMBAT_CHAIN)
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    # Apply Fate Foreseen effect (as player 1, the defender)
    ff_card = _make_defense_reaction("Fate Foreseen", instance_id=20, owner_index=1)
    game._apply_card_ability(ff_card, 1, "defense_reaction_effect")

    # Top card should have moved to the bottom
    assert game.state.players[1].deck[-1] is top_card
    assert game.state.players[1].deck[0] is bottom_card


def test_fate_foreseen_keep_all_on_top():
    """Fate Foreseen's Opt 1 — player can choose to keep all on top."""
    game = make_game_shell()

    top_card = make_card(instance_id=50, name="Top Card", owner_index=1, zone=Zone.DECK)
    game.state.players[1].deck = [top_card]

    # Mock ask: pass (keep on top)
    game._ask = make_mock_ask({"Opt": ["pass"]})
    game.keyword_engine._ask = game._ask

    attack = make_card(instance_id=1, power=5, zone=Zone.COMBAT_CHAIN)
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    ff_card = _make_defense_reaction("Fate Foreseen", instance_id=20, owner_index=1)
    game._apply_card_ability(ff_card, 1, "defense_reaction_effect")

    # Card should still be on top
    assert game.state.players[1].deck[0] is top_card


# ---------------------------------------------------------------------------
# Sink Below — put a card from hand on bottom, draw a card
# ---------------------------------------------------------------------------


def test_sink_below_cycles_card():
    """Sink Below: put a card from hand on bottom of deck, then draw."""
    game = make_game_shell()

    # Player 1's hand has one card to cycle
    hand_card = make_card(instance_id=30, name="Hand Card", owner_index=1, zone=Zone.HAND)
    game.state.players[1].hand = [hand_card]

    # Player 1's deck has one card to draw
    deck_card = make_card(instance_id=31, name="Deck Card", owner_index=1, zone=Zone.DECK)
    game.state.players[1].deck = [deck_card]

    # Mock ask: when Sink Below prompt appears, choose to put hand_card on bottom
    game._ask = make_mock_ask({"Sink Below": [f"bottom_{hand_card.instance_id}"]})

    attack = make_card(instance_id=1, power=5, zone=Zone.COMBAT_CHAIN)
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    sb_card = _make_defense_reaction("Sink Below", instance_id=20, owner_index=1)
    game._apply_card_ability(sb_card, 1, "defense_reaction_effect")

    # hand_card should be on bottom of deck
    assert hand_card in game.state.players[1].deck
    # deck_card should be in hand (drawn)
    assert deck_card in game.state.players[1].hand
    assert hand_card not in game.state.players[1].hand


def test_sink_below_pass_no_cycle():
    """Sink Below: player can choose not to put a card on bottom."""
    game = make_game_shell()

    hand_card = make_card(instance_id=30, name="Hand Card", owner_index=1, zone=Zone.HAND)
    game.state.players[1].hand = [hand_card]
    deck_card = make_card(instance_id=31, name="Deck Card", owner_index=1, zone=Zone.DECK)
    game.state.players[1].deck = [deck_card]

    # Mock ask: pass
    game._ask = make_mock_ask({"Sink Below": ["pass"]})

    attack = make_card(instance_id=1, power=5, zone=Zone.COMBAT_CHAIN)
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    sb_card = _make_defense_reaction("Sink Below", instance_id=20, owner_index=1)
    game._apply_card_ability(sb_card, 1, "defense_reaction_effect")

    # Nothing should have changed
    assert hand_card in game.state.players[1].hand
    assert deck_card in game.state.players[1].deck


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


def test_defense_reaction_no_ability_still_defends():
    """A defense reaction with no registered ability still contributes defense."""
    game = make_game_shell()
    attack = make_card(instance_id=1, power=5, zone=Zone.COMBAT_CHAIN)

    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    # Unknown defense reaction — no registered ability
    unknown_dr = _make_defense_reaction(
        "Unknown DR", instance_id=20, defense=3, owner_index=1,
    )
    game.combat_mgr.add_defender(game.state, link, unknown_dr)

    # Ability call does nothing
    game._apply_card_ability(unknown_dr, 1, "defense_reaction_effect")

    # But the card still defends for 3
    total_defense = game.combat_mgr.get_total_defense(game.state, link)
    assert total_defense == 3
