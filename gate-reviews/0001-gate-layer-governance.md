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
  round 2 — author re-verification via the new run-golden fixtures + a same-model fresh-clone cold pass
  (Round 3 below); round 3 of fixes — a **genuine different-VENDOR** cold pass (a non-Anthropic frontier
  model, run blind by the owner; Round 4 below). Every lens ran the script and the release gate.
- Independence limit, stated honestly: an in-environment different-*model* pass was attempted (Sonnet,
  Fable, Haiku) but **none was accessible as a subagent here**, so the round-2 cold pass was same-model
  (Opus) — *context* isolation, not weight decorrelation. It still found a BLOCKER + 3 MAJORs (Round 3).
  The owner then ran the real cross-vendor pass, which found **more** that same-vendor passes missed
  (Round 4) — the empirical case for decorrelation. Net: each off-axis instrument caught defects the
  previous tier did not.

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

(Line numbers below are as of this PR's final commit; the named symbols are the durable reference.
`./release-gate.sh` 5/5, golden 43/43.)

### Round 1 — initial self-application, all BLOCKER/MAJOR resolved

- **[BLOCKER] (enforcement-soundness)** The PR could not satisfy its own `gate-review` — no verdict was
  committed — and the docs cited a bootstrap verdict that did not exist. **Resolved:**
  `gate-reviews/0001-gate-layer-governance.md:1` is that record; `gate-review-check.py --base
  origin/main --head HEAD` → exit 0.
- **[MAJOR] (honesty)** The honest ceiling omitted the self-neutering bypass (checker runs from PR
  head). **Resolved:** `CONTRIBUTING.md:106` enumerates it as bypass route #3 with its mitigation.
- **[MAJOR] (coverage gap)** `shared/ci/`, `docs/SETTINGS.md`, `gate-reviews/TEMPLATE.md` were outside
  the gated set. **Resolved:** `.github/gate-paths:41` + `.github/CODEOWNERS:22` add them.
- **[MAJOR] (code correctness)** the coverage regex scanned the whole document and accepted `0/0` / a
  date. **Resolved:** `gate-review-check.py:81` (`COVERAGE_LINE_RE`) + replay-section scoping require a
  real `Coverage: N/M` (M>0, N≤M).
- **[MAJOR] (code correctness)** `Verdict: PASS` matched anywhere; `PASS-WITH-NITS` passed; a
  co-committed BLOCK was ignored. **Resolved:** `gate-review-check.py:85` (last-line, exact token) +
  `gate-review-check.py:248` (`decide_verdicts` blocks on any BLOCK/FAIL).
- **[MAJOR] (test discipline)** the linchpin shipped untested. **Resolved:** `tests/run-golden.py:281`
  (`gate_review_check`).
- **[MINOR] (fail-open)** an empty PR diff returned PASS. **Resolved:** `gate-review-check.py:153`
  (base==head) and `gate-review-check.py:324` (empty CI diff) fail closed (exit 2).
- **[NIT]** `gate-review-check.py:64` imports `NoReturn`; the workflow "EVERY/ALWAYS" wording made precise.

### Round 2 — the owner's 4 follow-ups (additions)

- **ADDITION 1 — self-inclusion (load-bearing) — VERIFIED.** The enforcement's own files are gate-layer
  (`.github/gate-paths:51` self-includes `.github/`; the prompt, checker, policy by name), proven by the
  `tests/run-golden.py:310` self-inclusion assertion. Single-sourcing alone was not sufficient; this is.
- **ADDITION 2 — proportionality — ADDED.** `gate-review-prompt.md` "Proportionality" section +
  `gate-review-check.py:100` (`TIER_LINE_RE`): a light tier for docs-only non-behavioral changes,
  defaulting to full.
- **ADDITION 3 — evidence-over-stamp — ADDED.** `gate-review-check.py:106` (`FINDING_ANCHOR_RE`) requires
  file:line findings or an explicit `none`; coverage stays replay-scoped. This very verdict was caught by
  that rule while it lacked anchors, then fixed — the check ate its own dogfood.
- **ADDITION 4 — different-vendor cold pass — DONE.** Ran same-model first (no alternate model accessible
  here → Round 3), then the owner ran the real cross-vendor pass → Round 4.

### Round 3 — same-model cold pass found these in the round-2 additions; all fixed and fixture-locked

