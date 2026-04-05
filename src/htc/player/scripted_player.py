"""A player that follows a predetermined script of actions.

Used for scenario tests to drive specific game sequences through
the real engine so events fire naturally and the auto-snapshot
recorder captures rich state histories.
"""

from __future__ import annotations

import logging

from htc.engine.actions import Decision, PlayerResponse
from htc.state.game_state import GameState

log = logging.getLogger(__name__)


class ScriptedPlayer:
    """Player that follows a scripted sequence of decisions.

    Used for scenario tests to drive specific game sequences through
    the real engine. Falls back to 'pass' when the script is exhausted.

    The script is a list of entries. Each ``decide()`` call consumes
    the next entry:

    - ``str`` — a single action_id to select.
    - ``list[str]`` — multiple action_ids (for multi-select like defend).
    - ``"*first"`` — pick the first non-pass option.
    - ``"*pass"`` — always pass.
    - ``"*first_attack"`` — pick the first option whose action_id starts
      with ``"play_"`` or ``"activate_"``, falling back to ``"*first"``.

    When the script is exhausted, auto-passes all remaining decisions.
    """

    def __init__(self, script: list[str | list[str]] | None = None) -> None:
        self._script: list[str | list[str]] = list(script) if script else []
        self._step = 0
        self.decisions_seen: list[Decision] = []

    @property
    def exhausted(self) -> bool:
        """True when the script has been fully consumed."""
        return self._step >= len(self._script)

    def decide(self, game_state: GameState, decision: Decision) -> PlayerResponse:
        self.decisions_seen.append(decision)

        if self.exhausted:
            return self._auto_pass(decision)

        entry = self._script[self._step]
        self._step += 1

        # Special directives
        if isinstance(entry, str):
            if entry == "*pass":
                return self._make_pass(decision)
            if entry == "*first":
                return self._pick_first(decision)
            if entry == "*first_attack":
                return self._pick_first_attack(decision)
            # Literal action_id
            return self._select_ids(decision, [entry])

        # list[str] — multi-select
        if isinstance(entry, list):
            return self._select_ids(decision, entry)

        log.warning("ScriptedPlayer: unrecognized script entry %r, auto-passing", entry)
        return self._make_pass(decision)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _auto_pass(self, decision: Decision) -> PlayerResponse:
        """Script exhausted — pass everything."""
        return self._make_pass(decision)

    def _make_pass(self, decision: Decision) -> PlayerResponse:
        """Return a pass response."""
        # Check if 'pass' is an explicit option
        pass_ids = [o.action_id for o in decision.options if o.action_id == "pass"]
        if pass_ids:
            return PlayerResponse(selected_option_ids=["pass"])
        # If no explicit pass and min_selections == 0, return empty
        if decision.min_selections == 0:
            return PlayerResponse(selected_option_ids=[])
        # Otherwise pick the first option (can't pass)
        if decision.options:
            return PlayerResponse(selected_option_ids=[decision.options[0].action_id])
        return PlayerResponse(selected_option_ids=[])

    def _pick_first(self, decision: Decision) -> PlayerResponse:
        """Pick the first non-pass option, or pass if none."""
        non_pass = [o for o in decision.options if o.action_id != "pass"]
        if non_pass:
            return PlayerResponse(selected_option_ids=[non_pass[0].action_id])
        return self._make_pass(decision)

    def _pick_first_attack(self, decision: Decision) -> PlayerResponse:
        """Pick the first play/activate option, falling back to *first."""
        for o in decision.options:
            if o.action_id.startswith("play_") or o.action_id.startswith("activate_"):
                return PlayerResponse(selected_option_ids=[o.action_id])
        return self._pick_first(decision)

    def _select_ids(self, decision: Decision, ids: list[str]) -> PlayerResponse:
        """Select specific action_ids. Warns if any are not available."""
        available = {o.action_id for o in decision.options}
        missing = [aid for aid in ids if aid not in available]
        if missing:
            log.warning(
                "ScriptedPlayer step %d: requested ids %s not in available %s. "
                "Falling back to *first.",
                self._step - 1,
                missing,
                sorted(available),
            )
            return self._pick_first(decision)
        return PlayerResponse(selected_option_ids=ids)
