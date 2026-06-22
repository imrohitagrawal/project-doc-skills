# Suite-hardening pass 2 — scope

Root-level planning scaffolding (like `per-skill-review-prompt.md`). **Never bundled** into a `.skill`
(`build-skills.sh` only copies `shared/` + `skills/<name>/`). This is the brief for the next focused
pass on the shared layer.

## 0. What kind of session this is

A **suite-hardening session** — one focused pass that *is* allowed to touch all seven skills and the
shared/root files, unlike a per-skill session. It is **not** "one session per skill." Its job is the
shared-layer work that a per-skill session is forbidden to do, plus finishing items that span skills.

## 1. Context — what pass 1 (2026-06-20) already delivered (verified green)

Confirmed by rebuild + gate runs against the delivered zip:

- `shared/verify.py`: a low-false-positive **secret/PII scan** (FAIL on private-key blocks / AWS keys /
  GitHub + Slack tokens; WARN on emails / JWTs / browser keys / `secret=<long>`; placeholders and
  example domains exempt; runs every scope) and a **staleness check** on an ISO last-reviewed stamp
  (`--max-age-months` > profile `max_doc_age_months` > 6; WARN-only). Readability now **excludes the
  licence `<footer>`** so the required `©` line can never trip the grade (the `©` check still reads the
  raw page, so the licensing gate is not weakened).
- `shared/render-contract.md`: P2 pins the **single canonical** ISO last-reviewed format; P14 is stated
  as a **generator-level `©` guarantee** for any HTML generator (one written home + the verifier as
  backstop) — chosen over a new shared Python helper, which was reasonably declined as over-engineering
  for two bespoke generators.
- `shared/licensing-and-credits.md` + `shared/project-profile.md`: the two new checks are documented;
  `max_doc_age_months` (default 6) added.
- `skills/project-faq/`: first-class **`credits` block**, a **`last_reviewed`** field emitting
  `<meta name="last-reviewed">` + a visible stamp, demo updated to model correct usage (v1.2.0).
- `build-skills.sh`: the **render-restatement lint is now an active `--strict` gate** that fails the
  build on any restatement. Verified: all seven build clean, lint clean.

Forensic verdict on pass 1: every change is additive, single-source-preserving, good for all seven,
and recorded in the root CHANGELOG. No prior work was reverted; `CROSS-SKILL-FINDINGS.md` was untouched
and correct. Pass 1 implemented the three "things you didn't ask" items raised in review.

## 2. In scope for pass 2 — the remaining items

Carried from `CROSS-SKILL-FINDINGS.md` (open) and this review. Each has an acceptance test so a wrong
fix cannot pass green.

### 2.1 F3 — make the staleness gate actually fire on the Markdown skills (highest value)
- **Problem:** `check_staleness` reads ISO `YYYY-MM-DD` only, but learning-track's stamp
  (`references/module-template.md:11`) is `Last reviewed: <date>` and real output is "12 June 2026" →
  the gate returns INFO (silently inert) on the suite's most stale-prone doc.
- **Do:** switch the learning-track stamp template (and its example modules) to an **ISO literal**
  `Last reviewed: YYYY-MM-DD` (and drop the `<date>` angle-bracket placeholder). Decide whether
  architecture-and-decisions / operations-runbook / onboarding-companion should adopt a stamp at all;
  if so, ISO. usage-guide stamp handled in 2.2.
- **Acceptance:** `verify.py` on a learning-track module with an old ISO stamp **WARNs**; with a
  current ISO stamp **INFOs "within window"**; the "12 June 2026" form no longer appears in any
  example. (Run with a non-default `--max-age-months` to prove the threshold is read, not assumed.)

### 2.2 F4 — give usage-guide's HTML path the same three guarantees as the FAQ
> **Resolved in the usage-guide per-skill session, 2026-06-20** — option (a-variant): usage-guide now
> ships its own generator (`assets/usage_guide_generator.py`), so the footer + credits block + ISO stamp
> are automatic by construction; no shared file changed. Detail in `CROSS-SKILL-FINDINGS.md` (Resolved).
> Left here only so this brief stays accurate; no pass-2 action needed.
- **Problem:** usage-guide is the other HTML producer but ships no generator; the `©` verifier backstop
  catches a missing footer (good), but there is nothing to make the **footer + `credits` block + ISO
  `last_reviewed`** the default — an author must hand-add all three.
- **Do (one of):** (a) extract a tiny shared HTML emitter both the FAQ and usage-guide call (carries
  footer + credits + ISO stamp by construction); or (b) have usage-guide **default to Markdown** and go
  HTML only with the same three guarantees stated and checked. Prefer (a) if a second HTML generator is
  expected; (b) is lighter if not.
- **Acceptance:** a usage-guide HTML page produced per the skill carries the `©` footer, an About &
  credits block, and an ISO last-reviewed stamp, and passes `verify.py --skill usage-guide` (public
  scope) with 0 FAIL — verified against a profile whose scope differs from the default.

