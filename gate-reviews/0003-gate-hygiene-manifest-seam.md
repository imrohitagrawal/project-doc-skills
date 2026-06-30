# Gate-review verdict — PR #9 (fix/gate-hygiene-manifest-seam)

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: PR #9 — fix/gate-hygiene-manifest-seam
- Head: 38adc46  (reviewed HEAD; `git rev-parse HEAD` = 38adc46cb8698e90e46e92b8a942fc5ca27a183b)
- Diff range: 61c0072...38adc46
- Gate-layer paths changed: (the list gate-review-check.py printed)
    - check-version.py        (matched: check-version.py)
    - gate-review-check.py    (matched: gate-review-check.py)
    - pkgtools.py             (matched: pkgtools.py)
    - tests/run-golden.py     (matched: tests/)
  (CHANGELOG.md, README.md, dist/MANIFEST.sha256 are NOT gated — they describe, they do not enforce.)
- Reviewers / instruments: one model running the A–D lenses, with code-grounded execution as the
  off-axis instrument — two real `./build-skills.sh` runs, two no-op-revert break-tests, and direct
  calls into the real `matches_gate` / `light_admissible` / `evaluate_verdicts` functions. The PR's own
  history already carried a different-vendor cold pass (it caught the over-broad predicate, commit
  a1cbeea, and the unsampled shared/ci/ subtree, commit 38adc46); this review re-verified those fixes
  against source by running them, rather than re-spawning a vendor pass.
- Independence limit honestly stated: this is context isolation + execution grounding, NOT model-weight
  decorrelation. A same-model lens shares its own blind spots; the decorrelation that found these two
  defects was the earlier different-vendor pass, which this review confirms but did not reproduce.
- NOTE — head binding is manual: gate-review-check.py does not yet machine-bind a verdict to the head
  it reviewed (logged follow-up). The `Head: 38adc46` line above is the manual binding. A prior
  cross-vendor pass mistakenly reviewed the stale cbfd9ae; this pass confirmed HEAD = 38adc46 before
  reviewing anything.

## Replay the real failure

This PR changes the enforcement engine on two axes; each has a distinct real failure.

**(1) Light-tier seam — a gate-path change reaching main via the LIGHT path when it must take the
FULL crew.** The real failure class is the archetype this layer exists for: a guard that covers some
sites of its class while a re-broadening slips through an unsampled one (the "2 of 5" trap). Concretely,
the predicate `light_admissible` was open-by-default — `all(p.endswith(".md") and p not in
BEHAVIORAL_GATE_DOCS ...)` (gate-review-check.py, old line ~301) — so any gated markdown that was NOT in
the four-item behavioral-docs set was silently admitted to the light path, even though it lives in a
gate-layer subtree. The sites this failure can occur in are exactly the SUBTREE rules in
`.github/gate-paths` that can contain markdown. I enumerated them live from the canonical file: they are
`tests/`, `.github/`, and `shared/ci/` (3). The fix replaces the denylist with a closed allow-list,
`LIGHT_ADMISSIBLE_GATE_PATHS = frozenset({"gate-reviews/README.md"})` (gate-review-check.py:81), and
`light_admissible` is now `set(gate_paths) <= LIGHT_ADMISSIBLE_GATE_PATHS` (gate-review-check.py:303).
I drove the REAL `matches_gate` + `light_admissible` against a markdown probe under each subtree: every
one is classified as a gate path AND refused the light path (forced to full); the inert allow-listed
`gate-reviews/README.md` is the only path that stays light-admissible. The fixture
(`tests/run-golden.py`, the `light_cases` unit block and the `gate_review_seam` end-to-end block) covers
all three subtrees — `tests/`, `.github/`, and `shared/ci/`. Commit 38adc46 is the one that added the
`shared/ci/README.md` rows (the previously-unsampled subtree); at parent a1cbeea coverage was 2 of 3.

Not circular — proven by break-test: reverting `light_admissible` to the old open-by-default predicate
turns the suite red with 9 failures, including `light_admissible(['shared/ci/README.md']) -> got True
want False` and the matching seam row, plus the `tests/` and `.github/` rows. A synthetic mutation of an
already-guarded line is not what was used; the real reverted predicate is.

**(2) Manifest churn — the integrity manifest flipping on a content-free change.** The real failure is
the `# source-commit: <HEAD>` line, which recorded the build-time HEAD — always the parent of the commit
that carries the manifest — so it changed on every build and produced spurious manifest diffs even when
no hashed content changed. The fix removes the field and the `_git_commit`/`subprocess` machinery
(pkgtools.py). I reproduced the corrected invariant directly: two back-to-back `./build-skills.sh` runs
on identical content produced a byte-identical manifest (both `c5b8293e34add4…`), and the committed
`dist/MANIFEST.sha256` at HEAD matches a fresh deterministic build byte-for-byte. The fixture
(`tests/run-golden.py`, `manifest_byte_stability`) drives the real `write_manifest` twice and asserts
both byte-identity and the absence of any commit/date token. Both assertions are load-bearing and cover
different volatility shapes; break-test confirms it — re-adding a static `# source-commit:` line keeps
byte-identity GREEN (the field is constant within one process) but trips the `no build-commit field`
regex RED. Byte-identity alone would have missed the revert; the regex is what catches it.

