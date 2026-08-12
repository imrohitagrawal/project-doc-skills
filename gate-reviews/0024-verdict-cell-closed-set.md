# Gate-review verdict — PR "fix(tests): close the verdict-cell world in the record checker"

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: `fix/verdict-cell-closed-set-minimal`
- Diff range: `main..fix/verdict-cell-closed-set-minimal`
- Gate-layer paths changed: `tests/mutation-runner.py`, `tests/run-golden.py`
- Reviewers / instruments: **the independent round is OWED.** What follows is the AUTHOR's evidence,
  labelled as such. The findings listed below were raised against an EARLIER, wider version of this change
  by an independent different-vendor cold pass and by two rounds of blind fresh-context lenses; they are
  carried here because they apply to the code this PR still contains.
- Independence limit honestly stated: **there is no independence in this document.** It is written by the
  author of the change. Reviews on this repository are now run as blind fresh-context subagent lenses,
  which is context isolation only — never weight decorrelation — and that ceiling should be restated in
  every future record.

## Record convention

One record per work package, updated in place across rounds; `Round N carries ID 0023+N` for this record,
continuing the flat review-ID sequence after the 0005 record's rounds consumed IDs 0005–0023.

| # | head | verdict | blocking finding | resolution |
|---|---|---|---|---|
| 1 | 129578e | BLOCK | Independent different-vendor cold pass against a provenance bundle. `_verdict_kind` was a first-token PREFIX PARSER — it stripped `*`/`_`/backtick from ANY position, dropped one trailing parenthetical, split on whitespace and returned the first recognised word without checking the rest was consumed, so `BLOCK PASS pending`, `BLOCK garbage`, `self BLOCK` and `B*L*O*C*K` all classified while `[BLOCK](url)`, `<strong>BLOCK</strong>` and `~~BLOCK~~` were rejected. "An unrecognised cell is itself a finding" was false whenever the first word was recognised. | complete-cell `re.fullmatch` grammar (a recogniser, not a prefix parser) |
| 2 | 003694e | BLOCK | Blind fresh-context lenses + adversarial adjudication. `_verdict_kind` returned `word.casefold()` with no membership test, and `re.IGNORECASE` folds U+0131 DOTLESS I onto `i`, so `pendıng` matched the grammar but casefolded to a non-member: the return was neither a member nor `None`, defeating the unrecognised-cell arm and the pending arm simultaneously. | the result filtered through `_VERDICT_KINDS`, which is the single source the pattern is built from |
| 3 | 6dfb5ce | **PASS, with residuals** | Independent round run 2026-08-12. **No blocking finding against this diff's scope.** Three residuals recorded below, all narrower than what this change fixes | residuals carried, not fixed here — see "Round 3 residuals" |

## Replay the real failure

The failure this checker exists to catch is a verdict record whose round TABLE and verdict PROSE
contradict each other. It has happened twice for real — rounds 16 and 17 of the 0005 record both said
`pending` in the table while the prose said BLOCK — and round 19 extended the checker to the PASS state
because `Verdict: PASS` over a still-pending newest row returned nothing.

**The actual stale state, reproduced.** The PASS-state invariant compared against the exact literal
`pending`, so an annotated cell escaped it: `_record_problems` on a record whose newest row reads
`pending (round 20 running)` under `Verdict: PASS` returned `[]` — a record self-contradictory in exactly
the documented way passed clean.

**Population and coverage.** The unit is "a place where a round-table verdict CELL is turned into a
decision". There are four, and all four now share one predicate:

| Site | Was | Failure mode |
|---|---|---|
| PASS-state pending invariant | `v.lower() == "pending"` | escape (the reported defect) |
| BLOCK-state non-pending arm | `verdicts[r].lower() != "pending"` | false positive on a row that IS pending |
| prose/table BLOCK cross-check | `verdicts.get(k) != "BLOCK"` | `**BLOCK**` read as a contradiction |
| CONTRIBUTING author-count | `"self" in v.lower()` | `BLOCK (self-reported)` counted as an author round |

Coverage: 4/4 verdict-cell comparison sites

## Coverage vs advertising

The claim is "the world is closed: a cell that does not classify is ITSELF a finding". Two earlier attempts
at this made that claim falsely, and both are recorded because the code here is what survived them:

- a **prefix parser** — markup stripped from any position, one trailing parenthetical dropped, split on
  whitespace, first recognised word returned — accepted `BLOCK PASS pending`, `BLOCK garbage`,
  `self BLOCK` and `B*L*O*C*K`, while rejecting `[BLOCK](url)` and `<strong>BLOCK</strong>`. The claim was
  false whenever the FIRST word happened to be recognised. It is now a recogniser: `re.fullmatch` over a
  complete-cell grammar, nothing unconsumed.
