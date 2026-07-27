# Contributing to project-doc-skills

Most of this repository is ordinary: edit a `shared/` file or a skill, run `./build-skills.sh`, keep
the changelogs honest, open a PR. The one part with extra rules is the **gate layer** — the build,
lint, test, and CI machinery that decides whether the suite is releasable. Those files gate everyone
else's work, so they are themselves gated. That rule is the subject of the **Governance** section
below; read it before you touch a gate file.

## Governance: the gate-layer review rule

> **The rule.** A pull request that changes any **gate-layer** path may not merge to `main` until it
> carries **(i)** an independent gate-review run with [`gate-review-prompt.md`](gate-review-prompt.md)
> and recorded as a committed verdict under [`gate-reviews/`](gate-reviews/), **and** — for any new or
> changed gate *correctness* check — **(ii)** a regression fixture derived from the real incident that
> check guards. **CI passing is necessary but not sufficient.**

What the machine actually enforces, stated precisely: a **structured, evidence-bearing review record**
(the right sections, a real coverage figure or a justified docs-only light tier, file:line findings, an
explicit `PASS`). It **cannot** verify the review was genuinely run, independent, or honest — that a
human/agent actually did the work is an *attestation*, the irreducible residual named in the Honest
ceiling below. So read this as "requires a recorded, evidence-bearing review", not "proves a good-faith
review happened". The record raises the floor and leaves a durable, auditable trail; it is not a lie
detector.

### What is the gate layer

The machine-readable, canonical list is [`.github/gate-paths`](.github/gate-paths) — that file is the
single source of truth, read by `gate-review-check.py`. **The list below is ILLUSTRATIVE, not
authoritative** (read the file; this prose can drift and the file is what gates): roughly, the build/
lint/test machinery (`release-gate.sh`, `build-skills.sh`, `pkgtools.py`, `validate_skill.py`,
`check-version.py`, every `lint-*.py`, `shared/verify.py`, `shared/ci/`, `tests/`), all of `.github/`,
and the governance files themselves. Deliberately *out* of scope (a documented choice, not an oversight
— recorded in `.github/gate-paths`): the authoring standards `shared/house-style.md` /
`shared/render-contract.md`, the historical `CHANGELOG.md`, and the verdict records
`gate-reviews/<NNNN>-*.md` (append-only history — see below).

These paths share one property: **each can pass CI green while silently weakening or mis-describing a
check.** That is why a green build is not enough for them.

**Self-inclusion is the load-bearing property.** The enforcement's own files —
`.github/workflows/gate-review.yml`, `.github/gate-paths`, `gate-review-prompt.md`,
`gate-review-check.py`, and this policy — are themselves in the gate-paths set (the first three via the
`.github/` subtree; the rest by name). Single-sourcing the list is necessary but **not** sufficient:
if the gate's own files were not gated, the review could be quietly weakened in an unreviewed PR and the
whole thing would unravel from the inside. A regression assertion in `tests/run-golden.py`
(`gate-review-check` section) locks this so it can't silently regress.

### Why CI green is necessary but not sufficient

Two real failures here shipped — or sat in an open PR — fully CI-green, because both were judgement
failures a build cannot see:

