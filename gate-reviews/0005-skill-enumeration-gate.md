# Gate-review verdict — PR #12 · feat/skill-count-generate (issue #7)

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: PR #12 · `feat/skill-count-generate` (issue #7)
- Diff range: e4bc544..ed1454b (current head; the PR was reviewed over seven rounds — see below)
- Gate-layer paths changed: `.github/gate-paths`, `.github/workflows/release-gate.yml`, `CONTRIBUTING.md`,
  `build-skills.sh`, `generate-skill-enumerations.py`, `lint-skill-count.py` (DELETED), `release-gate.sh`,
  `skills-order`, `tests/run-golden.py`, `tests/revert-battery.py`
- Reviewers / instruments: **seven independent review rounds**, each a same-model (Claude) blind
  multi-lens pass PLUS a different-vendor (GPT) cold pass on the same head, with the author reproducing
  every load-bearing finding against the real code before acting. Round 7 additionally produced a
  committed `tests/revert-battery.py`.
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
that is not an exact permutation exits 1. The fail-open class is replayed too: a count phrase reworded
away, suffixed, prefix-substring-evaded, or carrying a non-numeric token now produces a finding rather
than a silent skip.

Coverage: 5/5 enumeration sites

## Coverage vs advertising

The clean banner asserts exactly four things — marked enumerations match `skills-order` in the parsed
Markdown; governed docs contain no raw HTML except the comment markers; count phrases consistent;
drift-catcher scope pointer — and each maps to code that runs unconditionally in `check()`. The
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

`tests/run-golden.py` carries the `skill_enumerations` battery (133/133 assertions green), and
`tests/revert-battery.py` proves the fixtures BITE rather than merely existing: it stubs each of the
**19** guards on a full-repo copy and requires the golden suite to go red — **19/19 bite** — after first
asserting its own harness ran green. `CONTRIBUTING` requirement (ii) now mandates running it before
requesting a review, and requires a new guard to arrive with its stub.

## Findings

- none — every finding from rounds 1–7 is resolved, each resolution locked by a fixture proven to bite
  (`tests/revert-battery.py`, 19/19). Anchors for the last round's fixes:
  `generate-skill-enumerations.py:59` (number-only count slot), `generate-skill-enumerations.py:66`
  (whole-template boundaries), `generate-skill-enumerations.py:186` (marker identity allowlist),
  `tests/run-golden.py:634` (marker-branch unit locks), `tests/revert-battery.py:60` (harness sanity).

**Why this record is nevertheless BLOCK:** the most recent independent review (round 7) returned BLOCK,
and the fixes answering it have **not yet been reviewed by anyone independent**. Under the rule this
repository exists to enforce — a green build is necessary, not sufficient, and the author's own
verification is not a review — the verdict cannot flip on the author's say-so. It flips only when an
independent round-8 review (same-model lenses + a different-vendor cold pass, per the Independence note
above) examines the current head and finds it clean.

---

Verdict: BLOCK
