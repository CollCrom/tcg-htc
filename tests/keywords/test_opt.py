"""Tests for Opt N keyword (8.5).

Opt N: Look at the top N cards of your deck, you may put any of them
on the bottom in any order.
"""
from htc.enums import Zone
from tests.conftest import make_card, make_game_shell, make_mock_ask


def _mock_opt_ask(bottom_ids: list[int]):
    """Mock that selects specific cards to put on bottom."""
    ids = [f"opt_bottom_{iid}" for iid in bottom_ids]
    return make_mock_ask({"Opt": ids})


def test_opt_puts_cards_on_bottom():
    """Opt N: selected cards move to bottom of deck."""
    game = make_game_shell()
    state = game.state

    cards = [make_card(instance_id=i, name=f"Card {i}", owner_index=0, zone=Zone.DECK) for i in range(5)]
    state.players[0].deck = cards

    # Opt 3: look at top 3, put card 1 on bottom
    game._ask = _mock_opt_ask([1])
    game._perform_opt(0, 3)

    # Card 1 should be at the bottom
    deck = state.players[0].deck
    assert deck[-1].instance_id == 1
    # Other top cards stay in place
    assert deck[0].instance_id == 0
    assert deck[1].instance_id == 2


def test_opt_keep_all_on_top():
    """Opt N: player can choose to keep all on top."""
    game = make_game_shell()
    state = game.state

    cards = [make_card(instance_id=i, name=f"Card {i}", owner_index=0, zone=Zone.DECK) for i in range(5)]
    state.players[0].deck = cards

    game._ask = _mock_opt_ask([])
    game._perform_opt(0, 3)

    # Deck order unchanged
    deck = state.players[0].deck
    assert [c.instance_id for c in deck] == [0, 1, 2, 3, 4]


def test_opt_multiple_to_bottom():
    """Opt N: multiple cards can go to bottom."""
    game = make_game_shell()
    state = game.state

    cards = [make_card(instance_id=i, name=f"Card {i}", owner_index=0, zone=Zone.DECK) for i in range(5)]
    state.players[0].deck = cards

    game._ask = _mock_opt_ask([0, 2])
    game._perform_opt(0, 3)

    deck = state.players[0].deck
    # Cards 0 and 2 should be at the bottom, card 1 stays on top
    assert deck[0].instance_id == 1
    assert set(c.instance_id for c in deck[-2:]) == {0, 2}


def test_opt_empty_deck():
    """Opt N with empty deck does nothing."""
    game = make_game_shell()
    state = game.state
    state.players[0].deck = []

    game._ask = _mock_opt_ask([])
    game._perform_opt(0, 3)
    # No error
    assert state.players[0].deck == []


def test_opt_deck_smaller_than_n():
    """Opt N with fewer than N cards looks at all available cards."""
    game = make_game_shell()
    state = game.state

    cards = [make_card(instance_id=i, name=f"Card {i}", owner_index=0, zone=Zone.DECK) for i in range(2)]
    state.players[0].deck = cards

    game._ask = _mock_opt_ask([0])
    game._perform_opt(0, 5)

    deck = state.players[0].deck
    assert deck[0].instance_id == 1
    assert deck[-1].instance_id == 0
