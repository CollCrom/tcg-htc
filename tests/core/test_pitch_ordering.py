"""Tests for pitch-stacking: player-chosen order of pitched cards to deck bottom."""

from __future__ import annotations

from engine.rules.actions import PlayerResponse
from engine.enums import Zone
from tests.conftest import make_game_shell, make_pitch_card


def test_pitch_order_two_cards_player_chosen_order():
    """When 2 cards are pitched, the player's chosen order is reflected
    at the bottom of the deck.

    Set up: empty deck, 2 cards in the pitch zone.
    Mock ask: choose card B first, then card A goes automatically.
    Expect: deck bottom = [B, A] (B at index 0, A at index 1).
    """
    game = make_game_shell(life=20)
    player = game.state.players[0]
    player.deck.clear()

    card_a = make_pitch_card(instance_id=201, owner_index=0, pitch=1)
    card_b = make_pitch_card(instance_id=202, owner_index=0, pitch=3)
    card_a.zone = Zone.PITCH
    card_b.zone = Zone.PITCH
    player.pitch.extend([card_a, card_b])

    # Player chooses card_b first (it goes to the bottom-most position)
    def mock_ask(decision):
        return PlayerResponse(
            selected_option_ids=[f"pitch_order_{card_b.instance_id}"],
        )

    game._ask = mock_ask

    ordered = game._choose_pitch_order(player)

    assert len(ordered) == 2
    assert ordered[0] is card_b, "First chosen card should be bottom-most"
    assert ordered[1] is card_a, "Last card placed automatically on top"


def test_pitch_order_three_cards_player_chosen_order():
    """When 3 cards are pitched, the player's choices control the full order.

    Mock ask returns card_c first, then card_a. card_b goes automatically last.
    Expected deck bottom: [C, A, B].
    """
    game = make_game_shell(life=20)
    player = game.state.players[0]
    player.deck.clear()

    card_a = make_pitch_card(instance_id=301, owner_index=0, pitch=1)
    card_b = make_pitch_card(instance_id=302, owner_index=0, pitch=2)
    card_c = make_pitch_card(instance_id=303, owner_index=0, pitch=3)
    for c in (card_a, card_b, card_c):
        c.zone = Zone.PITCH
    player.pitch.extend([card_a, card_b, card_c])

    call_count = [0]

    def mock_ask(decision):
        call_count[0] += 1
        if call_count[0] == 1:
            # First pick: card_c
            return PlayerResponse(
                selected_option_ids=[f"pitch_order_{card_c.instance_id}"],
            )
        else:
            # Second pick: card_a
            return PlayerResponse(
                selected_option_ids=[f"pitch_order_{card_a.instance_id}"],
            )

    game._ask = mock_ask

    ordered = game._choose_pitch_order(player)

    assert len(ordered) == 3
    assert ordered[0] is card_c, "First chosen = bottom-most"
    assert ordered[1] is card_a, "Second chosen = middle"
    assert ordered[2] is card_b, "Last card placed automatically = top"


def test_pitch_order_reflected_in_deck_after_end_phase():
    """Full integration: pitched cards end up at deck bottom in chosen order
    after _run_end_phase().
    """
    game = make_game_shell(life=20)
    player = game.state.players[0]
    player.deck.clear()

    # Fill hand to intellect (default 4) so end-phase draw is skipped
    for i in range(4):
        hc = make_pitch_card(instance_id=50 + i, owner_index=0, pitch=1)
        hc.zone = Zone.HAND
        player.hand.append(hc)

    # Put an existing card in deck so we can verify ordering
    existing = make_pitch_card(instance_id=100, owner_index=0, pitch=1)
    existing.zone = Zone.DECK
    player.deck.append(existing)

    card_a = make_pitch_card(instance_id=201, owner_index=0, pitch=1)
    card_b = make_pitch_card(instance_id=202, owner_index=0, pitch=3)
    card_a.zone = Zone.PITCH
    card_b.zone = Zone.PITCH
    player.pitch.extend([card_a, card_b])

    # Choose card_b first (bottom-most), card_a automatically second
    def mock_ask(decision):
        # Check if this is a pitch ordering decision by looking at option IDs
        if decision.options and any(
            o.action_id.startswith("pitch_order_") for o in decision.options
        ):
            return PlayerResponse(
                selected_option_ids=[f"pitch_order_{card_b.instance_id}"],
            )
        return PlayerResponse(selected_option_ids=["pass"])

    game._ask = mock_ask

    game._run_end_phase()

    # Deck should be: [existing, card_b, card_a]
    # existing was already at index 0, then card_b (chosen first) and card_a appended
    assert len(player.deck) == 3
    assert player.deck[0] is existing
    assert player.deck[1] is card_b, "First chosen pitch card at deck bottom"
    assert player.deck[2] is card_a, "Last pitch card on top of pitched group"
    assert len(player.pitch) == 0, "Pitch zone should be cleared"
    assert card_a.zone == Zone.DECK
    assert card_b.zone == Zone.DECK