### 2.3 F5 — resolve the `{{today}}` placeholder convention (low)
- **Problem:** `{{today}}` (faq-method ref:55) does not back to a profile key.
- **Do:** either document a small **runtime-token** set (`{{today}}` = build date, `{{canonical_url}}`
  = wired at publish) in `project-profile.md` / `licensing-and-credits.md`, or reword to a literal.
- **Acceptance:** every `{{...}}` token in the suite resolves to either a profile/manifest key or a
  documented runtime token. Add a tiny check to the build (below) so this stays true.

### 2.4 F2 — onboarding-companion ↔ learning-track trigger boundary (owned elsewhere, track here)
- Per-skill item for the onboarding-companion session (reciprocal use-this-not-that line). Not pass-2
  shared work; listed so it is not forgotten.

## 3. In scope for pass 2 — the enterprise practice: treat the bundle as a released artifact

The suite is consumed as a **zip → built `.skill`s → installed**. Today nothing guarantees that what a
consumer installs is what was reviewed, that a future edit didn't silently weaken a gate, or that the
build is reproducible. The enterprise practice is **release engineering for the bundle**: reproducible
build + integrity manifest + golden-fixture regression + versioned, provenanced release. Concretely:

### 3.1 Reproducible build + integrity manifest
- Add `build-skills.sh --check`: rebuild every `.skill` and assert it is **byte-identical** to the
  committed/released one (the suite's stated delivery standard). Sort zip entries and pin timestamps so
  the build is deterministic.
- Emit `dist/MANIFEST.sha256`: SHA-256 of each `.skill` **and** each `shared/` file, plus the suite
  version and the source commit SHA. A consumer verifies the bundle before install; drift or tampering
  shows up as a hash mismatch.

### 3.2 Golden-fixture regression (the most important one — it guards the gates themselves)
This thread began because a generator shipped a page that failed its own gate, and a gate could be
weakened without anyone noticing. Lock both directions with fixtures under `tests/`:
- **golden-good/** — a known-good produced doc per output kind (an FAQ HTML, a learning-track module).
  CI generates/uses these and asserts `verify.py` returns **0 FAIL**.
- **golden-bad/** — deliberately broken docs (no `©` footer; a real-shaped `AKIA…` token; a stamp older
  than the threshold; a restated render mapping). CI asserts each is **caught** (the right FAIL/WARN
  fires). This is what stops a future refactor from silently turning a gate into a no-op.
- Pin one or two readability values too, so "simplify until green" can't be gamed by a future edit.

### 3.3 One release gate in CI (compose, don't sprinkle)
A single workflow, run on every change and tagged release, that fails the release unless all pass:
1. `build-skills.sh` (all 7 valid: description ≤1024, no angle brackets, frontmatter keys, kebab name,
   one SKILL.md).
2. `lint-render-restatement.py --strict` (no restatement).
3. `verify.py` over **golden-good** (0 FAIL) and **golden-bad** (each caught).
4. `build-skills.sh --check` (byte-identical) + emit `MANIFEST.sha256`.
5. Placeholder-resolution check (3 / F5): no unresolved `{{...}}`.
6. Version/changelog bump check: the suite version and any changed skill's `CHANGELOG.md` advanced.

### 3.4 Versioning, provenance, consumer docs
- **SemVer the suite** and each skill; keep the per-skill `CHANGELOG.md` + root `CHANGELOG.md` split
  (already the rule). Tag releases; attach `dist/*.skill` + `MANIFEST.sha256` to the tag.
- **Provenance:** record commit SHA + build environment in the manifest (sign the bundle if the
  platform supports it) so a consumer knows exactly what they installed.
- **Consumer "how to use this bundle"** (README addition): build → verify manifest → install; the
  one-paragraph "which skill when" routing table (already in README) + the producer/consumer order.

## 4. Guardrails for pass 2

- Shared/root edits must be **additive and good for all seven**; rebuild and re-run every gate after
  each. Do not fork a bundled copy; edit `shared/` and rebuild.
- Re-test every new/changed check against a value that **differs from the default** (scope, threshold,
  grade) and print the resolved values — a wrong fix passes green against the default.
- Keep new deterministic checks **low-false-positive**; a hard FAIL that lights up a legitimate page
  breaks a consumer's gate. WARN when unsure.
- Resolve each `CROSS-SKILL-FINDINGS.md` entry you close (mark `[resolved YYYY-MM-DD]`); record
  shared/suite changes in the root `CHANGELOG.md` (not in the findings log — no value in two places).

## 5. Definition of done

- F3, F4, F5 resolved with their acceptance tests passing; F2 left for its per-skill session.
- The CI release gate (3.3) exists and is green; `golden-good` passes and **every** `golden-bad`
  fixture is caught; `build-skills.sh --check` is byte-identical; `MANIFEST.sha256` is emitted.
- All seven skills still build valid and the strict render-lint is clean.
- Root `CHANGELOG.md` records the pass; `CROSS-SKILL-FINDINGS.md` updated. No homework left.
