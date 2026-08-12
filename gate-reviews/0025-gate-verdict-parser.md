# Gate-review verdict — PR "fix(gate): make the verdict-line parser fail closed"

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: `fix/gate-verdict-parser` (stacked on `fix/verdict-cell-closed-set-minimal`)
- Diff range: `fix/verdict-cell-closed-set-minimal..fix/gate-verdict-parser`
- Gate-layer paths changed: `gate-review-check.py`, `tests/mutation-runner.py`, `tests/run-golden.py`
- Reviewers / instruments: three rounds against an earlier, combined version of this work — one
  independent different-vendor cold pass, then two rounds of six blind fresh-context lenses each with a
  per-finding adversarial adjudicator (round 2: 38 candidates, 32 survived; round 3: 33 candidates, 26
  survived). A round against THIS diff at THIS scope is owed.
- Independence limit honestly stated: **context isolation only, never weight decorrelation** — the lenses
  are fresh contexts of the same model that wrote the change. Different-vendor review has been retired on
  this repository, so this is the permanent ceiling and every future record should keep saying so.

## Record convention

One record per work package, updated in place across rounds; `Round N carries ID 0024+N` for this record.

| # | head | verdict | blocking finding | resolution |
|---|---|---|---|---|
| 1 | 003694e | BLOCK | Anchoring the strict token INTO `VERDICT_LINE_RE` did not make an annotated verdict line fatal — it made it INVISIBLE, and `effective_verdict`'s last-MATCHED-line rule then fell back to an EARLIER line. A record ending `Verdict: BLOCK (2 blockers outstanding)` after an earlier `Verdict: PASS` CLEARED the required status check. | the line found LOOSELY and the token judged STRICTLY, so a malformed line is seen and rejected |
| 2 | 6c41a4b | BLOCK | Narrowing the leading class from `\s*` to `[ \t]*` made an NBSP-indented `Verdict: BLOCK` invisible — a REGRESSION against `main`, which saw it and blocked. Twelve Unicode space characters were affected. Six further spellings (`**Verdict: BLOCK**`, `**Verdict:** BLOCK`, `+`/`-` bullets, `## heading`, `> blockquote`, `1.` ordered) cleared on BOTH trees. A trailing `<!-- ... Verdict: PASS ... -->` became the last matched line over a visible BLOCK. An ANNOTATED blocking record collapsed to an unreadable verdict and, since `decide_verdicts` gated only on the literal BLOCK/FAIL, a SIBLING clean-PASS record cleared the gate on its behalf. | finding a declaration made deliberately OVER-INCLUSIVE; HTML comments stripped before reading; a record that is not a clean PASS now GATES |
| 3 | 3432168 | pass | Independent round run 2026-08-12, different-vendor. **No blocking finding against this diff's scope.** Three residuals recorded, each narrower than the five live bypasses this PR closes | residuals carried, not fixed here |

## Replay the real failure

The required status check decides whether a gate-layer change may merge. It reads the LAST verdict
declaration in each record, so a `PASS` quoted in prose cannot satisfy a record whose conclusion is BLOCK.

Coverage: 3/3 verdict-to-decision sites

*(That fraction sits here, above the sample block, deliberately. `gate-review-check.py`'s `_section_text`
matches `^#{1,2}\s` without tracking code fences, so the `## Verdict: BLOCK` sample below — which is
inside a fence and is not a heading to any reader — truncates this section and hides anything after it.
Recorded as RESIDUAL-7. Until that is fixed, a line that only a fence-aware parser would skip must not
sit above the required fraction.)*

**The real failure, reproduced on `main`.** A line the matcher cannot SEE is silently skipped, and the
last-line rule then falls back to an earlier, friendlier line. On `main` today, with a bare
`Verdict: PASS` anywhere earlier in the record, every one of these final lines is invisible and the gate
CLEARS:

```
**Verdict: BLOCK**      **Verdict:** BLOCK      + Verdict: BLOCK
## Verdict: BLOCK       > Verdict: BLOCK        1. Verdict: BLOCK
```

Three successive attempts to fix the token grammar each widened this, because each made the matcher
stricter and therefore blinder — including one that regressed `main` for twelve Unicode space characters.

**Population and coverage.** The unit is "a place where a verdict is turned into a gate decision":

