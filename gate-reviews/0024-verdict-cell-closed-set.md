# Gate-review verdict — PR "fix(tests): close the verdict-cell world in the record checker"

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: `fix/verdict-cell-closed-set`
- Diff range: `main..fix/verdict-cell-closed-set`
- Gate-layer paths changed: `tests/run-golden.py`   (the list `gate-review-check.py` printed)
- Reviewers / instruments: **NONE YET — the independent round is OWED.** What is recorded below is the
  AUTHOR's own verification and self-red-team, clearly labelled as such. Reviews on this repository are
  GPT-only by the owner's standing decision, and the author cannot run that pass.
- Independence limit honestly stated: **there is no independence here at all.** These sections were
  written by the author of the change. They are evidence for a reviewer to check, not a review. Nothing
  below may be read as an independent verdict, and the verdict line at the bottom is deliberately not
  `PASS` — see "Findings".

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

- **BLOCKER-1 — the independent review has not happened.** This record is authored by the author of the
  change. The owner's standing decision is that reviews on this repository are GPT-only, generated from a
  provenance bundle; that pass has not been run, so no independent lens has examined this diff. Per the
  prompt's own rule, `PASS` may not be written. The concrete fix is procedural: run the GPT round against
  the bundle prepared for this PR, record the result here as a round row, and only then flip the verdict.
  Raised by: the author, against the author's own work.
- **MINOR-2 — this record is not machine-checked.** `_record_problems` validates only
  `gate-reviews/0005-*.md` (`GATE_RECORD`, `:75`), so the table/prose/count invariants this very change
  strengthens do not apply to record `0024` or to any future record. Generalising `GATE_RECORD` to every
  `gate-reviews/00NN-*.md` with a round table is the obvious follow-up; it is deliberately NOT bundled
  here, because it would change which files the checker reads and deserves its own review round. Raised
  by: the author, while writing the "Coverage vs advertising" section.
- **NIT-3 — the `Verdict:` grammar is `(\w+)` at `:694`.** It accepts `pass`/`PASS` and would take the
  first token of `PASS-WITH-NITS` as `PASS`, diverging from `gate-review-check.py:96`
  (`[A-Za-z][A-Za-z-]*`, IGNORECASE). Untouched here on purpose: aligning it changes which branch such a
  verdict line takes, and neither behaviour is currently pinned by an assertion, so it needs its own
  fixtured change. Raised by: the author, from the D5 reconnaissance.

Also checked and found clean: the live record and CONTRIBUTING still agree (`LIVE record + CONTRIBUTING
are consistent`); the closed set accepts every value the live record actually carries; no gate-layer file
other than `tests/run-golden.py` is touched; no count or list changed anywhere in the gate layer.

---

Verdict: pending

The independent GPT round (BLOCKER-1) has not been run, so neither `PASS` nor `BLOCK` is honest here:
`PASS` would be a self-certification and `BLOCK` would claim findings a reviewer raised. The required
`gate-review` status check will therefore stay RED, which is the correct state for a gate-layer change
whose review is still owed — it is not a defect to route around. Flip this line only from the result of
a real independent round.
