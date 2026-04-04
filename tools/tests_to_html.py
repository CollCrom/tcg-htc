"""Convert scenario test files into an interactive HTML page for review.

Parses pytest test files and presents each test as a step-by-step walkthrough
with board state annotations, setup descriptions, and assertion explanations.

Usage:
    python3 tools/tests_to_html.py tests/scenarios/ scenario_tests.html
    open scenario_tests.html
"""

from __future__ import annotations

import ast
import html
import re
import sys
import textwrap
from pathlib import Path


def parse_test_file(path: Path) -> dict:
    """Parse a test file into structured data."""
    source = path.read_text()
    tree = ast.parse(source)
    lines = source.splitlines()

    file_info = {
        "path": str(path),
        "name": path.stem,
        "docstring": ast.get_docstring(tree) or "",
        "classes": [],
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            cls = {
                "name": node.name,
                "docstring": ast.get_docstring(node) or "",
                "tests": [],
            }
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                    test = _parse_test_function(item, lines)
                    cls["tests"].append(test)
            file_info["classes"].append(cls)

        # Top-level test functions (not in a class)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_") and not any(
            isinstance(p, ast.ClassDef) for p in ast.walk(tree)
            if hasattr(p, 'body') and node in getattr(p, 'body', [])
        ):
            # Only if truly top-level
            if node.col_offset == 0:
                if not file_info["classes"]:
                    file_info["classes"].append({
                        "name": "Top-level Tests",
                        "docstring": "",
                        "tests": [],
                    })
                test = _parse_test_function(node, lines)
                file_info["classes"][-1]["tests"].append(test)

    return file_info


def _parse_test_function(node: ast.FunctionDef, lines: list[str]) -> dict:
    """Parse a single test function into steps."""
    docstring = ast.get_docstring(node) or ""
    name = node.name

    # Extract the human-readable name
    readable = name.replace("test_", "").replace("_", " ").title()

    # Parse the function body into steps
    steps = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant):
            continue  # skip docstring
        if not hasattr(child, 'lineno'):
            continue  # skip arguments node etc.

        start = child.lineno - 1
        end = child.end_lineno if hasattr(child, 'end_lineno') and child.end_lineno else start + 1
        code_lines = lines[start:end]
        code = "\n".join(code_lines)

        step = _classify_step(child, code)
        if step:
            steps.append(step)

    return {
        "name": name,
        "readable": readable,
        "docstring": docstring,
        "steps": steps,
    }