1. **Coverage masquerading as completeness.** A skill-enumeration lint printed `clean` while it
   inspected only **2 of the 5** places the suite enumerates its skills (it never looked at the README
   "improve in this order" list, the repo-tree, or the per-skill prompt's attachment table). Green,
   and stale. A success message asserted more than the code verified.
2. **Self-description drift.** The PR that added a third suite lint left `release-gate.sh` describing
   "the **two** now-active suite lints." The gate's count of itself drifted from what it runs, and no
   check noticed.

An independent reader, replaying the *real* failure and reading the gate's claims against its code,
catches both. The gate-review is that reader.

### How it is enforced (designed for a solo maintainer)

This repository has one maintainer, so the usual "require a second reviewer's approval" does not work
— GitHub will not let you approve your own PR, and requiring it would make every gate PR un-mergeable
except by override, training exactly the reflex this rule exists to prevent. So the enforcement is a
**required status check the maintainer can satisfy alone** by producing the review record:

- **`gate-review` (required status check).** [`.github/workflows/gate-review.yml`](.github/workflows/gate-review.yml)
  runs `gate-review-check.py` on every PR. It detects whether the PR touches a gate-path; if so, it
  requires a well-formed `Verdict: PASS` record under `gate-reviews/`, checking the **evidence shape**
  (the prompt version, the four lens sections + Findings, a real `Coverage: N/M` or a justified
  docs-only light tier, file:line findings, filled provenance) — so a *one-line or unfilled* rubber
  stamp fails. (A determined fabrication that fills every field is the irreducible residual — see the
  Honest ceiling.) It **runs on every PR and always reports**, so non-gate PRs pass automatically while
  gate PRs without a recorded review go red. It **fails closed**: any setup error blocks.
- **`release-gate` (required status check).** The existing build/lint/test/reproducibility/version
  gate. Still required — necessary, just not sufficient.
- **A branch ruleset on `main` — once you apply it** (it is a manual step; settings are not committable,
  so this is NOT enforced by anything in the PR until you run the command). When applied, it requires
  *both* checks, blocks force-pushes and deletion, and has **no bypass actors** so it applies to the
  maintainer too. Exact command + a verify step (`gh api …/rules/branches/main`) in
  [`docs/SETTINGS.md`](docs/SETTINGS.md). Until then, the gating above is advisory.
- **`CODEOWNERS`** marks the gate paths and notifies the owner. It is **notify-only**, deliberately not
  a required Code Owner review (see above).

**Verdict records are append-only history.** Each `gate-reviews/<NNNN>-*.md` is the durable evidence for
one PR; treat them as immutable once merged. They are deliberately *not* in `.github/gate-paths` (every
gate PR adds one, so gating them would be self-referential), but editing a past verdict is discouraged
and is itself a gate-review-worthy act if ever done — the audit trail's value is that it does not change
after the fact.

### The honest ceiling (what this can and cannot promise)

No GitHub mechanism can make a solo administrator *unable* to bypass their own controls — the admin
owns the controls. With "no bypass actors" set, you cannot click-merge a red `gate-review`. The honest,
complete list of ways a gate change could still reach `main` without a genuine review is:

1. **Edit or delete the ruleset** (or push with protection removed) — a deliberate settings change,
   visible in the repository settings and the audit log.
2. **Fabricate a structured verdict** — write a `Verdict: PASS` record with invented evidence. The
   check verifies a review was *run and recorded with evidence*; it cannot verify *good faith*. This is
   a deliberate lie in the permanent record, not a one-click skip.
3. **Edit the checker itself in the same PR.** Because the workflow runs `gate-review-check.py` from the
   pull request's own head, a PR that rewrites the check (or `.github/workflows/gate-review.yml`) to
   pass can report `gate-review` green on the default path — no settings change, no separate fabricated
   verdict. The only thing standing between this and a silent bypass is that such an edit is a
   **conspicuous gate-layer diff** (it is in `.github/gate-paths`, so it *is* what the gate-review must
   scrutinize first), plus the owed `gate-review-check.py` unit tests as a regression backstop. There is
   no GitHub-native fix for "a PR edits the check that gates it" on a solo repo; the mitigation is
   attention, not automation — so we name it here rather than imply it away.

So the promise is precise: **the default path — open a PR, watch CI go green, merge — is closed for an
unreviewed gate change. Bypass is still possible, but never silent; every route above is deliberate and
leaves a trail.** That residual is irreducible for a single maintainer; naming it is the point, not
papering over it.

### Requirement (ii): the deterministic backstop

The independent review is the backstop for *judgement* — never an excuse to skip a check a machine can
make. So: **wherever a gate failure can be reduced to a deterministic fixture, it must be.** Concretely,
any **new or changed gate correctness-check** must arrive with a regression fixture derived from the
**real incident** it guards — a fixture that fails if the check is reverted to a no-op. This is the same
"gates that guard the gates" discipline as [`tests/run-golden.py`](tests/run-golden.py). When a
gate-review *finds* something, ask "could this have been a fixture rather than a human catch?" — if yes,
the fix is to add the fixture, not only to note the bug.

This binds the enforcement layer to itself. `gate-review-check.py` is a new gate check, so by the rule
above it ships **with** its fixture: the `gate-review-check` section of
[`tests/run-golden.py`](tests/run-golden.py) locks its path classifier and its verdict decision —
including the rubber-stamp vectors the bootstrap review (below) caught. It guards no prior *suite*
incident, so its fixture is derived from that review's own findings rather than a historical bug; that
is the closest honest analogue of "the real incident it guards" for a brand-new mechanism.

#### Backfill log (requirement ii is enforced going forward; existing gaps are tracked, not retro-fitted in one PR)

This rule binds **new and changed** gate checks immediately. Checks already on `main` are audited and
backfilled incrementally, each as its own gate-reviewed PR — not bundled into the PR that introduced
this policy (that would couple the mechanism to unrelated content):

- **`lint-placeholders.py` — real-incident fixture LANDED** (`tests/run-golden.py`, golden-bad case 5,
  `tests/golden-bad/unresolved-placeholder.md`). Replays **CROSS-SKILL-FINDINGS.md F5**: project-faq's
  `{{today}}` backed to no profile key. The fixture locks both directions — a still-unresolvable
  `{{todays_date}}` is caught, and the documented runtime token `{{today}}` plus a real profile key
  resolve cleanly (a regression dropping `{{today}}` from the runtime set turns it red). This was the
  real gap: the lint previously had no golden fixture at all. Break-tested both directions.
- **`lint-render-restatement.py` — upgraded to the real incident** (golden-bad case 4). The fixture now
  carries **F1**'s verbatim restatement ("callouts become panels", from project-faq's SKILL.md Step 6)
  rather than a synthetic shape, and the assertion checks that exact span is caught.
