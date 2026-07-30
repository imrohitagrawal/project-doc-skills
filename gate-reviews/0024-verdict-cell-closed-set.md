# Gate-review verdict — PR "fix(tests): close the verdict-cell world in the record checker"

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: `fix/verdict-cell-closed-set`
- Diff range: `main..fix/verdict-cell-closed-set`
- Gate-layer paths changed: `tests/run-golden.py`, `gate-review-check.py`   (the list
  `gate-review-check.py` printed)
- Reviewers / instruments: round 1 — an independent different-vendor (GPT) cold pass, code-grounded
  against a provenance bundle (HEAD sha + per-file sha256 + verbatim source). Round 2 — independent
  fresh-context subagent lenses; the owner ended different-vendor reviews after round 1.
- Independence limit honestly stated: round 1 was weight-decorrelated but had no repository checkout
  beyond the bundled files, so it could not run the full suite (it said so, and did not claim the
  author's 229/229). Round 2 is **context isolation only, not weight decorrelation** — the lenses are
  fresh contexts of the same model that wrote the change, which is a real and stated limit.

## Record convention

One record per work package, updated in place across rounds; `Round N carries ID 0023+N` for this
record (round 1 = ID 0024), continuing the flat review-ID sequence after the 0005 record's rounds
consumed IDs 0005–0023.

| # | head | verdict | blocking finding | resolution |
|---|---|---|---|---|
| 1 | 129578e | BLOCK | Independent GPT cold pass. **B1:** `_verdict_kind` was a first-token PREFIX PARSER, not a recogniser — it deleted `*`/`_`/backtick from ANY position, dropped one trailing parenthetical, split on whitespace and returned `head[0]` without checking the rest was consumed, so `BLOCK PASS pending`, `BLOCK garbage`, `self BLOCK`, `BLOCK <!-- pending -->` and `B*L*O*C*K` all classified while ordinary `[BLOCK](url)`/`<strong>BLOCK</strong>`/`~~BLOCK~~` were rejected; the "unrecognised cell is itself a finding" claim was false whenever the first word was recognised, and a live-shaped record carrying `BLOCK PASS pending` passed clean. **B2:** `gate-review-check.py:96`'s `VERDICT_LINE_RE` was not end-anchored, so the REQUIRED status check cleared a record whose final line read `Verdict: PASS pending` — a direct gate bypass. **B3:** the PASS arm treated both closure sentinels identically, so `review (round N) returned PASS` was accepted over a table row N saying BLOCK. **M4:** `GATE_RECORD` was hardcoded to the 0005 record, which policy declares append-only — the strengthened invariants applied only to the record least likely to change. **m5:** revert F published a 12-failure count without recording the exact mutation. | complete-cell `re.fullmatch` grammar (recogniser, not prefix parser); `VERDICT_LINE_RE` and the in-suite final-verdict parser both matched WHOLE against `PASS\|BLOCK\|FAIL`; the two PASS closure sentinels split and checked differently; `_record_problems` generalised over every record with a round table, found by its canonical HEADER; a committed, target-aware mutation runner replacing the hand-run reverts |
| 2 | pending | pending | pending | pending |

## Replay the real failure

The failure this checker exists to catch is a record whose round TABLE and verdict PROSE contradict each
other. It has already happened twice (rounds 16 and 17 both said `pending` in the table while the prose
said BLOCK), which is why `_record_problems` exists at all. Round 19 then extended it to the PASS state,
because `Verdict: PASS` over a still-pending newest row returned no problems — the one edit the checker
exists to protect.

**The actual stale state, reproduced.** The PASS-state invariant compared against the exact literal
`pending`:

```python
pend = [r for r, v in verdicts.items() if v.lower() == "pending"]
```

So an ANNOTATED cell escapes. Feeding `_record_problems` a record whose newest row reads
`pending (round 20 running)` under `Verdict: PASS` returns `[]` — no findings. A record that is
self-contradictory in exactly the documented way passes clean.

The same narrowness existed in the OPPOSITE sign, one arm down: `verdicts[r].lower() != "pending"` made
the BLOCK-state "a non-pending row follows it" check FIRE on a row that is in fact pending — a false
positive on the same edit. And two further cell comparisons had the identical defect:
`verdicts.get(k) != "BLOCK"` (so `**BLOCK**` reads as a contradiction) and `"self" in v.lower()` (so
`BLOCK (self-reported)` was counted as an author round while the prose arm simultaneously refused it).

**Census of every site where a verdict CELL is compared**, before and after:

| Line (after) | Site | Was | Now |
|---|---|---|---|
| 673 | PASS-state pending invariant | `v.lower() == "pending"` | `_verdict_kind(v) == "pending"` |
| 718 | BLOCK-state non-pending arm | `verdicts[r].lower() != "pending"` | `_verdict_kind(...) != "pending"` |
| 716 | prose/table cross-check | `verdicts.get(k) != "BLOCK"` | `_verdict_kind(...) != "block"` |
| 728 | CONTRIBUTING author-count | `"self" in v.lower()` | `_verdict_kind(v) == "self"` |

Coverage: 4/4 verdict-cell comparison sites

No site is left comparing a raw cell against a literal
(`grep -nE 'verdicts.*(==|!=)\s*"'` returns only the four normalised forms above). The fix is one shared
predicate rather than four edits, so the arms cannot drift apart again — which is how the two signs came
to disagree in the first place.

**Why a closed set rather than a wider match.** Loosening to `startswith("pending")` fixes the reported
instance and leaves the class open: the next unrecognised spelling escapes exactly as this one did, and
rounds 16, 17 and 18 each repeated a variant of "a spelling nobody thought of slipped past". So an
unrecognised cell is now ITSELF a finding (`_VERDICT_KINDS = {block, pass, pending, self}`), which fails
closed. The live record's cells were enumerated first to be sure the set accepts every value that
legitimately appears: `BLOCK` ×18 and `(self)` ×1, final `Verdict: PASS` — both classify, and the
author-round count stays 1, so CONTRIBUTING's `19 / 18 / 1` cross-check is unchanged.

`(self)` is the trap in the normaliser: a naive "strip anything in parentheses" maps it to the empty
string and would break both its classification and the live count. So a WHOLLY-parenthesised cell keeps
its content, and only a TRAILING annotation is dropped.

## Coverage vs advertising

The docstring claimed the suite reddens on "more than one pending row, a pending row that is not the
newest round" and, in the PASS state, "no pending rows anywhere". With the literal comparison those
sentences were true only for the unannotated spelling — the docstring described a stronger check than the
code implemented. That gap is what this change closes; the docstring now matches, and the new
unrecognised-cell finding is stated in the code comment at `_VERDICT_KINDS`.

Nothing in this change adds a new success/clean/PASS message, so there is no new way for the suite to
print agreement over a stale reality. The one status string touched is the problem list itself, which
grows a case rather than losing one.

**Self-check on this section's own honesty:** the change does NOT make the record checker complete. It
still validates only `gate-reviews/0005-*.md` (`GATE_RECORD`, `tests/run-golden.py:75`); no other record
file, including THIS one, is machine-checked for table/prose consistency. That was true before and stays
true. See Findings MINOR-2.

## Self-description drift

This change alters no count or list of checks, lints, steps, skills or paths. It adds one helper and one
finding to an existing function.

Two self-description defects in the SAME function were fixed in the same edit, because adding a record
file would otherwise have falsified one of them:

- `tests/run-golden.py:625` stated the review-ID range as a literal `0005-0022`. The live documented and
  enforced range is `0005`–`0023` (CONTRIBUTING.md:197; 19 rounds, round N carries ID 0004+N). The literal
  is now GONE rather than corrected: the range end is derived from the table at `:746-748`, so there is no
  second number to go stale at round 20.
- `tests/run-golden.py:627-628` asserted "there are no files 0006+". Adding
  `gate-reviews/0024-verdict-cell-closed-set.md` makes that false, so shipping it unchanged would have
  introduced fresh self-description drift inside the very function whose job is catching it. The sentence
  now says what is actually true: there is no separate record file per ROUND of the 0005 record, and a
  later work package does add its own file under the next free ID.

`CONTRIBUTING.md:197` is deliberately NOT touched. Two independent regexes read that one sentence
(`:744` for the `19 / 18 / 1` digit triple, `:746` for the en-dashed `` `0005`–`00NN` `` range), and the
range is cross-checked against the ROUND COUNT inside record 0005, not against the file inventory — so
bumping it to `0024` would redden the suite with "CONTRIBUTING's review-ID range ends at 0024 but the
record has 19 rounds". Verified: `CONTRIBUTING.md` is absent from this PR's changed-file list.

Grep for hard-coded counts in the changed file found none introduced; the new self-tests carry no
suite-wide totals.

## Fixture requirement

Every arm ships a fixture, and each was proven to redden by reverting that arm ALONE on a scratch copy of
the branch and requiring an assertion FAILURE (never a crash) in its DECLARED fixture:

```
A: pending arm back to the exact literal            -> 228/229, 1 failed
     [FAIL] checker: PASS over an ANNOTATED pending newest row is CAUGHT (0024; the literal escaped)
B: BLOCK-state non-pending arm back to the literal  -> 228/229, 1 failed
     [FAIL] checker: an ANNOTATED pending row does NOT false-positive the BLOCK-state arm (0024)
C: prose cross-check back to the raw == BLOCK       -> 226/229, 3 failed
     [FAIL] ... a bold-marked BLOCK cell still classifies as BLOCK (0024)
     [FAIL] ... a code-span-marked BLOCK cell still classifies as BLOCK (0024)
     [FAIL] ... an annotated `BLOCK (self-...)` counts as an INDEPENDENT round (0024)
D: drop the unrecognised-cell finding entirely      -> 225/229, 4 failed
     [FAIL] ... an unrecognised verdict cell 'blocked' / 'PASS-ish' / 'n/a' / '-' is CAUGHT (fail closed)
E: author-count arm back to the substring self      -> 228/229, 1 failed
     [FAIL] ... an annotated `BLOCK (self-...)` counts as an INDEPENDENT round, not an author one
F: _verdict_kind returns its input unnormalised     -> 217/229, 12 failed
```

Both DIRECTIONS are locked, not just the catch: the annotated-pending row must be CAUGHT in the PASS
state (A) and must NOT false-positive in the BLOCK state (B); emphasis-marked cells must still classify
(C); and `(self)` must keep both its classification and its author-round contribution (E). The
fail-closed half has its own fixtures over four unrecognised spellings (D).

**A `tests/revert-battery.py` GUARDS entry is NOT representable for this change — proven, not assumed.**
The battery patches only `dst / GEN` (`tests/revert-battery.py:135`, `GEN =
"generate-skill-enumerations.py"`), its coverage and provenance passes parse only that file, and all 30
distinct `covers` units resolve inside it. `_record_problems` appears 0 times in the generator and 15
times in `tests/run-golden.py`. A stub aimed at these lines returns the source unchanged, i.e.
`PATCH-MISS "the stub did not apply — the source moved"` plus a provenance `MIS-CLAIM`. So the proof
mechanism is the in-file synthetic self-test battery above, which is the same mechanism the existing
CONTRIBUTING cross-checks use (`:726`, `:756`).

**Consequence a reviewer should weigh, stated rather than left to be discovered:** `run-golden.py`'s own
checks are outside the mutation-proven denominator entirely. The `72/72 stubs bite` figure the battery
prints covers the generator, not this checker. The reverts above were run by hand, by the author, and are
not re-run by CI.

## Findings

- **BLOCKER-1 (round 1, GPT) — the "closed set" was a first-token prefix parser.** `_verdict_kind`
  deleted every `*`, `_` and backtick from ANY position, optionally dropped one trailing parenthetical,
  split on whitespace and returned `head[0]` — never checking the rest of the cell was consumed. So
  `BLOCK PASS pending`, `PASS pending`, `self BLOCK`, `BLOCK garbage`, `BLOCK\npending`,
  `BLOCK <!-- pending -->` and `B*L*O*C*K` all classified, while ordinary `[BLOCK](url)`,
  `<strong>BLOCK</strong>` and `~~BLOCK~~` were rejected — neither a closed set nor a coherent grammar.
  The advertised "an unrecognised cell is ITSELF a finding" was false whenever the FIRST word happened to
  be recognised, and the reviewer drove a live-shaped record carrying `BLOCK PASS pending` through the
  real section for a clean `23/23`. **RESOLVED** at round 2: `_verdict_kind` is now a recogniser —
  `re.fullmatch` against a complete-cell grammar (one verdict word; at most one correctly-paired OUTER
  emphasis wrapper; the wholly-parenthesised `(self)`; at most one non-nested trailing parenthetical;
  no newline; nothing unconsumed). 12 accept + 25 reject cases are pinned, including every cell above.
- **BLOCKER-2 (round 1, GPT) — the REQUIRED status check accepted `Verdict: PASS pending`.**
  `gate-review-check.py:96`'s `VERDICT_LINE_RE` captured `([A-Za-z][A-Za-z-]*)` with no end anchor, so
  `effective_verdict` read `PASS` out of `PASS pending`, `PASS garbage`, `PASS <!-- BLOCK -->` and
  `PASS [BLOCK](x)`, and `decide_verdicts` then cleared the gate. A record whose final line literally said
  `PASS pending` could merge a gate-layer change — the same unconsumed-suffix class the change claimed to
  close, in the enforcement mechanism itself, and the file's own comment already claimed the token "must
  be exactly PASS/BLOCK/FAIL". **RESOLVED** at round 2: matched whole against `PASS|BLOCK|FAIL`. All five
  live PASS records still parse; `TEMPLATE.md`'s bracketed placeholder still cannot match, by design.
  The in-suite twin at `tests/run-golden.py` (`^Verdict:\s*(\w+)`) had the identical defect and now uses
  the same grammar, so the two cannot disagree about a record's conclusion.
- **BLOCKER-3 (round 1, GPT) — "review (round N) returned PASS" could contradict a BLOCK row.** The PASS
  arm parsed both closure sentinels with one alternation and then treated them identically, checking only
  that N was the newest round. **RESOLVED** at round 2: the forms make different claims and are checked
  differently — an owner decision may close over a BLOCK row (the live 0005 record does exactly that), a
  claimed passing review may not, and row N must itself classify as `pass`.
- **MAJOR-4 (round 1, GPT) — the strengthened invariant was non-prospective.** `GATE_RECORD` was
  hardcoded to `gate-reviews/0005-*.md`, which CONTRIBUTING declares append-only history — so the new
  verdict-cell rules applied only to the one record policy says should not normally change, and to no
  record that will actually be created or extended. **RESOLVED** at round 2: `_record_problems` splits
  into a GENERIC round-table/prose validator (`contrib=None`) and the 0005-specific CONTRIBUTING
  count/range validator, and the suite sweeps every `gate-reviews/[0-9][0-9][0-9][0-9]-*.md` carrying a
  round history. The round table is located by its canonical HEADER rather than "any row whose first cell
  is an integer" — necessary, because THIS record's census table has source line numbers (673, 716, 718,
  728) in column one and would otherwise have been read as rounds. The sweep asserts it covers more than
  one record, so it cannot silently degrade to the old single-file behaviour.
