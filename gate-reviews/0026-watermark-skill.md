# Gate-review verdict — PR #26

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: PR #26, `feat/watermark-skill`
- Diff range: a94cd5b..fab2a8f
- Gate-layer paths changed: `skills-order`, `tests/revert-battery.py`, `tests/run-golden.py`
- Reviewers / instruments: 4 blind same-model lenses (A — replay the real failure; B — coverage
  vs advertising; C — self-description drift; D — fixture requirement) run in fresh contexts,
  each seeing only the brief + its own lens + the diff, followed by a sequential adjudicator
  (E) that saw all four raw outputs and independently re-ran/re-verified their load-bearing
  claims before merging them.
- Independence limit honestly stated: all five instruments are the same model family — this is
  *context* isolation (fresh, blind, non-communicating runs), not *model-weight* decorrelation.
  No different-vendor cold pass was run; the diff carries no BLOCKER-risk finding that would have
  made one worth the cost (see gate-review-prompt.md "Independence").

## Replay the real failure

The real failure this gate class exists to catch (per CHANGELOG 1.2.0 and `gate-reviews/0005`):
a lint that reported `clean`/CI-green while actually inspecting only 2 of the 5 places the suite
enumerates its skills. `generate-skill-enumerations.py` names exactly 5 sites: `PURE_SITES` =
improve-order, pick-list, tree (`generate-skill-enumerations.py:359-363`) and `TABLE_SITES` =
table, attach-table (`:364`).

Lens A reproduced the real failure against **this diff's own change** (adding a 9th skill,
`watermark`, to `skills-order`) rather than a toy mutation of an already-guarded case: in a
scratch copy (`git archive HEAD | tar -x`, never the real repo), it deleted the `watermark`
entry from each of the 5 sites one at a time and ran the real
`generate-skill-enumerations.py . --check` against each:

| Site | Mutation | Result |
|---|---|---|
| tree | deleted `├─ watermark/` | `FAIL … 'tree' fenced block is not the generated tree` |
| improve-order | dropped `→ watermark` from the arrow chain | `FAIL … 'improve-order' block is not the generated enumeration` |
| table | deleted the `**watermark**` row | `FAIL … 'table' rendered table first column […] does not equal the order […]` |
| pick-list | dropped `· watermark` | `FAIL … 'pick-list' block is not the generated enumeration` |
| attach-table | deleted the `\| watermark \|` row | `FAIL … 'attach-table' rendered table first column […] does not equal the order […]` |

On the unmutated live repo `--check` returns `clean (9 skills; every marked enumeration matches
skills-order …)`, exit 0. `python3 tests/run-golden.py`: **277/277 assertions passed, 0 failed**
(re-run live, independently, by three of the five instruments — A, C, and D — with matching
counts each time).

Lens A also reverted `CANON_ORDER` (in `tests/run-golden.py`) back to the pre-watermark 8-name
list, in a scratch copy: **276/277, 1 failed** — the fixture's own hardcoded banner no longer
matched the live 9-skill repo, confirming the fixture is load-bearing against reality, not merely
self-consistent.

Coverage: 5/5 enumeration sites. Re-confirmed independently by the adjudicator (E) by reading
`PURE_SITES`/`TABLE_SITES`/`ANCHORS` directly rather than trusting Lens A's table, and by
confirming the "near-complete competing run" threshold (`generate-skill-enumerations.py:390`,
`max(2, len(order)-1)`) is dynamically derived from `len(order)` — no second, latent 8→9 gap
hiding behind a hardcoded threshold.

The one actual logic change in the diff (as opposed to fixture-data updates) is
`tests/revert-battery.py`'s `load_order` mutation stub (`fab2a8f`), previously mis-targeted.
Three of the five instruments (A, B/D via git-history trace, and D directly) independently
reproduced both the broken and fixed versions:

- **Fixed stub** (this diff): `275/277`, exactly the two declared fixtures redden
  (`load_order reads skills-order: swapping two order lines… is CAUGHT`,
  `load_order returns skills-order's exact order…`) — no collateral drift.
- **Pre-fix (stale) stub**, reproduced from `268bc80`: `247/277`, **30 unrelated failures** —
  drifting on its own exactly as the diff's commit message claims ("measured: it did, against
  this exact stub, before this fix").

This is a real, reproduced-both-ways confirmation, not a synthetic mutation of an
already-guarded case.

## Coverage vs advertising

Lens B ran all three gates the sibling commit messages cite and checked each claim against real
output:

