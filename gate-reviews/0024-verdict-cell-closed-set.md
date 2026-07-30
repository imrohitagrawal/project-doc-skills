# Gate-review verdict — PR "fix(gate): make the verdict grammar a recogniser"

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: `fix/verdict-cell-closed-set`
- Diff range: `main..fix/verdict-cell-closed-set`
- Gate-layer paths changed: `gate-review-check.py`, `tests/mutation-runner.py`, `tests/run-golden.py`
  (the three paths `gate-review-check.py` prints at this head)
- Reviewers / instruments: round 1 — an independent different-vendor (GPT) cold pass against a provenance
  bundle (HEAD sha + per-file sha256 + verbatim source). Round 2 — six independent fresh-context lenses
  (cell grammar; enforcement bypass; coverage-vs-advertising; prospectiveness; regression; proof quality),
  each blind to the author's context, followed by a per-finding adversarial adjudicator whose default
  position was that the finding is wrong: 38 candidates raised, 32 survived refutation.
- Independence limit honestly stated: round 1 was weight-decorrelated but had no repository checkout
  beyond the bundled files, so it could not run the full suite and did not claim to. Round 2 is **context
  isolation only, not weight decorrelation** — fresh contexts of the same model that wrote the change.
  The owner ended different-vendor reviews after round 1, so this is now the permanent ceiling of every
  future round on this repository and every record should keep saying so.

## Record convention

One record per work package, updated in place across rounds; `Round N carries ID 0023+N` for this record
(round 1 = ID 0024), continuing the flat review-ID sequence after the 0005 record's rounds consumed IDs
0005–0023.

| # | head | verdict | blocking finding | resolution |
|---|---|---|---|---|
| 1 | 129578e | BLOCK | Independent GPT cold pass. **B1:** `_verdict_kind` was a first-token PREFIX PARSER — it deleted `*`/`_`/backtick from ANY position, dropped one trailing parenthetical, split on whitespace and returned the first recognised word without checking the rest was consumed, so `BLOCK PASS pending`, `BLOCK garbage`, `self BLOCK` and `B*L*O*C*K` all classified while `[BLOCK](url)`, `<strong>BLOCK</strong>` and `~~BLOCK~~` were rejected; "an unrecognised cell is itself a finding" was false whenever the first word was recognised. **B2:** `VERDICT_LINE_RE` was not end-anchored, so the REQUIRED status check cleared `Verdict: PASS pending`. **B3:** the PASS arm accepted `review (round N) returned PASS` over a table row saying BLOCK. **M4:** `GATE_RECORD` was hardcoded to the append-only 0005 record. **m5:** revert F published a failure count without its mutation. | complete-cell `re.fullmatch` grammar; both verdict-line parsers matched whole; the two closure sentinels split and checked differently; `_record_problems` generalised over every record; a committed target-aware mutation runner |
| 2 | 003694e | BLOCK | Six independent fresh-context lenses + per-finding adversarial adjudication. **B6, introduced BY the round-1 fix:** anchoring the strict token INTO `VERDICT_LINE_RE` made an annotated verdict line INVISIBLE rather than fatal, and `effective_verdict`'s last-line-wins rule then fell back to an EARLIER line — a record ending `Verdict: BLOCK (2 blockers outstanding)` after an earlier `Verdict: PASS` CLEARED the required check. The fix was worse than the defect it closed. **M7:** `_verdict_kind` returned `word.casefold()` with no membership test, and `re.IGNORECASE` folds U+0131 DOTLESS I onto `i`, so `pendıng` returned a non-member, non-`None` value that defeated the unrecognised-cell arm and the pending arm at once. **M8:** `_round_rows` silently DISCARDED an unparseable line inside the table, so invariants ran over fewer rows than the reader sees. **M9:** the new sweep had no mutation proving it bites and chose a narrower record population than the required check. **M10:** this record's own census, `Coverage: N/M`, revert table and gate-path list were round-1 text left stale by the round-2 commit. | loose line match + strict token validation in BOTH parsers, failing closed in both signs; membership test restored; an unparseable table line is now a finding; the sweep proven by mutation and aligned to `gate-reviews/*.md`; this record regenerated from the current head |
| 3 | 6c41a4b | BLOCK | Six blind fresh-context lenses + per-finding adversarial adjudication: 33 candidates, **26 survived** (5 BLOCKER, 11 MAJOR, 10 MINOR). **B14, a REGRESSION this branch introduced against `main`:** narrowing the verdict line's leading class from `\s*` to `[ \t]*` made a NBSP-indented `Verdict: BLOCK` invisible, so last-declaration-wins fell back to an earlier `PASS` — `main` blocked that input and this branch cleared it. Twelve Unicode space characters were affected. Six further spellings (`**Verdict: BLOCK**`, `**Verdict:** BLOCK`, `+`/`-` bullets, `## heading`, `> blockquote`, `1.` ordered) cleared on BOTH trees — pre-existing, not introduced. **B15:** a trailing `<!-- ... Verdict: PASS ... -->` — the commenting style TEMPLATE.md itself teaches — became the last matched line over a visible BLOCK. **B16:** an ANNOTATED blocking record collapsed to an unreadable verdict, and `decide_verdicts` only gated on the literal BLOCK/FAIL, so a SIBLING clean-PASS record cleared the gate on its behalf: the same fall-back shape one level up, across records. Plus MAJORs on unproven guards, a too-narrow round-table header, and stale census arithmetic in this record. | the verdict parser REDESIGNED so over-inclusion is the safe direction; HTML comments stripped before reading; ONE parser shared by the suite and the required check (delegation, not re-implementation); a record that is not a clean PASS now GATES; 10 decoration spellings + the across-record cases fixtured; mutation runner 13/13 |
| 4 | pending | pending | pending | pending |

