# Gate-review verdict — feat/skill-count-lint (PR #2: the skill-enumeration guard, Rounds 1–4)

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: PR #2 — feat/skill-count-lint @ 6f66dfa (imrohitagrawal/project-doc-skills)
- Diff range: origin/main...feat/skill-count-lint (HEAD 6f66dfa)
- Gate-layer paths changed: lint-skill-count.py (matched `lint-*.py`), tests/run-golden.py (matched `tests/`), build-skills.sh, release-gate.sh; plus the non-gated scaffolding the lint guards (README.md, per-skill-review-prompt.md) and CHANGELOG.md
- Reviewers / instruments: Round 4 — single reviewer, HONESTY + COMPLETENESS lens. Lint reconstructed at 6f66dfa and run live (clean / plain-drift / silent-pass cases); golden fixtures replayed (72/72).
- Independence limit, stated honestly: one reviewer in one environment — not a multi-lens or different-vendor pass. Rounds 1–3 were the prior independent reviews recorded below; this round audits the HONESTY of the 6f66dfa reframe, not fresh decoy-hunting, and explicitly does NOT re-block on the disclosed, accepted markup-decoy gap.

## Replay the real failure

The gate exists to catch ACCIDENTAL skill-enumeration drift — the `b65041f` incident where the suite's skill set drifted across SEVERAL scaffolding sites at once (README skill table, repo tree, improve-order list; the per-skill prompt's pick-list and attachment table; plus a stale "all seven" count) and shipped uncaught, because README.md and per-skill-review-prompt.md are root scaffolding invisible to validate_skill.py, the render/placeholder lints, and check-version.py. An earlier cut of this very lint printed "clean" while inspecting only 2 of its 5 sites — the guard under-covered its own target.

Reconstructed lint-skill-count.py @ 6f66dfa and replayed the in-scope failures live against the real docs (scratch copy, `--strict`):
- real docs -> `clean` / exit 0 (control).
- a plainly-broken visible list (drop `publish-mirror`, NO hidden decoy) -> exit 1 at ALL FIVE sites, and a wrong suite-count phrase (`eight`->`seven`) -> exit 1 — six independent live edits, each caught.
- the four prior decoy families (Rounds 1–3) stay closed AND fixture-locked in tests/run-golden.py: duplicate-anchor (1b) at tests/run-golden.py:490 and tests/run-golden.py:494; distant-decoy / reformatted-adjacent (1c) at tests/run-golden.py:492 and tests/run-golden.py:496 plus the full-decoy-run rejection at tests/run-golden.py:474; same-paragraph at tests/run-golden.py:498 and tests/run-golden.py:502; no-blank-tail at tests/run-golden.py:500 and tests/run-golden.py:504. Full golden suite: 72/72.
- the OUT-of-scope class was reproduced as a SILENT PASS to confirm the disclosure is accurate: a full canonical run hidden in an HTML comment immediately after the `producers before consumers` anchor makes the lint print `clean` / exit 0 while the visible improve-order list is missing `publish-mirror`; and a single decoy phrase merely CONTAINING the `below with one of` substring (real anchor reworded away) does the same for the pick-list. Both disclosed classes actually bypass the lint — the disclosure is neither understated nor fabricated. This class is excluded from coverage by the honest reframe and is NOT counted below.

Coverage: 21/21 in-scope replay assertions — the 2-of-5 under-coverage incident across all 5 enumeration sites (tests/run-golden.py:437) + the count-phrase drift in word and digit form (tests/run-golden.py:448) + 5 accidental-reformat fail-closed cases (tests/run-golden.py:466) + the 2 full-decoy-run rejections (tests/run-golden.py:479) + the 8 post-anchor decoy-family rejections (tests/run-golden.py:507) — all pass and are fixture-locked. This is 100% of the reframed (accidental-drift) scope. The single out-of-scope class (markup-hidden / substring-anchor decoy) is excluded by the reframe and tracked for the generate-don't-lint redesign; it is reproduced above only to confirm the disclosure, not as a coverage gap.

## Coverage vs advertising

Round 4's actual question: does every place that states the lint's guarantee now match what the code does? Read all of them, and the answer is yes — claim == reality, with the gap disclosed:
- module docstring (lint-skill-count.py:24) scopes the claim to "ACCIDENTAL drift," lists exactly the closed families, then states "KNOWN LIMITATION (not closed)" (lint-skill-count.py:32) naming the markup classes (HTML comment / code span / reference definition) and the substring-anchor class, and "NOT an adversarially-hidden decoy."
- the `_anchored_run` docstring carries the same disclosure at the function that owns the gap (lint-skill-count.py:124).
- the build script describes the lint factually with no adversarial-proofness claim (build-skills.sh:106).
- CHANGELOG [1.2.0] has a "Scope (honest):" paragraph — guards accidental drift, "It is not adversarially-decoy-proof," discloses both classes, points to the redesign (CHANGELOG.md:54).
- README carries NO blurb describing the lint's guarantee, so there is nothing there to overclaim.