- **[BLOCKER] (evidence defeated)** `FINDING_ANCHOR_RE` was `\S+:\d+`, so a clock time ("2:30") / port /
  version satisfied the "file:line" rule. **Resolved:** `gate-review-check.py:106` requires a real path
  anchor (a `/` or a `.ext` of 2–8 letters); locked by the `time '2:30'` fixture.
- **[MAJOR] (section hijack)** a `### decoy` subsection could stand in for the real `## Findings` /
  `## Replay`. **Resolved:** `REQUIRED_SECTIONS` matches top-level (`^#{1,2}`) only
  (`gate-review-check.py:88`); locked by the `### decoy` fixture.
- **[MAJOR] (tier override)** `effective_tier` was last-wins. **Resolved:** `gate-review-check.py:183` —
  light only if it is the SOLE tier; mixed → full; locked by the `mixed Tier` fixture.
- **[MAJOR] (light unverifiable)** a behavioral change could self-declare `Tier: light`. **Resolved:**
  `gate-review-check.py:214` + `gate-review-check.py:284` refuse light unless every changed gate path is
  docs-only (`*.md`); locked by the `allow_light=False` fixture.
- **[MINOR] (none too loose)** `FINDINGS_NONE_RE` matched "no blockers" in prose. **Resolved:**
  `gate-review-check.py:107` matches a leading `none` / `no findings` only.
- **[NIT]** self-inclusion test now pins `.github/CODEOWNERS` (`tests/run-golden.py:308`).

### Round 4 — the genuine different-VENDOR cold pass (owner-run); all addressed

The non-Anthropic reviewer could not `git clone` (DNS blocked) so it read the branch via web connectors
and reproduced the checker locally; I verified each finding against HEAD before fixing.

- **[MAJOR] (bulleted-tier bug — the standout catch)** the verdict TEMPLATE writes `- Tier: light`
  (bulleted), but the tier/justification/none regexes were unbulleted, so the template's OWN light path
  was silently ignored and defaulted to full. Both same-model passes missed this; the different-vendor
  pass caught it. **Resolved:** every line-anchored field tolerates an optional `- `/`* ` bullet
  (`gate-review-check.py:81`–`:107`); locked by a fixture that uses the exact TEMPLATE bullet form.
- **[MAJOR] (single-source overclaim)** `.github/gate-paths` claimed the prose "points here rather than
  re-listing", but `CONTRIBUTING.md` and `gate-review-prompt.md` re-listed the paths — the very
  self-description drift the layer fights. **Resolved:** the prose lists are now labelled *illustrative,
  non-authoritative* and `.github/gate-paths:5` no longer claims otherwise.
- **[MAJOR] (coverage gap)** `gate-reviews/README.md` (which asserts the verdict contract) was ungated.
  **Resolved:** added to `.github/gate-paths` + `.github/CODEOWNERS`; `CHANGELOG.md` and the verdict
  records are documented as deliberate exclusions (gate-paths "Deliberately NOT gated" block).
- **[BLOCKER → downgraded to disclosed residual] (a filled fake verdict passes)** a fully-filled
  fabricated verdict satisfies the shape check. This is the **good-faith residual already disclosed** in
  the honest ceiling, not a new hole — no shape check can verify a human did the work. **Addressed two
  ways:** (a) the CLAIM is tightened — the check enforces a *structured, evidence-bearing record*, not
  proof of a good-faith review (`CONTRIBUTING.md` headline + honest ceiling); (b) the floor is raised —
  unfilled template placeholders are rejected (`gate-review-check.py:112` + `:202`), so the realistic
  lazy stamp (copy template, flip Verdict) fails. A determined fabrication remains irreducible, stated.
- **[MINOR] (ruleset stated as active)** `CONTRIBUTING.md` read as if the branch ruleset were enforced;
  it is a manual step. **Resolved:** worded conditional ("once you apply it … until then, advisory") +
  the verify command in `docs/SETTINGS.md`.

- **Accepted with rationale (not defects):** the shape-check verifies evidence *shape*, not *good faith*
  (`CONTRIBUTING.md` honest ceiling); `gate-review-check.py:144` `lint-*.py` basename match errs *safe*
  (false-gate, never missed-gate), kept deliberately. **Empirical decorrelation result:** same-model
  passes caught Rounds 1–3; only the different-vendor pass caught the bulleted-tier bug — the case for
  the cross-vendor instrument, in this verdict's own history.

---

Verdict: PASS