## Replay the real failure

The failure this checker exists to catch is a verdict record whose round TABLE and verdict PROSE
contradict each other. It has happened twice for real — rounds 16 and 17 of the 0005 record both said
`pending` in the table while the prose said BLOCK — which is why `_record_problems` exists, and round 19
extended it to the PASS state because `Verdict: PASS` over a still-pending newest row returned nothing.

**The actual stale state, reproduced.** The PASS-state invariant compared against the exact literal
`pending`, so an annotated cell escaped it: `_record_problems` on a record whose newest row reads
`pending (round 20 running)` under `Verdict: PASS` returned `[]`.

Fixing that opened two further holes, both found by review rather than by the author, and both now closed:
the replacement grammar was a prefix parser (round 1, B1), and the replacement line anchor made an
annotated verdict line invisible so the required check cleared a BLOCKing record (round 2, B6).

**Population and coverage.** The unit is "a place where a verdict — a table cell or a final line — is
turned into a decision". At this head there are eight, and every one now goes through a whole-match
recogniser:

| Site | Consumes |
|---|---|
| `tests/run-golden.py:817` unrecognised-cell finding | `_verdict_kind` |
| `tests/run-golden.py:823` PASS-state pending invariant | `_verdict_kind` |
| `tests/run-golden.py:879` "review (round N) returned PASS" vs its row | `_verdict_kind` |
| `tests/run-golden.py:887` prose/table BLOCK cross-check | `_verdict_kind` |
| `tests/run-golden.py:889` BLOCK-state non-pending arm | `_verdict_kind` |
| `tests/run-golden.py:906` CONTRIBUTING author-round count | `_verdict_kind` |
| `gate-review-check.py` `effective_verdict` — the ONE verdict-line parser | loose find, strict token |
| `gate-review-check.py` `decide_verdicts` — verdict to gate decision | `effective_verdict` |

`tests/run-golden.py:841-842` is no longer a seventh site: it CALLS the parser above rather than
re-implementing it, so the two cannot disagree by construction. Round 2 asserted that property of a
re-implementation, which was false twice.

Coverage: 8/8 verdict-interpretation sites

No site compares a raw cell or a raw verdict token against a literal, and none accepts unconsumed text.

## Coverage vs advertising

The claim under test is "the world is closed: a cell that does not normalise into this set is ITSELF a
finding". At round 1 that was false — a recognised first word admitted any suffix. At round 2 it was still
false for one input class: a homoglyph matched the pattern but casefolded to a non-member, so the function
returned neither a member nor `None`. Both are closed now: the grammar matches the WHOLE cell, and the
return value is filtered through `_VERDICT_KINDS`, which is the single source the pattern is built from.

The required check's own comment claimed its token "must be exactly PASS/BLOCK/FAIL" while its regex had
no end anchor. That sentence is now true — and true in the SAFE direction, because the strictness lives in
a separate token test rather than in the line matcher, so a malformed line is seen and rejected instead of
skipped in favour of a friendlier line above it.

**What this change still does NOT do, stated plainly:**

- It does not normalise Unicode confusables beyond what `re.IGNORECASE` folds. A homoglyph cell is now
  REJECTED rather than misread, which is the fail-closed direction, but no confusable-folding is
  performed. `CONTRIBUTING.md` records the full confusables table as out of scope for this suite, and
  adding it here alone would put this checker out of step with `generate-skill-enumerations.py`.
