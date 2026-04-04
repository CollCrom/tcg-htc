Spawn the Test Generator agent to create targeted scenario tests for specific card interactions.

Use the Agent tool to spawn a test generator with this prompt:

---

You are the Test Generator. Read `agents/test-generator.md` and follow `PROTOCOL.md`.

## Task

Generate targeted scenario tests for the following interaction(s):

$ARGUMENTS

## Rules

- Place tests in `tests/scenarios/` with descriptive filenames
- Use existing test infrastructure: `make_game_shell()`, `make_ability_context()`, conftest fixtures
- Focus on edge cases and timing — happy paths are less valuable
- Run `python3 -m pytest tests/scenarios/ -q` after writing tests to verify they pass
- If a test reveals a bug (test fails), report it — do NOT fix engine code
- Make small, focused commits
