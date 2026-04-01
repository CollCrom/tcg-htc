"""Convert a game log .txt file into a styled HTML page.

Usage:
    python3 -m tools.log_to_html game_log.txt game_log.html
    open game_log.html
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path


def classify_line(line: str) -> str:
    """Classify a log line into a category for styling."""
    s = line.strip()
    if s.startswith("=== Turn"):
        return "turn-header"
    if "'s hand:" in s:
        return "hand"
    if "'s arsenal:" in s:
        return "arsenal"
    if " attacks with " in s:
        return "attack"
    if " chains " in s:
        return "chain-attack"
    if " defends with " in s:
        return "defend"
    if s.startswith("Hit!"):
        return "hit"
    if s.startswith("Blocked!"):
        return "blocked"
    if " plays attack reaction:" in s:
        return "atk-reaction"
    if " plays defense reaction:" in s:
        return "def-reaction"
    if " activates " in s:
        return "activate"
    if " plays " in s:
        return "play"
    if s.startswith("Pitched "):
        return "pitch"
    if " arsenals " in s:
        return "arsenal-action"
    if "Created " in s and "token" in s:
        return "token-create"
    if "Token destroyed:" in s:
        return "token-destroy"
    if "destroyed" in s.lower() and any(x in s for x in ["Blade Break", "Battleworn", "Temper"]):
        return "equip-break"
    if "Equipment destroyed:" in s:
        return "equip-break"
    if "prevented" in s.lower() or "prevention" in s.lower():
        return "prevention"
    if "Spring Tunic:" in s:
        return "upkeep"
    if "Marked " in s or "is now marked" in s:
        return "mark"
    if "Mark removed" in s:
        return "mark-remove"
    if "becomes " in s:
        return "transform"
    if s.startswith("Registered "):
        return "setup"
    if "end phase:" in s:
        return "end-phase"
    if s.startswith("RESULT:") or s.startswith("Final life:"):
        return "result"
    if s.startswith("==="):
        return "separator"
    return "effect"


def parse_turn_header(line: str) -> dict | None:
    m = re.match(
        r"=== Turn (\d+) \((\w+)'s turn\) \| Life: (\w+) (\d+) — (\w+) (\d+) ===",
        line.strip(),
    )
    if not m:
        return None
    return {
        "turn": int(m.group(1)),
        "active": m.group(2),
        "p1_name": m.group(3),
        "p1_life": int(m.group(4)),
        "p2_name": m.group(5),
        "p2_life": int(m.group(6)),
    }


CATEGORY_ICONS = {
    "attack": "\u2694\ufe0f",
    "chain-attack": "\u2694\ufe0f",
    "defend": "\U0001f6e1\ufe0f",
    "hit": "\U0001f4a5",
    "blocked": "\u270b",
    "atk-reaction": "\u26a1",
    "def-reaction": "\u26a1",
    "activate": "\u2699\ufe0f",
    "play": "\u25b6\ufe0f",
    "pitch": "\U0001f4b0",
    "arsenal-action": "\U0001f4e6",
    "token-create": "\u2728",
    "token-destroy": "\U0001f4a8",
    "equip-break": "\U0001f494",
    "prevention": "\U0001f6e1\ufe0f",
    "upkeep": "\U0001f504",
    "mark": "\U0001f534",
    "mark-remove": "\u26aa",
    "transform": "\U0001f500",
    "end-phase": "\U0001f319",
    "effect": "\u2022",
    "hand": "\u270b",
    "arsenal": "\U0001f4e6",
}


def render_html(lines: list[str], p1_name: str, p2_name: str) -> str:
    """Render log lines into a complete HTML document."""
    turns: list[dict] = []  # {header: dict, lines: [(category, text)]}
    setup_lines: list[tuple[str, str]] = []
    result_lines: list[str] = []
    current_turn: dict | None = None

    for line in lines:
        raw = line.rstrip()
        if not raw.strip():
            continue

        cat = classify_line(raw)
        text = raw.strip()

        if cat == "turn-header":
            if current_turn:
                turns.append(current_turn)
            header = parse_turn_header(text)
            current_turn = {"header": header, "lines": []}
        elif cat == "setup":
            setup_lines.append((cat, text))
        elif cat in ("result", "separator"):
            result_lines.append(text)
        elif current_turn is not None:
            current_turn["lines"].append((cat, text))
        else:
            setup_lines.append((cat, text))

    if current_turn:
        turns.append(current_turn)

    # Build HTML
    parts = [_HTML_HEAD.format(p1=html.escape(p1_name), p2=html.escape(p2_name))]

    # Game result summary at top
    if result_lines:
        parts.append('<div class="result-banner">')
        for rl in result_lines:
            if rl.startswith("==="):
                continue
            parts.append(f"<div>{html.escape(rl)}</div>")
        parts.append("</div>")

    # Setup section (collapsible)
    if setup_lines:
        parts.append('<details class="setup-section"><summary>Game Setup</summary>')
        for cat, text in setup_lines:
            parts.append(f'<div class="log-line setup">{html.escape(text)}</div>')
        parts.append("</details>")

    # Turns
    for turn in turns:
        h = turn["header"]
        if h is None:
            continue

        is_p1 = h["active"] == p1_name
        player_class = "p1-turn" if is_p1 else "p2-turn"
        p1_life_pct = max(0, min(100, h["p1_life"] * 100 // 40))
        p2_life_pct = max(0, min(100, h["p2_life"] * 100 // 40))

        # Check for notable events
        has_hit = any(c == "hit" for c, _ in turn["lines"])
        has_transform = any(c == "transform" for c, _ in turn["lines"])
        has_token = any(c in ("token-create", "token-destroy") for c, _ in turn["lines"])
        notable = " notable" if (has_hit or has_transform) else ""

        parts.append(f'<details class="turn {player_class}{notable}" open>')
        parts.append(f'<summary class="turn-header">')
        parts.append(f'<span class="turn-num">Turn {h["turn"]}</span>')
        parts.append(f'<span class="turn-player">{html.escape(h["active"])}</span>')
        parts.append(f'<span class="life-bars">')
        parts.append(f'<span class="life-bar p1-bar"><span class="life-fill" style="width:{p1_life_pct}%"></span><span class="life-text">{html.escape(h["p1_name"])} {h["p1_life"]}</span></span>')
        parts.append(f'<span class="life-bar p2-bar"><span class="life-fill" style="width:{p2_life_pct}%"></span><span class="life-text">{html.escape(h["p2_name"])} {h["p2_life"]}</span></span>')
        parts.append(f'</span>')
        parts.append(f'</summary>')

        # Turn content
        parts.append('<div class="turn-content">')

        # Group hand/arsenal at top
        hand_lines = [(c, t) for c, t in turn["lines"] if c in ("hand", "arsenal")]
        action_lines = [(c, t) for c, t in turn["lines"] if c not in ("hand", "arsenal")]

        if hand_lines:
            parts.append('<div class="zone-info">')
            for cat, text in hand_lines:
                parts.append(f'<div class="log-line {cat}">{html.escape(text)}</div>')
            parts.append("</div>")

        for cat, text in action_lines:
            icon = CATEGORY_ICONS.get(cat, "")
            escaped = html.escape(text)

            # Highlight card names in parenthetical color
            escaped = re.sub(
                r"\(Red\)", '<span class="color-red">(Red)</span>', escaped
            )
            escaped = re.sub(
                r"\(Yellow\)", '<span class="color-yellow">(Yellow)</span>', escaped
            )
            escaped = re.sub(
                r"\(Blue\)", '<span class="color-blue">(Blue)</span>', escaped
            )

            parts.append(f'<div class="log-line {cat}">{icon} {escaped}</div>')

        parts.append("</div>")  # turn-content
        parts.append("</details>")

    parts.append(_HTML_TAIL)
    return "\n".join(parts)


_HTML_HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>FaB Game Log — {p1} vs {p2}</title>
<style>
:root {{
  --p1-color: #c04040;
  --p1-bg: #fff0f0;
  --p2-color: #4040a0;
  --p2-bg: #f0f0ff;
  --hit-color: #d63030;
  --blocked-color: #30a030;
  --token-color: #b08020;
  --transform-color: #8030c0;
  --bg: #1a1a2e;
  --card-bg: #16213e;
  --text: #e0e0e0;
  --muted: #888;
  --border: #2a2a4a;
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.5;
  background: var(--bg);
  color: var(--text);
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;
}}

h1 {{
  text-align: center;
  font-size: 18px;
  margin-bottom: 16px;
  color: #fff;
}}

.result-banner {{
  background: linear-gradient(135deg, #2a1a3e, #1a2a4e);
  border: 1px solid #4a3a6a;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
  text-align: center;
  font-size: 15px;
  font-weight: bold;
  color: #f0d060;
}}

.setup-section {{
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  margin-bottom: 12px;
  padding: 8px 12px;
}}
.setup-section summary {{
  cursor: pointer;
  color: var(--muted);
  font-size: 12px;
}}
.setup-section .log-line {{
  color: var(--muted);
  font-size: 11px;
}}

.turn {{
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;
}}
.turn.notable {{
  border-color: #4a4a6a;
}}

.turn-header {{
  cursor: pointer;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  user-select: none;
}}
.p1-turn > .turn-header {{ background: rgba(192, 64, 64, 0.1); }}
.p2-turn > .turn-header {{ background: rgba(64, 64, 160, 0.1); }}

.turn-num {{
  font-weight: bold;
  font-size: 12px;
  color: var(--muted);
  min-width: 50px;
}}
.turn-player {{
  font-weight: bold;
  font-size: 14px;
  min-width: 80px;
}}
.p1-turn .turn-player {{ color: var(--p1-color); }}
.p2-turn .turn-player {{ color: var(--p2-color); }}

.life-bars {{
  display: flex;
  gap: 8px;
  flex: 1;
  justify-content: flex-end;
}}
.life-bar {{
  position: relative;
  width: 120px;
  height: 20px;
  background: #0a0a1e;
  border-radius: 4px;
  overflow: hidden;
}}
.life-fill {{
  position: absolute;
  top: 0; left: 0; bottom: 0;
  border-radius: 4px;
  transition: width 0.3s;
}}
.p1-bar .life-fill {{ background: rgba(192, 64, 64, 0.5); }}
.p2-bar .life-fill {{ background: rgba(64, 64, 160, 0.5); }}
.life-text {{
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 11px;
  font-weight: bold;
}}

.turn-content {{
  padding: 4px 12px 8px;
}}

.zone-info {{
  background: rgba(255,255,255,0.03);
  border-radius: 4px;
  padding: 4px 8px;
  margin-bottom: 6px;
  font-size: 11px;
  color: var(--muted);
}}

.log-line {{
  padding: 2px 0;
  font-size: 12px;
}}
.log-line.attack, .log-line.chain-attack {{
  color: #e06060;
  font-weight: bold;
}}
.log-line.defend {{
  color: #60a0e0;
  padding-left: 20px;
}}
.log-line.hit {{
  color: var(--hit-color);
  font-weight: bold;
  font-size: 13px;
  padding-left: 20px;
}}
.log-line.blocked {{
  color: var(--blocked-color);
  font-weight: bold;
  padding-left: 20px;
}}
.log-line.atk-reaction, .log-line.def-reaction {{
  color: #e0a030;
  padding-left: 20px;
}}
.log-line.activate {{
  color: #c090e0;
  padding-left: 20px;
}}
.log-line.play {{
  color: #70c070;
}}
.log-line.pitch {{
  color: #8090a0;
  padding-left: 20px;
  font-size: 11px;
}}
.log-line.arsenal-action {{
  color: #90b0d0;
}}
.log-line.token-create {{
  color: var(--token-color);
}}
.log-line.token-destroy {{
  color: #806020;
}}
.log-line.equip-break {{
  color: #a05050;
  padding-left: 20px;
}}
.log-line.prevention {{
  color: #50b0b0;
  padding-left: 20px;
}}
.log-line.upkeep {{
  color: var(--muted);
  font-size: 11px;
}}
.log-line.mark {{
  color: #e05050;
  font-weight: bold;
}}
.log-line.mark-remove {{
  color: #808080;
}}
.log-line.transform {{
  color: var(--transform-color);
  font-weight: bold;
  font-size: 13px;
}}
.log-line.end-phase {{
  color: #7070b0;
}}
.log-line.effect {{
  color: var(--muted);
  padding-left: 20px;
  font-size: 11px;
}}

.color-red {{ color: #e06060; font-weight: bold; }}
.color-yellow {{ color: #d0c040; font-weight: bold; }}
.color-blue {{ color: #6090d0; font-weight: bold; }}

details[open] > summary::before {{ content: "\\25BC "; font-size: 10px; }}
details:not([open]) > summary::before {{ content: "\\25B6 "; font-size: 10px; }}
</style>
</head>
<body>
<h1>\u2694\ufe0f {p1} vs {p2} \u2694\ufe0f</h1>
"""

_HTML_TAIL = """\
</body>
</html>
"""


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m tools.log_to_html <input.txt> [output.html]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_suffix(".html")

    lines = input_path.read_text().splitlines()

    # Detect player names from first turn header
    p1_name = "Player 1"
    p2_name = "Player 2"
    for line in lines:
        h = parse_turn_header(line)
        if h:
            p1_name = h["p1_name"]
            p2_name = h["p2_name"]
            break

    html_content = render_html(lines, p1_name, p2_name)
    output_path.write_text(html_content)
    print(f"Written to {output_path}")


if __name__ == "__main__":
    main()
