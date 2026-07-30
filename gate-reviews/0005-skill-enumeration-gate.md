# Gate-review verdict — PR #12 · feat/skill-count-generate (issue #7)

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: PR #12 · `feat/skill-count-generate` (issue #7)
- Diff range: e4bc544..HEAD (current head; the PR has been reviewed over NINETEEN rounds — see below)
- Gate-layer paths changed: `.github/gate-paths`, `.github/workflows/release-gate.yml`, `CONTRIBUTING.md`,
  `build-skills.sh`, `generate-skill-enumerations.py`, `lint-skill-count.py` (DELETED), `release-gate.sh`,
  `skills-order`, `tests/run-golden.py`, `tests/revert-battery.py`
- Reviewers / instruments: **nineteen review rounds — eighteen independent, plus the author's own red-team at round 13**. Rounds 1–11 paired a same-model
  (Claude) blind multi-lens pass with a different-vendor (GPT) cold pass on the same head; from round 12
  on, reviews are a different-vendor (GPT) cold pass by the owner's decision, each against a verbatim
  provenance bundle (HEAD sha + per-file sha256 + exact source). The author reproduces every load-bearing
  finding against the real code before acting. Round 7 produced the committed `tests/revert-battery.py`.
- Independence limit honestly stated: same-model lenses are context isolation, not weight decorrelation
  — and this PR is the proof: the same-model pass returned **PASS on a revision the different-vendor pass
  correctly BLOCKED** (round 1), and in later rounds each vendor found defects the other missed. The
  cross-vendor pass was load-bearing every round, not a formality.

> **Record convention.** This is ONE record for PR #12, updated in place across review rounds, because
> `gate-review-check.py` is fail-safe: a `BLOCK` record blocks even if a `PASS` is added later, so a PR
> needing more than one round cannot use one file per round without becoming permanently unmergeable.
> Nothing is lost — every round's blocking findings and their resolution are recorded below. The
> append-only rule in CONTRIBUTING binds records **once merged**; this PR is not merged.

## Round history (what blocked, and how it was resolved)