- **`shared/verify.py` (docs gate) — real incident confirmed + cited** as **F4** (the original sin: a
  generated page missing its ©/credits/ISO defaults). Both halves are locked: the generator-regression
  half by golden-good, which now **directly asserts** the regenerated HTML contains the ©, the credits
  block, and the ISO last-reviewed stamp (necessary because `verify.py`'s 0-FAIL catches only the © — a
  missing ISO stamp is INFO and there is no credits gate); and the verifier-catch half (the © itself) by
  golden-bad case 1 (the missing-© page).
- **`lint-skill-count.py` — its `b65041f` (2-of-5) fixture is DEFERRED to the `feat/skill-count-generate`
  work.** The lint is now on `main` (PR #2), but that exact file is being redesigned there
  ("generate-don't-lint"); landing the `b65041f` fixture in this PR would collide with the redesign and
  likely be rewritten, so it lands with (or right after) that work. The fixture must reconstruct the
  actual stale enumerations `b65041f` fixed (README table + count words + the "improve in this order"
  list + repo-tree; the per-skill prompt's pick-list + attachment table; `build-skills.sh` "all seven")
  and assert the lint catches each — measuring real coverage, not a mutation of an already-guarded line.
- **`gate-review-check.py` — fixture LANDED** (`tests/run-golden.py`, the `gate-review-check` +
  `gate-review-check SEAM` sections): path classification, the verdict decision, and the
  `evaluate_verdicts -> light_admissible` seam, locking the rubber-stamp vectors the bootstrap review
  caught and the closed-allow-list light-tier rule. Not owed — done.
- **Still audit-owed: `check-version.py`** — confirm its real-incident no-op-revert fixture and open a
  PR for any gap (out of scope for the fixture-backfill PR above, which covered the suite lints + the
  verifier docs gate).

### Running a gate-review

**Scale the review to the change (proportionality).** The default is the full blind multi-lens review,
but a one-line comment fix should not demand a 4-agent crew — if it always did, you would be tempted to
turn the gate off, and then it is theatre. So `gate-review-prompt.md` defines two tiers: a **light** path
(a single reviewer; `Tier: light` + `Coverage: N/A` + a `Light-path justification:`) for a change to an
**inert gated doc**; and the **full** path (the crew + a real `Coverage: N/M` + the optional
different-vendor pass) for everything else. The light path is not just self-declared: `gate-review-check.py`
**refuses** it unless every changed gate path is an inert `*.md` — **today exactly `gate-reviews/README.md`**.
Code/config *and* the behavioral governance docs (this policy, `gate-review-prompt.md`,
`gate-reviews/TEMPLATE.md`, `docs/SETTINGS.md`) all force the full review, because editing any of them
changes how the gate itself works. The tier defaults to **full** (and a mixed full+light resolves to
full), so the lighter bar is never granted by omission, and the verdict still carries file:line findings
(or an explicit `none`).

1. **Find the changed gate paths.** `python3 gate-review-check.py --base origin/main --head HEAD` (it
   prints the gate paths your PR touches, or tells you none are).
2. **Start the record.** Copy [`gate-reviews/TEMPLATE.md`](gate-reviews/TEMPLATE.md) to
   `gate-reviews/<short-name>.md`.
3. **Run the review, independent and blind.** Follow [`gate-review-prompt.md`](gate-review-prompt.md):
   spawn the lenses in fresh contexts that did not write the change; decorrelate (a code-grounded lens
   that runs things; ideally a different-vendor cold pass at any BLOCKER-risk change). Fill the verdict
   with evidence — replay the *real* failure and state `Coverage: N/M`.
4. **Resolve, don't rationalize.** Fix every BLOCKER and MAJOR in the change and re-run; write
   `Verdict: PASS` only when clean. Otherwise `Verdict: BLOCK` and the check stays red — correctly.
5. **Commit the verdict in the PR.** `gate-review` goes green; the owner merges.

## Everyday contributing (the non-gate path)

- **Edit the canonical source, never a generated copy.** Shared files live once in `shared/` and are
  copied into each `.skill` at build time; never hand-edit a bundled copy or a file inside
  `skills/<name>/`'s shared layer. Edit `shared/`, then rebuild. (See the README for the full build
  model.)
- **Rebuild what you changed.** Editing anything under `skills/<name>/` requires
  `./build-skills.sh` and committing the rebuilt `dist/<name>.skill` and `dist/MANIFEST.sha256`, or the
  reproducibility step DRIFTs. Root scaffolding (README, this file, `release-gate.sh`, the lints,
  `VERSION`, `tests/`) is not bundled and needs no rebuild.
- **Prove it locally before you push.** `./release-gate.sh` must be green (build + validation + the
  suite lints, the golden fixtures, byte-identical reproducibility, the manifest, and the
  version/changelog check). Paste what you ran in the PR — verify, don't assert.
- **Changelogs.** Shared/suite changes go in the root `CHANGELOG.md`; skill-specific changes in that
  skill's `CHANGELOG.md`. `check-version.py` requires the root changelog to name the current `VERSION`
  (it ignores a `## [Unreleased]` section, which is the right home for changes staged before the next
  version is cut).
- **Commits.** Conventional commits (`feat(scope): …`, `fix(scope): …`, `docs(scope): …`), with the
  `Co-Authored-By` trailer where it applies. Land everything via a branch + PR; never push `main`.
- **No `--no-verify`, no bypassing CI or the gate-review.** If a check is wrong, fix the check (with a
  gate-review, since the check is gate-layer) — don't route around it.

