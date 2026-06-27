# Changelog — project documentation skills (suite)

Suite-level and shared-file changes. Skill-specific changes live in `skills/<name>/CHANGELOG.md`.
Format follows Keep a Changelog.

## [Unreleased] (gate-layer governance: the enforced independent gate-review)

Suite tooling and governance, never copied into a `.skill`. No `VERSION` bump: this is process
scaffolding shipping no new `.skill` bytes, recorded here under `Unreleased` (which `check-version.py`
ignores) so it folds into whichever version is cut next — avoiding a number collision with the
in-flight skill-count PR.

### Added — the enforced independent gate-review (CI green is necessary, not sufficient)
- **`gate-review-prompt.md`** — the versioned, reusable independent-review prompt for any gate-layer
  change. Composes the suite's blind-axis review idiom (fresh-context lenses + adversarial adjudicator +
  a different-vendor cold pass) and bakes in the hard-won lenses: replay the *real* failure and measure
  coverage; coverage-vs-advertising (flag any `clean`/`PASS` a gate can emit while reality is stale);
  self-description drift; the fixture requirement; report-only, verify-don't-assert, enterprise bar.
- **`gate-review-check.py`** + **`.github/workflows/gate-review.yml`** — the `gate-review` required
  status check. On every PR it derives whether a gate-layer path changed (from `.github/gate-paths`)
  and, if so, requires a well-formed `Verdict: PASS` record under `gate-reviews/`, verifying the
  evidence (prompt version, the four lens sections, a real `Coverage: N/M`, findings) — not just a
  `PASS` word. Always reports (so non-gate PRs pass) and **fails closed** (any error blocks).
- **`.github/gate-paths`** — the single canonical list of the gate layer, read by the check; the policy
  prose points here rather than re-listing it, so the machine's notion of the gate layer cannot drift.
- **`.github/CODEOWNERS`** — notify-only path markers for the gate layer (deliberately not a required
  Code Owner review: a solo maintainer cannot approve their own PR).
- **`CONTRIBUTING.md`** — the governance policy: the rule, why CI is necessary-not-sufficient (the two
  real incidents), how it is enforced for a solo owner, the honest ceiling (bypass is possible but
  loud and logged, never silent), requirement (ii) and its backfill log.
- **`gate-reviews/`** (`TEMPLATE.md` + `README.md`) — the committed home of every review verdict.
- **`docs/SETTINGS.md`** — the exact branch-ruleset command to apply by hand (settings are not
  committable): require `release-gate` + `gate-review`, no bypass actors, block force-push/deletion.

## [1.2.0] — 2026-06-28 (suite lint: the skill-enumeration guard)

A new root-level suite lint, composed into the release gate. Suite tooling, never copied into a `.skill`.

### Added — `lint-skill-count.py` (new suite gate)
- `README.md` and `per-skill-review-prompt.md` are root scaffolding (never bundled), so they were
  invisible to `validate_skill.py`, the render/placeholder lints, and `check-version.py`. That blind
  spot let the skill **enumeration** drift twice — a stale "seven skills" count, and a skill table /
  pick-list missing a row — and ship uncaught (both fixed in the doc-critic PR, `b65041f`). This lint
  derives the canonical set from `skills/<name>/` and asserts the README skill table, the
  per-skill-prompt `{SKILL_NAME}` pick-list, and the suite count words all match it.
- **Low false-positive by design:** the set checks are exact directory-vs-document comparisons; the
  count-word checks are anchored to specific suite-count phrases, so the legitimate "the other seven
  skills" (N-1), "Six [authoring skills] turn ..." (a sub-count), and the dated "all seven skills were
  clean" history line never trip it.
- `build-skills.sh` runs it with `--strict` alongside the render-restatement and placeholder lints, so
  a drift now FAILS the build — and the release gate, via build step 1. Run by hand it defaults to WARN.

## [1.1.0] — 2026-06-28 (new skill: doc-critic — the independent critic gate)

The eighth skill plus one shared-layer addition that supports it. Additive and good for all skills.

