"""Tests for Retrieve keyword infrastructure.

Retrieve: Return a card from your graveyard to hand.
This tests the generic infrastructure; specific card restrictions are Phase 5.
"""
from htc.enums import Zone
from tests.conftest import make_card, make_game_shell, make_mock_ask


def _mock_retrieve_ask(retrieve_id: int | None):
    """Mock that selects a specific card to retrieve, or passes."""
    ids = [f"retrieve_{retrieve_id}"] if retrieve_id is not None else []
    return make_mock_ask({"retrieve": ids})


def test_retrieve_returns_card_to_hand():
    """Retrieve moves a card from graveyard to hand."""
    game = make_game_shell()
    state = game.state

    card = make_card(instance_id=10, name="Graveyard Card", owner_index=0, zone=Zone.GRAVEYARD)
    state.players[0].graveyard = [card]
    state.players[0].hand = []

    game._ask = _mock_retrieve_ask(10)
    result = game._perform_retrieve(0)

    assert result is card
    assert card.zone == Zone.HAND
    assert card in state.players[0].hand
    assert card not in state.players[0].graveyard


def test_retrieve_declined():
    """Player can decline to retrieve."""
    game = make_game_shell()
    state = game.state

    card = make_card(instance_id=10, name="Graveyard Card", owner_index=0, zone=Zone.GRAVEYARD)
    state.players[0].graveyard = [card]

    game._ask = _mock_retrieve_ask(None)
    result = game._perform_retrieve(0)

    assert result is None
    assert card in state.players[0].graveyard


def test_retrieve_empty_graveyard():
    """Retrieve with empty graveyard returns None."""
    game = make_game_shell()
    state = game.state
    state.players[0].graveyard = []

    result = game._perform_retrieve(0)
    assert result is None


def test_retrieve_with_filter():
    """Retrieve with a card_filter only shows matching cards."""
    game = make_game_shell()
    state = game.state

    card_a = make_card(instance_id=10, name="Attack Card", owner_index=0, zone=Zone.GRAVEYARD)
    card_b = make_card(instance_id=11, name="Non-Attack", owner_index=0, zone=Zone.GRAVEYARD,
                       is_attack=False)
    state.players[0].graveyard = [card_a, card_b]
    state.players[0].hand = []

    # Filter: only attack cards
    game._ask = _mock_retrieve_ask(10)
    result = game._perform_retrieve(0, card_filter=lambda c: c.definition.is_attack)

    assert result is card_a
    assert card_a.zone == Zone.HAND


def test_retrieve_filter_no_matches():
    """Retrieve with filter that matches nothing returns None."""
    game = make_game_shell()
    state = game.state

    card = make_card(instance_id=10, name="Card", owner_index=0, zone=Zone.GRAVEYARD)
    state.players[0].graveyard = [card]

    result = game._perform_retrieve(0, card_filter=lambda c: False)
    assert result is None
