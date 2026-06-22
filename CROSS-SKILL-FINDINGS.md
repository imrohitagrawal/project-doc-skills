# Cross-skill findings — the carry-over log

Internal scaffolding (root-level; **never** copied into a `.skill` bundle by `build-skills.sh`). Use
this when a per-skill review session finds a defect in a **sibling** skill it is not allowed to edit.

## How this works (two-way)

A per-skill session may **edit only its own skill**. But a defect found in one skill usually recurs in
others, and a note left only in chat is lost by the next session. So each session:

1. **Reads this file first** (review prompt, Step 1) and **resolves any open entry naming the skill it
   is improving** as part of that session's work — then marks it `[resolved YYYY-MM-DD]` or deletes
   the line. Clearing your own inbound entries is what makes the log worth keeping.
2. **Logs outbound findings**: when it fixes a defect that likely affects siblings, it reads (not
   edits) their `SKILL.md` to confirm, reports each by **file and line** in chat, and appends an entry
   here. This file is the **single** home for these (not the CHANGELOG — same no-value-in-two-places
   rule the suite uses everywhere).

Keep entries short: skill · file:line · what · why it matters · suggested action (the owning session
decides) · status.

---

## Open findings

None at present. The three findings carried here through 2026-06-21 (F3, F5, F7) were all resolved in suite-hardening pass 2 on 2026-06-22 and moved to **Resolved** below.

## Resolved

### F3 — learning-track's last-reviewed stamp is human-format, so the new staleness check can't read it  [resolved 2026-06-22]
- **Skill:** learning-track
- **Where:** `skills/learning-track/references/module-template.md:11` (the Stamp block:
  `… · Last reviewed: <date>`).
