Spawn the Skeptic agent to review a specific file or module for rules correctness.

Use the Agent tool to spawn a skeptic with this prompt:

---

You are the Skeptic. Read `agents/skeptic.md` and follow `PROTOCOL.md`.

## Task — Targeted Audit

Review the following file(s) for rules correctness:

$ARGUMENTS

Read `memory/skeptic.md` for your persistent context and known patterns.

### What to check

1. Every game mechanic in the file — does it match FaB comprehensive rules?
2. `definition.X` bypasses — should any use the effect engine instead?
3. Target filters with mutable state (consumed-closure pattern)
4. Zone transitions — are all references cleaned up?
5. Damage attribution — correct source on all events?
6. Trigger processing — events emitted without `_process_pending_triggers()`?

### Output

- **Issues found** (with severity and rule references)
- **Verified correct** (brief)
- **Missing tests** for this file

Update `memory/skeptic.md` if you find anything new.
