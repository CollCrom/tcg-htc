"""Generate a self-contained HTML board state viewer from a snapshot JSON file.

Reads a JSON file produced by demo_scenario.py and generates a single HTML
page that lets you step through game states with arrow keys or J/K.

Usage:
    python3 tools/board_viewer.py demo_snapshots.json board_view.html
    open board_view.html
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path


def _color_class(color: str | None) -> str:
    """Map a card color to a CSS class."""
    if color == "Red":
        return "card-red"
    elif color == "Yellow":
        return "card-yellow"
    elif color == "Blue":
        return "card-blue"
    return "card-none"


def generate_html(snapshots: list[dict]) -> str:
    """Generate a self-contained HTML page from snapshots."""
    # Serialize snapshots into JS
    snapshots_json = json.dumps(snapshots)

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>FaB Board Viewer</title>
<style>
:root {{
  --bg: #1a1a2e;
  --card-bg: #16213e;
  --text: #e0e0e0;
  --muted: #888;
  --border: #2a2a4a;
  --accent: #4a3a6a;
  --red: #c04040;
  --blue: #4070c0;
  --yellow: #c0a030;
  --gray: #606060;
  --life-bg: #0a0a1e;
  --hit-glow: #ff4444;
  --marked-glow: #ff2222;
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.4;
  background: var(--bg);
  color: var(--text);
  max-width: 1100px;
  margin: 0 auto;
  padding: 16px;
  user-select: none;
}}

/* --- Header / Nav --- */
.nav-bar {{
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 10px 0;
  margin-bottom: 12px;
}}
.nav-bar button {{
  background: var(--accent);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 16px;
  font-family: inherit;
  font-size: 13px;
  cursor: pointer;
}}
.nav-bar button:hover {{ background: #5a4a8a; }}
.nav-bar button:disabled {{ opacity: 0.3; cursor: default; }}
.step-counter {{
  color: var(--muted);
  font-size: 14px;
  min-width: 100px;
  text-align: center;
}}

/* --- Description --- */
.description {{
  text-align: center;
  font-size: 15px;
  font-weight: bold;
  color: #f0d060;
  padding: 8px 12px;
  margin-bottom: 12px;
  background: linear-gradient(135deg, #2a1a3e, #1a2a4e);
  border: 1px solid var(--accent);
  border-radius: 8px;
}}

/* --- Game info bar --- */
.game-info {{
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-bottom: 10px;
  font-size: 11px;
  color: var(--muted);
}}

/* --- Board layout --- */
.board {{
  display: flex;
  flex-direction: column;
  gap: 8px;
}}

.player-zone {{
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 14px;
}}
.player-zone.marked {{
  border-color: var(--marked-glow);
  box-shadow: 0 0 8px rgba(255, 34, 34, 0.3);
}}

.player-header {{
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}}
.player-name {{
  font-weight: bold;
  font-size: 15px;
}}
.player-name.opp {{ color: var(--red); }}
.player-name.turn {{ color: var(--blue); }}

.life-bar {{
  position: relative;
  width: 140px;
  height: 22px;
  background: var(--life-bg);
  border-radius: 4px;
  overflow: hidden;
}}
.life-fill {{
  position: absolute;
  top: 0; left: 0; bottom: 0;
  border-radius: 4px;
  transition: width 0.3s;
}}
.life-fill.opp {{ background: rgba(192, 64, 64, 0.6); }}
.life-fill.turn {{ background: rgba(64, 112, 192, 0.6); }}
.life-text {{
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 12px;
  font-weight: bold;
}}

.marked-badge {{
  background: var(--marked-glow);
  color: #fff;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: bold;
}}

.diplo-badge {{
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: bold;
  color: #fff;
}}
.diplo-war {{
  background: #c04040;
}}
.diplo-peace {{
  background: #4080c0;
}}

.deck-count {{
  color: var(--muted);
  font-size: 11px;
}}

/* --- Zone rows --- */
.zone-row {{
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}}
.zone-label {{
  color: var(--muted);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 1px;
  min-width: 70px;
  padding-top: 4px;
}}

/* --- Card rendering --- */
.card {{
  position: relative;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 70px;
  max-width: 90px;
  padding: 5px 6px;
  border-radius: 6px;
  border: 1px solid var(--border);
  font-size: 10px;
  text-align: center;
  line-height: 1.2;
  background: var(--bg);
}}
.card .card-name {{
  font-weight: bold;
  margin-bottom: 2px;
  word-break: break-word;
}}
.card .card-stats {{
  color: var(--muted);
  font-size: 9px;
}}

.card.card-red {{ border-color: var(--red); color: #e88; }}
.card.card-yellow {{ border-color: var(--yellow); color: #dd9; }}
.card.card-blue {{ border-color: var(--blue); color: #8af; }}
.card.card-none {{ border-color: var(--gray); color: #aaa; }}

.card.card-back {{
  background: #1a1030;
  border-color: var(--accent);
  color: var(--muted);
  min-width: 50px;
}}

.card.face-down {{
  opacity: 0.75;
  border-style: dashed;
}}
.fd-badge {{
  position: absolute;
  top: 2px;
  right: 2px;
  font-size: 8px;
  background: #555;
  color: #ccc;
  padding: 0 3px;
  border-radius: 2px;
}}

.card.tapped {{
  opacity: 0.5;
  transform: rotate(8deg);
}}

/* --- Equipment cards --- */
.equip-card {{
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  min-width: 80px;
  padding: 4px 6px;
  border-radius: 5px;
  border: 1px solid #3a5a3a;
  background: #0a1a0a;
  font-size: 10px;
  text-align: center;
}}
.equip-card .equip-name {{ font-weight: bold; color: #8c8; }}
.equip-card .equip-slot {{ color: var(--muted); font-size: 9px; }}
.equip-card .equip-def {{ color: #6a6; font-size: 9px; }}
.equip-card .equip-counters {{ color: #cc8; font-size: 9px; }}
.equip-card.tapped {{ opacity: 0.5; }}
.equip-card.activated {{
  border-color: #e0a030;
  box-shadow: 0 0 6px rgba(224, 160, 48, 0.5);
}}

/* --- Weapon cards --- */
.weapon-card {{
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  min-width: 80px;
  padding: 4px 6px;
  border-radius: 5px;
  border: 1px solid #5a3a3a;
  background: #1a0a0a;
  font-size: 10px;
  text-align: center;
}}
.weapon-card .weapon-name {{ font-weight: bold; color: #c88; }}
.weapon-card .weapon-power {{ color: #a66; font-size: 9px; }}
.weapon-card.tapped {{ opacity: 0.5; transform: rotate(8deg); }}

/* --- Permanent / Token cards --- */
.perm-card {{
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  min-width: 70px;
  padding: 4px 6px;
  border-radius: 5px;
  border: 1px solid #5a5a2a;
  background: #1a1a0a;
  font-size: 10px;
  text-align: center;
}}
.perm-card .perm-name {{ font-weight: bold; color: #cc8; }}
.perm-card .perm-counters {{ color: #aa6; font-size: 9px; }}

/* --- Combat chain --- */
.combat-zone {{
  background: linear-gradient(135deg, #2a1020, #201030);
  border: 1px solid #4a2a4a;
  border-radius: 8px;
  padding: 10px 14px;
}}
.combat-title {{
  color: #e06060;
  font-weight: bold;
  font-size: 12px;
  margin-bottom: 6px;
}}
.chain-links {{
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 4px;
}}
.chain-link {{
  flex-shrink: 0;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
  min-width: 130px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}}
.chain-link.hit-link {{ border-color: var(--hit-glow); }}
.chain-link.stack-link {{ border-style: dashed; opacity: 0.8; }}
.chain-link-num {{
  color: var(--muted);
  font-size: 10px;
}}
.chain-vs {{
  color: var(--muted);
  font-size: 10px;
  font-weight: bold;
}}
.chain-defenders-row {{
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  justify-content: center;
}}
.chain-attack {{
  font-weight: bold;
  font-size: 12px;
}}
.chain-defenders {{
  font-size: 11px;
  color: #8af;
}}
.chain-result {{
  font-size: 10px;
  margin-top: 3px;
  font-weight: bold;
}}
.chain-result.hit {{ color: var(--hit-glow); }}
.chain-result.blocked {{ color: #30a030; }}

/* --- Empty state --- */
.empty {{ color: var(--muted); font-style: italic; font-size: 11px; }}

/* --- Keyboard hint --- */
.hint {{
  text-align: center;
  color: var(--muted);
  font-size: 11px;
  margin-top: 12px;
}}
</style>
</head>
<body>

<div class="nav-bar">
  <button id="btn-prev" onclick="prev()">&larr; Prev</button>
  <span class="step-counter" id="step-counter">Step 1 / 1</span>
  <button id="btn-next" onclick="next()">Next &rarr;</button>
</div>

<div class="description" id="description"></div>

<div class="game-info" id="game-info"></div>

<div class="board" id="board"></div>

<div class="hint">Use &larr;/&rarr; arrow keys or J/K to navigate steps</div>

<script>
const SNAPSHOTS = {snapshots_json};
let currentStep = 0;

function escHtml(s) {{
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}}

function colorClass(color) {{
  if (color === 'Red') return 'card-red';
  if (color === 'Yellow') return 'card-yellow';
  if (color === 'Blue') return 'card-blue';
  return 'card-none';
}}

function renderCard(card) {{
  if (!card.face_up && card.name === '???') {{
    return '<div class="card card-back"><div class="card-name">?</div></div>';
  }}
  const cls = colorClass(card.color);
  const faceDown = !card.face_up ? ' face-down' : '';
  let stats = [];
  if (card.power != null) stats.push('P:' + card.power);
  if (card.defense != null) stats.push('D:' + card.defense);
  if (card.cost != null) stats.push('C:' + card.cost);
  const statsStr = stats.length ? '<div class="card-stats">' + stats.join(' ') + '</div>' : '';
  const fdBadge = !card.face_up ? '<div class="fd-badge">FD</div>' : '';
  return '<div class="card ' + cls + faceDown + '"><div class="card-name">' + escHtml(card.name) + '</div>' + statsStr + fdBadge + '</div>';
}}

function renderEquipment(eq) {{
  let cls = 'equip-card';
  if (eq.is_tapped) cls += ' tapped';
  if (eq.activated_this_turn) cls += ' activated';
  let counters = '';
  if (eq.counters && Object.keys(eq.counters).length > 0) {{
    const parts = Object.entries(eq.counters).map(([k, v]) => k + ':' + v);
    counters = '<div class="equip-counters">' + parts.join(' ') + '</div>';
  }}
  return '<div class="' + cls + '">' +
    '<div class="equip-name">' + escHtml(eq.name) + '</div>' +
    '<div class="equip-slot">' + eq.slot + '</div>' +
    (eq.defense != null ? '<div class="equip-def">Def: ' + eq.defense + '</div>' : '') +
    counters +
    '</div>';
}}

function renderWeapon(w) {{
  let cls = w.is_tapped ? 'weapon-card tapped' : 'weapon-card';
  let counters = '';
  if (w.counters && Object.keys(w.counters).length > 0) {{
    const parts = Object.entries(w.counters).map(([k, v]) => k + ':' + v);
    counters = '<div style="color:#aa6;font-size:9px">' + parts.join(' ') + '</div>';
  }}
  return '<div class="' + cls + '">' +
    '<div class="weapon-name">' + escHtml(w.name) + '</div>' +
    (w.power != null ? '<div class="weapon-power">Power: ' + w.power + '</div>' : '') +
    counters +
    '</div>';
}}

function renderPermanent(p) {{
  let counters = '';
  if (p.counters && Object.keys(p.counters).length > 0) {{
    const parts = Object.entries(p.counters).map(([k, v]) => k + ':' + v);
    counters = '<div class="perm-counters">' + parts.join(' ') + '</div>';
  }}
  return '<div class="perm-card"><div class="perm-name">' + escHtml(p.name) + '</div>' + counters + '</div>';
}}

function renderZoneRow(label, contentHtml) {{
  if (!contentHtml) return '';
  return '<div class="zone-row"><span class="zone-label">' + label + '</span>' + contentHtml + '</div>';
}}

function renderPlayer(player, role) {{
  // role: 'opp' or 'turn'
  const markedCls = player.is_marked ? ' marked' : '';
  let html = '<div class="player-zone' + markedCls + '">';

  // Header
  html += '<div class="player-header">';
  html += '<span class="player-name ' + role + '">' + escHtml(player.name) + '</span>';

  // Life bar
  const lifePct = Math.max(0, Math.min(100, Math.round(player.life * 100 / 40)));
  html += '<div class="life-bar"><div class="life-fill ' + role + '" style="width:' + lifePct + '%"></div>';
  html += '<div class="life-text">' + player.life + ' HP</div></div>';

  if (player.is_marked) {{
    html += '<span class="marked-badge">MARKED</span>';
  }}
  if (player.diplomacy_restriction) {{
    const dipCls = player.diplomacy_restriction === 'war' ? 'diplo-war' : 'diplo-peace';
    const dipLabel = player.diplomacy_restriction === 'war' ? 'WAR' : 'PEACE';
    html += '<span class="diplo-badge ' + dipCls + '">' + dipLabel + '</span>';
  }}
  html += '<span class="deck-count">Deck: ' + player.deck_count + '</span>';
  html += '</div>'; // player-header

  // Hand
  if (player.hand && player.hand.length > 0) {{
    const handHtml = player.hand.map(c => renderCard(c)).join('');
    html += renderZoneRow('Hand (' + player.hand_count + ')', handHtml);
  }} else {{
    html += renderZoneRow('Hand', '<span class="empty">empty</span>');
  }}

  // Arsenal
  if (player.arsenal && player.arsenal.length > 0) {{
    const arsHtml = player.arsenal.map(c => renderCard(c)).join('');
    html += renderZoneRow('Arsenal', arsHtml);
  }}

  // Equipment
  const eqSlots = player.equipment ? Object.values(player.equipment) : [];
  if (eqSlots.length > 0) {{
    const eqHtml = eqSlots.map(e => renderEquipment(e)).join('');
    html += renderZoneRow('Equip', eqHtml);
  }}

  // Weapons
  if (player.weapons && player.weapons.length > 0) {{
    const wHtml = player.weapons.map(w => renderWeapon(w)).join('');
    html += renderZoneRow('Weapons', wHtml);
  }}

  // Permanents / Tokens
  if (player.permanents && player.permanents.length > 0) {{
    const pHtml = player.permanents.map(p => renderPermanent(p)).join('');
    html += renderZoneRow('Tokens', pHtml);
  }}

  // Graveyard summary
  if (player.graveyard_count > 0) {{
    html += renderZoneRow('Grave', '<span class="empty">' + player.graveyard_count + ' cards</span>');
  }}

  // Banished zone
  if (player.banished && player.banished.length > 0) {{
    const bHtml = player.banished.map(b => {{
      const cls = colorClass(b.color);
      const fdCls = b.face_up ? '' : ' face-down';
      const fdBadge = b.face_up ? '' : '<div class="fd-badge">FD</div>';
      return '<div class="card ' + cls + fdCls + '"><div class="card-name">' + escHtml(b.name) + '</div>' + fdBadge + '</div>';
    }}).join('');
    html += renderZoneRow('Banish', bHtml);
  }}

  html += '</div>'; // player-zone
  return html;
}}

function renderCombatChain(chain) {{
  if (!chain || chain.length === 0) return '';

  let html = '<div class="combat-zone">';
  html += '<div class="combat-title">Combat Chain</div>';
  html += '<div class="chain-links">';

  for (const link of chain) {{
    const hitCls = link.hit ? ' hit-link' : '';
    const stackCls = link.on_stack ? ' stack-link' : '';
    html += '<div class="chain-link' + hitCls + stackCls + '">';
    const label = link.on_stack ? 'On Stack' : 'Link #' + link.link_number;
    html += '<div class="chain-link-num">' + label + '</div>';

    // Defenders first (top of screen = defending player)
    if (link.defenders && link.defenders.length > 0) {{
      html += '<div class="chain-defenders-row">';
      for (const d of link.defenders) {{
        const dCls = colorClass(d.color);
        html += '<div class="card ' + dCls + '">';
        html += '<div class="card-name">' + escHtml(d.name) + '</div>';
        if (d.defense != null) html += '<div class="card-stats">D:' + d.defense + '</div>';
        html += '</div>';
      }}
      html += '</div>';
      html += '<div class="chain-vs">vs</div>';
    }}

    // Attack card (bottom = attacking player)
    if (link.attack) {{
      const aCls = colorClass(link.attack.color);
      html += '<div class="card ' + aCls + '">';
      html += '<div class="card-name">' + escHtml(link.attack.name) + '</div>';
      if (link.attack.power != null) html += '<div class="card-stats">P:' + link.attack.power + '</div>';
      html += '</div>';
    }}

    if (link.damage_dealt > 0) {{
      html += '<div class="chain-result hit">Hit for ' + link.damage_dealt + '</div>';
    }} else if (link.defenders && link.defenders.length > 0 && link.damage_dealt === 0) {{
      html += '<div class="chain-result blocked">Blocked!</div>';
    }}

    html += '</div>'; // chain-link
  }}

  html += '</div>'; // chain-links
  html += '</div>'; // combat-zone
  return html;
}}

function render() {{
  const snap = SNAPSHOTS[currentStep];
  if (!snap) return;

  // Step counter
  document.getElementById('step-counter').textContent =
    'Step ' + (currentStep + 1) + ' / ' + SNAPSHOTS.length;

  // Description
  document.getElementById('description').textContent = snap.description;

  // Game info
  const fabTurn = Math.floor(snap.turn_number / 2);
  let info = 'Turn ' + fabTurn;
  if (snap.phase) info += ' | Phase: ' + snap.phase;
  if (snap.combat_step) info += ' | Combat: ' + snap.combat_step;
  info += ' | Actions: ' + snap.action_points + ' | Resources: ' + snap.resource_points;
  if (snap.game_over) info += ' | GAME OVER';
  document.getElementById('game-info').textContent = info;

  // Board
  let board = '';

  // Opponent at top
  board += renderPlayer(snap.opponent, 'opp');

  // Combat chain in middle
  board += renderCombatChain(snap.combat_chain);

  // Turn player at bottom
  board += renderPlayer(snap.turn_player, 'turn');

  document.getElementById('board').innerHTML = board;

  // Button state
  document.getElementById('btn-prev').disabled = (currentStep === 0);
  document.getElementById('btn-next').disabled = (currentStep >= SNAPSHOTS.length - 1);
}}

function prev() {{
  if (currentStep > 0) {{ currentStep--; render(); }}
}}
function next() {{
  if (currentStep < SNAPSHOTS.length - 1) {{ currentStep++; render(); }}
}}

document.addEventListener('keydown', function(e) {{
  if (e.key === 'ArrowLeft' || e.key === 'j' || e.key === 'J') prev();
  if (e.key === 'ArrowRight' || e.key === 'k' || e.key === 'K') next();
}});

// Initial render
render();
</script>
</body>
</html>"""


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 tools/board_viewer.py <snapshots.json> [output.html]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_suffix(".html")

    snapshots = json.loads(input_path.read_text())
    html_content = generate_html(snapshots)
    output_path.write_text(html_content)
    print(f"Written {len(snapshots)} snapshots to {output_path}")


if __name__ == "__main__":
    main()