No residual overclaim: there is no "no known decoy class remains" and no implied un-bypassability anywhere. The only use of the word "decoy-proof" is a test label scoped to one SPECIFIC closed family — the full-decoy-run-elsewhere best-match defeat — at tests/run-golden.py:471 (asserted at tests/run-golden.py:479 and tests/run-golden.py:481); it is accurate for that case and is not a blanket guarantee, and it is not a guarantee-bearing site. The live silent-pass reproduction confirms the lint IS bypassable exactly as disclosed.

## Self-description drift

The reframe altered the lint's guarantee wording in three places — the module docstring, the `_anchored_run` docstring, and CHANGELOG [1.2.0] — and all three were updated and are mutually consistent. The canonical skill set is single-sourced from `skills/<name>/` (lint-skill-count.py:74): the lint DERIVES the roster, it does not duplicate it in prose.
- MINOR drift: README.md:103 summarizes the release gate as "the render-restatement and placeholder lints" and omits the skill-count lint, even though build-skills.sh:111 and release-gate.sh:44 both run it `--strict`. This is an under-statement of the gate (not an overclaim of the lint). Tidy the README prose when convenient.

## Fixture requirement

The in-scope behavior is fixture-locked with synthetic inputs (alpha/beta/gamma, so it never couples to the live README) at tests/run-golden.py:411: 5 site extractors, the count phrases, 5 fail-closed reformats, 2 full-decoy-run rejections, and 8 post-anchor decoy-family rejections — 21 assertions, all green. Correctly, there is NO fixture asserting the markup-hidden decoy is closed — it is not closed, and a false "closed" fixture would itself be the overclaim this round exists to catch.
- MINOR / disclosed exception: the `b65041f` REAL-incident fixture (reconstructing the actual stale enumerations the incident fixed) is owed and openly logged at CONTRIBUTING.md:142. The present fixtures are synthetic unit-locks, not the real-incident replay. Acceptable as a tracked exception (the lint lives on an unmerged PR stack); land the real-incident fixture with the redesign, or immediately on merge.

## Findings

Severity-ranked. A BLOCKER here would be a residual overclaim, an inaccurate/incomplete disclosure, or the lint failing its CLAIMED accidental-drift job — none of which is present. The disclosed markup-decoy gap is accepted (out of scope) and is explicitly NOT a finding.

### Round 1 — distant / duplicate decoy (prior review; FIXED)
- **[MAJOR] (silent pass)** a BROKEN visible run with a FULL canonical decoy run elsewhere, and a DUPLICATE introducing anchor, were selected by the earlier best-match extractor and masked a broken list. **Resolved:** position-scoped, single-occurrence anchored run (lint-skill-count.py:119; the `len(occurrences) != 1` fail-closed at lint-skill-count.py:130). **Fixture-locked:** tests/run-golden.py:474 (full-decoy-run), tests/run-golden.py:490 and tests/run-golden.py:494 (duplicate anchor).

### Round 2 — no-blank-tail decoy (prior review; FIXED)
- **[MAJOR] (silent pass)** a decoy run on the line immediately after a no-blank-line tail was picked up. **Resolved:** the immediate-adjacency run rule (lint-skill-count.py:134). **Fixture-locked:** tests/run-golden.py:500 and tests/run-golden.py:504.

### Round 3 — immediate-adjacency / same-paragraph (prior review; CLOSED those)
- **[MAJOR] (silent pass)** a same-paragraph decoy after the anchor. **Resolved:** the run must begin immediately after the single anchor with only whitespace/markup/punctuation before it (lint-skill-count.py:134; commits bedb79d, b821e72). **Fixture-locked:** tests/run-golden.py:498 and tests/run-golden.py:502.

### Round 4 — HONESTY of the 6f66dfa reframe (this round)
- **[accepted — NOT a finding]** markup-hidden-decoy + substring-anchor silent pass — reproduced live at 6f66dfa, disclosed verbatim at lint-skill-count.py:32, lint-skill-count.py:124, and CHANGELOG.md:55. Out of scope by the honest reframe; redesign tracked. Not re-blocked, by design.
- **[MINOR] (tracking accuracy)** "tracked: feat/skill-count-generate" at lint-skill-count.py:37, lint-skill-count.py:128, and CHANGELOG.md:59 names a follow-up branch that does NOT exist on origin (no branch, PR, or issue as of 6f66dfa). "Tracked" currently means committed-to in writing only. **Fix:** cut the branch / open a tracking issue, or soften the wording to "planned."
- **[MINOR] (self-description)** README.md:103 omits the skill-count lint from the release-gate summary though it is run (build-skills.sh:111, release-gate.sh:44).
- **[MINOR / disclosed]** the `b65041f` real-incident fixture is owed (CONTRIBUTING.md:142); current coverage is synthetic unit-locks at tests/run-golden.py:411.

No BLOCKER or MAJOR remains open in the change under review. The reframe is HONEST (no residual overclaim in any guarantee-bearing site) and COMPLETE (both gap classes — markup-hidden and substring-anchor — disclosed in the docstring, the `_anchored_run` docstring, and the CHANGELOG), and the lint's claimed accidental-drift job HOLDS at all five sites with the four prior decoy families closed and fixture-locked.

---

Verdict: PASS
