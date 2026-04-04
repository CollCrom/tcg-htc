Spawn the Skeptic agent for a full codebase gate review (not just the diff).

Use the Agent tool to spawn a skeptic with this prompt:

---

You are the Skeptic. Read `agents/skeptic.md` and follow `PROTOCOL.md`.

## Task — Full Codebase Gate Review

This is a comprehensive review of the entire codebase on the current branch. Read `memory/skeptic.md` for prior findings.

### Scope

Review ALL source files in `src/htc/` for:

1. **Rules correctness** — game logic vs FaB comprehensive rules
2. **`definition.X` bypasses** — `definition.keywords`, `definition.supertypes`, `definition.subtypes`, `definition.power`, `definition.defense` that should use effect engine
3. **Consumed-closure bugs** — target_filters with mutable state consumed before resolution
4. **Zone cleanup** — equipment destruction, combat chain close, zone transitions
5. **Damage source attribution** — all damage events correctly attribute source
6. **Trigger processing gaps** — events emitted without `_process_pending_triggers()`
7. **Dead code** — unused functions, unreachable branches
8. **Missing preconditions** — cards offered when they shouldn't be

### How to review

1. Read `memory/skeptic.md` for known patterns
2. Grep for known bug patterns (`definition.keywords`, `definition.supertypes`, `consumed = [`, etc.)
3. Read through `src/htc/engine/` checking game flow
4. Read through `src/htc/cards/abilities/` checking card implementations
5. Run stress tests: `python3 -m pytest tests/integration/test_stress.py -q --tb=short`

### Output

- **Critical issues** (incorrect game outcomes)
- **Minor issues** (code quality, dormant edge cases)
- **Pre-existing accepted** (documented in memory, not blocking)
- **Missing tests**
- **Verified correct**

Update `memory/skeptic.md` — mark prior items resolved vs still open.