- It validates no record CONTENT beyond the round table, the closure prose and the final verdict.
- The generic sweep covers every `gate-reviews/*.md` carrying a round-history table — today the 0005
  record and this one. Records without a round table are skipped by design, which is why `0001`–`0004`
  are not swept. But `gate-reviews/TEMPLATE.md` produces no round table either, so a record created by
  copying the template is NOT covered until someone adds a table by hand. That is a real limit of the
  template, recorded as MINOR-11 rather than quietly accepted.

## Self-description drift

This change alters no count or list of checks, lints, steps, skills or paths.

Two self-description defects in the checker's own docstring were fixed, because adding a record file would
otherwise have falsified one of them:

- the review-ID range was stated as a literal `0005-0022`; the live enforced range is `0005`–`0023`. The
  literal is GONE rather than corrected — the range end is derived from the table, so no second number can
  go stale at round 20.
- the docstring asserted "there are no files 0006+", which this record makes false. It now says what is
  true: there is no separate record FILE per ROUND of the 0005 record.

`CONTRIBUTING.md:197` is deliberately untouched: two independent regexes read that one sentence, and the
range is cross-checked against record 0005's ROUND COUNT rather than the file inventory, so bumping it to
`0024` would redden the suite. Confirmed absent from this PR's changed-file list.

Round 2 additionally found that this record's OWN evidence had gone stale against the code it describes —
the census line numbers, the `Coverage: N/M`, the revert table and the gate-layer path list were all
round-1 text carried into a round-2 commit that had moved every one of them. That is precisely the drift
class this record is supposed to police, occurring in the record itself. The document has therefore been
REGENERATED from the current head rather than patched, and every number above was re-derived.

## Fixture requirement

Every guard ships a fixture, and every fixture is proven to bite by `tests/mutation-runner.py`, which
carries each mutation as an EXACT before/after string, requires it to apply at exactly one site, requires
the suite to RUN (a crash is never a bite), and requires it to redden the fixtures it DECLARES rather than
merely some fixture:

```
--- mutation runner: 11/11 mutations bite their declared fixtures ---
```

The runner earned its place three times over by failing on the author's own work rather than passing
quietly:

- it proved an explicit `if "\n" in cell` guard was DEAD CODE — deletable with the suite still green,
  because the grammar's horizontal-whitespace classes already reject a newline. It claimed coverage it did
  not provide, so it is gone;
- it reported two mutations as MIS-TARGETED because their declared fixture names were wrong, rather than
  counting them as bites;
- and it caught the round-2 mirror-hole fixture as GREEN, proving the author's first regression test for
  BLOCKER-6 exercised the in-suite twin and never touched the required check it was written for.

A `tests/revert-battery.py` GUARDS entry remains unrepresentable for these checks: the battery patches
only `dst / GEN` (`GEN = "generate-skill-enumerations.py"`) and parses only that file, so a stub aimed at
`run-golden.py` returns the source unchanged — `PATCH-MISS` plus a provenance `MIS-CLAIM`. The round-1
reviewer independently confirmed this and raised no finding against it. The consequence is worth stating
rather than leaving to be discovered: **`run-golden.py`'s own checks sit outside the battery's
mutation-proven denominator entirely**, and the battery's `72/72` covers the generator, not this checker.
That gap is what the mutation runner exists to fill, and unlike the round-1 hand-run reverts it is
committed, deterministic and re-runnable by anyone.

## Findings

Round-1 findings, all RESOLVED (reproductions in the round-1 row): **BLOCKER-1** prefix parser ·
**BLOCKER-2** the required check accepted `Verdict: PASS pending` · **BLOCKER-3** a claimed passing review
over a BLOCK row · **MAJOR-4** non-prospective · **MINOR-5** unreproducible revert.

Round-2 findings:

- **BLOCKER-6 — the round-1 fix opened a mirror hole. RESOLVED.** Anchoring the strict token into
  `VERDICT_LINE_RE` made an annotated verdict line invisible rather than fatal; last-line-wins then fell
  back to an earlier line, so a record ending `Verdict: BLOCK (2 blockers outstanding)` after an earlier
  `Verdict: PASS` cleared the required check (`effective_verdict` → `PASS`, `decide_verdicts` → `True`).
  Fixed by finding the line loosely and judging the token strictly; three fixtures pin it — annotated
  BLOCK after PASS, annotated BLOCK alone, and a well-formed later PASS still winning.
- **MAJOR-7 — `_verdict_kind` could return a non-member. RESOLVED.** No membership test followed the
  casefold, and `re.IGNORECASE` folds U+0131/U+0130 onto `i`, so `pendıng` returned `'pendıng'`,
  defeating the unrecognised-cell arm (not `None`) and the pending arm (not `"pending"`) at once. Fixed by
  filtering through `_VERDICT_KINDS`; four homoglyph unit fixtures plus a full-record fixture.
