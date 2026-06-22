# Per-skill review & rebuild prompt (reusable)

**How to use:** start a fresh chat, replace `{SKILL_NAME}` below with one of
`learning-track · architecture-and-decisions · project-faq · usage-guide · operations-runbook ·
onboarding-companion · publish-mirror`, and attach:

1. **`project-doc-skills-source.zip`** — the whole skills workspace (shared files, all seven skills,
   the build script, and the validator). This is the unit of work; the chat hands it back updated.
   Always attach the **latest** workspace zip, so improvements accumulate across sessions.
2. **The Aegis source files for this skill's domain** — see the table at the end.

Then paste everything between the lines.

> `{SKILL_NAME}` is this prompt's own fill-in marker — replace it before pasting. It is **not** the
> same as the skills' `{{key}}` placeholders (such as `{{project_name}}`), which are a suite-wide
> convention you must keep intact in skill content. See Step 3.

> **What changed in the suite (read this once).** The suite is now **seven** skills: the six
> authoring skills plus **`publish-mirror`**, the separate publish step that mirrors a verified repo
> page out to one or more targets (a wiki such as Confluence, an educational portal). It never
> authors content. Two shared files came with it and are copied into every skill bundle at build
> time: **`render-contract.md`** (the single standard for how a page is converted to each target —
> source primitives, per-target adapters, and the HTML-source path) and **`publish-targets.yaml`**
> (the per-project manifest of target coordinates). An authoring skill that produces publishable
> pages now ends with a short repo-first publish step that points to `publish-mirror`; it must keep
> that pointer and must not restate the conversion.

---

You are improving ONE skill in a seven-skill documentation suite: **{SKILL_NAME}**. The suite shares
canonical files (`house-style.md`, `project-profile.md`, `licensing-and-credits.md`,
`render-contract.md`, `publish-targets.yaml`, `verify.py`, `ci/`) that live in `shared/` and are
copied into each packaged skill by `build-skills.sh`. Work inside the attached workspace.

## Step 1 — Read everything before writing a word
- Unpack `project-doc-skills-source.zip`. Read `README.md` and `CHANGELOG.md` to learn the build
  model and the shared-file boundary.
- Read the target skill in full: `skills/{SKILL_NAME}/SKILL.md` and every file under it, plus the
  `shared/` files it depends on.
- Read `shared/licensing-and-credits.md` — the single standard for how every document the suite
  produces is licensed and credited: the per-page licence footer, the `LICENSE` file and About &
  credits page, the public vs internal variants, and the `{{key}}` placeholder convention. The skill
  must **reference** this standard, not restate it.
- Read `shared/render-contract.md` — the single standard for how a repo page is converted to each
  publish target: the small fixed set of source primitives, the per-target adapters (Confluence
  built; HTML-portal a defined seam), and the HTML-source path for a finished HTML page. An authoring
  skill that produces publishable pages **references** this (a short repo-first publish step that
  hands off to `publish-mirror`) and never restates the conversion. If `{SKILL_NAME}` is
  `publish-mirror`, also read `shared/publish-targets.yaml` (its manifest asset) in full.
- Read every attached Aegis source file in full — do not skim. If a source the skill should draw on
  is missing, say so before proceeding.
- Read `CROSS-SKILL-FINDINGS.md` at the workspace root if it exists — it is the carry-over log where
  an earlier session recorded a defect that affects a skill it was not allowed to edit. Note every
  open entry that names **this** skill; you will resolve those in Step 4 (that is the point of the
  log). Ignore entries for other skills except to confirm yours is not among them.

## Step 2 — Verify, never assert
- Wherever you would otherwise guess — a code path, a contrast ratio, a cross-reference, whether a
  library is installed, whether a check actually fires — check it by reading or running it. Ground
  every claim in a file path or a command you ran.
- Re-test every fix against a value that DIFFERS from the default. A wrong fix can pass as "green"
  against the default value — that is exactly how a real bug shipped in this suite once. Print the
  resolved values so a silent fallback cannot hide.
- This includes the **licensing gate**: confirm `verify.py` still hard-fails a public page with no
  `©` footer, and that `--license <LICENSE>` fails a LICENSE that drops the warranty disclaimer or
  does not name the content licence. Run these against a profile whose `scope` differs from the
  default, so a silent public/internal flip cannot disguise a pass. (`verify.py` also fails an
  internal document **set** that carries no `©` anywhere — the internal scope is not a free pass.)
- If `{SKILL_NAME}` is `publish-mirror`, the licensing gate it owns is **footer-preservation on the
  target**, checked by the publish-reviewer in `render-contract.md` Section 4, not a footer this
  skill emits. Verify the publish-reviewer still lists the footer check and the duplicate-prevention
  (bound-id) check, and that `publish-targets.yaml` keeps secrets by reference only and one home per
  coordinate (no value in two places).

