# Changelog — usage-guide skill

Skill-specific changes. Shared/suite changes live in the root `CHANGELOG.md`. Format follows Keep a
Changelog.

## [1.1.0] — 2026-06-20

Resolves the inbound cross-skill finding **F4** (see `CROSS-SKILL-FINDINGS.md`): usage-guide was the
suite's other HTML producer but shipped no generator, so the `©` footer, the About & credits block, and
the ISO last-reviewed stamp the FAQ now makes automatic had to be hand-added on a usage-guide HTML page
(only the `©` was caught — by the verifier backstop, after the fact). Closed by giving usage-guide its
own generator, so the three are automatic by construction. No shared file changed (the generator is
this skill's own asset), so nothing else in the suite is touched.

### Added
- **`assets/usage_guide_generator.py`** — a small, friendly, illustrated single-file-HTML generator for
  a grade-1 how-to (linear layout: big numbered steps, "what you will see" boxes, pictures, "if X → do
  Y" rows, glossary). It bakes in, by construction: the `©` licence **footer** (render-contract.md P14;
  watermark never replaces it), a first-class **`credits`** About & credits block (licensing-and-
  credits.md Section 4, kept plain/short — the full attribution line and disclaimer stay off the page),
  and a machine-readable **last-reviewed** stamp (`<meta name="last-reviewed">` + a visible line,
  render-contract.md P2). Fails loud rather than ship a defect: a picture with no `alt` raises, and a
  missing footer / missing credits block prints a NOTE. Values come from the profile (never a hard-coded
  name); distinctive friendly type (Baloo 2 / Nunito / JetBrains Mono), the house palette, AA contrast,
  one `h1`, a `lang` attribute, a skip link, and ✓+word success cues. The demo is written at grade ~1
  so it passes `verify.py --skill usage-guide`.

### Changed — `SKILL.md`
- New **"Before you start (inputs, when to run, where it sits)"** section: the inputs the skill needs,
  *when* to run it in a Claude-Code build (not an empty repo, not per commit; once a user-facing path
  works, refresh per release), and how it sequences with the other six skills (producer/consumer order
  and use-this-not-that — one task at a time is the line this skill holds).
- New Workflow **step 5 ("Build the page, repo-first")** wiring the generator (footer + `credits` block
  + `last_reviewed`), with Markdown kept as an option carrying the same three by hand; verify/present/
  publish renumbered to 6/7/8.
- Description gains a **sibling trigger boundary** (not learning-track / project-faq / architecture-and-
  decisions / onboarding-companion).
- Quality bar gains the footer / About & credits / staleness / secret-scan self-checks; the licensing
  paragraph documents the generator wiring (referencing `licensing-and-credits.md`, never restating);
  the structure section adds an **About & credits** section; references list adds the generator,
  `render-contract.md`, and `publish-targets.yaml`. Body version line added (v1.1.0).

### Changed — `references/usage-guide-structure.md`
- Standardised the example's placeholder style to the suite `{{key}}` convention (`{{contact}}`,
  `{{docs_home}}`) instead of square-bracket `[who]` / `[where]` slots.

## [1.0.0] — earlier

- Initial usage-guide skill: a grade-1 how-to builder (strict simple-English rules, the section-by-
  section structure, the readability gate via the shared verifier) with an optional repo-first publish
  step that hands the page to `publish-mirror` via the render contract's HTML-source path.
