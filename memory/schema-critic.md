# schema-critic memory

Patterns about *how to do structural critique well* on this project. Not game knowledge.

---

## On-spawn reading I actually used (2026-04-29, first spawn)

What was indispensable:
- `agents/schema-critic.md` — the role definition, especially the "no change is a valid output" line and the "player startup reading is the test" framing. Re-read this at the start of every spawn.
- `playbook/README.md` — documents the structure-as-hypothesis. Compare to ground truth.
- `playbook/proposals/notes-for-schema-critic.md` — librarian's drift signals. Check both whether they're real AND whether they're load-bearing yet.
- The two `fundamentals.md` files and `open-questions.md` — total content the librarian is currently routing.
- The two `lessons.md` files — the *shape* of incoming material, not just the content. What categories of lesson are arriving?
- `playbook/player_spawn_prompt.md` — **critical and easy to miss**. This tells you who actually reads the playbook at decision time. On this project today: nobody. That changed my entire calculus.

What I didn't need:
- `match_protocol.md` and `two_agent_match.md` are operator/wire docs, not lesson content. Skim once to confirm classification, then skip.

## Patterns I trust after one spawn

**Drift signals from the librarian are diagnostic, not prescriptive.** The librarian flags ambiguous routing because it's their job to flag, not because they want a restructure. Two real drift signals can both deserve "no change" if they aren't yet load-bearing. Don't conflate "the librarian flagged this" with "this needs fixing."

**"Load-bearing" requires a consumer.** A structural choice is only worth changing if some reader pays a cost for the current structure. On this project today the only readers are the librarian (writing) and the schema-critic (auditing). Both can navigate ad-hoc filenames. Player sub-agents do *not* read the playbook. Until that changes, structure decisions are optimizing for a hypothetical reader.

**An aspirational README is not the same as drift.** This project's README enumerated `overview.md` / `matchups/` / `lines.md` per hero before any lesson content existed. The slots filled out of order — `fundamentals.md` arrived first because rule-derived facts arrived first. That's the README being wrong about arrival order, not the content being wrong. Don't restructure content to match an aspirational layout; either update the layout doc or wait for evidence the layout is right.

**Count the inhabitants.** Before proposing a split, count the files / sections in the category being split. Splitting two files into a more elaborate hierarchy is premature. Splitting twenty files is overdue. The cutoff isn't precise but "fewer than 5 inhabitants" is almost always too few.

## Things that were hard to evaluate at this size

- **Whether a lesson is "matchup-specific" vs "hero-fundamental" with a matchup example.** LC-004 (Blade Break trade) is rules-grounded for both heroes (Cindra exploits Blade Break; Arakni's defense risk *is* Blade Break) and could plausibly live in either `arakni/fundamentals.md`, `cindra/matchups/arakni.md`, or a top-level matchup file. With one match of evidence, all three are defensible. Wait for promotion to force the call.
- **Whether the empty directories (`general/`, `fundamentals/`, all `matchups/`) are dead weight or scaffold.** Can't tell at this size. Marked them as TBD-on-first-inhabitant in the proposal anti-cases.
- **Whether `fundamentals.md` per hero will scale.** Both current files are ~26 lines. If they stay that size with 5+ heroes the structure is fine; if they grow to 200+ lines with 5+ subsections each, the per-hero file becomes the wrong unit. No way to predict from current data.

## Signals to start trusting (or distrusting)

Trust:
- **Librarian flags ambiguous routing** — these are real even if not yet actionable.
- **Promotion attempts that hit "where does this go?"** — that's the moment a category is forced to declare itself.
- **Duplication that actually happens in writing** — not "duplication that *would* happen" hypothetically.

Distrust:
- **"This would be cleaner if..." reasoning unmoored from a specific painful path.** The role file is explicit: walk through a specific player decision-time path that's broken under the current structure. If you can't, you don't have a proposal.
- **README/layout-doc symmetry as evidence of correctness.** A consistent-looking layout that nobody reads is no better than an inconsistent one nobody reads.
- **The first instance of any pattern.** One `fundamentals.md` is an experiment; two is a convention; three+ is structure. Don't generalize from one.

## Anti-patterns to avoid

- **Don't pile multiple changes into one proposal.** The role file says one per spawn for a reason — paired changes get evaluated as a bundle and the weaker one drags the stronger down.
- **Don't propose a restructure to "test the new layout."** Restructures are expensive enough that they need to be load-bearing on entry. Speculative reorganizations are content-churn for the librarian and risk losing/scrambling existing references.
- **Don't write content fixes into structure proposals.** If a lesson reads wrong, file a note for the librarian; don't fold it into a structure change.
- **Don't skip writing "no change" proposals.** A no-change file is the durable record that the question was asked. The next schema-critic shouldn't have to re-derive it from the absence of a proposal.

## Open meta-questions for the next spawn

- What fraction of "drift signals" turn out to be load-bearing on a 6-month horizon? Track this. If most resolve themselves (lessons promote into clean homes naturally), the librarian's flagging threshold is well-calibrated. If most accumulate, the threshold may need lowering or the structure is genuinely off.
- Does the operator ever route playbook content into the player sub-agent's context? If yes, re-evaluate everything — the consumer changes the test.
- When a "no change" proposal is on file, how should the next schema-critic treat it? Suggested practice: read it first, check whether any of its anti-cases have triggered, and only re-open the question if at least one has.