## Step 3 — Review ruthlessly, in three lenses
First a ruthless review grounded in fact and in enterprise-quality engineering and teaching
experience. Then a **Fable-5 lens**: if a staff/principal reviewer with your experience were in your
shoes, where would they draw blood? Then an **unbiased pass** that drops anything you claimed but
could not verify. Cover at least:
- **The operational layer (where these skills are weakest).** State concretely: what inputs the
  skill needs; WHEN in a Claude-Code build to invoke it (on an empty repo? per commit? per
  milestone? at the end?); and how it sequences with the other six skills (producer/consumer order,
  and use-this-not-that boundaries). No hand-waving.
- **The publish handoff.** If the skill produces publishable pages, does it end with a short
  repo-first publish step that hands off to `publish-mirror` and points to `render-contract.md` —
  rather than restating the Markdown→target conversion inline (single source for the conversion)? Is
  repo-first kept explicit (the verified source is always written to the repo first; publishing is a
  separate, later step; never author in the target)? For `publish-mirror` itself, judge the render
  contract, the manifest discipline (stable per-page id to prevent duplicates; secrets by reference;
  no value in two places), the governance gate (record-before-edit, human gate, publish-reviewer,
  closure), and the honest promise of semantic fidelity with **declared** graceful degradation.
- **Generality.** Does it hardcode Aegis specifics that should be project-agnostic, while keeping the
  transferable methodology? Placeholders use `{{key}}` (double curly, matching a key in
  `project-profile.md` or `publish-targets.yaml`) — never a literal project name, never `<...>`,
  never single-curly `{...}`.
- **Licensing & credits.** Does every page the skill produces carry the licence footer, and does the
  document set ship a `LICENSE` and an About & credits page, in the public or internal variant the
  profile's `scope` selects? Is the warranty disclaimer **referenced** from the profile
  (`{{licence_disclaimer}}`) rather than pasted (no value in two places)? Are the title, footer, and
  LICENSE built from `{{project_name}}` and never a hard-coded name? The verifier should fail a
  public page with no footer and, with `--license`, a LICENSE that omits the disclaimer. (For
  `publish-mirror` this lens is footer-preservation on the target — see Step 2.)
- **Methodology completeness.** Did it drop any hard-won method captured in the attached handoffs?
- **Machine-checkable vs human judgement.** Is the skill's verifier/generator (for `publish-mirror`,
  the publish-reviewer) doing what the skill promises? Add deterministic checks only where they are
  genuinely low-false-positive. A recurring cross-skill defect — e.g. the Markdown-to-target
  conversion leaking into a publish step instead of staying in `render-contract.md` — is a candidate
  for a suite-level lint; whether and how to add one is governed by Step 4's "Cross-skill findings"
  rule (it must target the mapping construction, and WARN rather than FAIL in a single-skill session).
- **Trigger boundary.** Does the description collide with a sibling skill? Add a use-this-not-that
  line — within the limits in Step 5.

## Step 4 — Make the changes, in the workspace, additively
- Prefer surgical, additive edits to `skills/{SKILL_NAME}/` over rewrites; keep what works.
- If a change genuinely belongs in a shared file, make it directly in `shared/` (it must be additive
  and good for ALL seven skills), then rebuild every skill and sanity-check that nothing else
  regressed. Do NOT fork the bundled copy, and do NOT hand back a diff to apply by hand — apply it.
- `licensing-and-credits.md` and `render-contract.md` are both shared files: a licensing or credits
  change belongs in the former, and a conversion / target / visual-fidelity change belongs in the
  latter — never inlined into a skill as a literal name, a second copy of the disclaimer, a restated
  conversion, or a `{...}` / `<...>` placeholder.
- Do NOT touch the bespoke content of the other six skills; they have their own sessions.

### Cross-skill findings — read-only on siblings, but never lost
The no-touch rule above is absolute for *editing* a sibling. It is **not** a reason to let a finding
evaporate in chat: a defect you find in one skill usually recurs in others, and the next session has
no way to know unless you record it. So:
- **Resolve inbound first (the log is two-way).** If `CROSS-SKILL-FINDINGS.md` (workspace root) has an
  open entry naming the skill you are improving, fix it here as part of the work and mark it
  `[resolved YYYY-MM-DD]` (or delete the line). A write-only log is useless; clearing your own
  inbound entries is what makes it work.
- **Audit, report, record — outbound (Options A + B).** When a defect you fixed here likely affects
  siblings, you MAY *read* their `SKILL.md` to confirm, but you must NOT edit them. Then do both: (a)
  report each affected sibling by **file and line** in the chat summary; and (b) append it to
  `CROSS-SKILL-FINDINGS.md` so that sibling's own session inherits it. Use that file as the **one**
  home for these (do not also note them in the CHANGELOG — same no-value-in-two-places rule). Create
  it with a one-line header if absent; it is internal scaffolding (root-level, never copied into a
  bundle by `build-skills.sh`).
