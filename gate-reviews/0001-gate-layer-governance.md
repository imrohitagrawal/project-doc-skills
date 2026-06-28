# Gate-review verdict — feat/gate-layer-governance (the governance change reviews itself)

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: feat/gate-layer-governance (the first PR reviewed under this policy — self-application)
- Diff range: origin/main...HEAD
- Gate-layer paths changed: .github/ (gate-paths, CODEOWNERS, workflows/gate-review.yml),
  gate-review-check.py, gate-review-prompt.md, gate-reviews/TEMPLATE.md, CONTRIBUTING.md,
  docs/SETTINGS.md, tests/run-golden.py
- Reviewers / instruments: round 1 — 3 blind same-model lenses in fresh contexts
  (enforcement-soundness; coverage-vs-advertising; convention & code-correctness) + an adjudication
  pass; round 2 (the owner's 4 follow-ups) — author re-verification via the new run-golden fixtures,
  plus a different-*model* cold pass (Anthropic Sonnet, blind, worktree-isolated) recorded under
  Findings → Round 2 → ADDITION 4. Every lens ran the script and the release gate (code-grounded).
- Independence limit, stated honestly: round 1 was same-model (context isolation, not weight
  decorrelation); the Sonnet pass is **different-weights, same vendor** — better, but still not a true
  cross-vendor pass. A non-Anthropic cold pass remains the owner's recommended step (the exact prompt is
  in the handoff); a different *vendor* was not runnable in this environment.

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

### Round 1 — all BLOCKER/MAJOR resolved (re-verified: `./release-gate.sh` 5/5, golden 36/36)

- **[BLOCKER] (enforcement-soundness)** The PR could not satisfy its own `gate-review` — no verdict was
  committed — and the docs cited a bootstrap verdict that did not exist. **Resolved:**
  `gate-reviews/0001-gate-layer-governance.md:1` is that record; `gate-review-check.py --base
  origin/main --head HEAD` → exit 0.
- **[MAJOR] (honesty)** The honest ceiling omitted the self-neutering bypass (checker runs from PR
  head). **Resolved:** `CONTRIBUTING.md:90` enumerates it as bypass route #3 with its mitigation.
- **[MAJOR] (coverage gap)** `shared/ci/`, `docs/SETTINGS.md`, `gate-reviews/TEMPLATE.md` were outside
  the gated set. **Resolved:** `.github/gate-paths:41` + `.github/CODEOWNERS:22` add them (coverage 21/21).
- **[MAJOR] (code correctness)** the coverage regex scanned the whole document and accepted `0/0` / a
  date. **Resolved:** `gate-review-check.py:77` (`COVERAGE_LINE_RE`) + replay-section scoping require a
  real `Coverage: N/M` (M>0, N≤M).
- **[MAJOR] (code correctness)** `Verdict: PASS` matched anywhere; `PASS-WITH-NITS` passed; a
  co-committed BLOCK was ignored. **Resolved:** `gate-review-check.py:81` (last-line, exact token) +
  `gate-review-check.py:216` (`decide_verdicts` blocks on any BLOCK/FAIL).
- **[MAJOR] (test discipline)** the linchpin shipped untested. **Resolved:** `tests/run-golden.py:281`
  (`gate_review_check`).
- **[MINOR] (fail-open)** an empty PR diff returned PASS. **Resolved:** `gate-review-check.py:140`
  (base==head) and `gate-review-check.py:289` (empty CI diff) fail closed (exit 2).
- **[NIT]** `gate-review-check.py:63` imports `NoReturn`; the workflow "EVERY/ALWAYS" wording made precise.

### Round 2 — the owner's 4 follow-ups

- **ADDITION 1 — self-inclusion (load-bearing) — VERIFIED.** The enforcement's own files are gate-layer
  (`.github/gate-paths:51` self-includes `.github/`; the prompt, checker, policy by name), proven by the
  `tests/run-golden.py:310` self-inclusion assertion. Single-sourcing alone was not sufficient; this is.
- **ADDITION 2 — proportionality — ADDED.** `gate-review-prompt.md` "Proportionality" section +
  `gate-review-check.py:94` (`TIER_LINE_RE`): a light tier (single reviewer; `Coverage: N/A` + a
  justification) for declared non-behavioral changes, defaulting to full. Locked by 3 tier fixtures.
- **ADDITION 3 — evidence-over-stamp — ADDED.** `gate-review-check.py:98` (`FINDING_ANCHOR_RE`) requires
  file:line findings or an explicit `none`; coverage stays replay-scoped. This very verdict was caught
  by that rule while it lacked anchors, then fixed — the check ate its own dogfood.
- **ADDITION 4 — different-model cold pass — run against this committed branch; result appended in a
  follow-up commit to this verdict.** (It reviews the pushed code, so it cannot precede the commit.)

- **Accepted with rationale (not defects):** the shape-check verifies evidence *shape*, not *good faith*
  (`CONTRIBUTING.md` honest ceiling); decorrelation here is same-vendor only (cross-vendor pass is the
  owner's step); `gate-review-check.py:131` `lint-*.py` basename match errs *safe* (false-gate, never
  missed-gate), kept deliberately.

---

Verdict: PASS
