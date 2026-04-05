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

# Ensure project root is on path for sibling imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

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
    """Render a rich board state view using client-side JS rendering.

    Emits a div with the snapshot data as a JSON attribute; the board viewer
    JS functions (injected in _HTML_HEAD) populate it on page load.
    """
    snapshot_json = json.dumps(snapshot)
    desc = html.escape(snapshot.get("description", ""))
    return (
        f'<div class="board-snapshot" data-snapshot=\'{snapshot_json}\'>'
        f'<div class="snap-desc">{desc}</div>'
        f'<div class="snap-board"></div>'
        f'</div>'
    )


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

                # Board viewer (single viewer with step-through nav) for tests with snapshots
                if test_snaps:
                    snaps_json = json.dumps(test_snaps)
                    parts.append(f'<div class="snapshot-viewer" data-snapshots=\'{snaps_json}\'>')
                    parts.append('<div class="snap-nav">')
                    parts.append('<button class="snap-prev" title="Previous snapshot">&larr; Prev</button>')
                    parts.append('<span class="snap-counter">Snapshot 1 / 1</span>')
                    parts.append('<button class="snap-next" title="Next snapshot">Next &rarr;</button>')
                    parts.append('</div>')
                    parts.append('<div class="snap-desc"></div>')
                    parts.append('<div class="snap-board"></div>')
                    parts.append('</div>')

                parts.append('<div class="steps">')

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