- **Machine-enforce only with care (Option C).** A recurring restatement can be promoted to a
  low-false-positive **suite lint**, but design it precisely: target the *mapping construction* — a
  source primitive described as turning into a target idiom, the tell being a verb or arrow that joins
  them ("callouts become panels", "collapsible blocks become an expand macro") — NOT bare vocabulary
  like "status lozenge" or "panel", which a publisher legitimately names when handling a target. Put
  it in a **new** suite-level check (a step in `build-skills.sh`, or a small `lint-*.py` it calls) —
  NOT in `verify.py` (which checks the docs a skill *produces*) and NOT in `validate_skill.py` (upload
  rules only). In a single-skill session it must **WARN, never FAIL**: a hard FAIL would break a
  sibling's build that you are forbidden to fix. Promoting it to FAIL — and fixing every skill it
  lights up — is the job of a dedicated **suite-hardening session** (one focused session on the shared
  layer that *is* allowed to touch all seven; this is not "one session per skill"), not a per-skill
  session.

> **Note (since the 2026-06-20 suite-hardening pass):** the render-restatement lint
> (`lint-render-restatement.py`) is **now an active gate** — `build-skills.sh` runs it with `--strict`
> and a finding **fails the build**. All seven skills were clean when it was promoted. So if your
> session restates the Markdown/HTML→target conversion in `skills/{SKILL_NAME}/SKILL.md`, the build
> will break and name the file:line; fix it by stating only the reader-facing consequence and pointing
> to `render-contract.md` (do not restate the per-element mapping). Running the lint by hand still
> defaults to WARN.

## Step 5 — Obey the hard packaging rules (non-negotiable; the platform rejects violators on upload)
The build validates these, but write to them from the start:
- **`description` <= 1024 characters** (aim for <= 950 for headroom) and it must contain **NO angle
  brackets** (`<` or `>`). Keep it a strong trigger — list the phrasings a user would actually type
  — plus the use-this-not-that boundary, but stay in budget. Never put a `<skill-name>`-style
  placeholder in the description.
- **Frontmatter keys limited to:** `name, description, license, allowed-tools, metadata,
  compatibility`. Nothing else — put any version line in the BODY, not the frontmatter.
- **`name`** kebab-case (lowercase letters, digits, hyphens), <= 64 chars; keep the existing name.
- **Exactly one `SKILL.md`** per skill.

## Step 6 — Build, validate, and deliver the COMPLETE package
- From the workspace root run `./build-skills.sh`. It validates every skill against the rules in
  Step 5 and FAILS if any is invalid. Confirm the target skill builds and prints `valid (...)`. Fix
  anything it flags and rebuild until clean. (To check one skill by hand:
  `python3 validate_skill.py skills/{SKILL_NAME}`.)
- Deliver with `present_files`:
  1. the rebuilt **`{SKILL_NAME}.skill`** (ready to install), and
  2. the **updated `project-doc-skills-source.zip`** (the whole workspace, so it becomes the input
     to the next skill's session).
- In the chat give me: concise bullet observations (the three lenses), the final decision, and a
  one-line note of any shared-file change you made and which other skills it touched (a change to
  `licensing-and-credits.md`, `render-contract.md`, `verify.py`, or another `shared/` file touches
  all seven). If you resolved an inbound `CROSS-SKILL-FINDINGS.md` entry, or logged a new outbound one
  (with file and line), say so and name the file — the carry-over trail must be visible, not buried in
  chat. Do not give me homework — everything must be applied and built.

Standard: the delivered skill should be something I could not deny or see scope to improve.

---

### File-attachment guide — the Aegis sources to attach per skill

The licensing & credits standard and the render contract are already in the workspace
(`shared/licensing-and-credits.md`, `shared/render-contract.md`) — no separate attachment is needed
for them.

| `{SKILL_NAME}` | Attach these (besides the workspace zip) |
|---|---|
| learning-track | `CONTENT-BUILD-BRIEF.md`, the learning-companion + build-template handoffs, `M0/M1/M2`, the ai-deep-dive and building-with-ai-and-practice handoffs |
| architecture-and-decisions | ADR files `0001`–`0019`, `aegis-diagram-set-handoff.md`, `failure-mode-analysis-and-recovery.md`, `0015-scalability-design.md`, backbone `m2`/`m4` |
| project-faq | `aegis-faq-generation-handoff.md`, `glossary.md`, `M0/M1/M2` |
| usage-guide | `aegis-integration-handoff-v2.md`, `M2`, and a real target API doc if you have one |
| operations-runbook | `runbook-template.md`, `0017-operational-failure-mode-analysis.md`, the observability + monitoring handoffs, `nfr-slo-error-budget-register.md` |
| onboarding-companion | `aegis-building-with-ai-and-practice-handoff.md`, `aegis-cowork-operating-blueprint.md`, `M0` |
| publish-mirror | `aegis-integration-handoff-v2.md`, `aegis-cowork-operating-blueprint.md`, `aegis-learning-companion-build-template-handoff.md` (the Markdown→Confluence mapping), `aegis-diagram-set-handoff.md` (watermark/border/colour rules), backbone `m3-governance-and-process.md` (record-before-edit, publish-reviewer, closure) |