### Added — `skills/doc-critic/` (new skill, v0.1.0)
- The independent **critic gate**: the human-judgement review layer that runs **after**
  `verify.py` (deterministic) and **before** `publish-mirror`, over the docs an authoring skill
  produced. It catches what a regex/readability verifier cannot — cross-module contradictions,
  analogy-shape errors and term collisions, code-vs-doc mismatches, term/glossary gaps,
  simplifications-gone-false, honesty-posture drift, and broken cross-references. Runs a blind
  multi-axis critique (whole-document consistency, code-grounded correctness, the beginner floor, an
  adversarial adjudicator; a different-vendor pass at a public gate), writes a severity-ranked review
  register, and gates publishing on unresolved BLOCKERs. Ships `review-playbook.md`,
  `reviewer-prompts.md`, and `review-profiles.md` (learning-track profile implemented; the other five
  doc types stubbed). Independently reviewed (unbiased + expert) before landing; per-run reviewer
  slots use the suite's `[...]` author-fill convention so the placeholder lint stays clean.

### Added — `shared/house-style.md` Section 5a "Lock the registers before writing" (all skills)
- A new pre-writing discipline: settle the **analogy / term / honesty-maturity registers** before
  writing a multi-page document, because cross-page decisions propagate. Each page is checked against
  them in the authoring loop (Section 10); the independent whole-set confirmation is doc-critic's job.
  Additive; references Section 4 rather than restating it. `skills/learning-track` adopts it (Step 3 +
  new Step 6a handoff to doc-critic; bumped to 1.4.0, header/changelog drift realigned). The other
  authoring skills inherit the shared section and gain the doc-critic handoff in their own sessions.

## [1.0.0] — 2026-06-22 (suite-hardening pass 2 — first released, reproducibly-built, manifest-verified suite)

A focused pass on the shared layer plus the release-engineering of the bundle as a shipped artifact.
Every change below is in a `shared/` file (reaches **all seven** skills via the build) or a root-level
build/lint/test file (suite tooling, never copied into a `.skill`). The three source-document fixes
this pass made are recorded in their own skill changelogs (learning-track 1.3.1, operations-runbook
1.1.1, project-faq 1.2.1) and cross-referenced here.

### Changed — `shared/verify.py` staleness regex widened to read both bold last-reviewed forms (all seven skills)
- The last-reviewed regex read `**Last reviewed: DATE**` (date inside the bold span) but silently
  missed `**Last reviewed:** DATE` (bold closed before the date) — the suite was one keystroke from an
  inert freshness gate. The separator class after the literal phrase "last reviewed" now tolerates
  stray Markdown emphasis (`*`, `_`), so both bold forms, the plain form, and the `<meta>` form all
  read. The widening only adds separators *after* the matched phrase, so an unrelated bracket or
  citation still cannot trip it (proven by a golden pin). Pairs with the learning-track F3 fix below.

### Added — `shared/project-profile.md` now declares the runtime-token set in one place (all seven skills)
- New "Runtime tokens" section names the only two `{{...}}` slots that do **not** back to a profile
  key: `{{today}}` (the build date, ISO `YYYY-MM-DD`) and `{{canonical_url}}` (the real published URL,
  wired at publish time). Single home for the convention, so the new placeholder gate (below) has an
  authority to check against. Closes the documentation half of `CROSS-SKILL-FINDINGS.md` F5.

### Changed — `shared/licensing-and-credits.md` cross-references the `{{canonical_url}}` runtime token (all seven skills)
- The footer/attribution canonical-link placeholder is now named as the `{{canonical_url}}` runtime
  token defined in `project-profile.md`, so the two files agree on one convention rather than each
  describing the slot in its own words. Additive; no value defined twice.

### Added — `lint-placeholders.py`, a build-time placeholder-resolution gate (suite tooling; guards all seven)
- Every `{{...}}` token under `skills/` and `shared/` must resolve to a profile key, a manifest slot
  (a token used in `publish-targets.yaml`), or a documented runtime token (`{{today}}`,
  `{{canonical_url}}`); illustration tokens like `{{key}}` and non-identifier braces are skipped. WARN
  by default; `--strict` exits 1. Wired into `build-skills.sh --strict` so a leftover unresolved token
  FAILs the build and is named by `file:line`. Closes the enforcement half of F5 (scope item 3.3.5).

