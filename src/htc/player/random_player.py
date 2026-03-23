from __future__ import annotations

from random import Random

from htc.engine.actions import Decision, PlayerResponse
from htc.enums import DecisionType
from htc.state.game_state import GameState


class RandomPlayer:
    """Picks randomly from legal options. Used for testing and simulation."""

    def __init__(self, seed: int = 0) -> None:
        self.rng = Random(seed)

    def decide(self, game_state: GameState, decision: Decision) -> PlayerResponse:
        if not decision.options:
            return PlayerResponse()

        # For single-select decisions, pick one at random
        if decision.max_selections == 1 or decision.decision_type in (
            DecisionType.PLAY_OR_PASS,
            DecisionType.CHOOSE_ARSENAL_CARD,
            DecisionType.CHOOSE_CARDS_TO_PITCH,
            DecisionType.OPTIONAL_ABILITY,
        ):
            opt = self.rng.choice(decision.options)
            return PlayerResponse(selected_option_ids=[opt.action_id])

        # For reaction decisions: usually pass, occasionally play one
        if decision.decision_type == DecisionType.PLAY_REACTION_OR_PASS:
            non_pass = [o for o in decision.options if o.action_id != "pass"]
            if non_pass and self.rng.random() < 0.3:
                opt = self.rng.choice(non_pass)
                return PlayerResponse(selected_option_ids=[opt.action_id])
            return PlayerResponse(selected_option_ids=["pass"])

        # For defend decisions: pick 0-3 cards randomly (not the whole hand)
        if decision.decision_type == DecisionType.CHOOSE_DEFENDERS:
            non_pass = [o for o in decision.options if o.action_id != "pass"]
            n = self.rng.randint(0, min(3, len(non_pass)))
            if n == 0:
                return PlayerResponse(selected_option_ids=["pass"])
            selected = self.rng.sample(non_pass, n)
            return PlayerResponse(selected_option_ids=[o.action_id for o in selected])

        # Multi-select: pick a random subset
        n = self.rng.randint(decision.min_selections, min(decision.max_selections, len(decision.options)))
        selected = self.rng.sample(decision.options, n)
        return PlayerResponse(selected_option_ids=[opt.action_id for opt in selected])