| Site | Now |
|---|---|
| `gate-review-check.py` `effective_verdict` | loose find, strict token, comments stripped |
| `gate-review-check.py` `decide_verdicts` | a record that is not a clean PASS gates the PR |
| `tests/run-golden.py` `_record_problems` final-verdict | CALLS `effective_verdict` — no re-implementation |

## Coverage vs advertising

The design is now what enforces the property, not the pattern's cleverness. The two jobs point in
opposite directions: **finding** a declaration is deliberately over-inclusive, because an extra line can
only ever become the authoritative one and then fail the token test — it can only cause a BLOCK, never a
fallback to an earlier PASS. **Judging** the token stays exact.

An earlier version of this change asserted that the suite's parser used "the same grammar the required
check uses, so the two cannot disagree". That was false: a re-implementation is precisely a thing that can
disagree, and it did, twice. The suite now calls the required check's parser, so parity is structural.

`decide_verdicts`' docstring has always promised "a malformed record blocks". Until now it did not — a
record whose verdict was unreadable merely failed to join `passing`, so a sibling clean PASS cleared the
gate on its behalf. The sentence is now true.

**What this change does NOT do:** it does not normalise Unicode confusables in the verdict token; it does
not validate record CONTENT beyond the round table, the closure prose and the final verdict; and
`gate-reviews/TEMPLATE.md` still produces no round-history table, so a record copied from it is not
covered by the generic sweep until a table is added by hand.

## Self-description drift

The change alters no count or list of checks, lints, steps, skills or paths. `CONTRIBUTING.md:197` is
untouched, and `CONTRIBUTING.md` is absent from this PR's changed-file list.

Two documents still describe the older, looser verdict-line expectations and are NOT updated here:
`gate-review-prompt.md` and `gate-reviews/TEMPLATE.md`. `CONTRIBUTING.md` requirement (ii) also still names
only `tests/revert-battery.py` as the bite-prover and does not mention `tests/mutation-runner.py`. Editing
any of them changes what every future reviewer is instructed to do, which is a governance change that
deserves its own round rather than a rider here. Recorded as MINOR-4.

## Fixture requirement

Ten decoration spellings, both across-record cases, the comment mirror and the annotated-BLOCK fallback are
fixtured, and every guard is proven to bite by `tests/mutation-runner.py`:

```
--- mutation runner: 13/13 mutations bite their declared fixtures ---
```

The runner failed on the author's own work four times rather than passing quietly: a dead-code guard that
was deletable with the suite still green; two mutations whose declared fixture names were wrong (reported
MIS-TARGETED, not counted as bites); a mutation too coarse to isolate its target; and — most usefully — the
first mirror-hole regression test, which it caught as GREEN, proving that fixture exercised the in-suite
twin and never touched the required check it was written for.

A `revert-battery.py` GUARDS entry remains unrepresentable for these checks (the battery patches only
`dst / GEN`), which is why the runner exists. **`run-golden.py`'s own checks sit outside the battery's
mutation-proven denominator entirely**, and the battery's `72/72` covers the generator, not this checker.

## Findings

- **BLOCKER-1 — an independent round of THIS scope is owed.** Rounds 1 and 2 examined this code inside a
  wider change. `PASS` may not be written until a blind round runs against this diff.
  **RESOLVED 2026-08-12 — the round has run and returned.** A genuine different-vendor cold pass (Codex,
  read-only) plus a fresh-context execution lens plus direct execution of `effective_verdict` from both
  `origin/main` and this tip. See "Round 3" below.

### Round 3 residuals — recorded, not fixed here

- **RESIDUAL-4 — two annotation holes survive this fix.** Executed against this tip,
  `tests/run-golden.py:700`'s `[^()\n]*` lets both through:
  `PASS (&lpar;BLOCK&rpar;)` → **`pass`**, though it renders to a reader as `PASS ((BLOCK))`, bypassing
  the advertised no-nesting rule through HTML entities; and `PASS (x\u2028BLOCK)` → **`pass`**, because
  U+2028 is a Unicode line separator and is not `\n`, so the "annotations are single-line" claim does not
  hold. Both mean a cell a human reads as BLOCK classifies as PASS — narrower than the five bypasses this
  PR closes, but the same failure class, and each wants a mutant.
- **RESIDUAL-5 — `tests/run-golden.py:695` redefines a round-1 finding rather than fixing it.**
  `[BLOCK](url)` was identified in round 1 as a real rejection defect; it is now declared deliberate.
  That sits inconsistently beside the Markdown wrappers that *are* accepted (`**BLOCK**`, `~~BLOCK~~`
  are rejected while bolded verdict *lines* are now seen). Defensible, but it is a scope decision that
  should be stated as one.