### Added — `pkgtools.py`, deterministic packaging + integrity manifest (suite tooling)
- `zip`: a deterministic packer — files only, entries sorted by archive name, every timestamp pinned
  to the zip epoch, fixed permissions and compression — so identical source produces a byte-identical
  `.skill` within one toolchain. `manifest`: a SHA-256 over each built `.skill` **and** each `shared/`
  file, plus the suite version and the source commit (honest `unknown` fallback off a git checkout).
  Carries a built-vs-designed honesty note: byte-identity holds per toolchain; the SHA-256 manifest is
  the cross-environment guarantee. Both the packer and the manifest exclude build cruft
  (`__pycache__/*.pyc`, `.DS_Store`), so a bytecode cache left by a test import can never enter a
  `.skill` or be hashed into the manifest. (Scope items 3.1.)

### Changed — `build-skills.sh` rewritten for reproducible, verifiable, manifested builds (suite tooling)
- Packages via `pkgtools.py zip` instead of the `zip` CLI; adds `--check`, which rebuilds every
  `.skill` into a scratch path and asserts it is **byte-identical** to the committed `dist/<name>.skill`
  (DRIFT fails the build); runs `lint-placeholders.py --strict` alongside the existing
  `lint-render-restatement.py --strict`; and emits `dist/MANIFEST.sha256` on a clean, unfiltered full
  build. Proven: two clean builds are byte-identical; `--check` passes on the committed artifacts and
  DRIFTs on a one-character source edit. (Scope items 3.1, composes 3.3.1/3.3.2/3.3.4.)

### Added — `VERSION` (suite tooling)
- The suite is now SemVer-tracked, starting at `1.0.0` — the first reproducibly-built, manifest-verified
  release. The per-skill / root CHANGELOG split is unchanged; skills keep their own version numbers.

### Added — `tests/` golden-fixture regression that guards the gates themselves (suite tooling)
- `tests/run-golden.py` with `tests/golden-good/` and `tests/golden-bad/`. golden-good: an FAQ HTML and
  a usage-guide HTML page produced by the **live** generators, plus a hand-written learning-track
  module, each must pass `verify.py` with **0 FAIL** (so a generator that stops emitting its © footer /
  credits / ISO stamp is caught — the original-sin failure). golden-bad: a missing-© page, a
  real-shaped AWS key, a years-old stamp, and a SKILL.md that restates the render mapping — each must
  be **caught** by the right gate. Plus deterministic pins: the staleness boundary at a non-default
  threshold with a pinned "today" (old→WARN, recent→INFO, future→WARN, both bold forms read), and a
  Flesch-Kincaid grade pin on a fixed string so "simplify until green" cannot turn readability into a
  no-op. Proven non-vacuous: defusing a golden-bad fixture turns the runner red. (Scope item 3.2.)

### Added — `check-version.py`, a version & changelog-bump check (suite tooling)
- Asserts `VERSION` is valid SemVer, that the root `CHANGELOG.md` carries a heading for that version,
  and that every skill is independently versioned. The "advanced since the last tag" comparison runs
  only when git history is present and never fails on its absence (honest skip). (Scope item 3.3.6.)

### Added — `release-gate.sh` + `.github/workflows/release-gate.yml`, one composed CI release gate (suite tooling)
- A single root script (runnable locally and from CI) that fails a release unless every step passes,
  composing the existing and new gates rather than re-adding them: `build-skills.sh` (validity + the
  now-active render-restatement and placeholder lints + the manifest) → `tests/run-golden.py`
  (golden-good 0 FAIL, every golden-bad caught) → `build-skills.sh --check` (byte-identical) →
  `dist/MANIFEST.sha256` presence → `check-version.py`. The render-restatement lint is not added a
  second time — it already runs inside the build step with `--strict`, which is the "compose, don't
  re-add" rule. The workflow at `.github/workflows/release-gate.yml` runs the script on push/PR/tag and
  uploads the built `.skill` files + manifest. Distinct from the per-skill `shared/ci/verify-docs.yml`
  that ships inside each `.skill` to verify a *consumer's* produced docs. (Scope item 3.3.)

