"""End-to-end test for the HTTP match-server bridge.

Spawns ``python tools/match_server.py`` as a subprocess and drives both
seats over real HTTP with a "random pick" client until the game ends.
This exercises:

* The ``HttpBridgePlayer`` threading bridge (engine thread blocking on
  Condition vars while HTTP handler threads deliver responses).
* The wire-format parity with the JSONL stdio protocol — every decision
  payload should have the documented fields and use enum *values*.
* The pre-game-setup placeholder, since the chosen decks have multi-option
  equipment slots that fire ``CHOOSE_EQUIPMENT`` before ``state.players``
  is populated.
* The redacted ``state`` snapshot once the game starts.
* Game completion: ``game_over`` reports a winner, valid final life
  totals, and a positive turn count.
"""

from __future__ import annotations

import json
import random
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

from engine.enums import ActionType, DecisionType
from tests.conftest import CARDS_TSV, REF_DIR, REPO_ROOT

# Generous: random play can take ~1500 decisions / ~30s to converge.
SUBPROCESS_TIMEOUT_S = 120
HTTP_TIMEOUT_S = 10
SERVER_BOOT_TIMEOUT_S = 10
DRIVE_DEADLINE_S = 90

MATCH_SERVER = REPO_ROOT / "tools" / "match_server.py"
DECK_A = REF_DIR / "decks" / "decklist-cindra-blue.md"
DECK_B = REF_DIR / "decks" / "decklist-arakni.md"

_ALLOWED_DECISION_TYPES = {e.value for e in DecisionType}
_ALLOWED_ACTION_TYPES = {e.value for e in ActionType}