- **RESIDUAL-7 — `gate-review-check.py:264` `_section_text` is fence-blind.** It splits sections on
  `^#{1,2}\s` with no code-fence tracking, so a fenced sample line beginning `##` — exactly what this
  record contains at its replay section, showing the bypass spellings — silently truncates the section
  and hides the `Coverage: N/M` line beneath it. **Found by this round, by execution:** the record was
  well-formed to a reader and malformed to the checker, and the old `BLOCK` verdict short-circuited the
  check before it could surface. Worked around here by moving the fraction above the fence; the real fix
  is fence-aware section splitting, which is a gate-layer change needing its own review.
- **RESIDUAL-6 — the HTML-comment arm is only half closed.** `gate-review-check.py` strips comments
  before reading, which fixes the documented failure, but a commented `Verdict: PASS` as the sole
  declaration still yields `PASS` rather than an unreadable-record error.
- **MAJOR-2 — unproven guards.** Several behaviours survive a no-op revert against the committed test
  apparatus, among them the non-nesting class and the back-reference inside the cell grammar, and the
  BLOCK-state non-pending arm. They are covered by the accept/reject table but not isolated by a mutation
  of their own.
- **MAJOR-3 — `_ROUND_HEADER_RE` is byte-exact.** A future record whose round table is headed slightly
  differently is silently skipped by the sweep rather than reported. The `swept >= 2` floor stops that
  degrading to zero today, but a floor is a count, not a guarantee about WHICH records are covered.
- **MINOR-4 — governance docs not updated** (`gate-review-prompt.md`, `gate-reviews/TEMPLATE.md`,
  `CONTRIBUTING.md` requirement (ii)), as described above.
- **MINOR-5 — `TEMPLATE.md` produces no round-history table**, so a record created from it escapes the
  generic sweep.

---

## Round 3 — the independent round, returned 2026-08-12

The independent review (round 3) returned PASS.

Rounds 1 and 2 returned BLOCK, including one finding that was a regression this work introduced against
`main`. Both are reproduced and fixed above. This round examined the diff at the scope shipped here.

**Instruments, and the independence limit.** A **different-vendor cold pass** (Codex,
`codex exec --sandbox read-only`) — genuine weight decorrelation — plus a fresh-context execution lens
that ran every gate on every branch, plus direct execution of `effective_verdict` imported from both
`origin/main` and this tip. **The line above saying different-vendor review "has been retired on this
repository" did not hold for this round and should be revisited:** the different-vendor lens found every
residual recorded in Findings, and the same-family lenses found none of them.

**What this PR actually fixes, executed rather than asserted.** With an earlier bare `Verdict: PASS`,
against `effective_verdict` from `origin/main` versus this tip:

| final line in the record | `main` today | this branch |
|---|---|---|
| `Verdict: BLOCK` (control) | `BLOCK` | `BLOCK` |
| `**Verdict: BLOCK**` | **`PASS`** | `BLOCK` |
| `**Verdict:** BLOCK` | **`PASS`** | `BLOCK` |
| `## Verdict: BLOCK` | **`PASS`** | `BLOCK` |
| `> Verdict: BLOCK` | **`PASS`** | `BLOCK` |
| `1. Verdict: BLOCK` | **`PASS`** | `BLOCK` |

**Five live bypasses in the gate that guards every merge.** Bolding a word makes a BLOCK verdict
invisible and clears the check. All five close here.

| | `run-golden` | `mutation-runner` | `release-gate.sh` |
|---|---|---|---|
| `main` | 218/218 | *(absent)* | pass |
| `#17` | 243/243 | 5/5 bite | pass |
| this branch | **277/277** | **13/13 bite** | pass |

Assertion-name check: this branch renames 16 of `#17`'s names (splitting "unrecognised" from
"unconsumed-suffix") and adds one case. No coverage lost.

### Why this is PASS and not BLOCK

Every residual in Findings is **narrower than what this change fixes**. RESIDUAL-4's two holes require a
deliberately crafted HTML entity or a U+2028; the five bypasses this closes require pressing `**`.
Holding the repair would leave the worse state standing, which is what the two-round cap and "ship with
the leftovers written down" exist to prevent. The residuals are carried, not dropped.

Verdict: PASS
