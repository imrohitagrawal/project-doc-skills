# Gate-review verdict — PR #10 (chore/backfill-incident-fixtures)

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: PR #10 — chore/backfill-incident-fixtures
- Head: 2969076  (reviewed HEAD; gh pr view headRefOid = 2969076…; confirmed before reviewing. Supersedes a prior pass on a598fa2, now stale.)
- Diff range: 0739ea0...2969076
- Gate-layer paths changed: (the list gate-review-check.py printed)
    - CONTRIBUTING.md                              (matched: CONTRIBUTING.md — behavioral governance doc)
    - tests/run-golden.py                          (matched: tests/)
    - tests/golden-bad/restated-mapping/SKILL.md   (matched: tests/)
    - tests/golden-bad/unresolved-placeholder.md   (matched: tests/)
  (CHANGELOG.md is NOT gated — it describes, it does not enforce.)
- Reviewers / instruments: one Claude model running lenses A-D, code-grounded — ran the full
  tests/run-golden.py at 2969076 in an isolated `git worktree` (104/104), and break-tested the
  load-bearing fixtures against source: F4 (regenerated a golden page, dropped the credits div and the
  ISO stamp — each flips the marker assertion to caught), F5 (scan_text over the fixture: exactly
  {todays_date}; no-op and drop-{{today}} each go red), F1 (verbatim "callouts become panels" caught).
- Independence limit honestly stated: this is context isolation + execution grounding, NOT model-weight
  decorrelation. The prior a598fa2 pass (same-model) MISSED the F4 MAJOR below; a different-vendor (GPT)
  cold pass caught it. The GPT cross-vendor pass for THIS head (2969076) is still owed — this record is
  the Claude code-grounded half only.
- NOTE — head binding is manual (Item 6 pending): `Head: 2969076` above is the manual binding; I
  confirmed `gh pr view 10 headRefOid == 2969076` before reviewing.

## Replay the real failure

Backfills requirement-(ii) fixtures for on-`main` gates, each replaying the ACTUAL incident from
`CROSS-SKILL-FINDINGS.md` (root CHANGELOG 1.0.0).

**F4 — verify.py docs gate (the fix this head adds; a prior review round's MAJOR).** The original sin:
a generated page shipped missing its ©/credits/ISO-stamp defaults. The subtle gap a prior pass missed
and this head fixes: golden-good only asserts `verify.py` 0-FAIL, and 0-FAIL hard-catches ONLY the © (a
missing © footer FAILs on a public page) — a dropped *credits* block is un-gated and a missing *ISO*
stamp is INFO, so 0-FAIL alone would NOT catch a generator that dropped credits or the stamp. 2969076
now locks all three with DIRECT marker assertions on each regenerated page (`©`, `class="box
box-credits"`, `name="last-reviewed"`+pinned date), across BOTH live generators. I ran all 6 (PASS) and
break-tested: dropping the credits div or the ISO stamp flips its assertion to caught. Verifier-catch
half (the © specifically) stays golden-bad case 1.

**F5 — lint-placeholders (the real gap: had no golden fixture).** `tests/golden-bad/unresolved-placeholder.md`
replays the F5 class via `{{todays_date}}` (a token backing to nothing) AND locks the fix (`{{today}}`
now a documented runtime token). Ran the real `scan_text(text, known_keys(ROOT))`: flags exactly
`{todays_date}`; `today`/`project_name` resolve. Break-tested both directions (no-op → red; drop
`{{today}}` from the runtime set → red).

**F1 — lint-render-restatement (synthetic → real).** The fixture now carries F1's verbatim "callouts
become panels" (project-faq SKILL.md Step 6); the assertion requires `"become panels"` in the caught
spans. Ran it: 3 findings, present.

Coverage: 3/5 on-main incident-guarding gates locked here (F4, F5, F1). The other 2 are NOT silent:
`lint-skill-count.py` (b65041f, 2-of-5) is deferred to the live `feat/skill-count-generate` redesign of
that exact lint (would collide), `check-version.py` is audit-owed — both in CONTRIBUTING's Backfill log;
neither gate is changed by this PR.

## Coverage vs advertising

Each new lock asserts specifics, not a weak floor: F4 checks the three exact emitted markers (not the
verify pass, which the docstring now correctly says catches only ©); F5 asserts the EXACT set
`{"todays_date"}`; F1 asserts the `"become panels"` span. No printed success string over-claims — the
run-golden summary is a dynamic `N/N`. The docstring "What it locks" inventory now describes the direct
F4 lock and the F1/F5 cases; I confirmed the code runs exactly those cases (claim == reality).

## Self-description drift

The PR grows golden-bad and golden-good, and every self-description was updated in lockstep: the
run-golden docstring (direct F4 lock; F1/F4/F5 named), the needed-paths tuple (adds LINT_PLACEHOLDERS),
CONTRIBUTING's Backfill log (all five gates re-stated LANDED/DEFERRED/OWED), and the CHANGELOG. The
CONTRIBUTING cites a `evaluate_verdicts -> light_admissible` seam fixture — verified present in
tests/run-golden.py (landed #9). No hard-coded count drifted (assertion total is derived).

## Fixture requirement

This PR IS the requirement-(ii) backfill and every lock is non-vacuous, verified by reverting/mutating
and re-running: F4 (drop credits or ISO → caught), F5 (no-op → red; drop-{{today}} → red), F1 (verbatim
span asserted). skill-count b65041f deferred with logged+verified justification; check-version
audit-owed — both tracked, neither silent.

## Findings

- **NIT** — `tests/golden-bad/unresolved-placeholder.md:9` (the leading HTML `<!-- ... -->` comment):
  its explanatory text contains live `{{todays_date}}`/`{{today}}` tokens that `scan_text` picks up (the
  case passes only because it is set-based and the comment names the same tokens as the body). A future
  edit naming a *different* unresolvable token in that comment would turn the case spuriously red. No
  current impact. Fix: backtick-escape or split the braces in the comment so only the body is the
  assertion surface. (Lens A/D, code-grounded.)
- (Resolved this head, recorded) The F4 credits/ISO lock a prior round flagged MAJOR is fixed at
  2969076 (`tests/run-golden.py`, golden_good direct marker assertions) and break-tested green→red.

No BLOCKER, no unresolved MAJOR. Checked with the command/line behind each: 104/104 at 2969076; F4's 6
marker assertions pass and flip red when a marker is dropped; F5 flags exactly {todays_date} and reverts
red both ways; F1's verbatim span caught; inventory/needed-paths/CONTRIBUTING/CHANGELOG match the cases;
the cited seam section exists; the 2 uncovered gates are logged deferrals.

---

Verdict: PASS
Every checked invariant holds at 2969076; the F4/F5/F1 locks each fail on a no-op/marker-drop revert; the
prior-round F4 MAJOR is fixed and re-verified here; the 2 uncovered incident gates are logged, justified
deferrals; the lone NIT is latent. Reviewed head: 2969076 (range 0739ea0...2969076). The GPT cross-vendor
pass on this head is still owed. Report only — landing is the owner's separate act.
