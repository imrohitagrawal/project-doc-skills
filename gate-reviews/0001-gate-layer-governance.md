# Gate-review verdict — feat/gate-layer-governance (the governance change reviews itself)

- Prompt: gate-review-prompt.md v1.0.0
- PR / branch: feat/gate-layer-governance (the first PR reviewed under this policy — self-application)
- Diff range: origin/main...HEAD
- Gate-layer paths changed: .github/ (gate-paths, CODEOWNERS, workflows/gate-review.yml),
  gate-review-check.py, gate-review-prompt.md, gate-reviews/TEMPLATE.md, CONTRIBUTING.md,
  docs/SETTINGS.md, tests/run-golden.py
- Reviewers / instruments: 3 blind same-model lenses in fresh contexts (enforcement-soundness;
  coverage-vs-advertising; convention & code-correctness), each given only the diff + a neutral brief +
  one lens, then an adjudication pass; plus code-grounded verification (every lens ran the script and
  the release gate).
- Independence limit, stated honestly: the three lenses are the same model family in isolated contexts
  — that is *context* isolation, not model-*weight* decorrelation. A different-vendor cold pass (per the
  prompt's "Independence" section) is recommended as an owner-run step before merge; it was not run here.

## Replay the real failure

The two real incidents this governance targets: (1) `lint-skill-count.py` printed `clean` while it
inspected **2 of 5** skill-enumeration sites (it missed the README "improve in this order" list, the
repo-tree, and the per-skill prompt's attachment table — the `b65041f` drift); (2) the third-lint PR
left `release-gate.sh` saying "the two now-active suite lints" while three ran. Neither is fixed *by*
this PR (the lint lives on an unmerged stack; `release-gate.sh` on `main` correctly says "two") — what
this PR must do is make those *classes* impossible to ship unreviewed. It does: `gate-review-prompt.md`
Lens A forces a reviewer to reproduce the real stale state and state `Coverage: N/M` (rejecting a
synthetic mutation of an already-guarded case as circular), and Lens C forces a grep for hard-coded
self-counts. The machine half then refuses to go green for a gate-path change without that recorded.

The reviewers also measured this PR's own gate-path coverage — the analogue of the skill-count "N of M"
— and an early gap (`shared/ci/*`, the docs-as-code gate that ships inside every `.skill`, plus
`docs/SETTINGS.md` and `gate-reviews/TEMPLATE.md`) was found and closed.

Coverage: 21/21 gate-machinery files are matched by `.github/gate-paths` (verified by running
`matches_gate` over the full list). The only gate-adjacent files left out — `shared/house-style.md`
and `shared/render-contract.md` (authoring standards) — are excluded by an explicit, documented
decision, not an oversight.

## Coverage vs advertising

Reviewer B held every claim against the code. The serious finding: the honest-ceiling section listed
only two bypass routes, omitting that the workflow runs `gate-review-check.py` from the PR head, so a PR
editing the checker can neuter it on the default green path. Fixed — the ceiling now enumerates three
routes and names the (attention-not-automation) mitigation. The docstring claim "checks the evidence,
not just a PASS word" was over-strong relative to the regexes; the checks were tightened (below) and the
wording made precise. `gate-review-check.py`'s success line never prints PASS for an unreviewed gate
change (re-verified). No success/clean string now asserts more than the code verified.

## Self-description drift

The change alters the gate layer's own enumeration, so every place that states it was re-synced:
`.github/gate-paths` (canonical), `.github/CODEOWNERS` (mirror), the `CONTRIBUTING.md` prose list, and
`gate-review-prompt.md` were checked to agree; `tests/run-golden.py`'s "What it locks" docstring gained
the new section; the checker docstring's "four lens sections" was corrected to "four lens sections plus
Findings — five required headings" (a 4-vs-5 miscount is exactly this project's thesis). The gate-paths
prose points at the file as canonical rather than re-deriving it, so the machine and the docs cannot
drift.

## Fixture requirement

`gate-review-check.py` is itself a new gate check, so by requirement (ii) it ships **with** its fixture
in this PR: `tests/run-golden.py`'s `gate-review-check` section (10 assertions) locks the path
classifier and the verdict decision, including every rubber-stamp vector the review caught. Deferred and
logged (not built here, per scope): the `lint-skill-count.py` `b65041f` fixture (blocked on the
unmerged PR-#2 stack) and an audit of `lint-placeholders.py` / `check-version.py`.

## Findings

All BLOCKER and MAJOR findings below were resolved in this PR (re-verified by `./release-gate.sh` →
5/5, 30/30 golden assertions, and direct scenario runs of the checker).

- **[BLOCKER] (enforcement-soundness, convention)** The PR could not satisfy its own `gate-review` check
  — no verdict record was committed — and `CONTRIBUTING.md` / `docs/SETTINGS.md` cited a bootstrap
  verdict that did not exist, making the documented rollout impossible. **Resolved:** this file is that
  record; with it, the PR's own `gate-review` clears (verified: exit 0).
- **[MAJOR] (coverage-vs-advertising → honesty)** The honest ceiling omitted the self-neutering vector
  (checker runs from PR head). **Resolved:** disclosed as bypass route #3 with its mitigation.
- **[MAJOR] (coverage gap)** `shared/ci/` (the gate shipped into every `.skill`), `docs/SETTINGS.md`,
  and `gate-reviews/TEMPLATE.md` were outside `.github/gate-paths`. **Resolved:** added (and mirrored to
  CODEOWNERS); coverage now 21/21.
- **[MAJOR] (code correctness)** `COVERAGE_RE` scanned the whole document and accepted `0/0` or a date
  (`6/29`). **Resolved:** the coverage figure must now be a real `Coverage: N/M` line (M>0, N≤M) inside
  the replay section.
- **[MAJOR] (code correctness)** `Verdict: PASS` matched anywhere (a PASS quoted in prose passed a BLOCK
  review), `PASS-WITH-NITS` was accepted, and a co-committed BLOCK was ignored beside a PASS.
  **Resolved:** the *effective* (last) verdict line must be exactly `PASS`, and any BLOCK/FAIL record
  gates regardless of other PASS records.
- **[MAJOR] (test discipline)** The enforcement linchpin shipped with no tests. **Resolved:** the
  `gate-review-check` fixture above (also satisfies requirement (ii) for the new mechanism).
- **[MINOR] (fail-open)** An empty PR diff returned PASS. **Resolved:** in CI mode an empty diff and a
  `base == head` range now fail closed (exit 2).
- **[NIT]** `NoReturn` annotation now imported; the workflow "EVERY/ALWAYS" wording made precise.
- **Accepted with rationale (not defects):** the shape-check verifies evidence *shape*, not *good
  faith* (stated plainly in the ceiling); same-model review is context-isolation only (different-vendor
  pass recommended); `lint-*.py` matching a nested basename errs *safe* (false-gate, never missed-gate),
  kept deliberately.

---

Verdict: PASS