/* --- Snapshot viewer with step-through nav --- */
.snapshot-viewer {
  margin: 8px 14px 4px;
  padding: 10px 12px;
  background: linear-gradient(135deg, #1a2030, #1a1a30);
  border: 1px solid #3a4a5a;
  border-radius: 6px;
  border-left: 3px solid #4a8a6a;
}

.snap-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 8px;
}
.snap-nav button {
  background: #4a3a6a;
  color: #e0e0e0;
  border: 1px solid var(--border);
  border-radius: 5px;
  padding: 4px 12px;
  font-family: inherit;
  font-size: 11px;
  cursor: pointer;
}
.snap-nav button:hover { background: #5a4a8a; }
.snap-nav button:disabled { opacity: 0.3; cursor: default; }
.snap-counter {
  color: var(--muted);
  font-size: 12px;
  min-width: 110px;
  text-align: center;
}

.snap-desc {
  font-weight: bold;
  font-size: 12px;
  color: #f0d060;
  margin-bottom: 4px;
  text-align: center;
}

/* Legacy inline board-snapshot (no longer used but kept for safety) */
.board-snapshot {
  margin: 8px 0;
  padding: 10px 12px;
  background: linear-gradient(135deg, #1a2030, #1a1a30);
  border: 1px solid #3a4a5a;
  border-radius: 6px;
  border-left: 3px solid #4a8a6a;
}

.snap-board .game-info {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-bottom: 8px;
  font-size: 11px;
  color: var(--muted);
}

/* --- Board viewer styles (namespaced under .board-snapshot) --- */
.board-snapshot .board {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.board-snapshot .player-zone {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
}
.board-snapshot .player-zone.marked {
  border-color: #ff2222;
  box-shadow: 0 0 8px rgba(255, 34, 34, 0.3);
}

.board-snapshot .player-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.board-snapshot .player-name {
  font-weight: bold;
  font-size: 13px;
}
.board-snapshot .player-name.opp { color: var(--red); }
.board-snapshot .player-name.turn { color: var(--blue); }

.board-snapshot .life-bar {
  position: relative;
  width: 120px;
  height: 18px;
  background: #0a0a1e;
  border-radius: 4px;
  overflow: hidden;
}
.board-snapshot .life-fill {
  position: absolute;
  top: 0; left: 0; bottom: 0;
  border-radius: 4px;
}
.board-snapshot .life-fill.opp { background: rgba(192, 64, 64, 0.6); }
.board-snapshot .life-fill.turn { background: rgba(64, 112, 192, 0.6); }
.board-snapshot .life-text {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 11px;
  font-weight: bold;
}

.board-snapshot .marked-badge {
  background: #ff2222;
  color: #fff;
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: bold;
}

.board-snapshot .diplo-badge {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: bold;
  color: #fff;
}
.board-snapshot .diplo-war { background: #c04040; }
.board-snapshot .diplo-peace { background: #4080c0; }

.board-snapshot .deck-count {
  color: var(--muted);
  font-size: 10px;
}

/* Zone rows */
.board-snapshot .zone-row {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}
.board-snapshot .zone-label {
  color: var(--muted);
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 1px;
  min-width: 60px;
  padding-top: 3px;
}

/* Card rendering */
.board-snapshot .card {
  position: relative;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 60px;
  max-width: 80px;
  padding: 4px 5px;
  border-radius: 5px;
  border: 1px solid var(--border);
  font-size: 9px;
  text-align: center;
  line-height: 1.2;
  background: var(--bg);
}
.board-snapshot .card .card-name {
  font-weight: bold;
  margin-bottom: 1px;
  word-break: break-word;
}
.board-snapshot .card .card-stats {
  color: var(--muted);
  font-size: 8px;
}
.board-snapshot .card.card-red { border-color: var(--red); color: #e88; }
.board-snapshot .card.card-yellow { border-color: var(--yellow); color: #dd9; }
.board-snapshot .card.card-blue { border-color: var(--blue); color: #8af; }
.board-snapshot .card.card-none { border-color: #606060; color: #aaa; }
.board-snapshot .card.card-back {
  background: #1a1030;
  border-color: #4a3a6a;
  color: var(--muted);
  min-width: 45px;
}
.board-snapshot .card.face-down {
  opacity: 0.75;
  border-style: dashed;
}
.board-snapshot .fd-badge {
  position: absolute;
  top: 1px;
  right: 1px;
  font-size: 7px;
  background: #555;
  color: #ccc;
  padding: 0 2px;
  border-radius: 2px;
}
.board-snapshot .card.tapped {
  opacity: 0.5;
  transform: rotate(8deg);
}

/* Equipment */
.board-snapshot .equip-card {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  min-width: 70px;
  padding: 3px 5px;
  border-radius: 5px;
  border: 1px solid #3a5a3a;
  background: #0a1a0a;
  font-size: 9px;
  text-align: center;
}
.board-snapshot .equip-card .equip-name { font-weight: bold; color: #8c8; }
.board-snapshot .equip-card .equip-slot { color: var(--muted); font-size: 8px; }
.board-snapshot .equip-card .equip-def { color: #6a6; font-size: 8px; }
.board-snapshot .equip-card .equip-counters { color: #cc8; font-size: 8px; }
.board-snapshot .equip-card.tapped { opacity: 0.5; }
.board-snapshot .equip-card.activated {
  border-color: #e0a030;
  box-shadow: 0 0 6px rgba(224, 160, 48, 0.5);
}

/* Weapons */
.board-snapshot .weapon-card {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  min-width: 70px;
  padding: 3px 5px;
  border-radius: 5px;
  border: 1px solid #5a3a3a;
  background: #1a0a0a;
  font-size: 9px;
  text-align: center;
}
.board-snapshot .weapon-card .weapon-name { font-weight: bold; color: #c88; }
.board-snapshot .weapon-card .weapon-power { color: #a66; font-size: 8px; }
.board-snapshot .weapon-card.tapped { opacity: 0.5; transform: rotate(8deg); }

/* Permanents */
.board-snapshot .perm-card {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
  padding: 3px 5px;
  border-radius: 5px;
  border: 1px solid #5a5a2a;
  background: #1a1a0a;
  font-size: 9px;
  text-align: center;
}
.board-snapshot .perm-card .perm-name { font-weight: bold; color: #cc8; }
.board-snapshot .perm-card .perm-counters { color: #aa6; font-size: 8px; }

/* Combat chain */
.board-snapshot .combat-zone {
  background: linear-gradient(135deg, #2a1020, #201030);
  border: 1px solid #4a2a4a;
  border-radius: 6px;
  padding: 6px 10px;
}
.board-snapshot .combat-title {
  color: #e06060;
  font-weight: bold;
  font-size: 11px;
  margin-bottom: 4px;
}
.board-snapshot .chain-links {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 3px;
}
.board-snapshot .chain-link {
  flex-shrink: 0;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 5px;
  padding: 5px 8px;
  min-width: 110px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
}
.board-snapshot .chain-link.hit-link { border-color: #ff4444; }
.board-snapshot .chain-link.stack-link { border-style: dashed; opacity: 0.8; }
.board-snapshot .chain-link-num { color: var(--muted); font-size: 9px; }
.board-snapshot .chain-vs { color: var(--muted); font-size: 9px; font-weight: bold; }
.board-snapshot .chain-defenders-row {
  display: flex;
  gap: 3px;
  flex-wrap: wrap;
  justify-content: center;
}
.board-snapshot .chain-attack { font-weight: bold; font-size: 11px; }
.board-snapshot .chain-defenders { font-size: 10px; color: #8af; }
.board-snapshot .chain-result { font-size: 9px; margin-top: 2px; font-weight: bold; }
.board-snapshot .chain-result.hit { color: #ff4444; }
.board-snapshot .chain-result.blocked { color: #30a030; }

.board-snapshot .empty { color: var(--muted); font-style: italic; font-size: 10px; }

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
  <kbd>J</kbd> next test &nbsp; <kbd>K</kbd> prev test &nbsp; <kbd>Enter</kbd> toggle &nbsp; <kbd>&larr;</kbd><kbd>&rarr;</kbd> snapshots
</div>
<script>
// Keyboard navigation
document.addEventListener('keydown', (e) => {
  const tests = [...document.querySelectorAll('.test-case')];
  const current = tests.findIndex(t => t.hasAttribute('open'));

  // Left/Right arrows navigate snapshots within the open test
  if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
    if (current >= 0) {
      const viewer = tests[current].querySelector('.snapshot-viewer');
      if (viewer && viewer._snapData) {
        e.preventDefault();
        if (e.key === 'ArrowLeft') navigateSnapshot(viewer, -1);
        else navigateSnapshot(viewer, 1);
        return;
      }
    }
  }

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

// --- Board viewer rendering functions ---
function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function colorClass(color) {
  if (color === 'Red') return 'card-red';
  if (color === 'Yellow') return 'card-yellow';
  if (color === 'Blue') return 'card-blue';
  return 'card-none';
}

function renderCard(card) {
  if (!card.face_up && card.name === '???') {
    return '<div class="card card-back"><div class="card-name">?</div></div>';
  }
  const cls = colorClass(card.color);
  const faceDown = !card.face_up ? ' face-down' : '';
  let stats = [];
  if (card.power != null) stats.push('P:' + card.power);
  if (card.defense != null) stats.push('D:' + card.defense);
  if (card.cost != null) stats.push('C:' + card.cost);
  const statsStr = stats.length ? '<div class="card-stats">' + stats.join(' ') + '</div>' : '';
  const fdBadge = !card.face_up ? '<div class="fd-badge">FD</div>' : '';
  return '<div class="card ' + cls + faceDown + '"><div class="card-name">' + escHtml(card.name) + '</div>' + statsStr + fdBadge + '</div>';
}

function renderEquipment(eq) {
  let cls = 'equip-card';
  if (eq.is_tapped) cls += ' tapped';
  if (eq.activated_this_turn) cls += ' activated';
  let counters = '';
  if (eq.counters && Object.keys(eq.counters).length > 0) {
    const parts = Object.entries(eq.counters).map(function(e) { return e[0] + ':' + e[1]; });
    counters = '<div class="equip-counters">' + parts.join(' ') + '</div>';
  }
  return '<div class="' + cls + '">' +
    '<div class="equip-name">' + escHtml(eq.name) + '</div>' +
    '<div class="equip-slot">' + eq.slot + '</div>' +
    (eq.defense != null ? '<div class="equip-def">Def: ' + eq.defense + '</div>' : '') +
    counters +
    '</div>';
}

function renderWeapon(w) {
  let cls = w.is_tapped ? 'weapon-card tapped' : 'weapon-card';
  let counters = '';
  if (w.counters && Object.keys(w.counters).length > 0) {
    const parts = Object.entries(w.counters).map(function(e) { return e[0] + ':' + e[1]; });
    counters = '<div style="color:#aa6;font-size:8px">' + parts.join(' ') + '</div>';
  }
  return '<div class="' + cls + '">' +
    '<div class="weapon-name">' + escHtml(w.name) + '</div>' +
    (w.power != null ? '<div class="weapon-power">Power: ' + w.power + '</div>' : '') +
    counters +
    '</div>';
}

function renderPermanent(p) {
  let counters = '';
  if (p.counters && Object.keys(p.counters).length > 0) {
    const parts = Object.entries(p.counters).map(function(e) { return e[0] + ':' + e[1]; });
    counters = '<div class="perm-counters">' + parts.join(' ') + '</div>';
  }
  return '<div class="perm-card"><div class="perm-name">' + escHtml(p.name) + '</div>' + counters + '</div>';
}

function renderZoneRow(label, contentHtml) {
  if (!contentHtml) return '';
  return '<div class="zone-row"><span class="zone-label">' + label + '</span>' + contentHtml + '</div>';
}

function renderPlayer(player, role) {
  const markedCls = player.is_marked ? ' marked' : '';
  let h = '<div class="player-zone' + markedCls + '">';

  h += '<div class="player-header">';
  h += '<span class="player-name ' + role + '">' + escHtml(player.name) + '</span>';

  const lifePct = Math.max(0, Math.min(100, Math.round(player.life * 100 / 40)));
  h += '<div class="life-bar"><div class="life-fill ' + role + '" style="width:' + lifePct + '%"></div>';
  h += '<div class="life-text">' + player.life + ' HP</div></div>';

  if (player.is_marked) {
    h += '<span class="marked-badge">MARKED</span>';
  }
  if (player.diplomacy_restriction) {
    const dipCls = player.diplomacy_restriction === 'war' ? 'diplo-war' : 'diplo-peace';
    const dipLabel = player.diplomacy_restriction === 'war' ? 'WAR' : 'PEACE';
    h += '<span class="diplo-badge ' + dipCls + '">' + dipLabel + '</span>';
  }
  h += '<span class="deck-count">Deck: ' + player.deck_count + '</span>';
  h += '</div>';

  if (player.hand && player.hand.length > 0) {
    h += renderZoneRow('Hand (' + player.hand_count + ')', player.hand.map(renderCard).join(''));
  } else {
    h += renderZoneRow('Hand', '<span class="empty">empty</span>');
  }

  if (player.arsenal && player.arsenal.length > 0) {
    h += renderZoneRow('Arsenal', player.arsenal.map(renderCard).join(''));
  }

  var eqSlots = player.equipment ? Object.values(player.equipment) : [];
  if (eqSlots.length > 0) {
    h += renderZoneRow('Equip', eqSlots.map(renderEquipment).join(''));
  }

  if (player.weapons && player.weapons.length > 0) {
    h += renderZoneRow('Weapons', player.weapons.map(renderWeapon).join(''));
  }

  if (player.permanents && player.permanents.length > 0) {
    h += renderZoneRow('Tokens', player.permanents.map(renderPermanent).join(''));
  }

  if (player.graveyard_count > 0) {
    h += renderZoneRow('Grave', '<span class="empty">' + player.graveyard_count + ' cards</span>');
  }

  if (player.banished && player.banished.length > 0) {
    var bHtml = player.banished.map(function(b) {
      var cls = colorClass(b.color);
      var fdCls = b.face_up ? '' : ' face-down';
      var fdBadge = b.face_up ? '' : '<div class="fd-badge">FD</div>';
      return '<div class="card ' + cls + fdCls + '"><div class="card-name">' + escHtml(b.name) + '</div>' + fdBadge + '</div>';
    }).join('');
    h += renderZoneRow('Banish', bHtml);
  }

  h += '</div>';
  return h;
}

function renderCombatChain(chain) {
  if (!chain || chain.length === 0) return '';

  let h = '<div class="combat-zone">';
  h += '<div class="combat-title">Combat Chain</div>';
  h += '<div class="chain-links">';

  for (const link of chain) {
    const hitCls = link.hit ? ' hit-link' : '';
    const stackCls = link.on_stack ? ' stack-link' : '';
    h += '<div class="chain-link' + hitCls + stackCls + '">';
    const label = link.on_stack ? 'On Stack' : 'Link #' + link.link_number;
    h += '<div class="chain-link-num">' + label + '</div>';

    if (link.defenders && link.defenders.length > 0) {
      h += '<div class="chain-defenders-row">';
      for (const d of link.defenders) {
        const dCls = colorClass(d.color);
        h += '<div class="card ' + dCls + '">';
        h += '<div class="card-name">' + escHtml(d.name) + '</div>';
        if (d.defense != null) h += '<div class="card-stats">D:' + d.defense + '</div>';
        h += '</div>';
      }
      h += '</div>';
      h += '<div class="chain-vs">vs</div>';
    }

    if (link.attack) {
      const aCls = colorClass(link.attack.color);
      h += '<div class="card ' + aCls + '">';
      h += '<div class="card-name">' + escHtml(link.attack.name) + '</div>';
      if (link.attack.power != null) h += '<div class="card-stats">P:' + link.attack.power + '</div>';
      h += '</div>';
    }

    if (link.damage_dealt > 0) {
      h += '<div class="chain-result hit">Hit for ' + link.damage_dealt + '</div>';
    } else if (link.defenders && link.defenders.length > 0 && link.damage_dealt === 0) {
      h += '<div class="chain-result blocked">Blocked!</div>';
    }

    h += '</div>';
  }

  h += '</div>';
  h += '</div>';
  return h;
}

function renderBoardSnapshot(container, snap) {
  var infoDiv = '<div class="game-info">';
  var fabTurn = Math.floor((snap.turn_number || 0) / 2);
  var info = 'Turn ' + fabTurn;
  if (snap.phase) info += ' | Phase: ' + snap.phase;
  if (snap.combat_step) info += ' | Combat: ' + snap.combat_step;
  info += ' | AP: ' + (snap.action_points || 0) + ' | RP: ' + (snap.resource_points || 0);
  if (snap.game_over) info += ' | GAME OVER';
  infoDiv += info + '</div>';

  var board = '<div class="board">';
  if (snap.opponent) board += renderPlayer(snap.opponent, 'opp');
  board += renderCombatChain(snap.combat_chain);
  if (snap.turn_player) board += renderPlayer(snap.turn_player, 'turn');
  board += '</div>';

  container.innerHTML = infoDiv + board;
}

// --- Snapshot step-through viewer ---
function navigateSnapshot(viewer, delta) {
  if (!viewer._snapData) return;
  var idx = viewer._snapIndex + delta;
  if (idx < 0 || idx >= viewer._snapData.length) return;
  viewer._snapIndex = idx;
  showSnapshot(viewer);
}

function showSnapshot(viewer) {
  var snaps = viewer._snapData;
  var idx = viewer._snapIndex;
  var snap = snaps[idx];

  // Update counter
  var counter = viewer.querySelector('.snap-counter');
  if (counter) counter.textContent = 'Snapshot ' + (idx + 1) + ' / ' + snaps.length;

  // Update description
  var descEl = viewer.querySelector('.snap-desc');
  if (descEl) descEl.textContent = snap.description || '';

  // Update board
  var boardEl = viewer.querySelector('.snap-board');
  if (boardEl) renderBoardSnapshot(boardEl, snap);

  // Update button states
  var prevBtn = viewer.querySelector('.snap-prev');
  var nextBtn = viewer.querySelector('.snap-next');
  if (prevBtn) prevBtn.disabled = (idx === 0);
  if (nextBtn) nextBtn.disabled = (idx >= snaps.length - 1);
}

function initSnapshotViewers(root) {
  var viewers = (root || document).querySelectorAll('.snapshot-viewer[data-snapshots]');
  for (var i = 0; i < viewers.length; i++) {
    var viewer = viewers[i];
    if (viewer._snapData) continue; // already initialized
    try {
      var snaps = JSON.parse(viewer.getAttribute('data-snapshots'));
      if (!snaps || snaps.length === 0) continue;
      viewer._snapData = snaps;
      viewer._snapIndex = 0;

      // Wire up buttons
      var prevBtn = viewer.querySelector('.snap-prev');
      var nextBtn = viewer.querySelector('.snap-next');
      if (prevBtn) prevBtn.addEventListener('click', (function(v) {
        return function() { navigateSnapshot(v, -1); };
      })(viewer));
      if (nextBtn) nextBtn.addEventListener('click', (function(v) {
        return function() { navigateSnapshot(v, 1); };
      })(viewer));

      // Render first snapshot
      showSnapshot(viewer);
    } catch(e) {
      var boardEl = viewer.querySelector('.snap-board');
      if (boardEl) boardEl.textContent = 'Error loading snapshots';
    }
  }
}

// Initialize viewers when details elements are opened (lazy rendering)
document.addEventListener('toggle', function(e) {
  if (e.target.tagName === 'DETAILS' && e.target.open) {
    initSnapshotViewers(e.target);
  }
}, true);

// Also initialize any that are already visible
document.addEventListener('DOMContentLoaded', function() {
  initSnapshotViewers();
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
