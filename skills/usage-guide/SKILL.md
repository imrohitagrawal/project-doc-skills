---
name: usage-guide
description: Create a usage guide or how-to-use guide for a software project written so simply that even a young child at a grade-1 reading level can follow it. Short sentences, common words, one idea at a time, lots of concrete numbered steps, and pictures. Produces a clean illustrated single-file HTML page (or Markdown). Use this whenever the user wants a usage guide, how-to, user manual, getting-started guide, quickstart, step-by-step instructions, or the simplest-possible explanation of how to use their project. Use it even if the user only says "explain how to use this like I'm five", "write the simplest instructions", or "a guide my non-technical users can follow". Not a concepts course (learning-track), not a Q&A or knowledge base (project-faq), not the design-rationale doc (architecture-and-decisions), not contributor onboarding (onboarding-companion). Enforce the reading level with the bundled readability check.
---

# Usage Guide Builder (grade-1 reading level)

Build a guide that shows a reader **how to use the project**, written so simply that a young child
could follow it. The reader wants to *do* a task, not understand the theory. Read
`references/house-style.md` first, then apply the stricter simple-English rules here.

**Diátaxis mode:** *how-to* (task-oriented). Each section helps the reader do one thing. Keep it
distinct from a learning track (which teaches concepts) and an FAQ (which answers questions).

---

## Before you start (inputs, when to run, where it sits)

**Inputs it needs.** A project that a user can already *do something* with, plus enough to name the
real tasks: a README, the commands or the screens a user actually touches, and the project profile
(`assets/project-profile.md`, copied to `docs/project-profile.md` — it sets `grade_target_usage_guide`
and `scope_usage_guide`). The guide describes only tasks you can ground in the real interface; it does
not invent steps. If a task cannot be grounded, say so rather than guess.

**When to run it in a Claude-Code build.** *Not* on an empty repo, and *not* per commit. A usage guide
needs a usable surface to point at, so run it once a user-facing path actually works (a working command
or a screen a user can complete a task on) — in practice once the quickstart runs end to end — and
**refresh it per release/milestone** whenever the steps a user follows change. Treat it like
docs-as-code: it carries a last-reviewed date and is re-checked when those steps change (the verifier
WARNs once that date goes stale).

**How it sequences with the other six skills** (producers before consumers; one task at a time is the
line this skill holds):

- **learning-track** (public concepts course) — teaches *why/how it works*; this guide only shows
  *how to do a task*. Send theory and background there, not here.
- **architecture-and-decisions** (design rationale) — the *why it is built this way*; never in a usage
  guide.
- **project-faq** (broad Q&A reference) — answers many questions across breadth; a step-by-step for a
  single task belongs here instead.
- **operations-runbook** (operator recovery) — for an operator restoring a broken system; this guide is
  for an end user doing a normal task.
- **onboarding-companion** (contributor onboarding) — for someone joining to *contribute*; this guide is
  for someone *using* the project.
- **publish-mirror** (downstream publish step) — when the owner wants the page on a wiki or portal, hand
  off to it (Workflow step 8); never author in the target.

---

## The grade-1 clarity gate (the whole point)

This is the simplest document in the suite. The reading-grade target is **`grade_target_usage_guide`
from the profile (default ~2)**. Hold to these rules:

- **Very short sentences.** Aim for about 8 words. One idea per sentence.
- **Common words only.** If a word is hard, use an easier one or explain it in tiny words right there.
- **Say the steps.** Number every step. Tell the reader exactly what to click, type, or tap.
- **Say what they will see.** After a step, say what should happen, so they know it worked.
- **Pictures help.** Add a simple diagram or screenshot-style image for each main task (original
  images only; alt text required).
- **No jargon.** If a technical word cannot be avoided, give it a one-line "this means…" in kid words.
- **Be kind and calm.** Short, friendly, encouraging. Never make the reader feel slow.

**Safety:** never tell the reader to type a password, card number, or secret into a place this guide
controls. For anything like signing in or paying, tell the reader to do that step themselves, the
normal way.

---

## Structure (use this order)

1. **What this is.** One short line: what the thing does, in plain words.
2. **What you need first.** A tiny checklist (an account, a device, the app installed).
3. **Do this first (quickstart).** The fastest path to a first success, ideally one command or a few
   clicks. Number the steps. End with "Now you have done it once."
4. **The main things you can do.** One short section per task. Each task is: a one-line goal → numbered
   steps → "what you will see" → a picture. Keep tasks small.
5. **If something goes wrong.** The few common problems, each as: "If you see X → do Y." Calm and
   clear.
6. **Words we used.** A tiny glossary of any hard word, each defined in kid words.
7. **Where to get help.** Who to ask or where to look, and the feedback line.
8. **About & credits.** Who made it, the licence, and how to credit it on reshare — kept plain, as the
   generator's first-class `credits` block, per `references/licensing-and-credits.md`.

Carry the profile's licence footer (the `©` line) on the page, and a `Last reviewed: YYYY-MM-DD` stamp
near the top — the HTML generator below renders both for you. If `scope_usage_guide` is `public`, follow
the public-output rules (no internal tool names, no author motivation).

---

## Workflow

1. Read `house-style.md`; find or create the project profile. Note `grade_target_usage_guide` and
   `scope_usage_guide`. Read `references/simple-english-rules.md` and
   `references/usage-guide-structure.md`.
2. List the real tasks a user does with the project (from the README, the commands, the interface).
   Keep only what a user actually needs; cut everything else.