| Gate | Claimed | Actual (ran it) | Match |
|---|---|---|---|
| `tests/run-golden.py` | 277/277 | `--- golden: 277/277 assertions passed, 0 failed ---` | exact |
| `tests/mutation-runner.py` | 13/13 | `--- mutation runner: 13/13 mutations bite their declared fixtures ---` | exact, but see finding below |
| `tests/revert-battery.py` | 72/72 | structurally confirmed (72-entry `GUARDS` list, AST-parsed; 20-24/72 live `[BITES]` observed across two instruments before host contention forced an early stop) | partial — see Findings |

`release-gate.sh`'s `--check` step (`build-skills.sh --check`, unfiltered — not scoped away from
the new skill) was run directly against `watermark`: `ok watermark — byte-identical (45327
bytes, sha256 269ff303e3f5…)`. No stale-`dist/*.skill` hole — a rebuild-and-byte-compare, not a
trust-the-cache step.

Traced git history to confirm the `load_order` mutant fix is real and correctly targeted, not
cosmetic: at `268bc80` (which added `watermark` to `skills-order` but did **not** touch
`tests/revert-battery.py` — confirmed via `git show 268bc80 --stat`), the mutant was left
hardcoding a stale 8-name order that no longer matched pristine reality. `fab2a8f` fixes exactly
that gap.

