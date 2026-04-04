"""Generate a combined HTML viewer showing test steps + board state snapshots.

Reads the static test step walkthrough (from tests_to_html.py) and the
captured board state snapshots (from scenario_recorder.py), then generates
a single self-contained HTML page that interleaves code steps with
visual board states.

Usage:
    # First, run the instrumented tests to capture snapshots:
    pytest tests/scenarios/ -k "scenario" --tb=short

    # Then generate the combined HTML:
    python3 tools/scenario_viewer.py tests/scenarios/ scenario_snapshots/ combined_view.html
    open combined_view.html
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

from tools.tests_to_html import parse_test_file, STEP_ICONS, STEP_COLORS


def load_snapshots(snapshot_dir: Path) -> dict[str, list[dict]]:
    """Load all snapshot JSON files, keyed by test node ID."""
    result: dict[str, list[dict]] = {}
    if not snapshot_dir.exists():
        return result

    for json_file in sorted(snapshot_dir.glob("*.json")):
        try:
            snapshots = json.loads(json_file.read_text())
            if snapshots and isinstance(snapshots, list):
                test_name = snapshots[0].get("test_name", json_file.stem)
                result[test_name] = snapshots
        except (json.JSONDecodeError, KeyError):
            pass

    return result


def _match_snapshots_to_test(test_nodeid: str, all_snapshots: dict[str, list[dict]]) -> list[dict]:
    """Find snapshots matching a test by node ID."""
    # Direct match
    if test_nodeid in all_snapshots:
        return all_snapshots[test_nodeid]

    # Partial match — the node ID might differ slightly
    for key, snaps in all_snapshots.items():
        if test_nodeid in key or key in test_nodeid:
            return snaps

    return []


def _render_compact_board(snapshot: dict) -> str:
    """Render a compact inline board state view for a single snapshot."""
    parts = []
    parts.append('<div class="board-snapshot">')
    parts.append(f'<div class="snap-desc">{html.escape(snapshot.get("description", ""))}</div>')

    info_parts = []
    if snapshot.get("turn_number") is not None:
        info_parts.append(f'Turn {snapshot["turn_number"] // 2}')
    if snapshot.get("phase"):
        info_parts.append(snapshot["phase"])
    if snapshot.get("combat_step"):
        info_parts.append(snapshot["combat_step"])
    info_parts.append(f'AP:{snapshot.get("action_points", 0)}')
    info_parts.append(f'RP:{snapshot.get("resource_points", 0)}')
    if info_parts:
        parts.append(f'<div class="snap-info">{" | ".join(info_parts)}</div>')

    # Render both players side by side
    parts.append('<div class="snap-players">')

    for role, player_key in [("turn", "turn_player"), ("opp", "opponent")]:
        player = snapshot.get(player_key, {})
        if not player:
            continue
        parts.append(f'<div class="snap-player snap-{role}">')
        name = html.escape(player.get("name", "?"))
        life = player.get("life", "?")
        marked = ' <span class="snap-marked">MARKED</span>' if player.get("is_marked") else ""
        parts.append(f'<div class="snap-player-header">{name} ({life} HP){marked}</div>')

        # Zones
        zones = []

        # Hand
        hand = player.get("hand", [])
        if hand:
            cards = ", ".join(_compact_card(c) for c in hand)
            zones.append(f'<span class="snap-zone">Hand: {cards}</span>')

        # Arsenal
        arsenal = player.get("arsenal", [])
        if arsenal:
            cards = ", ".join(_compact_card(c) for c in arsenal)
            zones.append(f'<span class="snap-zone">Arsenal: {cards}</span>')

        # Equipment
        equipment = player.get("equipment", {})
        if equipment:
            eqs = ", ".join(
                f'{html.escape(e["name"])}' + (f' [{e.get("slot", "")}]' if e.get("slot") else "")
                for e in equipment.values()
            )
            zones.append(f'<span class="snap-zone">Equip: {eqs}</span>')

        # Weapons
        weapons = player.get("weapons", [])
        if weapons:
            ws = ", ".join(
                html.escape(w["name"]) + (f' P:{w["power"]}' if w.get("power") else "")
                + (" (tapped)" if w.get("is_tapped") else "")
                for w in weapons
            )
            zones.append(f'<span class="snap-zone">Weapons: {ws}</span>')

        # Permanents
        permanents = player.get("permanents", [])
        if permanents:
            ps = ", ".join(html.escape(p["name"]) for p in permanents)
            zones.append(f'<span class="snap-zone">Permanents: {ps}</span>')

        # Graveyard + Banished counts
        gy = player.get("graveyard_count", 0)
        banished = player.get("banished", [])
        deck = player.get("deck_count", 0)
        counts = []
        if deck:
            counts.append(f'Deck:{deck}')
        if gy:
            counts.append(f'Grave:{gy}')
        if banished:
            counts.append(f'Banish:{len(banished)}')
        if counts:
            zones.append(f'<span class="snap-zone snap-counts">{" | ".join(counts)}</span>')

        for z in zones:
            parts.append(z)

        parts.append('</div>')  # snap-player

    parts.append('</div>')  # snap-players

    # Combat chain
    chain = snapshot.get("combat_chain", [])
    if chain:
        parts.append('<div class="snap-combat">')
        for link in chain:
            atk = link.get("attack", {})
            atk_name = html.escape(atk.get("name", "?")) if atk else "?"
            atk_power = atk.get("power", "?") if atk else "?"
            defenders = link.get("defenders", [])
            def_str = " + ".join(
                f'{html.escape(d["name"])} (D:{d.get("defense", "?")})'
                for d in defenders
            ) if defenders else "unblocked"

            hit_class = "snap-hit" if link.get("hit") else ""
            dmg = link.get("damage_dealt", 0)
            result = f" -> Hit for {dmg}" if link.get("hit") and dmg else ""
            if not link.get("hit") and defenders:
                result = " -> Blocked"

            parts.append(
                f'<span class="snap-chain-link {hit_class}">'
                f'L{link.get("link_number", "?")}: '
                f'{atk_name} (P:{atk_power}) vs {def_str}{result}'
                f'</span>'
            )
        parts.append('</div>')

    parts.append('</div>')  # board-snapshot
    return "\n".join(parts)


def _compact_card(card: dict) -> str:
    """Render a card name with color indicator."""
    name = html.escape(card.get("name", "?"))
    color = card.get("color", "")
    if color == "Red":
        return f'<span class="c-red">{name}</span>'
    elif color == "Yellow":
        return f'<span class="c-yellow">{name}</span>'
    elif color == "Blue":
        return f'<span class="c-blue">{name}</span>'
    return name


def render_combined_html(files: list[dict], all_snapshots: dict[str, list[dict]]) -> str:
    """Generate the combined HTML page."""
    parts = [_HTML_HEAD]

    total_tests = sum(len(t) for f in files for c in f["classes"] for t in [c["tests"]])
    total_files = len(files)
    total_snaps = sum(len(s) for s in all_snapshots.values())
    instrumented = sum(1 for f in files for c in f["classes"] for t in c["tests"]
                       if _match_snapshots_to_test(_make_nodeid(f, c, t), all_snapshots))

    parts.append(
        f'<div class="summary">{total_tests} scenario tests across {total_files} files '
        f'| {instrumented} tests with board snapshots ({total_snaps} total snapshots)</div>'
    )

    # Table of contents
    parts.append('<div class="toc"><h2>Contents</h2><ul>')
    for f in files:
        fname = f["name"].replace("test_scenario_", "").replace("_", " ").title()
        parts.append(f'<li><a href="#{f["name"]}">{fname}</a>')
        parts.append("<ul>")
        for cls in f["classes"]:
            for test in cls["tests"]:
                tid = f'{f["name"]}_{test["name"]}'
                nodeid = _make_nodeid(f, cls, test)
                has_snaps = bool(_match_snapshots_to_test(nodeid, all_snapshots))
                badge = ' <span class="has-snaps">+board</span>' if has_snaps else ''
                parts.append(f'<li><a href="#{tid}">{test["readable"]}</a>{badge}</li>')
        parts.append("</ul></li>")
    parts.append("</ul></div>")

    for f in files:
        fname = f["name"].replace("test_scenario_", "").replace("_", " ").title()
        parts.append(f'<div class="file-section" id="{f["name"]}">')
        parts.append(f'<h2>{fname}</h2>')
        if f["docstring"]:
            parts.append(f'<div class="file-doc">{html.escape(f["docstring"])}</div>')

        for cls in f["classes"]:
            if cls["docstring"]:
                parts.append(f'<div class="class-doc">{html.escape(cls["docstring"])}</div>')

            for test in cls["tests"]:
                tid = f'{f["name"]}_{test["name"]}'
                nodeid = _make_nodeid(f, cls, test)
                test_snaps = _match_snapshots_to_test(nodeid, all_snapshots)

                has_snaps_class = " has-board" if test_snaps else ""
                parts.append(f'<details class="test-case{has_snaps_class}" id="{tid}">')
                parts.append(f'<summary class="test-header">')
                if test_snaps:
                    parts.append(f'<span class="test-icon board-icon">B</span>')
                else:
                    parts.append(f'<span class="test-icon">T</span>')
                parts.append(f'<span class="test-name">{html.escape(test["readable"])}</span>')
                parts.append(f'<span class="step-count">{len(test["steps"])} steps')
                if test_snaps:
                    parts.append(f' | {len(test_snaps)} snapshots')
                parts.append(f'</span>')
                parts.append(f'</summary>')

                if test["docstring"]:
                    parts.append(f'<div class="test-doc">{html.escape(test["docstring"])}</div>')

                parts.append('<div class="steps">')

                # Interleave steps and snapshots
                snap_idx = 0
                for i, step in enumerate(test["steps"]):
                    icon = STEP_ICONS.get(step["type"], "")
                    color = STEP_COLORS.get(step["type"], "#999")
                    step_class = step["type"]

                    parts.append(f'<div class="step {step_class}" style="border-left-color: {color}">')
                    parts.append(f'<div class="step-header">')
                    parts.append(f'<span class="step-num">{i+1}</span>')
                    parts.append(f'<span class="step-icon">{icon}</span>')
                    parts.append(f'<span class="step-desc">{html.escape(step["desc"])}</span>')
                    parts.append(f'</div>')
                    if step["code"]:
                        escaped_code = html.escape(step["code"])
                        escaped_code = re.sub(
                            r'\bassert\b',
                            '<span class="kw-assert">assert</span>',
                            escaped_code,
                        )
                        parts.append(f'<pre class="step-code">{escaped_code}</pre>')
                    parts.append(f'</div>')

                    # Insert any snapshots that belong after this step
                    # Heuristic: distribute snapshots evenly across steps,
                    # or insert after setup/combat/event/assert steps
                    if test_snaps and snap_idx < len(test_snaps):
                        should_insert = step["type"] in (
                            "setup", "combat", "event", "assert", "mark",
                            "transform", "effect",
                        )
                        # Also insert at the last step
                        if i == len(test["steps"]) - 1:
                            should_insert = True

                        if should_insert:
                            parts.append(_render_compact_board(test_snaps[snap_idx]))
                            snap_idx += 1

                # Any remaining snapshots go at the end
                while snap_idx < len(test_snaps):
                    parts.append(_render_compact_board(test_snaps[snap_idx]))
                    snap_idx += 1

                parts.append('</div>')  # steps
                parts.append('</details>')

        parts.append('</div>')  # file-section

    parts.append(_HTML_TAIL)
    return "\n".join(parts)


def _make_nodeid(file_info: dict, cls_info: dict, test_info: dict) -> str:
    """Reconstruct a pytest-style node ID for matching snapshots."""
    path = file_info["path"]
    cls_name = cls_info["name"]
    test_name = test_info["name"]
    if cls_name == "Top-level Tests":
        return f"{path}::{test_name}"
    return f"{path}::{cls_name}::{test_name}"


_HTML_HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>FaB Scenario Tests + Board State Viewer</title>
<style>
:root {
  --bg: #1a1a2e;
  --card-bg: #16213e;
  --text: #e0e0e0;
  --muted: #888;
  --border: #2a2a4a;
  --accent: #4a6a8a;
  --red: #c04040;
  --blue: #4070c0;
  --yellow: #c0a030;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  background: var(--bg);
  color: var(--text);
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px;
}

h1 { text-align: center; font-size: 20px; margin-bottom: 8px; color: #fff; }
h2 { font-size: 16px; color: #c0c0e0; margin: 24px 0 12px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }

.summary {
  text-align: center;
  color: var(--muted);
  margin-bottom: 16px;
  font-size: 14px;
}

.toc {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 20px;
}
.toc h2 { margin: 0 0 8px; font-size: 14px; border: none; padding: 0; }
.toc ul { list-style: none; padding-left: 16px; }
.toc > ul { padding-left: 0; }
.toc li { margin: 2px 0; }
.toc a { color: #7090c0; text-decoration: none; font-size: 12px; }
.toc a:hover { color: #90b0e0; text-decoration: underline; }

.has-snaps {
  background: #2a4a3a;
  color: #6c6;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  margin-left: 4px;
}

.file-section { margin-bottom: 24px; }
.file-doc, .class-doc {
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: rgba(255,255,255,0.03);
  border-radius: 4px;
  white-space: pre-wrap;
}

.test-case {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;
}
.test-case.has-board {
  border-color: #3a5a4a;
}

.test-header {
  cursor: pointer;
  padding: 10px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  user-select: none;
}
.test-header:hover { background: rgba(255,255,255,0.03); }
.test-icon {
  font-size: 11px;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  background: #2a2a4a;
  color: #aaa;
}
.test-icon.board-icon {
  background: #2a4a3a;
  color: #6c6;
  font-weight: bold;
}
.test-name { font-weight: bold; font-size: 13px; flex: 1; }
.step-count { color: var(--muted); font-size: 11px; }

.test-doc {
  color: var(--muted);
  font-size: 11px;
  padding: 0 14px 8px;
  white-space: pre-wrap;
  border-bottom: 1px solid var(--border);
  margin-bottom: 4px;
}

.steps { padding: 8px 14px 12px; }

.step {
  margin-bottom: 6px;
  padding: 6px 10px;
  border-left: 3px solid #555;
  border-radius: 0 4px 4px 0;
  background: rgba(255,255,255,0.02);
}
.step.assert { background: rgba(80, 176, 80, 0.08); }
.step.combat { background: rgba(192, 96, 96, 0.06); }
.step.event { background: rgba(192, 144, 64, 0.06); }

.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.step-num {
  color: var(--muted);
  font-size: 10px;
  min-width: 16px;
  text-align: right;
}
.step-icon { font-size: 14px; }
.step-desc { font-size: 12px; }

.step-code {
  margin-top: 4px;
  padding: 6px 8px;
  background: rgba(0,0,0,0.3);
  border-radius: 4px;
  font-size: 11px;
  color: #b0b0c0;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.kw-assert { color: #60c060; font-weight: bold; }

details[open] > summary::before { content: "\\25BC "; font-size: 10px; }
details:not([open]) > summary::before { content: "\\25B6 "; font-size: 10px; }

/* --- Board snapshot styles --- */
.board-snapshot {
  margin: 8px 0;
  padding: 10px 12px;
  background: linear-gradient(135deg, #1a2030, #1a1a30);
  border: 1px solid #3a4a5a;
  border-radius: 6px;
  border-left: 3px solid #4a8a6a;
}

.snap-desc {
  font-weight: bold;
  font-size: 12px;
  color: #f0d060;
  margin-bottom: 4px;
}

.snap-info {
  font-size: 10px;
  color: var(--muted);
  margin-bottom: 6px;
}

.snap-players {
  display: flex;
  gap: 12px;
}

.snap-player {
  flex: 1;
  padding: 6px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.snap-turn { background: rgba(64, 112, 192, 0.1); border: 1px solid rgba(64, 112, 192, 0.3); }
.snap-opp { background: rgba(192, 64, 64, 0.1); border: 1px solid rgba(192, 64, 64, 0.3); }

.snap-player-header {
  font-weight: bold;
  font-size: 12px;
  margin-bottom: 4px;
}
.snap-turn .snap-player-header { color: var(--blue); }
.snap-opp .snap-player-header { color: var(--red); }

.snap-marked {
  background: #c04040;
  color: #fff;
  font-size: 9px;
  padding: 1px 4px;
  border-radius: 3px;
}

.snap-zone {
  display: block;
  color: #b0b0c0;
  font-size: 10px;
  margin: 1px 0;
}

.snap-counts {
  color: var(--muted);
  font-size: 9px;
  margin-top: 2px;
}

.c-red { color: #e88; }
.c-yellow { color: #dd9; }
.c-blue { color: #8af; }

/* Combat chain in snapshot */
.snap-combat {
  margin-top: 6px;
  padding: 4px 8px;
  background: rgba(192, 64, 64, 0.08);
  border: 1px solid rgba(192, 64, 64, 0.2);
  border-radius: 4px;
}

.snap-chain-link {
  display: block;
  font-size: 10px;
  color: #c0a0a0;
  margin: 1px 0;
}
.snap-chain-link.snap-hit {
  color: #e06060;
  font-weight: bold;
}

/* Keyboard navigation hint */
.nav-hint {
  position: fixed;
  bottom: 12px;
  right: 12px;
  background: rgba(0,0,0,0.7);
  color: var(--muted);
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 11px;
}
kbd {
  background: #333;
  border: 1px solid #555;
  border-radius: 3px;
  padding: 1px 4px;
  font-size: 10px;
}
</style>
</head>
<body>
<h1>FaB Scenario Tests + Board State</h1>
<div class="nav-hint">
  <kbd>J</kbd> next test &nbsp; <kbd>K</kbd> prev test &nbsp; <kbd>Enter</kbd> toggle
</div>
<script>
// Keyboard navigation
document.addEventListener('keydown', (e) => {
  const tests = [...document.querySelectorAll('.test-case')];
  const current = tests.findIndex(t => t.hasAttribute('open'));

  if (e.key === 'j' || e.key === 'ArrowDown') {
    e.preventDefault();
    const next = current + 1;
    if (next < tests.length) {
      if (current >= 0) tests[current].removeAttribute('open');
      tests[next].setAttribute('open', '');
      tests[next].scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  } else if (e.key === 'k' || e.key === 'ArrowUp') {
    e.preventDefault();
    const prev = current - 1;
    if (prev >= 0) {
      if (current >= 0) tests[current].removeAttribute('open');
      tests[prev].setAttribute('open', '');
      tests[prev].scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  } else if (e.key === 'Enter') {
    e.preventDefault();
    if (current >= 0) {
      if (tests[current].hasAttribute('open'))
        tests[current].removeAttribute('open');
      else
        tests[current].setAttribute('open', '');
    }
  }
});
</script>
"""

_HTML_TAIL = """\
</body>
</html>
"""


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 tools/scenario_viewer.py <test_dir> [snapshot_dir] [output.html]")
        sys.exit(1)

    test_path = Path(sys.argv[1])
    snapshot_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("scenario_snapshots")
    output_path = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("scenario_combined.html")

    # Parse test files
    if test_path.is_dir():
        test_files = sorted(test_path.glob("test_scenario_*.py"))
    else:
        test_files = [test_path]

    files = []
    for tf in test_files:
        try:
            files.append(parse_test_file(tf))
        except Exception as e:
            print(f"Warning: failed to parse {tf}: {e}")

    # Load snapshots
    all_snapshots = load_snapshots(snapshot_dir)

    # Generate
    html_content = render_combined_html(files, all_snapshots)
    output_path.write_text(html_content)

    total_tests = sum(len(t) for f in files for c in f["classes"] for t in [c["tests"]])
    print(f"Written {len(files)} files ({total_tests} tests) with {len(all_snapshots)} instrumented tests to {output_path}")


if __name__ == "__main__":
    main()