| # | head | verdict | blocking finding | resolution |
|---|---|---|---|---|
| 1 | aedddc3 | BLOCK | Same-model pass said PASS; **GPT cold pass found substring marker matching** — a marker embedded in a spanning HTML comment (or duplicated on one line) hid a canonical block while the visible list was broken; table decoy rows inside `<!-- -->` were read as real. Author reproduced both. | exact standalone marker lines + anchoring + comment-stripped table rows |
| 2 | 60dcc8d | BLOCK | **Both** reviewers converged: a byte-stream check cannot tell a rendered enumeration from a hidden one — a correct block wrapped in `<details>`/a fence renders hidden while a broken list shows; a code-span comment delimiter hid a visible row; empty `skills/` failed **open**. | pivot to checking the **parsed Markdown** (markdown-it-py); empty source fails closed |
| 3 | 74d7d22 | BLOCK | Both converged again: `t.level == 0` is markdown-it **token** nesting, not **DOM** nesting — a blank line ends a raw-HTML block, so `<details>` left markers top-level while the browser still nested the content. Confirmed in cmark-gfm. | **honest re-scope**: drop the "no decoy class" claim; ship as a drift-catcher + casual-decoy guard with a **raw-HTML ban** that removes the enabling surface by enforcement |
| 4 | 6ff8f1e | BLOCK | Accuracy, not decoys: fixtures did not bite for 3 of 5 sites; a comment-prefixed `<div>` passed the ban; "no raw HTML" was region-only while claimed document-wide; a code-span/line-wrap count slipped. | per-site fixtures; whole-block comment check; document-wide ban; count over rendered visible text |
| 5 | 212dbca | BLOCK | Wording precision: "no raw HTML" is false while comment markers are permitted **and required**; a backslash hard-break count slipped; two guards shipped unfixtured. | precise wording everywhere; count via `_visible_text`; fixtures added |
| 6 | 6211e33 | BLOCK | **A regression the author shipped**: round 5 fed the count check rendered text but its pattern still carried a literal `\*\*`, so it could never match — that phrase went unguarded while the banner printed "count phrases consistent". | count check made **fail-closed** (presence-required + value-exact); HTML allowlist made **marker-identity** |
| 7 | f206035 | BLOCK | Duplicate-marker guard did not bite and its "isolating" fixture did not isolate; GPT found the count slot read ordinary prose as a count (`"now review skills"` → `review`) and that missing boundaries let substrings satisfy phrases (`build all eight-skill bundles`, `know eight skills`, `skillsets`). | unit-locked marker branches; **number-only count slot + whole-template boundaries**; vacuous-success paths closed; image ban and cross-file gap disclosed |
| 8 | d07e66e | BLOCK | Round 8 attacked the verification itself, as round 7 required. It confirmed the battery **sound** where it reaches (harness sanity real; all stubs compile, apply uniquely, redden via the semantically correct assertion — 19/19 independently re-verified) but **incomplete**: `_pure_source`'s exactly-one-paragraph and `_fence_body`'s exactly-one-fence checks had no stub and no fixture. `_competing` skips the marked region by design, so those two are the only guards stopping a reader-visible decoy smuggled *between the real block and the end marker*; loosening either one character (`==` → `>=`) left golden green and admitted the decoy. Both reviewers converged on the root cause: **the battery's denominator was self-declared**, so a guard with no stub was invisible. (GPT's headline `mkdtemp`/`Path` BLOCKER was a defect in the excerpt the author pasted into the prompt, not in the committed script — the author's error, and it cost the reviewer part of a round.) | see round 9 |
| 9 | fdc2073 | BLOCK | *(reviewed at round 10, which found more — see below)* — three in-region smuggle fixtures + stubs (paragraph, fence and table regions); `_table_names` reduced to a **single positive grammar** (the redundant blacklist beside it was exactly why neither branch could be proven by a revert); battery rebuilt so the class cannot recur: **coverage is derived from the source by `ast`** — every finding-producing function must be claimed by a stub, an unclaimed one is OWED — a bite now requires the suite to have RUN and ASSERTED (crash, syntax error, timeout or signal is never a bite), stubs must apply at exactly one site and produce distinct mutants, the scratch tree copies tracked files only, `PYTHONPATH` is stripped, the baseline must run a minimum number of assertions, and guards unprovable by source mutation are declared REDUNDANT rather than counted as proven. **136/136 golden, 5/5 release gate, 23/23 stubs bite, 12/12 guard functions claimed.** | — |
| 10 | 1c76c9a | BLOCK | GPT found the count was not location-bound, anchors were not unique, competing runs were not aggregated across lists/columns, and the battery over-claimed. | location-bound counts; unique anchors; aggregated competing runs; honest battery |
| 11 | 2bfb677 | BLOCK | GPT: the count was still maskable within one unit; the competing scan missed a whole-document run; the battery was blind to verdict-forwarders. | anchor+count combined pattern; whole-doc competing scan; forwarder-aware battery (fixpoint) |
| 12 | 2a09f8f | BLOCK | **Owner flagged the review loop** and demanded a root-cause fix: count-by-regex-over-prose is inherently leaky, and there was no normalization. | rebuild — structural marked count sites; ONE `_norm` at every match point; per-container competing; call-graph battery |
| 13 | 5ca2232 | (self) | Three adversarial self-red-team rounds + an AST mutation sweep found 13 issues (count number-continuation, competing-scan-before-spans, blockquote/list lead-in FP, the `_doc_raw_inline` image arm, `_norm` Greek-casefold non-idempotence, …). | all 13 fixed; final NFKC pass added; anchoring reduced to adjacency-only |
| 14 | eab308a→c095772 | BLOCK | GPT: the count sites were never LOCATION-bound; the presence guard was a one-sided lookahead that both masked and false-positived; the banner over-claimed; the battery proved FUNCTION- not BRANCH-level and counted any red as a bite. | **DROP the scalar count check entirely** (a bottomless FP/mask well over five rounds, little value over the five generated sites); battery made assertion-specific (`expect_fx`) + branch-level + committed AST finding-branch sweep |
| 15 | 8fccfe5 | BLOCK | GPT: the real `--check` CLI verdict path was outside golden and the battery; the finding-branch sweep counted CRASHES as reddens and mis-labeled its denominator (`_inline_text` data appends); the source-of-truth producers were not locked to their files; the raw-HTML ban + retired-marker allowlist were fixtured on one file only; `_preceding_visible`'s heading arm and both `_norm` call sites were unproven. | *(this round)* end-to-end CLI fixture + main mutants; sweep requires RED + semantic inventory; producer file-dependency fixtures; both-files raw-HTML + retired-marker fixtures; heading + normalized anchor fixtures |
| 16 | aea626d | BLOCK | GPT: `main()`'s EXCEPTIONAL verdict path (`except MarkerError` -> `return 1`) was still uncovered — no fixture made the parser unavailable to the CLI; the CLI oracle used SUBSTRINGS, so a traceback containing "FAIL" satisfied the drift arm and a phantom `FAIL` beside the clean banner satisfied the pristine arm; the inventory oracle checked OWNER membership not statements, so deleting the collector's `ast.Raise` arm (21->18) stayed green; `genuine()` was applied to 13 sites but SEVEN inline `len(scratch(...)) >= 1` positives still accepted the crash sentinel; the `hardbreak` half of `_inline_text` had no fixture; the producers' declared FILTERING semantics (blank/`#` lines; the `SKILL.md` predicate) were unlocked. | *(this round)* a typed `ScratchResult` makes crash-as-finding UNREPRESENTABLE (exception is a separate field; all 33 positives go through `was_caught`/`was_caught_msg`); a LINE-BASED CLI oracle (exact `FAIL  skill-enum:` lines, no traceback, one banner carrying every advertised scope clause) plus a parser-missing arm that shadows `markdown_it` in the child; a STATEMENT-LEVEL inventory oracle (synthetic collector probe + independently-derived raise owners + per-owner append cardinality); hardbreak fixture+mutant; producer filtering fixtures+mutants; curated `_md` mutant. |
| 17 | 22e62d3 | BLOCK | GPT: the clean-banner oracle was still SUBSTRING-based — a wrong skill COUNT (`n = 0`), a NEGATED clause and a DUPLICATED clause all passed; two CLI mutants named in the round-16 commit message (crash-in-diagnostic, phantom FAIL) were never committed; the inventory was still shrinkable (`errs.append` -> `errs.extend` dropped it 21->20 with every oracle green) and its "independent" counter shared the collector's assumptions; the producer-filter fixture locked one FORMATTING instance, not the whitespace-normalised contract; `ScratchResult(list)` did NOT make crash-as-finding unrepresentable (`ScratchResult([], exc) == []` was True); and this table said round 16 was `pending` while the prose said it returned BLOCK. | *(this round)* the pristine banner is compared EXACTLY against one built from the fixture's own inventory, with five new mutants (count, negation, duplication, phantom FAIL, traceback-after-diagnostic); the inventory covers append/extend/insert/`+=` and FAILS CLOSED on any unrecognised mutation of a returned list accumulator (which immediately surfaced a 22nd emission, `findings += _competing_findings(...)`, that the append-only rule had missed); owners are derived without descending into nested scopes; the producer fixture carries indented comments and whitespace-only lines, with a matching mutant; `ScratchResult` is COMPOSITION with `was_clean()` and a harness self-test; the record is reconciled. |
| 18 | 526620c | BLOCK | GPT: the inventory was STILL denominator-shrinkable (aliasing, `list.append(acc, m)`, slice-writes, rebinding — four semantics-preserving forms each dropped it 22 -> 21 with every shared-assumption oracle green); the new fail-closed unknown-mutation guard itself had no biting fixture; `ScratchResult` defined no dunders, so default object truthiness made `bool(result)` True for a crash (the round-17 'structural' claim was false); the record contradicted itself AGAIN (row 17 `pending` vs prose 'round 17 returned BLOCK') and CONTRIBUTING called all seventeen rounds independent though round 13 was a self-red-team; the drift CLI arm was materially weaker than the pristine arm (a constant phantom FAIL passed; no summary required). | *(this round)* the enumeration approach is REPLACED by a TOTAL closed-world audit: EVERY appearance of an accumulator name in EVERY function must fit one of five finite shapes (VERDICT / DATA-TEXT / SET-ALLOW / FORWARD / none), and ANY occurrence fitting none — emission forms, init forms, return forms, parameters, globals, forms not yet invented — HALTS the battery. The author's own pre-ship red-team then REPRODUCED a BLOCKER against the first audit design (keying membership on 'returned bare' let `return list(errs)` / `list()`-init / relay-init silently drop emissions) and the total design closed it; all escape forms are committed as 12 flagged bypass probes + 4 clean-shape exclusion probes + the 4 real-source rewrites. `ScratchResult` now RAISES on bool/len/iter/== (self-tested on all three result shapes). Every CLI arm pins EXACT complete stdout with stderr required EMPTY, with 5 new mutants (phantom, truncation, wrong count, SystemExit, stderr-routing). The record and CONTRIBUTING are reconciled, and a MECHANICAL record-consistency check now runs in golden — self-tested on synthetic bad records, and FAIL-CLOSED on its prose anchors while the final verdict is BLOCK (a reworded sentinel is itself a finding) — so a table/prose or count mismatch reddens the suite instead of waiting for a reviewer. |
| 19 | 8240f3a | BLOCK | GPT: the total audit keyed candidate discovery on the LITERAL names findings/errs/out, so renaming an accumulator (`out` -> `results`) moved it outside the closed world and dropped its emissions (19 -> 16) with zero problems; two emissions on one physical line deduplicated to one line-level sweep branch; the record checker was silent in the PASS state (PASS over a newest-BLOCK or still-pending row passed) and CONTRIBUTING's prose counts were not machine-checked; the closure-capture check flagged a nested helper's OWN local `out` (a false positive on a legitimate refactor). | *(final round — dispositioned under the owner's stopping rule)* FIXED: nested-capture is now binding-aware (a name the nested def binds is a fresh scope; genuine captures still halt — probes for both); multiple emissions on one line now FAIL CLOSED; the checker enforces PASS-state invariants (no pending rows; a closure sentinel naming the newest round) and cross-checks CONTRIBUTING's digit counts against the table, all with biting synthetic fixtures. RESIDUAL (disclosed, owner decision): the branch-level sweep's completeness is SCOPED TO THE ACCUMULATOR-NAME CONVENTION (findings/errs/out) — renaming an accumulator moves it outside the sweep. Closing rename-invariance would need whole-program dataflow or an emission-API refactor of the generator, which has been deliberately unchanged for six rounds; the 72 curated function-level guards are name-independent (provenance is AST-derived from the mutation, not from names) and were re-verified to still bite after the rename. |

**The author's own verification was the root cause of the loop.** Rounds 4–7 each reported "every guard
bites"; that claim rested on a hand-rolled battery whose scratch copy was incomplete, so
`tests/run-golden.py` aborted with *"required path missing"* before running a single assertion and every
stub appeared to bite. Reproduced and owned at round 7. The battery is now the committed
`tests/revert-battery.py`, which **checks its own harness first** and refuses to report unless the
unpatched suite actually ran green. Running it immediately exposed six real gaps (the duplicate-marker
branch the reviewer named, a second unfixtured branch nobody had tested, and four more).

## Replay the real failure

The gate exists to catch **`b65041f`** — a skill was added and the suite's five enumeration sites went
stale in root scaffolding invisible to every other check — and, since round 6, a second failure this PR
itself committed: **a check that goes fail-open and prints "consistent" while guarding nothing.**

Replayed at the current head on scratch copies of the REAL `README.md` / `per-skill-review-prompt.md`
(never fixtures), one mutation at a time: a skill **dropped** and, separately, **reordered** inside each
of the five marked blocks — `--check` exits 1 in all ten, each naming the offending site. Empty/missing
`skills/` exits 1 with its own "no skills found … (fail closed, not clean)" message; a `skills-order`
that is not an exact permutation exits 1. The scalar COUNT check that drove rounds 6–14 was **dropped**
at round 14 (a bottomless false-positive/mask well over five rounds that added little over the five
generated enumeration sites); the headline count sentences are now plain, ungated prose. Round 15 added
the end-to-end proof that the CLI itself fails: on a drifted scratch repo `--check` exits nonzero, prints
a FAIL diagnostic, and does NOT print the clean banner (the branch that decides exit code + banner is now
a battery guard of its own).

Coverage: 5/5 enumeration sites

## Coverage vs advertising

The clean banner asserts exactly three things — marked enumerations match `skills-order` in the parsed
Markdown; governed docs contain no raw HTML except the comment markers; drift-catcher scope pointer — and
each maps to code that runs unconditionally in `check()` (the count-consistency claim was removed with the
count check at round 14, so the banner no longer over-claims it). The
historically over-claimed strings ("no decoy class", enumeration "byte-identical", "the `6f66dfa` decoy
now FAILS") survive only inside the ADR's fenced ⚠ SUPERSEDED body and in this record's history, both
explicitly labelled as retired. `CONTRIBUTING.md` "Skill-enumeration gate: scope" is authoritative and
names the residuals rather than hand-waving them: markdown-it-py vs cmark-gfm parse edge cases,
**cross-file competing enumerations**, and anything the raw-HTML ban does not cover; it also discloses
the deliberate Markdown-image ban.

## Self-description drift

No stale self-description of the enumeration gate survives: `build-skills.sh`, `release-gate.sh`,
`.github/gate-paths` and the CI workflow all describe the shipped check (parsed-Markdown verification,
`markdown-it-py` dependency, drift-catcher scope with the comment-marker exception). The site count is
derived from `PURE_SITES`/`TABLE_SITES` and the skill count from `skills/` at runtime — no hard-coded
number can drift. `docs/adr/` is recorded in the gate-paths "deliberately NOT gated" ledger with a reason.

## Fixture requirement

`tests/run-golden.py` carries the whole-suite golden battery (**213/213** assertions green, including a
mechanical record-consistency check that is itself self-tested on synthetic bad records), and
`tests/revert-battery.py` proves the fixtures BITE rather than merely existing: it stubs each of the
**72** guards on a full-repo copy and requires the golden suite to go red **via the guard's DECLARED
assertion** (`expect_fx`) — a mutant that reddens only some unrelated assertion is rejected as
MIS-TARGETED — **72/72 bite** — after first asserting its own harness ran green. The finding-branch
inventory is derived from a CLOSED-WORLD accumulator audit: a returned finding accumulator may only be
initialised, emitted-to (`append`/`extend`/`insert`/`+=`), and returned; ANY other use of the name halts
the battery, so a bypass cannot shrink the denominator — it stops the run. The audit's own bite is proven
by 12 synthetic bypass probes and 4 clean-shape exclusion probes, plus the 4 review-produced real-source forms (aliasing, `list.append`,
slice-write, rebinding), all of which must be flagged, and a returned SET must stay untracked. Every
inventoried branch (**22/22**: 19 emissions + 3 raises, the raises censused independently) reverted to a
no-op must redden golden as an ASSERTION, not a crash, and every stub's declared `covers` must equal the
units it actually mutates (**72/72** provenance-clean). `CONTRIBUTING` requirement (ii) mandates running
it before requesting a review, and requires a new guard to arrive with its stub.

## Findings

- none outstanding in the author's own verification — every round-18 finding is resolved, each original
  break-test RE-RUN and confirmed to now redden or halt: the four inventory-shrinking forms (aliasing,
  `list.append(acc, m)`, slice-write, rebinding) each HALT the battery via the closed-world audit; the
  audit's no-op revert fails its bypass probes; `bool()/len()/iter()/==` on every `ScratchResult` shape
  raise `TypeError` (self-tested); the four CLI escape shapes (phantom diagnostic, truncated findings,
  wrong summary count, silent `SystemExit`) each redden an EXACT-output CLI arm; and the record/
  CONTRIBUTING agreement is now checked mechanically by the golden suite, self-tested on synthetic bad
  records. Anchors: `tests/revert-battery.py` `_audit_accumulators` / `_audit_bypass_probes` / the four
  `0022` CLI GUARDS; `tests/run-golden.py` `ScratchResult` dunders + protocol self-test, the exact-output
  CLI arms (`_FAIL_IMPROVE` / `_summary` / `EXPECTED_BANNER` / `_FAIL_PARSER`), and
  `_record_problems` / `review_record_consistency`.

  **Pattern acknowledged and closed at the mechanism level (rounds 14–18).** Each earlier round fixed
  the INSTANCES a review named; the review then produced fresh instances of the same class. This round
  removes the class where it recurred: emission-form ENUMERATION is replaced by a closed-world audit
  that refuses what it cannot see; CLI properties are replaced by exact-output equality; loud failure
  replaces call-site convention in `ScratchResult`; and the record's internal consistency moved from
  authorial care into a checked invariant.

**Why this record is now PASS — closed by owner decision after round 19.** Nineteen review rounds ran
(18 independent cold-pass reviews and 1 author self-red-team round). From round 15 on, every finding was
against the TEST HARNESS's self-proof depth — the generator itself has been unchanged and every drift
fixture green since round 14. At round 17 the owner set a stopping rule (reaffirmed at rounds 18 and 19):
when a review returns no REAL GATE ESCAPE — no way for a bad document to pass or a good document to be
blocked — the bounded findings are fixed, the unbounded one is disclosed as a residual, and the PR ships.
Round 19 is exactly that case: its bounded findings are fixed above (row 19), and the one unbounded item
— rename-invariance of the branch-level sweep — is a disclosed residual with its name-independent
curated-guard backstop re-verified. The verdict below is therefore the owner's recorded decision under
that rule, not a claim that an independent review returned zero findings; the full nineteen-round
history above is the evidence trail.

---

Verdict: PASS