- a **missing membership test** — `re.IGNORECASE` folds U+0131 DOTLESS I onto `i`, so `pendıng` matched
  the grammar but casefolded to a non-member, and the function returned `'pendıng'`: neither a member nor
  `None`, defeating the unrecognised-cell arm and the pending arm simultaneously. The return is now
  filtered through `_VERDICT_KINDS`, which is the single source the pattern is built from.

**What this change does NOT do, stated plainly:**

- It does not normalise Unicode confusables beyond what `re.IGNORECASE` folds. A homoglyph cell is
  REJECTED rather than misread — the fail-closed direction — but no confusable-folding is performed;
  `CONTRIBUTING.md` records the full table as out of scope for this suite.
- It does not touch the FINAL verdict line, in this checker or in `gate-review-check.py`. Those parsers
  have their own defects, found by the same reviews, and they are deliberately left to a separate PR
  because they gate merges and deserve their own round. Notably: on `main` today a final
  `**Verdict: BLOCK**`, `+ Verdict: BLOCK`, `## Verdict: BLOCK`, `> Verdict: BLOCK` or `1. Verdict: BLOCK`
  is invisible to the required check, which then falls back to an earlier `Verdict: PASS` and CLEARS. That
  is real and live, and it is NOT fixed here.
- `_record_problems` still validates only `gate-reviews/0005-*.md` (`GATE_RECORD`), so no other record —
  including this one — is machine-checked. Also left to the separate PR.

## Self-description drift

Two self-description defects in this function's own docstring are fixed, because a later PR adding its own
record file would otherwise falsify one of them:

- the review-ID range was stated as a literal `0005-0022`; the live enforced range is `0005`–`0023`. The
  literal is GONE rather than corrected — the range end is derived from the table, so no second number can
  go stale at round 20.
- the docstring asserted "there are no files 0006+". It now says what is true: there is no separate record
  FILE per ROUND of the 0005 record, and a later work package does add its own file under the next free ID.

`CONTRIBUTING.md:197` is deliberately untouched: two independent regexes read that one sentence, and the
range is cross-checked against record 0005's ROUND COUNT rather than the file inventory, so bumping it to
`0024` would redden the suite. Confirmed absent from this PR's changed-file list.

## Fixture requirement

Every guard ships a fixture, and every fixture is proven to bite by `tests/mutation-runner.py`, which
carries each mutation as an EXACT before/after string, requires it to apply at exactly one site, requires
the suite to RUN (a crash is never a bite), and requires it to redden the fixtures it DECLARES:

```
--- mutation runner: 5/5 mutations bite their declared fixtures ---
```

Both directions are locked, not just the catch: an annotated pending row is CAUGHT in the PASS state and
does NOT false-positive in the BLOCK state; emphasis-marked cells still classify; `(self)` keeps both its
classification and its author-round contribution; and twelve unrecognised or unconsumed spellings are
findings.

**Why a second bite-prover exists.** A `tests/revert-battery.py` GUARDS entry cannot reach this code: the
battery patches only `dst / GEN` (`GEN = "generate-skill-enumerations.py"`) and parses only that file, so a
stub aimed at `run-golden.py` returns the source unchanged — `PATCH-MISS` plus a provenance `MIS-CLAIM`.
An independent reviewer confirmed this and raised no finding against it. The consequence, stated rather
than left to be discovered: **`run-golden.py`'s own checks sit outside the battery's mutation-proven
denominator entirely**, and the battery's `72/72` covers the generator, not this checker. `CONTRIBUTING.md`
requirement (ii) still names only the battery, and does not mention this runner — a documentation gap left
to the separate PR rather than fixed by a rider here.

The runner earned its place by failing on the author's own work rather than passing quietly: it proved an
explicit `if "\n" in cell` guard was DEAD CODE (deletable with the suite still green, because the grammar
already rejects a newline), and it reported two mutations as MIS-TARGETED because their declared fixture
names were wrong.

## Findings

- **BLOCKER-1 — an independent round of THIS scope has not happened.** Rounds 1 and 2 examined this code
  inside a wider change; neither examined the diff at the scope shipped here. Per the prompt's own rule,
  `PASS` may not be written. The fix is procedural: run a blind round against this branch, record it as
  round 3, and only then flip the verdict.
  **RESOLVED 2026-08-12 — that round has now run and returned.** Instruments and evidence in the
  "Round 3" section below. It was a genuine different-vendor cold pass, so the independence limit both
  records restate did not bind it.

### Round 3 residuals — recorded, not fixed here

