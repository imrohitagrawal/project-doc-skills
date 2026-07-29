# Gate-review verdict — PR #12 · feat/skill-count-generate (issue #7)

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: PR #12 · `feat/skill-count-generate` (issue #7)
- Diff range: e4bc544..HEAD (current head; the PR has been reviewed over FIFTEEN rounds — see below)
- Gate-layer paths changed: `.github/gate-paths`, `.github/workflows/release-gate.yml`, `CONTRIBUTING.md`,
  `build-skills.sh`, `generate-skill-enumerations.py`, `lint-skill-count.py` (DELETED), `release-gate.sh`,
  `skills-order`, `tests/run-golden.py`, `tests/revert-battery.py`
- Reviewers / instruments: **fifteen independent review rounds**. Rounds 1–11 paired a same-model
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
| 15 | (this head) | pending | GPT: the real `--check` CLI verdict path was outside golden and the battery; the finding-branch sweep counted CRASHES as reddens and mis-labeled its denominator (`_inline_text` data appends); the source-of-truth producers were not locked to their files; the raw-HTML ban + retired-marker allowlist were fixtured on one file only; `_preceding_visible`'s heading arm and both `_norm` call sites were unproven. | *(this round)* end-to-end CLI fixture + main mutants; sweep requires RED + semantic inventory; producer file-dependency fixtures; both-files raw-HTML + retired-marker fixtures; heading + normalized anchor fixtures |

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

`tests/run-golden.py` carries the `skill_enumerations` battery (**199/199** assertions green), and
`tests/revert-battery.py` proves the fixtures BITE rather than merely existing: it stubs each of the
**53** guards on a full-repo copy and requires the golden suite to go red **via the guard's DECLARED
assertion** (`expect_fx`) — a mutant that reddens only some unrelated assertion is rejected as
MIS-TARGETED — **53/53 bite** — after first asserting its own harness ran green. It also derives
finding-branch coverage from the AST: every `raise MarkerError` and every verdict-accumulator append
reverted to a no-op must redden golden as an ASSERTION, not a crash (**21/21**), and every stub's
declared `covers` must equal the units it actually mutates (**53/53** provenance-clean). `CONTRIBUTING`
requirement (ii) mandates running it before requesting a review, and requires a new guard to arrive with
its stub.

## Findings

- none outstanding in the author's own verification — every round-15 finding is resolved and locked by a
  fixture proven to bite (`tests/revert-battery.py`: 53/53 stubs + 21/21 finding-branches). Anchors for
  this round's fixes: `tests/run-golden.py` `_cli_check` (end-to-end CLI verdict), the `0019` fixture
  block (source-of-truth, both-files raw-HTML, retired markers, heading/normalized anchors), and
  `tests/revert-battery.py` `_finding_branches` (semantic inventory) + the sweep's RED requirement + the
  eleven `0019` GUARDS. A 5-lens adversarial self-red-team then found two issues in the fixes themselves
  (the inventory oracle only pinned inclusion for `check()`; the new broad `except` in `scratch()` let a
  crash pass a bare `len>=1` assertion) — both fixed (oracle now pins every verdict-append function; a
  `genuine()` helper rejects the crash sentinel). The resolution has NOT yet been independently reviewed,
  so the record stays BLOCK.

**Why this record is nevertheless BLOCK:** the most recent independent review (round 15) returned BLOCK,
and the fixes answering it have **not yet been reviewed by anyone independent**. Under the rule this
repository exists to enforce — a green build is necessary, not sufficient, and the author's own
verification is not a review — the verdict cannot flip on the author's say-so. It flips only when an
independent round-16 review (a different-vendor cold pass, per the Independence note above) examines the
current head and finds it clean.

---

Verdict: BLOCK
