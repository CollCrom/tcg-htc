# Claude Agents run through Claude Code in print mode, not the Anthropic API

A Claude Agent makes each decision by spawning Claude Code (`claude -p`) on the developer's machine, authenticated by their Claude subscription, rather than by calling the Anthropic API with a key. One process per decision, tools disabled, the answer constrained by a JSON schema. We chose this because the subscription is already paid for and a Game of 250 or so decisions costs about $12 of Opus tokens through the API, so a ten-Game suite would be an API bill of over $100 every run.

## Considered Options

- **The Anthropic API through `@anthropic-ai/sdk`**: the documented path, with structured outputs, explicit prompt caching and per-token billing. Rejected for cost, and because it needs a key to manage.
- **The Claude Agent SDK**: programmatic Claude Code, but its docs direct users to an API key and bar third parties from offering claude.ai login in products built on it. The CLI is the documented subscription path.

## Consequences

- Runs are bounded by the subscription's rolling and weekly usage windows, which Anthropic does not publish. The suite must be resumable, and a rate limit pauses a run rather than failing it.
- The `claude` binary is a runtime dependency, and `ANTHROPIC_API_KEY` must be absent from the child process's environment, or print mode bills the API instead.
- Model choice is by Claude Code alias (`opus`, `sonnet`, `haiku`, `fable`), so what a Game was played by is whatever the alias mapped to on that day; the Decision record keeps Claude Code's reported model.