3. Write each section to the structure above, at the grade target. Write a step, then read it aloud in
   your head — if a child could not follow it, cut words and split the sentence.
4. Add a simple picture for each main task (themed Mermaid or a clean original diagram; alt text and a
   static fallback per `house-style.md` Section 7).
5. **Build the page (repo-first).** A styled, illustrated HTML page is the default for non-technical
   readers — build it with `assets/usage_guide_generator.py`: author the guide as a Python data
   structure (sections of `steps`, `see`, `picture`, `trouble`, `glossary`, and `credits` blocks) and
   render it. The generator bakes in the three required pieces so you cannot silently drop them:
   - the `©` licence **footer** — set `footer` to the licence line from
     `references/licensing-and-credits.md` (the public variant, built from the profile's
     `{{licence_footer}}` / `{{year}}` / `{{owner_name}}`); the decorative `watermark` does not replace
     it;
   - the **About & credits** block — the first-class `credits` block, kept plain and short (the full
     attribution line and the `LICENSE` disclaimer live off the page);
   - a machine-readable **last-reviewed** stamp — set `last_reviewed` to the date you last checked the
     steps (`YYYY-MM-DD`); it emits a `<meta name="last-reviewed">` plus a visible line.

   **Markdown is fine if asked** — then carry the same three by hand: the `©` footer line, a
   `Last reviewed: YYYY-MM-DD` stamp, and the About & credits page + `LICENSE` per
   `references/licensing-and-credits.md`. Either way, **write the page to the repository first**
   (`docs/usage-guide/index.html`; `outputs/{{project_name}}-usage-guide.html` in this tool) — that is
   the source of truth; you never author in the target.
6. **Check the reading level** — this matters most here:
   ```bash
   python3 scripts/verify.py docs/usage-guide.md --format md --skill usage-guide --profile docs/project-profile.md
   # or for an HTML build:
   python3 scripts/verify.py outputs/usage-guide.html --format html --skill usage-guide --profile docs/project-profile.md
   ```
   If the grade is too high, simplify until it passes. Do not game the number — actually make it
   simpler. (The verifier also fails a public page with no `©` footer, and WARNs once the last-reviewed
   stamp goes stale.)
7. Present the file (a single illustrated HTML page is best for non-technical readers; Markdown is
   fine if asked).
8. **Publish (optional, repo-first — a separate step).** Write the source to the repository first;
   that is always the source of truth, and you never author in the target. Publishing is optional and
   separate: when the owner wants it, hand the page to the **publish-mirror** skill, which renders it
   to each destination in `docs/publish-targets.yaml` following `references/render-contract.md`. An
   HTML page goes by the HTML-source path (faithful on a portal that hosts HTML; degraded to native
   structure on a wiki, where the interactivity is lost — state that on the page); a Markdown page
   goes by the primitive path.

---

## Quality bar (self-check before presenting)
- A young child could read most sentences out loud and understand them.
- Every step says exactly what to do, and what they will see next.
- No jargon without a tiny "this means…" right beside it.
- Each main task has a picture with alt text.
- The reading-grade check passes the target.
- No step asks the reader to type a secret into a place this guide controls.
- The page carries the `©` licence footer (HTML: `footer` was set; the watermark alone is not enough)
  and an **About & credits** block; the verifier fails a public page with no `©`.
- A `last_reviewed` date (`YYYY-MM-DD`) is set, so the page carries the freshness stamp and the
  staleness check has something to read.
- No real secrets or personal data on the page (the verifier fails near-certain credential shapes and
  warns on softer ones); redact before publishing.


**Licensing and credits (required).** When you build the HTML page (Workflow step 5), the generator
carries all of this for you: set its `footer` to the licence line (the `©`, public variant for a usage
guide) so every page carries the footer, and include the **About & credits** block with the generator's
first-class `credits` block (the short licence line, never the full disclaimer). The document set also
ships a `LICENSE` carrying the warranty disclaimer and an About & credits page. All of this is defined
once in `references/licensing-and-credits.md` (referenced, never restated); the disclaimer text lives
only in the profile (`{{licence_disclaimer}}`), and the footer/title are built from `{{project_name}}` /
`{{owner_name}}` / `{{year}}`, never a hard-coded name. The verifier fails a public page with no footer
and, in CI with `--license LICENSE`, a LICENSE that drops the disclaimer or does not name the content
licence. It also runs a low-false-positive secret/PII scan (every scope) and a staleness check on the
`last_reviewed` stamp.

---

*Skill version: v1.1.0 — see `CHANGELOG.md` in this folder. Earlier passes are recorded there.*

## References and assets
- `references/licensing-and-credits.md` — the licensing + credits standard; applies to every document this skill produces.
- `references/house-style.md` — the shared writing standard (read first).
- `references/simple-english-rules.md` — the strict grade-1 word and sentence rules.
- `references/usage-guide-structure.md` — the section-by-section template with examples.
- `references/render-contract.md` — how the finished page maps to each publish target (step 8); the conversion lives here, not in this skill.
- `assets/usage_guide_generator.py` — the reusable illustrated-page generator (carries the footer, About & credits block, and ISO last-reviewed stamp by construction).
- `assets/project-profile.md` — copy into the repo and fill once per project.
- `assets/publish-targets.yaml` — the publish destinations manifest used by `publish-mirror` (step 8).
- `scripts/verify.py` — run the reading-level (and licensing/staleness) checks before presenting.
