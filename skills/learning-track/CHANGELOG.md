# Changelog — learning-track skill

All notable changes to this skill are recorded here. Format follows Keep a Changelog; versions
follow Semantic Versioning. This skill is documentation-as-code: it is versioned, and a learning
track it produces should keep its own short changelog too.

## [1.3.1] — 2026-06-22

Picked up in suite-hardening pass 2 (root `CHANGELOG.md` 1.0.0).

### Fixed
- **The module last-reviewed stamp is now an ISO literal** (`references/module-template.md`). It read
  `Last reviewed: <date>` and real modules emitted a human date ("12 June 2026"), which the shared
  staleness check (ISO-only) could not read — so the suite's most stale-prone document was silently
  exempt from the freshness gate. The stamp is now `Last reviewed: YYYY-MM-DD` and the `<date>`
  angle-bracket placeholder is dropped, so a stale module now WARNs as intended. (Closes
  `CROSS-SKILL-FINDINGS.md` F3; the matching shared regex widening is recorded in the root changelog.)

## [1.3.0] — 2026-06-20

### Fixed
- **`module-template.md` no longer restates the About & credits contents (single source for
  licensing/credits).** Its "About & credits page" step listed the page's contents inline — a partial
  copy of `licensing-and-credits.md` Section 4 that had silently dropped the **no-personal-data rule**
  Section 4 mandates, so an author following the template would have shipped a credits page missing the
  privacy clause. The step now points to Section 4 as the single source (public or internal variant per
  the profile's `scope`) and folds the privacy clause back into a short preview, matching this skill's
  own `SKILL.md` licensing pointer and the reference-don't-restate discipline the licence footer and the
  render contract already follow. No content was lost; the drift hazard and the omission were removed.

### Changed
- **Description: added the missing use-this-not-that boundary against `onboarding-companion`.** Both
  skills are tutorials for newcomers, yet neither named the other — the only sibling-tutorial boundary
  learning-track had not triangulated (it already did so with architecture-and-decisions). The
  description now adds "NOT contributor onboarding (use onboarding-companion)", so a request to onboard
  contributors to a codebase routes to the contributor skill instead of colliding here. Re-tightened to
  935/1024 with no angle brackets by dropping the publish-posture phrase ("ready to publish to a wiki" —
  publishing is not a trigger for this skill; `publish-mirror` owns it) and one redundant example;
  every distinct trigger phrase is preserved. The reciprocal gap (onboarding-companion's description
  not naming learning-track) is recorded in `CROSS-SKILL-FINDINGS.md` for that skill's own session.
- **`module-template.md` placeholder note made precise.** "Values in braces come from the project
  profile" was ambiguous because the template uses both `{{key}}` (profile-resolved) and `<...>`
  (author-chosen per-module slots such as the title, slug, and date). The note now distinguishes the
  two, so an author does not hunt for a profile key behind `<title>`.

### Notes
- **No shared file changed in this session.** Every edit is confined to `skills/learning-track/`
  (plus the root `CROSS-SKILL-FINDINGS.md` scaffolding, which is never bundled into a `.skill`). The
  other six skills are unaffected; the build and the suite lint behave exactly as before.

## [1.2.1] — 2026-06-20


### Fixed
- **Step 7 no longer restates the Markdown-to-target conversion (single source for the conversion).**
  The previous wording claimed "this skill does not restate it" while doing exactly that — spelling
  out the mapping inline ("collapsible blocks become expand macros, callouts become panels, the
  table-of-contents line becomes a TOC macro, … the licence line becomes a footer panel"). That is a
  second copy of `render-contract.md` Section 2a (the Confluence adapter), the precise drift hazard
  the shared-file model exists to remove: if an adapter's mapping changes, the copied prose silently
  goes stale. Step 7 now names only the page's renderable *parts* and points to `render-contract.md`
  as the single source for how each is converted to a target's idiom — matching the more disciplined
  publish step the sibling Markdown skills already use. Repo-first stays explicit (verified Markdown
  is written to the repository first; publishing is a separate, later step via `publish-mirror`); the
  per-module incremental cadence and the glossary-update rule are unchanged.

### Changed
- **`render-contract.md` (and the publish-targets manifest) added to the References list.** Step 7
  relies on `references/render-contract.md`, but the References section omitted it; the bundle ships
  it (the build copies it in), so the list now names it and the per-project `publish-targets.yaml`
  manifest the publish step reads.

### Notes
- **No shared file changed in this session** — the fix is confined to `skills/learning-track/SKILL.md`,
  so the other six skills are unaffected. The sibling Markdown skills (architecture-and-decisions,
  operations-runbook, onboarding-companion) carry a more restrained version of the same publish step;
  if any still leans toward the target mapping, that is for its own session, not this one.

## [1.2.0] — 2026-06-20

### Added
- **A use-this-not-that boundary against `architecture-and-decisions`** in the `description` and in
  `SKILL.md` ("Where this fits"). Both skills own *why*; the split is audience and arc — learning
  track is a zero-to-understanding, mixed-audience course with a practice ladder, whereas
  architecture-and-decisions is a focused design/decision walkthrough for one technical reader who can
  already use the system. Closes the trigger collision on requests like "explain the design and the
  why". The `description` was also generalised (dropped the "built with an AI coding agent" narrowing
  so it triggers for any project) and trimmed to 948/1024 with the new boundary, no angle brackets.
- **The two-examples / everyday-analogy requirement is now in `module-template.md`.** House style
  Section 6 mandates a concrete in-project example *and* an everyday analogy (or per-audience bridge)
  for every explanatory page; the template an author follows now states it, instead of relying on the
  writer's instinct.
- **A "building with AI responsibly" blueprint** in `references/information-architecture-method.md`
  for projects built with an AI coding agent — the transferable Part F capstone lesson (the
  structure-for-speed debt trap; the cited-and-caveated evidence on AI-generated-code security; the
  fast-junior-developer operating model with the human as final gate; lifecycle + AI literacy +
  judgement first; the single neutral AI-assistance line). Restores parity with the already-restored
  deep-dive and practice-ladder shapes, which had left this collapsed to two words.
- **`--license LICENSE` added to the prescribed local verifier command** in `SKILL.md` Step 6, so an
  author's own pre-present pass confirms the LICENSE carries the warranty disclaimer and names the
  content licence — the check the shipped CI gate already runs.
- **Glossary-density guidance** in `module-template.md` and `SKILL.md`: a glossary is a definitions
  list and reads denser than the teaching target; the verifier now treats that as a warning, not a
  failure, so necessary terms are not stripped to chase the score.

### Changed — `scripts/verify.py` (shared; touches all seven skills — see root CHANGELOG)
- **A glossary no longer hard-FAILs the readability gate.** Flesch–Kincaid (built for prose)
  over-reports difficulty on a definitions list, which must name the domain's terms; a high grade on a
  file named `glossary` is now a WARN, never a FAIL. Verified glossary-only: identical text under a
  different filename still FAILs. This unblocks the suite's "verifier passes (no FAIL)" bar on the
  real shipped glossary, which previously FAILed (~10.8 vs a 9 target).
- **A new low-false-positive check for GitHub-style alert tokens** (`> [!NOTE]` and kin), which the
  module template bans because non-GitHub renderers show the raw token. Fence-aware (a documented
  example inside a code block is exempt).

## [1.1.0] — 2026-06-19

### Added
- **Operational guidance in `SKILL.md`** — a "Before you start" section answering three questions a
  new project raises:
  - *What this skill needs* — the required inputs (filled profile, one-line summary, architecture,
    ADR sequence, contracts/interfaces, stack-with-the-why, phase plan, and the AI techniques used),
    and an explicit stop: do not start on an empty repository; run architecture-and-decisions first.
  - *When to run it in the build* — a three-wave, milestone-anchored cadence (foundations early;
    build/deep-dive modules as each capability's ADR lands; practice ladder at the end). Explicitly
    not per-commit and not end-only. The link-back rule (teach the stable concept, link the volatile
    specific) is stated as the anti-staleness mechanism.
  - *Where it fits among the documentation skills* — run architecture-and-decisions first/in
    lockstep; the use-this-not-that boundary against usage-guide (how-to), project-faq (reference),
    and onboarding-companion (internal), plus operations-runbook for operator steps.
- **A concrete depth bar in `SKILL.md` Step 5** — the retrieval reference set (hit-rate, answer
  correctness, where naive approaches fail, the honest-builder thread) as the worked standard for
  "teach failure modes", applied to every distinctive technique.
- **A distinct AI-accuracy critic** in the authoring loop (Step 6), separate from the general expert
  critic, for AI projects.
- **A grounding step** (Workflow Step 1): tie each project claim to a path/ADR/issue; cite field
  facts; never fabricate.
- **AI-project deep-dive shape and a multi-audience practice-ladder blueprint** in
  `references/information-architecture-method.md`, restoring the transferable structure (talking to
  models, retrieval internals, tools/MCP, agents, safety; and the AI-testing/trust modules) that the
  reusable shape had collapsed to a single line.
- **The one-time global built-vs-designed honesty panel** and the **"two honest notes for readers
  who already know X"** convention in `references/module-template.md`, plus guidance to cite field
  facts precisely with their honest caveat.
- **`ci/`** — a ready pre-commit hook and a GitHub Actions workflow that run the verifier over the
  docs, so the docs-as-code-in-lockstep rule the house style mandates is actually shipped.
- **`CHANGELOG.md`** (this file) and a version stamp in `SKILL.md`.

### Fixed (`scripts/verify.py`)
- **The verifier now reads the profile.** With `--skill <name>` it resolves `grade_target_<skill>`
  and `scope_<skill>` from the project profile (an explicit CLI flag still overrides). The profile's
  per-skill targets are no longer decorative.
- **Replaced the hand-rolled regex profile parser with real YAML parsing.** The profile's embedded
  fenced `yaml` blocks are parsed with `yaml.safe_load` (PyYAML); a plain `.yaml` profile is also
  supported. If PyYAML is absent the profile is skipped with a notice rather than mis-parsed.
- **`extra_banned_words` is now wired in** (it was computed and then discarded — dead code).
- **Two-tier internal-reference terms.** Unambiguous internal artifacts (filenames, acronyms, named
  tools) still hard-FAIL on public pages; ordinary English words that are also internal jargon
  (for example "backbone", "handoff") now only WARN, ending false-positive failures on legitimate
  public prose. Profile-supplied internal terms are classified into the right tier automatically.

### Notes
- `references/house-style.md` and `assets/project-profile.md` are intentionally unchanged: they are
  shared across the documentation-skill suite, and editing this copy alone would create drift. The
  additions above that logically belong to the shared standard (the AI-accuracy critic, the depth
  bar) are placed in the learning-track-owned files as an addendum that *extends* the shared loop,
  not a fork of it. When the suite adopts them, fold them into the canonical shared copy.

## [1.0.0] — 2026-06-18
- Initial learning-track skill: workflow, house style, information-architecture method, module
  template, project profile, and verifier.