Coverage: 3/3 gated-markdown subtrees (tests/, .github/, shared/ci/)   <!-- the light-tier seam, the
centerpiece failure class; manifest stability separately proven by 2 real builds + a break-test -->
All three subtrees the over-broad predicate could leak are covered. No site is silently ignored.

## Coverage vs advertising

The advertised contract — stated in the gate-paths prose, the prompt, and the docstrings — has always
said the sole light-eligible gate path is `gate-reviews/README.md`. The code now matches that exactly: a
closed allow-list of one entry. I checked every place `allow_light` can be set: it is computed in a
single location, `evaluate_verdicts` -> `light_admissible(gate_paths)` (gate-review-check.py:311), and
threaded into `decide_verdicts` -> `shape_problems`. There is no second path that can set it True, so a
gated change cannot reach a clean light verdict except through the one inert doc. No printed
success/clean/PASS string over-claims relative to what the code verifies.

For the manifest half, the success surface is the manifest header itself and the three live
self-descriptions that referenced the dropped field. All were updated in lockstep: `pkgtools.py`'s
module docstring and `write_manifest` comment, `README.md` (the "when built from git, the source commit"
clause is gone), and `check-version.py`'s not-a-git-checkout note (now "the manifest's SHA-256 rows are
the integrity record"). I grepped the whole tree for `source-commit`/`_git_commit`: the only remaining
hits are the regression test (which guards against re-adding it) and CHANGELOG (which describes the
removal). No live or gated description still promises a commit field.

## Self-description drift

This PR does not change any count or set of checks/lints/skills/steps, so there is no hard-coded count
to fall out of sync; the skill-count and render-restatement lints stay green on a full build (8 skills,
5 enumeration sites). The one set that matters here — the gated-markdown subtrees — is NOT duplicated as
a drift-prone literal: `light_admissible` enforces the allow-list, and `matches_gate` reads the subtree
rules live from `.github/gate-paths`. I confirmed the three subtree rules the file actually carries
(`shared/ci/`, `tests/`, `.github/`) are exactly the three the fixture comment names and the fixture
samples. The only place subtree names appear as prose is the fixture's own explanatory comment, which is
test scaffolding, not an enforced second source. The dropped manifest field left no orphan reference
(verified by grep, above).

## Fixture requirement

Both correctness changes ship WITH a regression fixture derived from the real incident, and both
fixtures fail on a no-op revert — I verified this by actually reverting each fix and re-running:

- Light-tier seam: `tests/run-golden.py` `light_cases` (pure `light_admissible`) + `gate_review_seam`
  (end-to-end `evaluate_verdicts` against a temp root). Reverting the allow-list -> 9 reds, including
  every gated-markdown-subtree row. The seam fixture is exhaustive over the three subtrees.
- Manifest stability: `tests/run-golden.py` `manifest_byte_stability`. Re-adding `# source-commit:` ->
  the `no build-commit field` assertion goes red (byte-identity stays green, by design, so both
  assertions are needed).

Full suite: 97/97 assertions pass at HEAD = 38adc46. No fixture is owed; no logged-exception case
applies (these are correctness gates, not pure process/bootstrap mechanisms).

## Findings

none.

Checked, with the file/line or command behind each: the predicate is a closed allow-list
(gate-review-check.py:81, :303) and `allow_light` has exactly one source (gate-review-check.py:311);
`matches_gate` classifies markdown under each of the three subtree rules as gated and `light_admissible`
refuses it (ran the real functions); the fixture covers tests/, .github/, AND shared/ci/ in both the
unit and the end-to-end block, with shared/ci/ added by 38adc46 (2/3 -> 3/3); reverting the predicate
fails 9 assertions including the shared/ci/ rows; the manifest is byte-stable across two real builds
(`c5b8293e…`) and the committed artifact reproduces byte-for-byte; re-adding source-commit fails the
manifest fixture's regex assertion; all live self-descriptions (pkgtools.py, README.md, check-version.py)
were updated and no orphan source-commit reference remains; no check/lint/skill count drifted. No
new silent-pass was found, and the change's claims match what the code does (claim == reality).

---

Verdict: PASS
Every checked invariant holds at the reviewed head, both correctness fixes are backed by fixtures that
fail on revert, and no BLOCKER or MAJOR remains. Reviewed head: 38adc46 (range 61c0072...38adc46).
Report only — landing is the owner's separate act.