- **MAJOR-8 — an unparseable row inside the round table was silently dropped. RESOLVED.** Every
  downstream invariant then ran over a shorter table than the reader sees. It is now a finding, fixtured
  with a GFM-legal space-indented row.
- **MAJOR-9 — the sweep was unproven and mis-scoped. RESOLVED.** It had no mutation-runner entry, so
  nothing proved it bites, and it used a narrower glob than the required check's record predicate. It now
  sweeps every `gate-reviews/*.md` carrying a round history, and a mutation that makes it skip every
  record reddens the floor assertion.
- **MAJOR-10 — this record's own evidence was stale. RESOLVED** by regenerating it from the current head.
- **MINOR-11 — `gate-reviews/TEMPLATE.md` produces no round-history table**, so a record created by
  copying the template is not covered by the generic sweep until a table is added by hand. NOT fixed here:
  changing the template changes what every future reviewer is instructed to write, which is a governance
  edit deserving its own round rather than a rider on this one.
- **NIT-12 — the closed set was written twice**, as a frozenset and as a regex alternation twenty lines
  apart with nothing binding them. RESOLVED: the pattern is built from the frozenset, so there is one
  source.
- **NIT-13 — a duplicated assertion** re-evaluated an identical call seventy lines below the original.
  RESOLVED: removed.

## Outstanding — round-3 findings NOT fixed here

Round 3 returned 26 surviving findings. The five BLOCKERs and the regression are fixed above. These are
written down rather than quietly dropped, because the repository's rule is to ship with the leftovers
recorded, not to keep grinding:

- **Unproven guards (MAJOR).** Several behaviours added across rounds 1-3 survive a no-op revert against
  the committed test apparatus — among them the `[^()\n]` non-nesting class and the `(?P=wrap)`
  back-reference inside the cell grammar, and the BLOCK-state non-pending arm at
  `tests/run-golden.py:889`. They are covered by the grammar's accept/reject table but not isolated by a
  mutation of their own, so a subtler revert of any one of them would not redden.
- **`_ROUND_HEADER_RE` is byte-exact (MAJOR).** A future record whose round table is headed slightly
  differently — bolded cells, `Round`, `outcome`, an extra leading space — is silently skipped by the
  sweep rather than reported. The sweep's `swept >= 2` floor is what stops that degrading to zero today,
  but the floor is a count, not a guarantee about WHICH records are covered.
- **Governance docs not updated (MINOR).** `gate-review-prompt.md` and `gate-reviews/TEMPLATE.md` still
  describe the older, looser verdict-line expectations, and `CONTRIBUTING.md`'s requirement (ii) names
  only `tests/revert-battery.py` as the bite-prover — `tests/mutation-runner.py` is registered nowhere a
  contributor would find it. Editing those files changes what every future reviewer is told to do, so it
  belongs in its own round rather than as a rider here.
- **This record's `## Findings` shape (MINOR).** `gate-review-check.py`'s own `shape_problems` wants a
  `file:line` anchor or an explicit `none` in that section; this record's narrative form may not satisfy
  it. It does not matter while the verdict is BLOCK, and it must be fixed before any PASS.
- **`gate-reviews/TEMPLATE.md` produces no round-history table (MINOR, carried from round 2)**, so a
  record created from it escapes the generic sweep until a table is added by hand.

---

## Why this record is nevertheless BLOCK

The most recent independent review (round 3) returned BLOCK: five BLOCKERs — one of them a REGRESSION
this branch introduced against `main`, and one the round-2 fix itself created — plus eleven MAJORs and
ten MINORs. The BLOCKERs and the regression are reproduced, fixed and fixtured above; the remaining
findings are listed under "Outstanding" rather than silently dropped. The round-4 row is `pending`
because an independent round-4 review has not returned.

Three rounds have now each found that the previous round's FIX introduced the next defect, always in the
same shape: a verdict line the matcher could not see was skipped, and the decision fell back to a
friendlier answer. Round 3 stopped patching the pattern and changed the design instead — finding a
declaration is now deliberately over-inclusive, because over-inclusion can only ever cause a BLOCK,
while judging the token stays exact. That is the only arrangement in which a gap in the matcher fails in
the safe direction.

The author may not certify the author's own fixes, and the prompt forbids `PASS` while the newest round
is unresolved. The required `gate-review` check therefore stays RED — the correct state for a gate-layer
change whose current round is open, not a defect to route around. An independent round-4 review is what
would clear it.

Verdict: BLOCK