- **MINOR-5 (round 1, GPT) — revert F was not independently reproducible.** The record published
  "12 failed" without recording the exact mutation; three reasonable readings of "returns its input
  unnormalised" give 11, 12 and 13. **RESOLVED** at round 2: the hand-run reverts are replaced by
  `tests/mutation-runner.py`, a committed target-aware runner that carries each mutation as an exact
  before/after string and asserts the named fixtures redden.

Also checked and found clean at round 1: the live record and CONTRIBUTING still agree; `(self)` keeps its
classification and its author-round contribution; the A–E revert deltas reproduced exactly as recorded;
and the argument that a current-form `revert-battery.py` GUARDS entry is unrepresentable for a
`run-golden.py` check was independently confirmed, with no finding raised against it.

---

## Why this record is nevertheless BLOCK

The most recent independent review (round 1) returned BLOCK with three BLOCKERs, one MAJOR and one MINOR.
Every one is reproduced, fixed and fixtured at round 2, and the round-2 row above is still `pending`
because an independent round-2 review has not yet returned. Per the prompt's own rule, `PASS` may not be
written while the newest round is unresolved, and the author may not self-certify the fixes to the
author's own change. The required `gate-review` check therefore stays RED — the correct state for a
gate-layer change whose current round is open, not a defect to route around.

Verdict: BLOCK
