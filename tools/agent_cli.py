"""Tiny client for tools/match_server.py.

Designed for sub-agents that play a match by issuing one Bash call per
decision. Pure stdlib (urllib + json) so no extra deps in the agent's
shell.

Subcommands
-----------

``status``
    Print current match status.

``pending --player A``
    Print the pending decision for that seat (or ``"pending": null`` if
    it is not their turn). Returns immediately.

``wait --player A [--timeout 120] [--interval 0.5]``
    Block until either a pending decision is available for that seat or
    the game ends. Prints the response. Useful right after submitting an
    action when the engine needs to advance through the opponent's turn
    before asking again.

``act --player A --id pass [--id ...]``
    Submit one or more action_ids for the seat's current pending
    decision. Use ``--id`` once per id (multi-select decisions take >1).

``card --name "Codex of Frailty"``
    Look up a card's full ``functional_text`` / ``type_text``. Useful
    when the snapshot omitted that text for a cold-zone card (graveyard,
    banished face-up). Case- and diacritic-insensitive.

All commands print one JSON line to stdout. Exit code 0 on success, 1 on
HTTP error, 2 on local error or timeout.

Examples::

    python tools/agent_cli.py wait --player A
    python tools/agent_cli.py act --player A --id pass
    python tools/agent_cli.py status
    python tools/agent_cli.py card --name "Codex of Frailty"
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def _http(method: str, url: str, body: dict | None = None, timeout: float = 30.0) -> dict:
    data: bytes | None = None
    headers: dict[str, str] = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        # Surface the server's JSON error body if it sent one.
        try:
            return {"_http_status": exc.code, **json.loads(exc.read().decode("utf-8") or "{}")}
        except Exception:
            return {"_http_status": exc.code, "error": exc.reason}


def _base(args: argparse.Namespace) -> str:
    return f"http://{args.host}:{args.port}"


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> int:
    out = _http("GET", f"{_base(args)}/status")
    print(json.dumps(out, ensure_ascii=False))
    return 0 if "error" not in out else 1


def cmd_pending(args: argparse.Namespace) -> int:
    out = _http("GET", f"{_base(args)}/pending?player={args.player}")
    print(json.dumps(out, ensure_ascii=False))
    return 0 if "error" not in out else 1


def cmd_act(args: argparse.Namespace) -> int:
    body = {"selected_option_ids": list(args.id)}
    out = _http("POST", f"{_base(args)}/action?player={args.player}", body=body)
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out.get("ok") else 1


def cmd_card(args: argparse.Namespace) -> int:
    from urllib.parse import quote
    out = _http("GET", f"{_base(args)}/card?name={quote(args.name)}")
    print(json.dumps(out, ensure_ascii=False))
    return 0 if "error" not in out else 1


def cmd_wait(args: argparse.Namespace) -> int:
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        out = _http("GET", f"{_base(args)}/pending?player={args.player}")
        status = out.get("status") or {}
        if isinstance(status, dict):
            phase = status.get("status")
        else:
            phase = None
        # If game finished or errored, surface immediately.
        if phase in ("game_over", "error"):
            print(json.dumps(out, ensure_ascii=False))
            return 0
        if out.get("pending") is not None:
            print(json.dumps(out, ensure_ascii=False))
            return 0
        time.sleep(args.interval)
    print(
        json.dumps({"error": "timed out waiting for pending decision"}, ensure_ascii=False)
    )
    return 2


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python tools/agent_cli.py")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")

    sp = sub.add_parser("pending")
    sp.add_argument("--player", required=True, choices=["A", "B"])

    sa = sub.add_parser("act")
    sa.add_argument("--player", required=True, choices=["A", "B"])
    sa.add_argument(
        "--id", action="append", required=True,
        help="One action_id from the current decision's options. "
             "Pass --id multiple times for multi-select decisions.",
    )

    sw = sub.add_parser("wait")
    sw.add_argument("--player", required=True, choices=["A", "B"])
    sw.add_argument("--interval", type=float, default=0.5)
    sw.add_argument("--timeout", type=float, default=120.0)

    sc = sub.add_parser("card")
    sc.add_argument(
        "--name", required=True,
        help="Card name; case- and diacritic-insensitive lookup.",
    )

    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    return {
        "status": cmd_status,
        "pending": cmd_pending,
        "act": cmd_act,
        "wait": cmd_wait,
        "card": cmd_card,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