The gate's own governance check was run directly rather than assumed: `python3
gate-review-check.py --base a94cd5b --head fab2a8f` returns `BLOCKED — a gate-layer change
requires an independent gate-review. No gate-reviews/ verdict was added/modified in this PR` —
the enforcement layer correctly refusing to let this exact diff merge unreviewed. That is the
mechanism working, not a defect; it is what this verdict file, once committed, resolves.

## Self-description drift

Lens C grepped the **entire repo**, not just the 3 changed files, for stale "8 skill(s)"
mentions, `ORDER8`, and `== 8`/`% 8` literals. Result: no orphaned hardcoded 8-skill count or
enumeration survives outside the two test files this diff already touches. The remaining
"eight skill(s)" prose occurrences (`README.md:55`, `per-skill-review-prompt.md:11/35/123`,
`CONTRIBUTING.md:264`, `docs/adr/0001…:48/83`) are the repo's own explicitly documented,
deliberately-not-gated headline-count residual, ratified in `gate-reviews/0018` — re-verified by
reading that section directly, not assumed, and correctly out of scope for this diff to touch.

`generate-skill-enumerations.py --check` run live: the printed count (`9 skills`) is genuinely
derived from `skills-order`/`skills/` (confirmed by reading `load_order`/`canonical_skills`, not
a second hardcoded copy). The "near-complete" threshold is dynamic (`len(order)-1`), not a
hardcoded `7`.

Two real but inert self-description drifts were found and are carried into Findings below:
`tests/run-golden.py:1569` and `:1574` — comments describing "8 names" / "4 … AND 4" that are
now stale against the fixture's own 9-entry `CANON_ORDER` split (`[:4]` / `[4:]`, the latter now
5 items). Both are comment-only; the code beneath each is correct and covered by the 277/277 pass.

## Fixture requirement

Lens D asked the two questions this lens exists to ask, directly, by execution rather than by
reading the commit message: (1) does the `load_order` stub fix arrive proven, not merely
asserted; (2) is there a new correctness-check in this diff that arrived without its own
regression fixture.

On (1): confirmed via `git show 268bc80:tests/revert-battery.py` that the pre-fix version really
did hardcode the stale 8-skill order, then reproduced both the broken (`247/277`, 30 collateral
failures) and fixed (`275/277`, exactly the two declared fixtures) versions directly against the
live repo. A separate Agent-tool instrument launched in parallel to this workflow (not one of the
four blind lenses, but corroborating) independently reproduced the same result by loading
`tests/revert-battery.py` as a module and calling its own `_run`/`_classify` machinery against
reconstructed stale and pre-swapped mutants — both mis-targeted exactly as the commit describes,
the current fix biting only its declared fixture. Three independent reproductions in total (Lens
A, Lens D, and the corroborating instrument) all agree.

On (2): no. Every change in `tests/run-golden.py` is a data update to pre-existing fixture lists
(`ORDER8`→`CANON_ORDER` rename, `+watermark`); the `tests/revert-battery.py` change fixes an
existing guard's stub data, it does not add a new check; `skills-order` itself is data, not code.
Nothing new is unfixtured. Lens D additionally confirmed the generic "10th skill added without
updating skills-order" class is already covered by existing scratch-directory-built fixtures
(`canonical_skills reads skills/: a new skill dir absent from skills-order is reported (missing)`
and its symmetric "extra" case), so no new fixture is owed by this specific change.

A partial run of the full 72-stub battery (bounded to keep review time reasonable, given a
contended shared host running multiple reviewers' copies of the same suite concurrently) covered
20-24 of 72 stubs live with zero `FAIL`/`CRASH`/`MISS`, corroborating but not fully substituting
for the specific-stub proof above, which is complete.

## Findings

Adjudicated (Lens E) merged, de-duplicated, severity-ranked register. Two items each lens raised
were explicitly downgraded or excluded by the adjudicator with reasoning, not silently kept:

| # | Sev | File:line | Finding | Fix | Raised by |
|---|---|---|---|---|---|
| 1 | MAJOR | `tests/revert-battery.py` (whole file) — not referenced in `release-gate.sh` or `.github/workflows/*.yml` (`grep -rn "revert-battery" release-gate.sh .github/workflows/*.yml` → zero hits, re-confirmed by two instruments) | The 72-stub mutation battery — the deterministic backstop for exactly this class of change (a stale hardcoded order silently drifting) — runs only as a manual, self-reported pre-review step (`CONTRIBUTING.md:129-133`), not as a CI gate. **Pre-existing, not introduced by this diff**, but a gate-layer PR is precisely where its absence from CI matters most, and every reviewer this session hit the same wall (host contention, ~25-30 min full run) trying to spot-check it. | Add a `-k`/`--only <name>` filter to `revert-battery.py` so a gate-layer PR touching one stub can be spot-checked in seconds instead of a full run; separately, consider budgeting CI time to run at least the touched-stub subset automatically on `tests/` diffs. | A, independently reconfirmed by D and E |
| 2 | MINOR | `268bc80` commit message | "Mutation runner: 13/13 bite" is listed alongside the watermark/9-skill work in the same paragraph, but `tests/mutation-runner.py` targets `gate-review-check.py` (verdict-cell/record-checker parsing) — confirmed by reading `tests/mutation-runner.py:10-13,44` and `tests/revert-battery.py:63` (different `GEN`/`CHECKER` targets) — and proves nothing about this diff's enumeration-fixture change. Originally raised as MAJOR by Lens B; downgraded by the adjudicator because it is a one-time historical commit-message phrasing, not a persistent gate self-description a future reader relies on, and it does not change what any gate actually guards or claims about itself going forward. | Future commit messages: don't co-list `mutation-runner` next to enumeration-gate work; name what it actually proves. | B (downgraded MAJOR→MINOR by E) |
| 3 | MINOR | `tests/run-golden.py:1569` | Comment says "all 8 names" — the fixture now iterates `CANON_ORDER` (9 entries). Comment-only, inert; verified verbatim at this exact line by both C and E. | `all 8 names` → `all 9 names` | C, verified by E |
| 4 | MINOR | `tests/run-golden.py:1574` | Comment says "4 in a paragraph AND 4 in an indented code block" — code below is `CANON_ORDER[:4]` (4) and `CANON_ORDER[4:]` (now 5, since `len(CANON_ORDER)==9`). Comment-only, inert; verified verbatim at this exact line by both C and E. | `4 in an indented code block` → `5 in an indented code block` | C, verified by E |
| 5 | NIT | `tests/run-golden.py:1453-1454` | `CANON_ORDER = [...]` continuation line is no longer bracket-aligned after the rename from the shorter `ORDER8` name. No lint config exists in the repo (`pyproject.toml`/`.flake8`/`setup.cfg` — none present) that would catch this; `ast.parse` confirms the file is syntactically fine. | Realign continuation indent (cosmetic). | missed by all four lenses, found by E |

Excluded from the register, with reasoning: the "`gate-review-check.py` reports BLOCKED" /
"PR #26 `mergeStateStatus: BLOCKED`" observation, raised independently by all four lenses, is
**not a finding** — it is the expected, correct state of an unreviewed gate-layer PR, and is what
committing this file resolves. Also excluded: README.md's "a suite of eight independent Claude
skills" and its 3 sibling occurrences — a documented, deliberately-not-gated scope boundary
(`gate-reviews/0018`), re-litigating a settled decision, not a new gap.

No BLOCKER found anywhere in the diff by any of the five instruments. All 5 enumeration sites
correctly cover the new skill (measured, not assumed), the one logic-bearing change
(`load_order`'s mutation stub) is correctly targeted and independently reproduced to bite exactly
as declared by three separate instruments, and there is no leftover 8-skill literal anywhere in
either changed file (`grep -n "ORDER8"` and `grep -n "% 8\b"`, repo-wide: zero hits, confirmed by
three instruments independently).

---

Verdict: PASS