### Decision — declined to extract a shared HTML emitter for the two generators (F4 / scope item 2.2)
- F4 (usage-guide's HTML path carrying the © footer + credits + ISO stamp by construction) was already
  resolved on 2026-06-20: usage-guide ships its own `assets/usage_guide_generator.py` that emits all
  three. The remaining suite-hardening choice was whether to extract a shared emitter both generators
  call so a future producer inherits the guarantees. **Declined, deliberately.** The two generators
  have different skeletons, CSS, and block vocabularies; the only duplication is a few lines of
  render-contract-dictated wrapper markup whose *values* are already single-sourced from the profile,
  and CSS cannot be single-sourced across two bespoke layouts anyway. The stronger, by-construction
  guarantee for *every* producer is the golden-good/golden-bad fixtures above (a produced page that
  drops its © now fails CI), which is what was added instead of a third abstraction. A prior pass and
  the usage-guide session both reached the same conclusion (a shared helper was over-engineering for
  two bespoke generators).

### Consolidation note
- `1.0.0` is the first tagged release. It also consolidates the two previously-unreleased shared
  changes recorded below (the 2026-06-21 scope-aware publish-reviewer change and the 2026-06-20
  suite-hardening pass); those sections are retained as the detailed record and are part of this
  release.

## Folded into 1.0.0 — 2026-06-21 (shared change made during the publish-mirror per-skill session)

One shared-file change, additive and good for all seven skills, so it is recorded here (skill-only
changes for publish-mirror are in `skills/publish-mirror/CHANGELOG.md`).

### Changed — `shared/render-contract.md` Section 4 publish-reviewer is now scope-aware (all seven skills)
- The licence-credit check in the publish-reviewer was phrased for **public** pages only ("a hard
  failure on public pages"). But three of the six authoring outputs are **internal** scope
  (project-faq, operations-runbook, onboarding-companion) and are mirrored too, so an internal
  document could lose its copyright line on a target without the reviewer flagging it. The check now
  reads: on a public page the `©` footer must survive; on an internal document the short copyright
  line or credits block must survive (per `licensing-and-credits.md` Sections 1–2); a watermark never
  satisfies it. Additive; it references the licensing standard rather than restating it. All seven
  rebuilt valid; the render-restatement lint stays clean. (Source-side enforcement is unchanged:
  `verify.py` already FAILs a public page with no `©` and an internal set with no `©` anywhere — this
  closes the same gap on the *shipped target* artifact, which is the publish-reviewer's job.)

## Folded into 1.0.0 — 2026-06-20 (suite-hardening pass)

A focused pass on the shared layer (allowed to touch all seven skills). Every change below is in a
`shared/` file or a root-level build/lint/prompt file, so it reaches **all seven** skills via the
build — except the FAQ-generator-specific items, which are recorded in `skills/project-faq/CHANGELOG.md`.

### Added — two deterministic, low-false-positive checks in `shared/verify.py` (all seven skills)
- **Secret / PII scan (every scope).** Gives the Section 4 privacy rule a machine backstop it never
  had. **FAILS** near-certain credential shapes on a produced page (private-key blocks, AWS access-key
  ids, GitHub `ghp_`/`github_pat_` tokens, Slack `xox*` tokens) and **WARNs** softer signals (email
  addresses, JSON Web Tokens, browser API keys, a `secret/key/token = <long value>` assignment).
  Placeholders are exempt (`{{key}}`, example/test domains, obvious dummy values). Names and phone
  numbers are deliberately **not** scanned (too false-positive-prone for a machine; they stay a
  human-review item). Runs for public **and** internal output — a leaked key is a leak regardless of
  audience. (During testing this caught a real bug in its own placeholder list: digit-run markers were
  incidentally exempting genuine tokens that contained those digits; fixed.)
- **Staleness check (last-reviewed).** Gives "refresh per milestone" teeth. **WARNs** when a page's
  last-reviewed stamp is older than the threshold (CLI `--max-age-months` > profile
  `max_doc_age_months` > built-in 6) or is in the future; an absent stamp is an INFO nudge, never a
  failure. New CLI flag `--max-age-months`. One canonical stamp format (ISO `YYYY-MM-DD`, as a
  `<meta name="last-reviewed">` or a visible `Last reviewed:` line), defined in `render-contract.md` P2.

### Changed — readability now excludes the required licence footer (`shared/verify.py`)
- The licence `<footer>` is stripped before the reading-grade is computed (HTML output). Its fixed
  legal boilerplate is page furniture, not body prose; on a short page those ~20 words pushed the
  Flesch–Kincaid grade over the gate (the demo read 8.1 with the footer, 8.0 without). The `©` check
  still reads the original page, so the licensing gate is never weakened — this can only prevent a
  false readability WARN from the *required* footer. Closes the point-3 footgun structurally.

### Changed — the render-restatement lint is now an ACTIVE gate
- `build-skills.sh` runs `lint-render-restatement.py` with `--strict`, and a finding now **fails the
  build** (folded into the failure count). All seven skills were confirmed clean first. A future
  session that restates the Markdown/HTML→target conversion in a `SKILL.md` will break the build at
  that file:line. The lint docstring and `per-skill-review-prompt.md` record that the gate is active;
  running the lint by hand still defaults to WARN.

### Changed — shared standards document the new rules (single source, no restating)
- **`render-contract.md`** — after the primitives table: P2 now pins the single canonical
  machine-readable last-reviewed stamp format, and P14 is stated as a generator-level guarantee (any
  HTML generator must render the `©` footer, not just the watermark; `verify.py` is the backstop). This
  is the "shared HTML-footer guarantee" — one written home + one enforcement point, rather than a new
  shared Python helper (declined as over-engineering for two bespoke generators).
- **`licensing-and-credits.md`** — Section 4 (privacy bullet) and Section 6 (machine-enforcement list)
  now describe the secret/PII scan and the staleness check.
- **`project-profile.md`** — new `max_doc_age_months` key (default 6) with a comment, by the
  audience/reading-level block.

## Folded into 1.0.0 — 2026-06-19 (publish layer added)

### Added — publish layer (new skill + two shared files)
- **New skill `publish-mirror`** — the publish step the suite was missing. It mirrors repo-first
  Markdown that an authoring skill has already verified out to one or more targets (a wiki such as
  Confluence, an educational portal). It never authors content; the repository stays the source of
  truth and the default write path. Carries the governance gate into the publish layer:
  record-before-edit for a published artifact, a human gate on every write, the publish-reviewer
  afterwards, and the page-tracker closure rule.
- **`shared/render-contract.md`** — the canonical, target-agnostic conversion: the small fixed set
  of source primitives, a per-target adapter (Confluence built; HTML-portal a defined seam marked
  designed-not-yet-built), an **HTML-source path** (Section 1a) for a finished HTML page (the FAQ; an
  HTML usage guide) — faithful on a portal that hosts HTML, degraded to native structure on a wiki —
  and the honest promise of semantic fidelity with declared graceful degradation, not pixel parity.
  The conversion is now defined here once.
- **`shared/publish-targets.yaml`** — the per-project manifest (generalises the old single-target
  page-map): the one home of every target's coordinates, secrets by reference only, and a stable
  per-page id that makes a re-publish an update, not a duplicate. Both new shared files are copied
  into every skill bundle by the build (build-skills.sh patched).

### Changed — authoring skills point to the publish step (single source for the conversion)
- **learning-track** — its Step 7 used to describe the Markdown→wiki conversion inline; that prose
  is replaced with a pointer to `publish-mirror` and `render-contract.md`, so the conversion lives
  in exactly one place. Repo-first is kept explicit: the verified Markdown is always written to the
  repository first, and publishing is a separate, later step.
- **architecture-and-decisions, operations-runbook, onboarding-companion** — each gains the same
  short repo-first publish step (added, not replacing anything), so the handoff is uniform across
  every Markdown-producing skill.
- **usage-guide and project-faq publish by an HTML-source path (optional).** Their primary output
  is a finished HTML page, so they do not use the Markdown primitive mapping. `render-contract.md`
  now has an HTML-source path (Section 1a): faithful on a portal that hosts HTML, degraded to
  native structure on a wiki (interactivity is lost there — stated on the page). Each gains an
  **optional** repo-first publish step. The manifest gains an optional `source_format` flag
  (markdown | html; inferred from the file extension when omitted).


### Added — suite lint (2026-06-20, architecture-and-decisions session)
- **New `lint-render-restatement.py` (root, suite-level — not copied into any bundle) + a WARN-only
  step in `build-skills.sh`.** Machine-enforcement for the recurring cross-skill defect where the
  Markdown/HTML→target conversion leaks into a skill's publish step instead of staying in
  `shared/render-contract.md`. It targets only the **mapping construction** — a transformation
  connective (`becomes` / `renders as` / `maps to` / `turns into`) adjacent to a wiki/portal target
  idiom (`panels` / `lozenges` / `expand macro` / `info panel`), e.g. "callouts become panels" — and
  deliberately ignores bare target vocabulary a publisher legitimately names and any construction
  inside a code fence. It scans `skills/*/SKILL.md`, **skips `publish-mirror`** (handling targets is
  its job), and never reads `render-contract.md`. **WARN-only** in `build-skills.sh` (guarded with
  `|| true`, never changes build pass/fail); a `--strict` flag (exit 1 on any hit) is reserved for a
  dedicated suite-hardening session that is allowed to fix every skill it lights up. Currently it
  surfaces exactly one open finding — `project-faq/SKILL.md:103` (the F1 entry in
  `CROSS-SKILL-FINDINGS.md`) — and is silent on the other six skills.

### Added — shared/verify.py (2026-06-20, architecture-and-decisions session)
- **New check: a non-canonical built-vs-designed marker is flagged (`[designed, not yet built]`).**
  The house style, the architecture NFR/failure-mode methods, the render contract, and the module
  template all use the exact token `[designed, not yet built]`, and `render-contract.md` requires it to
  survive every publish target **verbatim** (downstream tools and readers match it literally). A
  bracketed near-miss — a dropped comma, `[designed but not yet built]`, `[designed, not built]` —
  silently defeats that guarantee. The verifier now **warns** (never fails) when a bracketed span
  carries "designed" plus "built"/"yet" but is not the exact token; it is fence-stripped (a documented
  example is exempt) and the match shape means an unrelated bracket (a citation `[3]`, `[see above]`)
  cannot trip it. The suite was already 100% canonical, so this adds no noise and guards against drift.
  Touches all seven skills.

### Changed — shared/verify.py (2026-06-20, learning-track session)
- **A glossary's reading grade is a warning, never a hard fail.** Flesch–Kincaid is built for
  continuous prose and over-reports on a definitions list, which must name the domain's terms; the
  real Aegis glossary tripped the readability FAIL for that reason alone — which both blocked the
  gate and contradicted the no-number-gaming rule. A file named `glossary` is now exempt from the
  readability FAIL: it warns instead, with a note to keep terms plain rather than strip them to lower
  the number. Every other page is unchanged. Touches all seven skills.

### Added — shared/verify.py (2026-06-20, learning-track session)
- **New check: GitHub-style alert tokens are flagged (`> [!NOTE]` and the rest).** The module
  template already bans them because non-GitHub renderers (wikis, plain Markdown) show the raw token;
  the verifier now warns when one appears outside a code fence, so a documented example stays exempt.
  Touches all seven skills.

### Added — licensing and credits (suite-wide)
- **`shared/licensing-and-credits.md`** — one canonical standard for how every document is licensed
  and credited: per-page footer, LICENSE file, About & credits page, the warranty/liability
  disclaimer, the attribution line for reshare, and IP rules — with separate **public** and
  **internal** variants chosen by each skill's scope. Copied into every skill bundle by the build.
- **All six authoring skills now apply it.** Previously only learning-track carried licensing; the
  other five (architecture-and-decisions, project-faq, usage-guide, operations-runbook,
  onboarding-companion) emitted
  documents with no licence, credit, or disclaimer. Each SKILL.md now references the standard and is
  required to apply it; the mandate lives once in `house-style.md` Section 9.
- **The verifier enforces it as a HARD FAIL.** A public page without the licence footer (the © line)
  fails; an internal doc set with no copyright notice anywhere fails; a missing licence id warns.
- **Profile additions:** `licence_disclaimer` (the verbatim AS-IS warranty/liability text),
  `code_licence` (MIT, for any source code — separate from the CC docs licence), and `year` (so the
  footer reads `© {{year}}` instead of a hard-coded 2026). The attribution line now names the brand
  and links GitHub for credit-on-reshare.

### Added
- **Build-time validation against the platform upload rules (`validate_skill.py`).** Mirrors the
  platform's `quick_validate.py`: every skill is checked before packaging, and `build-skills.sh`
  FAILS the build if a skill is invalid (description over 1024 chars or containing angle brackets,
  a frontmatter key outside the allowed set, a non-kebab-case or over-64-char name, or more than one
  SKILL.md). The error that used to appear only on upload now appears at build time.

### Added
- **Canonical-source build model.** Shared files (`house-style.md`, `project-profile.md`,
  `verify.py`, `ci/`) now live once in `shared/` and are copied into each `.skill` by
  `build-skills.sh`. This keeps all seven skills self-contained at install time while removing the
  6-copy drift hazard. The rule: edit `shared/`, never the bundled copies, then rebuild.
- **A shipped docs-as-code gate (`shared/ci/`)** — a ready pre-commit hook and GitHub Actions
  workflow that run the verifier, with a per-skill mapping table. The house style mandated this
  gate; the suite now ships it.

### Fixed — shared/verify.py
- **The verifier now actually reads the profile per skill (this is the important one).** The
  earlier `--skill` support silently fell back to the default grade/scope because the skill name
  (`learning-track`, hyphen) did not match the profile key (`grade_target_learning_track`,
  underscore), and four of the six profile stems (`faq`, `architecture`, `runbook`, `onboarding`)
  did not match their skill folder names at all. The verifier now normalises hyphens to underscores
  and keeps backward-compatible aliases for the legacy short stems, so `--skill <name>` resolves the
  profile value. The resolution source is printed (`grade-target=… (profile|flag|default)`) so a
  silent fallback can never hide again.
- Replaced the hand-rolled regex profile parser with real `yaml.safe_load` over the profile's
  embedded YAML blocks (PyYAML); a plain `.yaml` profile is also supported; graceful notice if
  PyYAML is absent.
- `extra_banned_words` is wired into the banned-words check (was computed and discarded).
- Two-tier internal-reference terms: filenames/acronyms/tool names hard-fail on public pages;
  ordinary English words (e.g. "backbone", "handoff") only warn — ending false positives on
  legitimate public prose.

### Changed — shared/project-profile.md
- Renamed the per-skill grade/scope keys so each stem matches its skill name exactly
  (`grade_target_project_faq`, `…_architecture_and_decisions`, `…_operations_runbook`,
  `…_onboarding_companion`). The verifier's aliases keep older profiles working.
- Documented the `--skill` convention and the two-tier internal-terms behaviour inline.

### Changed — shared/house-style.md
- Section 11 shows the `--skill` (profile-driven) invocation instead of hardcoded grade/scope flags.
- Section 12 points the docs-as-code and version-the-documents clauses at the shipped `ci/` gate and
  the changelog discipline.

### Changed
- **learning-track description trimmed** from 1019 to 923 characters for safe headroom
  under the 1024 limit (triggers and the use-this-not-that boundary preserved).

### Changed — all six authoring skills
- Each `SKILL.md` now invokes the verifier in `--skill` form, removing the inline duplication of the
  grade/scope values the profile already holds (single source of truth).

### Note
- **architecture-and-decisions** now carries its v1.1.0 content (see its `CHANGELOG.md`): the
  operational "Before you start" section, the new `nfr-posture-method.md` reference, the
  reference-values-by-key rule, the diagram-method and failure-mode-method additions, the `--license`
  pass, and a use-this-not-that boundary. That session changed **no shared file**, so the other skills
  are unaffected.
- Skill-specific content for project-faq, usage-guide, operations-runbook, and onboarding-companion is
  unchanged in this pass — those are scheduled for their own focused sessions. learning-track carries
  its v1.2.0 content (see its CHANGELOG).