def _classify_step(node, code: str) -> dict | None:
    """Classify a code statement into a step type with description."""
    code_stripped = code.strip()

    # Skip imports and trivial assignments
    if code_stripped.startswith("from ") or code_stripped.startswith("import "):
        return None

    # Setup calls
    if "make_game_shell" in code or "_setup_" in code:
        return {"type": "setup", "desc": "Initialize game state", "code": code_stripped}

    if "make_card(" in code or "_make_" in code or "make_ninja" in code or "make_dagger" in code:
        return {"type": "create", "desc": _extract_card_creation(code_stripped), "code": code_stripped}

    if ".equipment[" in code:
        return {"type": "equip", "desc": _extract_equipment(code_stripped), "code": code_stripped}

    if ".weapons" in code and ("=" in code or "append" in code):
        return {"type": "equip", "desc": "Set up weapons", "code": code_stripped}

    if "register_equipment_triggers" in code or "register_token" in code:
        return {"type": "register", "desc": "Register triggered effects", "code": code_stripped}

    if "open_chain" in code:
        return {"type": "combat", "desc": "Open combat chain", "code": code_stripped}

    if "add_chain_link" in code:
        return {"type": "combat", "desc": _extract_chain_link(code_stripped), "code": code_stripped}

    if ".hit = True" in code:
        return {"type": "combat", "desc": "Mark chain link as hit", "code": code_stripped}

    if ".hit = False" in code:
        return {"type": "combat", "desc": "Mark chain link as missed", "code": code_stripped}

    if "events.emit" in code:
        return {"type": "event", "desc": _extract_event(code_stripped), "code": code_stripped}

    if "get_pending_triggers" in code and "assert" not in code:
        return {"type": "cleanup", "desc": "Clear pending triggers", "code": code_stripped}

    if ".is_marked = True" in code:
        return {"type": "mark", "desc": "Mark the opponent", "code": code_stripped}

    if ".is_marked = False" in code:
        return {"type": "mark", "desc": "Remove mark", "code": code_stripped}

    if "diplomacy_restriction" in code:
        return {"type": "effect", "desc": "Set diplomacy restriction", "code": code_stripped}

    if ".life_total" in code and "=" in code:
        return {"type": "state", "desc": "Set life total", "code": code_stripped}

    if ".hand" in code and ("append" in code or "=" in code):
        return {"type": "state", "desc": "Set up hand", "code": code_stripped}

    if ".deck" in code and "append" in code:
        return {"type": "state", "desc": "Add cards to deck", "code": code_stripped}

    if ".permanents" in code and "append" in code:
        return {"type": "state", "desc": "Add permanent/token", "code": code_stripped}

    if ".demi_heroes" in code:
        return {"type": "state", "desc": "Set up demi-heroes", "code": code_stripped}

    if "turn_counters" in code:
        return {"type": "state", "desc": _extract_counter(code_stripped), "code": code_stripped}

    if "original_hero" in code:
        return {"type": "state", "desc": "Set original hero (pre-transformation)", "code": code_stripped}

    if "_become_agent" in code:
        return {"type": "transform", "desc": "Transform to Agent of Chaos", "code": code_stripped}

    if "_can_play_attack_reaction" in code or "_can_use_equipment_reaction" in code:
        if "assert" in code:
            return {"type": "assert", "desc": _extract_assertion(code_stripped), "code": code_stripped}
        return {"type": "check", "desc": "Check reaction eligibility", "code": code_stripped}

    if "assert" in code_stripped:
        return {"type": "assert", "desc": _extract_assertion(code_stripped), "code": code_stripped}

    if "resource_points" in code:
        return {"type": "state", "desc": "Set resource points", "code": code_stripped}

    if code_stripped.startswith("#"):
        return {"type": "comment", "desc": code_stripped.lstrip("# "), "code": ""}

    if code_stripped.startswith("initial_") or code_stripped.startswith("result"):
        return {"type": "measure", "desc": "Record initial state for comparison", "code": code_stripped}

    # Generic assignment or call
    if "=" in code_stripped or "(" in code_stripped:
        return {"type": "action", "desc": _shorten(code_stripped), "code": code_stripped}

    return None


def _extract_card_creation(code: str) -> str:
    m = re.search(r'name="([^"]+)"', code)
    if m:
        return f"Create card: {m.group(1)}"
    m = re.search(r'make_(\w+)\(', code)
    if m:
        return f"Create {m.group(1).replace('_', ' ')}"
    return "Create card"


def _extract_equipment(code: str) -> str:
    m = re.search(r'EquipmentSlot\.(\w+)', code)
    slot = m.group(1) if m else "?"
    m2 = re.search(r'_make_(\w+)', code)
    name = m2.group(1).replace("_", " ").title() if m2 else "equipment"
    return f"Equip {name} in {slot} slot"


def _extract_chain_link(code: str) -> str:
    m = re.search(r'name="([^"]+)"', code)
    if m:
        return f"Add chain link: {m.group(1)}"
    return "Add chain link to combat"


def _extract_event(code: str) -> str:
    m = re.search(r'EventType\.(\w+)', code)
    etype = m.group(1) if m else "event"
    return f"Emit {etype} event"


def _extract_counter(code: str) -> str:
    m = re.search(r'\.(\w+)\s*=', code)
    if m:
        field = m.group(1).replace("_", " ")
        return f"Set turn counter: {field}"
    return "Update turn counter"


def _extract_assertion(code: str) -> str:
    # Try to find the assertion message
    m = re.search(r'",?\s*\(\s*"([^"]+)"', code)
    if m:
        return m.group(1)
    m = re.search(r'",?\s*"([^"]+)"', code)
    if m:
        return m.group(1)
    # Fallback: describe the assertion
    if "== 0" in code:
        return "Verify: count is zero"
    if "== 1" in code:
        return "Verify: count is one"
    if "is None" in code:
        return "Verify: value is None"
    if "is True" in code or "assert " in code and "True" in code:
        return "Verify: condition is true"
    if "is False" in code or "assert not " in code:
        return "Verify: condition is false"
    return "Verify assertion"


def _shorten(code: str) -> str:
    if len(code) > 80:
        return code[:77] + "..."
    return code


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