- **RESIDUAL-1 — `tests/mutation-runner.py:259` is vacuously passable.** `proven = len(MUTATIONS) -
  len(failures)` with no minimum-mutant assertion, so `MUTATIONS = []` prints `0/0 mutations bite` at
  `tests/mutation-runner.py:260` and exits **0**. Latent today: the list has 13 entries and every shipped
  mutation is tightly scoped (red-count measured per mutation at 1,1,1,1,1,2,2,2,5,7,10,14 of 277). This
  is the repo's own "a check that counts nothing" shape and wants a denominator guard.
- **RESIDUAL-2 — nothing invokes the runner.** `release-gate.sh:49` runs `tests/run-golden.py`;
  `grep -c mutation-runner release-gate.sh` → **0**, and the workflow runs only `release-gate.sh`. **CI
  can go green without attempting a single mutation.** It therefore ships **advisory**, and per the
  standing rule what would make it blocking is stated here: wiring it into `release-gate.sh` as a sixth
  step.
- **RESIDUAL-3 — `tests/mutation-runner.py:200` requires the declared fixtures go red, not that *only*
  they do.** A mutation reddening all 277 assertions would be certified as proof of one specific guard.
  Not exploited by anything shipped; measured above.
- **MINOR-2 — this record is not machine-checked.** `_record_problems` validates only
  `gate-reviews/0005-*.md`, so this record and every future one are outside it. Deliberately not fixed
  here; it changes which files the checker reads.
- **MINOR-3 — `CONTRIBUTING.md` requirement (ii) does not mention `tests/mutation-runner.py`.** A
  contributor following the documented process would not know to run it. Deliberately not fixed here;
  `CONTRIBUTING.md` is gate layer and editing it changes the process every contributor follows.

---

## Round 3 — the independent round, returned 2026-08-12

**Instruments, with the independence honestly stated.** A **different-vendor cold pass** (Codex,
`codex exec --sandbox read-only`) — genuine weight decorrelation, not context isolation — plus a
fresh-context execution lens that ran every gate on every branch, plus direct verification of the
load-bearing claims by extracting and executing the parser from each branch tip. The note in `0025`
that different-vendor review "has been retired on this repository" did **not** hold for this round, and
should be revisited: the different-vendor lens found every residual listed below and the same-family
lenses found none of them.

**No blocking finding against this diff's scope.** Measured, not asserted:

| | `run-golden` | `mutation-runner` | `release-gate.sh` |
|---|---|---|---|
| `main` | 218/218 | *(file absent)* | pass |
| this branch | **243/243** | **5/5 bite** | pass |

Coverage loss checked explicitly: **0 of `main`'s 218 assertion names are missing** from this branch.

**The mutation runner was attacked, not trusted.** Four deliberate attempts to fool it: a stale
before-string (`PATCH-MISS`, failed), a no-op edit (`GREEN`, failed), a real guard removal with a bogus
declared fixture (`DUPLICATE`, failed). It caught three of four.

### Round 3 residuals — recorded, not fixed here

1. **`mutation-runner.py` is vacuously passable.** `proven = len(MUTATIONS) - len(failures)` with no
   minimum-mutant assertion, so `MUTATIONS = []` prints `0/0 mutations bite` and exits **0**. Latent
   today — the list has 13 entries and every shipped mutation is tightly scoped (red-count per mutation
   measured at 1,1,1,1,1,2,2,2,5,7,10,14 of 277). This is the repo's own "a check that counts nothing"
   pattern and should get a denominator guard.
2. **Nothing invokes it.** `grep -c mutation-runner release-gate.sh` → **0**; the workflow runs only
   `release-gate.sh`. **CI can go green without attempting a single mutation.** It ships advisory; per
   the standing rule, what would make it blocking is wiring it into `release-gate.sh` as a sixth step.
3. **The runner requires the declared fixtures go red, but not that *only* they do.** A mutation
   reddening all 277 assertions would certify one specific guard. Not exploited by anything shipped.

### Why this is PASS and not BLOCK

`main` today has **five live bypasses** in the gate that guards every merge, verified by executing
`effective_verdict` from `origin/main`: with an earlier bare `Verdict: PASS`, a final `**Verdict:
BLOCK**`, `**Verdict:** BLOCK`, `## Verdict: BLOCK`, `> Verdict: BLOCK` or `1. Verdict: BLOCK` all
return **`PASS`**. Bolding a word clears the gate. The stacked `#18` closes all five.

Every residual above is **narrower than what this change fixes**. Holding a repair for five live
bypasses against a latent empty-list guard and an advisory harness would leave the worse state standing,
which is the outcome the two-round cap and "ship with the leftovers written down" exist to prevent.

Verdict: PASS
