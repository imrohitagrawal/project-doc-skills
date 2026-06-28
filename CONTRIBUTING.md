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

### What is the gate layer

The machine-readable, canonical list is [`.github/gate-paths`](.github/gate-paths) — that file is the
single source of truth, read by `gate-review-check.py`. As of this writing it covers `release-gate.sh`,
`build-skills.sh`, `pkgtools.py`, `validate_skill.py`, `check-version.py`, every `lint-*.py`,
`shared/verify.py`, `tests/`, `.github/`, and the governance files themselves (`gate-review-check.py`,
`gate-review-prompt.md`, `CONTRIBUTING.md`). Do not re-derive the list from this prose — read the file;
the prose can drift, the file is what gates.

These paths share one property: **each can pass CI green while silently weakening or mis-describing a
check.** That is why a green build is not enough for them.

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
  requires a well-formed `Verdict: PASS` record under `gate-reviews/`, checking the **evidence**
  (the prompt version, the four lens sections, a real `Coverage: N/M` figure, the findings) — not just
  a `PASS` word, so a rubber stamp fails. It **runs on every PR and always reports**, so non-gate PRs
  pass automatically while gate PRs without a recorded review go red. It **fails closed**: any setup
  error blocks rather than letting a change through.
- **`release-gate` (required status check).** The existing build/lint/test/reproducibility/version
  gate. Still required — necessary, just not sufficient.
- **A branch ruleset on `main`** requires *both* checks, blocks force-pushes and deletion, and has **no
  bypass actors** so it applies to the maintainer too. The exact command is in
  [`docs/SETTINGS.md`](docs/SETTINGS.md) (settings are not committable — applying it is a manual step).
- **`CODEOWNERS`** marks the gate paths and notifies the owner. It is **notify-only**, deliberately not
  a required Code Owner review (see above).

### The honest ceiling (what this can and cannot promise)

No GitHub mechanism can make a solo administrator *unable* to bypass their own controls — the admin
owns the controls. With "no bypass actors" set, you cannot click-merge a red `gate-review`; to get a
gate change in without a review you would have to take a **deliberate, logged** action: edit or delete
the ruleset, or push with protection removed. Both are visible in the repository's settings and audit
log.

So the promise is precise: **the default path — open a PR, watch CI go green, merge — is closed for an
unreviewed gate change. Bypass is still possible, but never silent; it is loud, deliberate, and leaves
a trail.** The check verifies that the review was *run and recorded with evidence*; it cannot verify it
was done in *good faith*. Fabricating a structured verdict is possible — but it is a deliberate lie in
the permanent record, not a one-click skip. That residual is irreducible for a single maintainer;
naming it here is the point, not papering over it.

### Requirement (ii): the deterministic backstop

The independent review is the backstop for *judgement* — never an excuse to skip a check a machine can
make. So: **wherever a gate failure can be reduced to a deterministic fixture, it must be.** Concretely,
any **new or changed gate correctness-check** must arrive with a regression fixture derived from the
**real incident** it guards — a fixture that fails if the check is reverted to a no-op. This is the same
"gates that guard the gates" discipline as [`tests/run-golden.py`](tests/run-golden.py). When a
gate-review *finds* something, ask "could this have been a fixture rather than a human catch?" — if yes,
the fix is to add the fixture, not only to note the bug.

One honest exception: a pure **process/bootstrap** mechanism (this enforcement layer itself —
`gate-review-check.py`) does not guard a past *suite* incident, so it has no real-incident fixture to
derive. It is instead proven by demonstration (the scenario runs recorded in its bootstrap verdict
under `gate-reviews/`), and a unit-test backfill for it is logged below.

#### Backfill log (requirement ii is enforced going forward; existing gaps are tracked, not retro-fitted in one PR)

This rule binds **new and changed** gate checks immediately. Checks already on `main` are audited and
backfilled incrementally, each as its own gate-reviewed PR — not bundled into the PR that introduced
this policy (that would couple the mechanism to unrelated content):

- **`lint-skill-count.py` — its `b65041f` real-incident fixture is owed.** The lint lives on an
  unmerged PR stack, not on `main`, so the fixture lands with it (or in a follow-up the moment it
  merges). The fixture must reconstruct the actual stale enumerations `b65041f` fixed (README table +
  count words + the "improve in this order" list + repo-tree; the per-skill prompt's pick-list +
  attachment table; `build-skills.sh` "all seven") and assert the lint catches each — measuring real
  coverage, not a mutation of an already-guarded line.
- **`gate-review-check.py` — unit-test backfill owed** (the scenarios proven by hand in its bootstrap
  verdict: non-gate→pass, gate-without-verdict→block, malformed/FAIL verdict→block, fail-closed on
  missing inputs).
- **Audit owed for the other on-`main` checks** (`lint-placeholders.py`, `check-version.py`;
  `lint-render-restatement.py` and `shared/verify.py` already have golden-bad coverage in
  `tests/run-golden.py`): confirm each that guards a real past incident has a no-op-revert fixture, and
  open a PR for any gap.

### Running a gate-review

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