STEP_ICONS = {
    "setup": "🔧",
    "create": "🃏",
    "equip": "🛡️",
    "register": "📋",
    "combat": "⚔️",
    "event": "📣",
    "cleanup": "🧹",
    "mark": "🔴",
    "effect": "✨",
    "state": "📦",
    "transform": "🔀",
    "check": "🔍",
    "assert": "✅",
    "measure": "📏",
    "action": "▶️",
    "comment": "💬",
}

STEP_COLORS = {
    "setup": "#7090b0",
    "create": "#90b070",
    "equip": "#b0a060",
    "register": "#8080a0",
    "combat": "#c06060",
    "event": "#c09040",
    "cleanup": "#707070",
    "mark": "#e05050",
    "effect": "#b080d0",
    "state": "#6090c0",
    "transform": "#a050c0",
    "check": "#60a0a0",
    "assert": "#50b050",
    "measure": "#8090a0",
    "action": "#a0a0a0",
    "comment": "#909090",
}


def render_html(files: list[dict]) -> str:
    parts = [_HTML_HEAD]

    total_tests = sum(
        len(t) for f in files for c in f["classes"] for t in [c["tests"]]
    )
    total_files = len(files)

    parts.append(f'<div class="summary">📋 {total_tests} scenario tests across {total_files} files</div>')

    # Table of contents
    parts.append('<div class="toc"><h2>Contents</h2><ul>')
    for f in files:
        fname = f["name"].replace("test_scenario_", "").replace("_", " ").title()
        parts.append(f'<li><a href="#{f["name"]}">{fname}</a>')
        parts.append("<ul>")
        for cls in f["classes"]:
            for test in cls["tests"]:
                tid = f'{f["name"]}_{test["name"]}'
                parts.append(f'<li><a href="#{tid}">{test["readable"]}</a></li>')
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
                parts.append(f'<details class="test-case" id="{tid}">')
                parts.append(f'<summary class="test-header">')
                parts.append(f'<span class="test-icon">🧪</span>')
                parts.append(f'<span class="test-name">{html.escape(test["readable"])}</span>')
                parts.append(f'<span class="step-count">{len(test["steps"])} steps</span>')
                parts.append(f'</summary>')

                if test["docstring"]:
                    parts.append(f'<div class="test-doc">{html.escape(test["docstring"])}</div>')

                parts.append('<div class="steps">')
                for i, step in enumerate(test["steps"]):
                    icon = STEP_ICONS.get(step["type"], "•")
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
                        # Highlight keywords
                        escaped_code = re.sub(r'\bassert\b', '<span class="kw-assert">assert</span>', escaped_code)
                        parts.append(f'<pre class="step-code">{escaped_code}</pre>')
                    parts.append(f'</div>')

                parts.append('</div>')  # steps
                parts.append('</details>')

        parts.append('</div>')  # file-section

    parts.append(_HTML_TAIL)
    return "\n".join(parts)


_HTML_HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>FaB Scenario Tests — Step-by-Step Review</title>
<style>
:root {
  --bg: #1a1a2e;
  --card-bg: #16213e;
  --text: #e0e0e0;
  --muted: #888;
  --border: #2a2a4a;
  --accent: #4a6a8a;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  background: var(--bg);
  color: var(--text);
  max-width: 950px;
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

.test-header {
  cursor: pointer;
  padding: 10px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  user-select: none;
}
.test-header:hover { background: rgba(255,255,255,0.03); }
.test-icon { font-size: 16px; }
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
.step.assert {
  background: rgba(80, 176, 80, 0.08);
}
.step.combat {
  background: rgba(192, 96, 96, 0.06);
}
.step.event {
  background: rgba(192, 144, 64, 0.06);
}

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
<h1>🧪 FaB Scenario Tests — Step-by-Step Review</h1>
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
        print("Usage: python3 tools/tests_to_html.py <test_dir_or_file> [output.html]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("scenario_tests.html")

    if input_path.is_dir():
        test_files = sorted(input_path.glob("test_scenario_*.py"))
    else:
        test_files = [input_path]

    files = []
    for tf in test_files:
        try:
            files.append(parse_test_file(tf))
        except Exception as e:
            print(f"Warning: failed to parse {tf}: {e}")

    html_content = render_html(files)
    output_path.write_text(html_content)
    print(f"Written {len(files)} test files ({sum(len(t) for f in files for c in f['classes'] for t in [c['tests']])} tests) to {output_path}")


if __name__ == "__main__":
    main()
