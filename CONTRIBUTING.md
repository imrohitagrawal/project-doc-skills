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
`shared/verify.py`, `shared/ci/` (the docs-as-code gate that ships inside every `.skill`), `tests/`,
`.github/`, and the governance files themselves (`gate-review-check.py`, `gate-review-prompt.md`,
`gate-reviews/TEMPLATE.md`, `CONTRIBUTING.md`, `docs/SETTINGS.md`). Do not re-derive the list from this
prose — read the file; the prose can drift, the file is what gates. (Deliberately *out* of scope: the
authoring standards `shared/house-style.md` and `shared/render-contract.md` — they change often during
normal authoring and gating every edit would be friction; the *checks* that enforce them are gated, and
a hollowed-out contract is a visible diff. Add them if you want maximal coverage.)

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

- **`lint-skill-count.py` — its `b65041f` real-incident fixture is owed.** The lint lives on an
  unmerged PR stack, not on `main`, so the fixture lands with it (or in a follow-up the moment it
  merges). The fixture must reconstruct the actual stale enumerations `b65041f` fixed (README table +
  count words + the "improve in this order" list + repo-tree; the per-skill prompt's pick-list +
  attachment table; `build-skills.sh` "all seven") and assert the lint catches each — measuring real
  coverage, not a mutation of an already-guarded line.
- **`gate-review-check.py` — fixture LANDED in this PR** (`tests/run-golden.py`, the `gate-review-check`
  section): path classification plus the verdict decision, locking the rubber-stamp vectors the
  bootstrap review caught (PASS quoted in prose over a BLOCK, coverage `0/0` or outside the replay
  section, `PASS-WITH-NITS`, a co-committed BLOCK). Not owed — done.
- **Audit owed for the other on-`main` checks** (`lint-placeholders.py`, `check-version.py`;
  `lint-render-restatement.py` and `shared/verify.py` already have golden-bad coverage in
  `tests/run-golden.py`): confirm each that guards a real past incident has a no-op-revert fixture, and
  open a PR for any gap.

### Running a gate-review

**Scale the review to the change (proportionality).** The default is the full blind multi-lens review,
but a one-line comment fix should not demand a 4-agent crew — if it always did, you would be tempted to
turn the gate off, and then it is theatre. So `gate-review-prompt.md` defines two tiers: a **light** path
(a single reviewer; `Tier: light` + `Coverage: N/A` + a `Light-path justification:`) allowed **only**
for a declared non-behavioral change (comment/doc/whitespace, no change to a check's logic, the gated
set, a count/threshold, or the policy); and the **full** path (the crew + a real `Coverage: N/M` + the
optional different-vendor pass) for everything else. The tier defaults to **full**, so the lighter bar
is never granted by omission, and the verdict still carries file:line findings (or an explicit `none`).

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

