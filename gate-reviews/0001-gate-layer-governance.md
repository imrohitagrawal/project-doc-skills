# Gate-review verdict — feat/gate-layer-governance (the governance change reviews itself)

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: feat/gate-layer-governance (the first PR reviewed under this policy — self-application)
- Diff range: origin/main...HEAD
- Gate-layer paths changed: .github/ (gate-paths, CODEOWNERS, workflows/gate-review.yml),
  gate-review-check.py, gate-review-prompt.md, gate-reviews/TEMPLATE.md, CONTRIBUTING.md,
  docs/SETTINGS.md, tests/run-golden.py
- Reviewers / instruments: round 1 — 3 blind same-model lenses in fresh contexts
  (enforcement-soundness; coverage-vs-advertising; convention & code-correctness) + adjudication;
  round 2 (the owner's 4 follow-ups) — author re-verification via the new run-golden fixtures, plus a
  fresh-context blind cold pass on a freshly-cloned tree (recorded under Findings → Round 3). Every lens
  ran the script and the release gate (code-grounded).
- Independence limit, stated honestly: a different-*model* pass was attempted (Sonnet, then Fable, then
  Haiku) but **none was accessible in this environment**, so the round-2 cold pass ran on the **same
  model** (Opus) in an isolated fresh clone — that is *context* isolation, **not** weight decorrelation.
  Despite that limit it still found a BLOCKER + 3 MAJORs (Round 3), which is why same-context author
  review is insufficient. A genuine different-vendor cold pass remains the owner's recommended step; the
  exact prompt is in the handoff. (That it was NOT a different-model pass is recorded here rather than
  glossed — the honesty wall applies to this verdict too.)

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
in this PR: `tests/run-golden.py`'s `gate-review-check` section locks the path classifier, self-inclusion,
the review tiers, and the verdict decision, including every rubber-stamp vector the reviews caught.
Deferred and logged (not built here, per scope): the `lint-skill-count.py` `b65041f` fixture (blocked on
the unmerged PR-#2 stack) and an audit of `lint-placeholders.py` / `check-version.py`.

## Findings

### Round 1 — all BLOCKER/MAJOR resolved (re-verified: `./release-gate.sh` 5/5, golden 41/41)

- **[BLOCKER] (enforcement-soundness)** The PR could not satisfy its own `gate-review` — no verdict was
  committed — and the docs cited a bootstrap verdict that did not exist. **Resolved:**
  `gate-reviews/0001-gate-layer-governance.md:1` is that record; `gate-review-check.py --base
  origin/main --head HEAD` → exit 0.
- **[MAJOR] (honesty)** The honest ceiling omitted the self-neutering bypass (checker runs from PR
  head). **Resolved:** `CONTRIBUTING.md:90` enumerates it as bypass route #3 with its mitigation.
- **[MAJOR] (coverage gap)** `shared/ci/`, `docs/SETTINGS.md`, `gate-reviews/TEMPLATE.md` were outside
  the gated set. **Resolved:** `.github/gate-paths:41` + `.github/CODEOWNERS:22` add them (coverage 21/21).
- **[MAJOR] (code correctness)** the coverage regex scanned the whole document and accepted `0/0` / a
  date. **Resolved:** `gate-review-check.py:78` (`COVERAGE_LINE_RE`) + replay-section scoping require a
  real `Coverage: N/M` (M>0, N≤M).
- **[MAJOR] (code correctness)** `Verdict: PASS` matched anywhere; `PASS-WITH-NITS` passed; a
  co-committed BLOCK was ignored. **Resolved:** `gate-review-check.py:82` (last-line, exact token) +
  `gate-review-check.py:235` (`decide_verdicts` blocks on any BLOCK/FAIL).
- **[MAJOR] (test discipline)** the linchpin shipped untested. **Resolved:** `tests/run-golden.py:281`
  (`gate_review_check`).
- **[MINOR] (fail-open)** an empty PR diff returned PASS. **Resolved:** `gate-review-check.py:145`
  (base==head) and `gate-review-check.py:311` (empty CI diff) fail closed (exit 2).
- **[NIT]** `gate-review-check.py:64` imports `NoReturn`; the workflow "EVERY/ALWAYS" wording made precise.

### Round 2 — the owner's 4 follow-ups (additions)

- **ADDITION 1 — self-inclusion (load-bearing) — VERIFIED.** The enforcement's own files are gate-layer
  (`.github/gate-paths:51` self-includes `.github/`; the prompt, checker, policy by name), proven by the
  `tests/run-golden.py:310` self-inclusion assertion. Single-sourcing alone was not sufficient; this is.
- **ADDITION 2 — proportionality — ADDED.** `gate-review-prompt.md` "Proportionality" section +
  `gate-review-check.py:97` (`TIER_LINE_RE`): a light tier (single reviewer; `Coverage: N/A` + a
  justification) for docs-only non-behavioral changes, defaulting to full.
- **ADDITION 3 — evidence-over-stamp — ADDED.** `gate-review-check.py:103` (`FINDING_ANCHOR_RE`) requires
  file:line findings or an explicit `none`; coverage stays replay-scoped. This very verdict was caught by
  that rule while it lacked anchors, then fixed — the check ate its own dogfood.
- **ADDITION 4 — cold pass — DONE (honest caveat in the instruments note):** no alternate model was
  accessible, so it ran same-model in a fresh isolated clone. Its findings are Round 3 below.

### Round 3 — the cold pass found these in the round-2 additions; all fixed and fixture-locked

- **[BLOCKER] (evidence defeated)** `FINDING_ANCHOR_RE` was `\S+:\d+`, so a clock time ("2:30"), a port,
  or a version satisfied the "file:line evidence" rule — a full-tier rubber stamp cleared. **Resolved:**
  `gate-review-check.py:103` now requires a real path anchor (a `/` or a `.ext` of 2–8 letters); locked
  by the `time '2:30'` fixture.
- **[MAJOR] (section hijack)** a `### decoy` subsection carrying a trigger word could stand in for the
  real `## Findings` / `## Replay` section. **Resolved:** `REQUIRED_SECTIONS` matches top-level
  (`^#{1,2}`) only (`gate-review-check.py:84`); locked by the `### decoy` fixture.
- **[MAJOR] (tier override)** `effective_tier` was last-wins, so a stray `Tier: light` overrode the
  template's `Tier: full`. **Resolved:** `gate-review-check.py:175` — light only if it is the SOLE tier;
  mixed → full; locked by the `mixed Tier` fixture.
- **[MAJOR] (light unverifiable)** a behavioral gate change could self-declare `Tier: light` and skip the
  coverage fraction. **Resolved:** `gate-review-check.py:201` + `gate-review-check.py:271` refuse light
  unless every changed gate path is docs-only (`*.md`); locked by the `allow_light=False` fixture.
- **[MINOR] (none too loose)** `FINDINGS_NONE_RE` matched "no blockers" inside prose admitting MAJORs.
  **Resolved:** `gate-review-check.py:104` matches a leading `none` / `no findings` only.
- **[NIT]** the self-inclusion test did not pin `.github/CODEOWNERS`. **Resolved:**
  `tests/run-golden.py:308`. This verdict's anchors were re-pinned after the round-3 line shifts.

- **Accepted with rationale (not defects):** the shape-check verifies evidence *shape*, not *good faith*
  (`CONTRIBUTING.md` honest ceiling); the round-2 cold pass was same-model (no alternate model available)
  — context isolation, not weight decorrelation; `gate-review-check.py:136` `lint-*.py` basename match
  errs *safe* (false-gate, never missed-gate), kept deliberately.

---

Verdict: PASS