pytestmark = pytest.mark.skipif(
    not (CARDS_TSV.exists() and DECK_A.exists() and DECK_B.exists()),
    reason="card database or required decks missing",
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _free_port() -> int:
    """Bind to port 0 to let the OS pick a free port, then release it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _http_get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _http_post(url: str, body: dict) -> tuple[int, dict]:
    """POST JSON; return (status_code, parsed_body). Raises only on 5xx."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            return resp.getcode(), json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        if 500 <= exc.code < 600:
            err_body = exc.read().decode("utf-8")
            raise AssertionError(
                f"POST {url} failed {exc.code}: {err_body}"
            ) from exc
        # 4xx — surface to caller so it can decide whether to retry.
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


def _wait_until_listening(port: int, timeout_s: float) -> None:
    """Poll /status until the server responds or timeout fires."""
    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            _http_get(f"http://127.0.0.1:{port}/status")
            return
        except Exception as exc:  # noqa: BLE001 — expected during boot
            last_err = exc
            time.sleep(0.1)
    raise TimeoutError(
        f"match server did not come up on port {port} within {timeout_s}s "
        f"(last error: {last_err})"
    )


def _validate_decision(decision: dict) -> None:
    """Assert a decision payload conforms to the documented wire format."""
    assert decision["type"] == "decision"
    assert decision["decision_type"] in _ALLOWED_DECISION_TYPES, (
        f"unknown decision_type {decision['decision_type']!r}"
    )
    assert isinstance(decision["prompt"], str)
    assert isinstance(decision["min_selections"], int)
    assert isinstance(decision["max_selections"], int)
    assert decision["min_selections"] <= decision["max_selections"]
    assert decision["player_index"] in (0, 1)
    options = decision["options"]
    assert isinstance(options, list) and len(options) >= 1
    for opt in options:
        assert isinstance(opt["action_id"], str) and opt["action_id"]
        assert opt["action_type"] in _ALLOWED_ACTION_TYPES
        assert isinstance(opt["description"], str)
    state = decision["state"]
    assert isinstance(state, dict) and state, "state must be a non-empty dict"
    if state.get("phase") == "pre_game_setup":
        # Placeholder during _setup_game — only requires the marker fields.
        return
    # Mid-game snapshot — must have the four top-level keys.
    for key in ("you", "opponent", "combat_chain", "turn"):
        assert key in state, f"snapshot missing {key!r}"
    # Info-hiding: opponent must not expose 'hand' (only 'hand_size').
    assert "hand" not in state["opponent"], (
        "opponent view leaked 'hand' field (info-hiding broken)"
    )
    assert "hand_size" in state["opponent"]


def _pick(rng: random.Random, decision: dict) -> list[str]:
    options = decision["options"]
    min_n = decision["min_selections"]
    max_n = decision["max_selections"]
    if not options:
        return []
    if max_n == 1:
        return [rng.choice(options)["action_id"]]
    n = rng.randint(min_n, min(max_n, len(options)))
    if n == 0:
        for opt in options:
            if opt["action_id"] == "pass":
                return ["pass"]
        return []
    chosen = rng.sample(options, n)
    return [o["action_id"] for o in chosen]


# ---------------------------------------------------------------------------
# the test
# ---------------------------------------------------------------------------


def test_match_server_drives_full_game_to_completion(tmp_path):
    """Boot match_server, drive both seats with random picks, expect game_over."""
    port = _free_port()
    log_path = tmp_path / "server.log"

    proc = subprocess.Popen(
        [
            sys.executable, str(MATCH_SERVER),
            "--port", str(port),
            "--seed", "7",
            "--deck-a", str(DECK_A),
            "--deck-b", str(DECK_B),
            "--no-event-log",
        ],
        stdout=log_path.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        cwd=REPO_ROOT,
    )
    try:
        _wait_until_listening(port, SERVER_BOOT_TIMEOUT_S)

        base = f"http://127.0.0.1:{port}"
        rng = random.Random(11)
        decisions_seen = 0
        deadline = time.time() + DRIVE_DEADLINE_S
        last_status = "in_progress"

        while time.time() < deadline:
            status = _http_get(f"{base}/status")["status"]
            phase = status.get("status")
            last_status = phase
            if phase in ("game_over", "error"):
                break

            progressed = False
            for player in ("A", "B"):
                # Fetch + pick + submit, retrying once on a 409 indicating
                # the engine state moved between our GET and POST. Two
                # benign races we tolerate:
                #   * "unknown action_ids" — a new decision was raised for
                #     this player; the action_ids we picked belong to the
                #     previous decision.
                #   * "no pending decision" — the player's pending was
                #     cleared between our GET and POST (e.g. engine thread
                #     advanced after another seat acted, briefly leaving
                #     this seat idle). Re-fetching either returns the next
                #     decision or null (in which case the inner loop
                #     breaks). Manifests on slower runners where the GET
                #     reads stale pending state momentarily.
                # If two consecutive submissions both 409, that's a real
                # bridge bug and the test should fail.
                for attempt in range(2):
                    pending_resp = _http_get(
                        f"{base}/pending?player={player}",
                    )
                    pending = pending_resp.get("pending")
                    if pending is None:
                        break
                    _validate_decision(pending)
                    ids = _pick(rng, pending)
                    code, ack = _http_post(
                        f"{base}/action?player={player}",
                        {"selected_option_ids": ids},
                    )
                    if code == 200 and ack.get("ok") is True:
                        decisions_seen += 1
                        progressed = True
                        break
                    if code == 409:
                        err_msg = str(ack.get("error", ""))
                        if (
                            "unknown action_ids" in err_msg
                            or "no pending decision" in err_msg
                        ):
                            # Decision raced; loop and re-fetch.
                            continue
                    raise AssertionError(
                        f"act rejected for player {player} (code={code}): {ack}"
                    )
            if not progressed:
                # Engine is mid-resolution — yield briefly.
                time.sleep(0.02)

        assert last_status == "game_over", (
            f"game did not finish in {DRIVE_DEADLINE_S}s "
            f"(status={last_status}, decisions={decisions_seen}). "
            f"server log: {log_path}"
        )

        final = _http_get(f"{base}/status")["status"]
        assert final["status"] == "game_over"
        assert final["turns"] >= 1
        assert len(final["final_life"]) == 2
        assert decisions_seen > 0
        # Game can end with a winner (someone hit 0 life) or as a draw
        # (engine MAX_TURNS cap fires; both seats still alive).
        if final["winner"] is None:
            assert final["winner_seat"] is None
        else:
            assert final["winner"] in (0, 1)
            assert final["winner_seat"] in ("A", "B")
            loser_idx = 1 - final["winner"]
            assert final["final_life"][loser_idx] <= 0
            assert final["final_life"][final["winner"]] > 0

    finally:
        # Politely terminate; force-kill if it doesn't stop.
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def test_match_server_reports_pending_age_seconds(tmp_path):
    """``/pending`` exposes an increasing age while a decision is pending.

    Observability hook for analysts/orchestrators: when an opposing agent
    dies, the surviving seat's polls would otherwise look healthy
    (200 OK forever). ``pending_age_seconds`` lets a watchdog spot a
    wedged decision without requiring server-side enforcement.
    """
    port = _free_port()
    log_path = tmp_path / "server.log"
    proc = subprocess.Popen(
        [
            sys.executable, str(MATCH_SERVER),
            "--port", str(port),
            "--seed", "7",
            "--deck-a", str(DECK_A),
            "--deck-b", str(DECK_B),
            "--no-event-log",
        ],
        stdout=log_path.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        cwd=REPO_ROOT,
    )
    try:
        _wait_until_listening(port, SERVER_BOOT_TIMEOUT_S)
        base = f"http://127.0.0.1:{port}"

        # 1) Find a seat with a pending decision (whichever fires first
        # during pre-game equipment selection or the opening turn).
        active_seat: str | None = None
        first_age: float | None = None
        deadline = time.time() + 15.0
        while time.time() < deadline and active_seat is None:
            for seat in ("A", "B"):
                resp = _http_get(f"{base}/pending?player={seat}")
                if resp.get("pending") is not None:
                    active_seat = seat
                    age = resp.get("pending_age_seconds")
                    assert isinstance(age, (int, float)) and age >= 0.0, (
                        f"expected pending_age_seconds to be a non-negative number "
                        f"while a decision is pending; got {age!r}"
                    )
                    first_age = float(age)
                    break
            if active_seat is None:
                time.sleep(0.05)
        assert active_seat is not None, "no pending decision appeared within 15s"
        assert first_age is not None

        # Capture the decision payload for later submission.
        first_resp = _http_get(f"{base}/pending?player={active_seat}")
        decision = first_resp["pending"]
        assert decision is not None, "decision vanished between polls"

        # 2) Sleep, then re-poll: age should have increased.
        time.sleep(0.2)
        second = _http_get(f"{base}/pending?player={active_seat}")
        # If the decision is still pending, age must have grown.
        if second.get("pending") is not None:
            second_age = second.get("pending_age_seconds")
            assert isinstance(second_age, (int, float))
            assert second_age > first_age, (
                f"pending_age_seconds did not increase across polls: "
                f"first={first_age} second={second_age}"
            )
            prior_age = float(second_age)
        else:
            # Decision raced to completion before we could re-poll. Fine —
            # the age must be null in that case.
            assert second.get("pending_age_seconds") is None
            prior_age = first_age

        # 3) The seat with no pending decision (if any) must report
        # pending_age_seconds == null.
        idle_seat = "B" if active_seat == "A" else "A"
        idle_resp = _http_get(f"{base}/pending?player={idle_seat}")
        if idle_resp.get("pending") is None:
            assert idle_resp.get("pending_age_seconds") is None, (
                f"idle seat {idle_seat} reported non-null pending_age_seconds"
            )

        # 4) Submit an action for the active seat. Use the original
        # decision payload (re-fetch if the engine raced past it).
        cur = _http_get(f"{base}/pending?player={active_seat}")
        if cur.get("pending") is None:
            # Engine moved on; nothing more to verify on the post-submit
            # path beyond confirming the age really cleared.
            assert cur.get("pending_age_seconds") is None
            return
        decision = cur["pending"]
        rng = random.Random(31)
        ids = _pick(rng, decision)
        code, ack = _http_post(
            f"{base}/action?player={active_seat}",
            {"selected_option_ids": ids},
        )
        # Allow one retry on the documented 409 race.
        if code == 409 and "unknown action_ids" in str(ack.get("error", "")):
            cur = _http_get(f"{base}/pending?player={active_seat}")
            if cur.get("pending") is None:
                assert cur.get("pending_age_seconds") is None
                return
            ids = _pick(rng, cur["pending"])
            code, ack = _http_post(
                f"{base}/action?player={active_seat}",
                {"selected_option_ids": ids},
            )
        assert code == 200 and ack.get("ok") is True, (
            f"submission failed: code={code} ack={ack}"
        )

        # 5) Post-submit: the next /pending for this seat must NOT
        # carry the stale age. Either pending is null
        # (pending_age_seconds null) or a brand-new decision was raised
        # with a fresh, smaller age.
        post = _http_get(f"{base}/pending?player={active_seat}")
        post_age = post.get("pending_age_seconds")
        if post.get("pending") is None:
            assert post_age is None, (
                f"expected null pending_age_seconds after submission with no "
                f"pending decision; got {post_age!r}"
            )
        else:
            assert isinstance(post_age, (int, float))
            assert post_age < prior_age, (
                f"post-submission decision reported stale age "
                f"{post_age} >= prior {prior_age}"
            )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def test_match_server_rejects_unknown_player():
    """Sanity: invalid ?player= values get a 400."""
    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable, str(MATCH_SERVER),
            "--port", str(port),
            "--seed", "1",
            "--deck-a", str(DECK_A),
            "--deck-b", str(DECK_B),
            "--no-event-log",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=REPO_ROOT,
    )
    try:
        _wait_until_listening(port, SERVER_BOOT_TIMEOUT_S)
        url = f"http://127.0.0.1:{port}/pending?player=Z"
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S)
        assert exc_info.value.code == 400
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