- **What:** the 2026-06-20 suite-hardening pass added a staleness check to `shared/verify.py` that reads
  an **ISO `YYYY-MM-DD`** date only (`render-contract.md` P2 now pins ISO). The module template
  instructs `Last reviewed: <date>` with no format, and real output (the Aegis modules) is
  "Last reviewed: 12 June 2026". For that, `check_staleness` returns **INFO** ("no machine-readable
  date"), so the staleness gate is **silently inert** on learning-track. Verified by running
  `check_staleness`: an ISO stamp WARNs when old; "12 June 2026" returns INFO.
- **Why it matters:** a multi-module course is the doc most likely to go stale, and the new gate never
  fires on it. Separately, `<date>` is an angle-bracket placeholder — the suite convention is `{{key}}`
  or an ISO literal, never `<...>`.
- **Suggested action (learning-track session decides):** change the stamp to a real ISO literal
  (`Last reviewed: YYYY-MM-DD`, not `<date>`) and update the example modules to ISO, so the staleness
  check reads them. Skills that emit no stamp (architecture-and-decisions, operations-runbook,
  onboarding-companion, usage-guide) get an INFO nudge only — acceptable, but any stamp they add later
  must be ISO.
- **Resolution (suite-hardening pass 2, 2026-06-22):** the stamp in `module-template.md` is now the ISO literal `Last reviewed: YYYY-MM-DD` (the `<date>` angle-bracket placeholder dropped). Paired shared fix: `verify.py`'s last-reviewed regex was widened to also read the bold-closed form `**Last reviewed:** DATE` (it already read the date-inside-bold form), so both bold forms, the plain form, and the `<meta>` form read — locked by a golden pin. A stale module now WARNs. Recorded in learning-track 1.3.1 + root `CHANGELOG.md` 1.0.0. **Found by:** project-faq session, 2026-06-20. **Resolved by:** suite-hardening pass 2, 2026-06-22.

### F5 — project-faq's `{{today}}` placeholder does not resolve to a profile key  [resolved 2026-06-22]
- **Skill:** project-faq
- **Where:** `skills/project-faq/references/faq-method-and-question-bank.md:55`
  (`"last_reviewed": "{{today}}"`), added in the 2026-06-20 hardening pass.
- **What:** the placeholder convention is `{{key}}` matching a key in `project-profile.md` /
  `publish-targets.yaml`. `today` is **not** a profile key (the profile has `year`). The generator demo
  uses `datetime.date.today()`, so the intent is the current date — a **runtime** value — but the
  reference example shows `{{today}}`, which an agent filling the template cannot resolve from the
  profile.
- **Why it matters:** minor, but it is a placeholder that does not resolve — the exact class the
  generality rule bars (`{{key}}` must back to a real key); introduced alongside otherwise-correct work.
- **Suggested action:** either document a small set of **runtime** tokens (e.g. `{{today}}` = the build
  date) in `project-profile.md` / `licensing-and-credits.md` so the convention is explicit, or reword
  the example to a literal instruction ("set to today's date, `YYYY-MM-DD`"). Low priority.
- **Resolution (suite-hardening pass 2, 2026-06-22):** option (a) — `project-profile.md` now declares a small **Runtime tokens** set (`{{today}}` = build date, `{{canonical_url}}` = the published URL wired at publish), and `licensing-and-credits.md` cross-references it; the faq-method reference points at that section instead of using `{{today}}` as if it were a profile key. A new build-time gate, `lint-placeholders.py --strict`, confirms every `{{...}}` resolves to a profile key, a manifest slot, or a runtime token. Recorded in project-faq 1.2.1 + root `CHANGELOG.md` 1.0.0. **Found by:** project-faq session, 2026-06-20. **Resolved by:** suite-hardening pass 2, 2026-06-22.

### F7 — operations-runbook's SKILL.md uses the legacy profile-key stems (`grade_target_runbook` / `scope_runbook`)  [resolved 2026-06-22]
- **Skill:** operations-runbook
- **Where:** `skills/operations-runbook/SKILL.md:51` (`grade_target_runbook` and `scope_runbook`).
- **What:** the profile's canonical per-skill keys were renamed so each stem matches its skill name
  exactly (`grade_target_operations_runbook` / `scope_operations_runbook`); 4 of 6 authoring skills
  were aligned, and onboarding-companion was aligned in its 2026-06-21 session. operations-runbook
  still names the legacy short stems. It is **not broken** — the verifier keeps backward-compatible
  aliases (`runbook` -> `operations_runbook`), so resolution still works — but the prose names a key
  the profile no longer spells that way, a minor drift from the rename decision.
- **Why it matters:** cosmetic/consistency only (works via the alias). Worth aligning so the skill's
  own instruction matches the profile's canonical keys, as its siblings now do.
- **Suggested action:** in operations-runbook's own session (or a suite-hardening pass), change the two
  references to `grade_target_operations_runbook` / `scope_operations_runbook`. Low priority.
- **Resolution (suite-hardening pass 2, 2026-06-22):** `operations-runbook/SKILL.md` now names the canonical stems `grade_target_operations_runbook` / `scope_operations_runbook`, so the verifier resolves the key directly with no alias fallback. Prose-only; behaviour was already correct via the alias. Recorded in operations-runbook 1.1.1 + root `CHANGELOG.md` 1.0.0. **Found by:** onboarding-companion session, 2026-06-21. **Resolved by:** suite-hardening pass 2, 2026-06-22.

### F2 — onboarding-companion's description did not disambiguate against learning-track  [resolved 2026-06-21]
- **Skill:** onboarding-companion · `skills/onboarding-companion/SKILL.md` (description frontmatter).
- **What it was:** the description's only boundary clause named usage-guide, not learning-track, so a
  contributor-onboarding request phrased as "teach a new joiner the codebase" could mis-route to
  learning-track (the two are the sibling-tutorial pair that neither side had triangulated).
- **Resolution (onboarding-companion session, 2026-06-21):** the description now carries the
  reciprocal use-this-not-that clause — "it is not a multi-audience concepts course (use
  learning-track)" — alongside the existing usage-guide distinction. The redundant "from scratch" was
  trimmed to stay in budget (final 950/1024, no angle brackets). learning-track already names
  onboarding-companion (v1.3.0), so the pair now triangulates from both sides. **No shared file
  changed.**
- **Found by:** learning-track session, 2026-06-20. **Resolved by:** onboarding-companion session,
  2026-06-21.

### F6 — operations-runbook's entry template used `[...]` square-bracket slots, a second placeholder style  [resolved 2026-06-20]
- **Skill:** operations-runbook · `skills/operations-runbook/assets/runbook-entry.template.md`.
- **What it was:** the entry template used `[...]` square-bracket slots (`[component]`, `[one line]`,
  `[links]`, the old `Last tested: [date …]`, etc.) — a second fill-in style alongside the suite's
  `{{key}}`. The nuance the finder flagged: **most of these are per-entry author content, not
  profile-resolvable values**, so blanket-converting them to `{{…}}` would be wrong (there is no
  `component` key in the profile, and it differs per entry).
- **Resolution (operations-runbook session, 2026-06-20):** option (a) — the template now states
  explicitly that the square-bracket slots are **author-fill** (replaced by hand per entry),
  deliberately distinct from `{{key}}` profile placeholders, with the reason (per-entry values are
  not profile keys). The slots are kept as-is, as advised; none were converted to `{{…}}`. The one
  fixed-format slot, the freshness stamp, was changed from the non-ISO `Last tested: [date …]` to the
  canonical `Last reviewed: YYYY-MM-DD` ISO literal the verifier's staleness check reads (it could
  not read the old label/format — verified). For consistency, the incident-timeline slots in
  `references/incident-response.md` were switched from `<…>` to `[…]`, so author-fill uses one style
  throughout the skill. **No shared file changed.**
- **Found by:** usage-guide review session, 2026-06-20. **Resolved by:** operations-runbook session,
  2026-06-20.

### F4 — usage-guide's HTML output had no generator, so the footer/credits/ISO-stamp defaults were missing  [resolved 2026-06-20]
- **Skill:** usage-guide · `skills/usage-guide/` (was: `SKILL.md` + two references only, no generator).
- **What it was:** usage-guide is the suite's other HTML producer (`render-contract.md` 1a) but
  hand-wrote the HTML. The `©` footer was a generator-level P14 guarantee + verifier backstop, the FAQ
  had a first-class `credits` block, and an ISO last-reviewed stamp + staleness check existed — but
  usage-guide had no generator to make the **footer + About & credits block + ISO stamp** the default
  (only the `©` was caught, by the verifier, after the fact).
- **Resolution (usage-guide session, 2026-06-20):** gave usage-guide its **own** generator,
  `assets/usage_guide_generator.py` (option a-variant — a per-skill generator, not a shared emitter both
  pages call, since this session may not edit the FAQ and the two layouts differ; the shared-emitter
  route is the suite-hardening session's job). It renders the `©` footer, the first-class `credits`
  block, and the `<meta name="last-reviewed">` + visible stamp **by construction**, fails loud on a
  missing `alt` and NOTEs a missing footer/credits, and takes all values from the profile (no hard-coded
  name). Verified: the generated page passes `verify.py --skill usage-guide` (grade ~1.2, 0 FAIL) with
  all three present; the `©` gate FAILs a no-footer page under both public (per-page) and internal (set)
  scope; the staleness gate WARNs an old ISO stamp at a non-default threshold and INFOs within a loose
  one; `--license` FAILs a LICENSE missing the disclaimer or the licence id. SKILL.md gained the
  "Before you start" operational section, the generator build step, the sibling trigger boundary, and
  the licensing/staleness self-checks. **No shared file changed** (the generator is this skill's own
  asset), so no other skill is touched. This also satisfies `SUITE-HARDENING-PASS-2-SCOPE.md` item 2.2.
- **Found by:** project-faq review session, 2026-06-20. **Resolved by:** usage-guide session, 2026-06-20.

### F1 — project-faq restated the HTML→wiki conversion in its publish step  [resolved 2026-06-20]
- **Skill:** project-faq · `skills/project-faq/SKILL.md` Step 6.
- **What it was:** Step 6 named the per-element HTML→wiki mapping ("each tab or section becomes a
  heading, callouts become panels") — a second copy of `shared/render-contract.md` Section 1a.
- **Resolution (project-faq session, 2026-06-20):** Step 6 now states only the reader-facing
  consequence (the live tabbed widget is unavailable on a wiki) and points to `render-contract.md`
  Section 1a for the degradation. The per-element mapping is no longer duplicated. The suite
  render-restatement lint (`lint-render-restatement.py`) now reports clean on project-faq.
- **Audited clean at the same time (no action):** architecture-and-decisions, operations-runbook,
  onboarding-companion (each names primitives and points to the render contract, without the
  mapping), usage-guide (degrades "to native structure … interactivity is lost" with no per-element
  mapping), and publish-mirror (its format-handling note is legitimate, not a restatement).
