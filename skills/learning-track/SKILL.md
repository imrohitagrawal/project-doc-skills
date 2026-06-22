---
name: learning-track
description: Create a multi-audience learning track, course, or study companion teaching the concepts behind a software project using the project itself as the example. Produces modular, beginner-first Markdown lessons, repo-first, taking a reader from zero to understanding how it works and why. Use this whenever the user wants a learning track, course, curriculum, study guide, tutorial series, teaching material, lesson modules, or to turn a codebase into educational content. Use it even for requests like "help people learn how my project works" or "make study material from this codebase". Teaches concepts and the reasons behind them for newcomers (a tutorial, in Diataxis terms) — NOT step-by-step task instructions (use usage-guide), NOT a look-up reference (use project-faq), NOT contributor onboarding (use onboarding-companion), and NOT a deep design-and-decisions doc for engineers who already use it (use architecture-and-decisions).
---

# Learning Track Builder

Version: 1.3.0 · see `CHANGELOG.md`.

Build a **learning companion**: a set of modular lessons that use a real software project as the
worked example to take readers from "curious but lost" to "I understand what this system does, why
it is built this way, and how I would start building something like it."

This skill owns the *workflow and the page template*. The shared writing standard lives in
`references/house-style.md` — **read it first, every time.** The project's facts, audience targets,
palette, and licence live in the project profile (`references/house-style.md` Section 1 explains how
to find or create it).

**Diátaxis mode:** primarily *tutorial* (learning-oriented) with *explanation* layers. Keep it
distinct from a how-to usage guide and a reference FAQ.

---

## Before you start: what this needs, when to run it, where it fits

This section answers three questions a new project raises: *do I have what the skill needs yet, at
what point in the build do I run it, and how does it sit next to the other documentation skills?*
Read it before the workflow.

### What this skill needs (the inputs)

The learning track teaches the *concepts the project actually exercises*, so it has to read the
project first. Before writing modules, make sure these exist and point the skill at them:

- **The filled project profile** (`docs/project-profile.md`) — owner, brand, licence, palette,
  audience targets, the public-vs-internal setting, and the canonical worked example.
- **A one-line summary** of what the project does and the pain it removes.
- **The architecture** — even a high-level sketch is enough to start the orientation and foundations
  modules; component detail can follow.
- **The decision records (ADRs)** — the sequence of choices and their reasons. The "why" in every
  module comes from here.
- **The contracts or interfaces** — the shape of the inputs and outputs the system promises.
- **The technology stack with the reason for each choice**, not just the names.
- **The phase plan** — how the work was cut into small steps, so "from zero to phases" has real
  content.
- **If the project uses AI**, the AI techniques it relies on: prompting and context engineering,
  retrieval (RAG), tools and function calling, agents, evaluation, safety, cost, and observability.

> **Status.** On a brand-new repository none of this exists yet. **Do not start the learning track on
> an empty project.** A learning track cannot teach "how it is built" before the project is designed.
> Run the architecture-and-decisions skill first so there is an architecture, an ADR sequence, and
> contracts to teach from. Foundations modules (the problem, what software is) can be written as soon
> as the problem and the high-level shape are clear; the "how it is built" and deep-dive modules wait
> for the matching design to land.

### When to run it in the build (the cadence)

A learning track is **not a per-commit check, and not a single pass at the end.**

- **Not per commit.** The per-change gate — banned words, link-check, lint, secret-scan — is a
  deterministic hook, not this skill. Running the full authoring loop on every commit wastes effort
  and produces churn.
- **Not only at the end.** Writing every module after the build is finished loses the link-back
  discipline below and ships modules that teach numbers the build has already changed.
- **Run it per module or per batch, anchored to build milestones, in three waves:**
  - **Wave 1 — after the architecture and the foundational decisions stabilise.** Write *orientation
    and foundations*: the problem; what software is and the lifecycle; system design and the patterns
    the project uses; the technology choices and why; and (if the project uses AI) the AI
    foundations. These teach stable concepts, so they are safe to write before the feature build is
    complete.
  - **Wave 2 — as each capability's design or implementation lands.** Write or deepen the *how it is
    built*, *deep dive*, and *trust and quality* modules. Write a module when its feature exists, so
    you are teaching something real. For any specific the build has not yet locked (a chunk size, a
    model-routing order, a service-level target), teach the stable idea and **link** the live value
    to its decision record or implementation page — do not copy the number into the lesson.
  - **Wave 3 — near the end.** Write the *practice ladder* once the reader has met everything it
    asks them to build.
- **The link-back rule (this is what keeps the teaching from going stale).** A module teaches the
  stable concept and links the volatile specific to the live source (the decision log, an ADR, an
  implementation page). When the build records that decision, fill the link. Teaching and build stay
  in step through links, not through copied values — so when a number changes in the code, the lesson
  does not silently become wrong.

### Where this fits among the documentation skills

- **Run architecture-and-decisions first, or in lockstep.** It produces the ADRs, the architecture,
  and the contracts that this skill teaches *from* and links *to*. Without them the "how it is built"
  and deep-dive modules have nothing to anchor.
- **This skill is the public, learner-facing tutorial.** Tell it apart from its neighbours by what
  the reader wants:
  - "Take me from zero to understanding the *whole* system and *why*, with a path to build my own" →
    **this skill** (learning track): mixed-audience, foundations-first, with a practice ladder.
  - "I can already use it — explain the *design and the decisions* in depth so I can change, debug, or
    extend it" → **architecture-and-decisions** (a focused design/decision walkthrough for one
    technical reader, not a zero-to-hero course). Both cover *why*; the split is audience and arc.
  - "Help me *do* a specific task, step by step" → **usage-guide** (a much simpler reading grade;
    different audience).
  - "Tell me the *facts* / the parameters" → **project-faq** (reference; usually internal).
  - "Help me start *contributing* to this codebase" → **onboarding-companion** (internal,
    contributor-facing).
- **operations-runbook** owns the operator procedures that the "designed to run and last" and the
  monitoring modules point to. Teach the concept here; link the runbook for the steps.

---

## Workflow

### 1. Ground yourself in the project and the profile
- Read `references/house-style.md`. Then find or create the project profile (copy
  `assets/project-profile.md` into the repo as `docs/project-profile.md` and fill it).
- Survey the inputs listed above: the README, the architecture, the decision records, the contracts,
  the stack, and the phases. The learning track teaches the *concepts the project actually exercises*
  — not a generic syllabus.
- **Ground every claim.** Tie each project-specific statement to a repository path, an ADR, or an
  issue; cite each general field fact to a credible, verifiable source; if a fact, number, tool name,
  or capability is missing, say so plainly or leave it out. Never invent one. (House style Section 4.)
- Read `grade_target_learning_track` and `scope_learning_track` from the profile (default: grade ~9,
  scope `public`).

### 2. Choose the canonical worked example
Pick **one** example that exercises as many of the project's capabilities as possible, and thread it
through every module so depth compounds. Justify the choice in a short table (capability → how the
example exercises it). The profile suggests one (room booking) as a strong default; confirm it fits
this project or pick a better one.

### 3. Derive the information architecture
Do **not** reuse a fixed module list. Derive the right modules for *this* project using
`references/information-architecture-method.md`. In short: one objective per module; split a module
once it passes ~20 minutes; group modules into parts for navigation; an orientation module first; a
glossary running across all modules; and a practice ladder at the end. **If the project uses AI, the
deep-dive part expands into several modules — the method gives the transferable shape.** Bring the
proposed module map to the owner before writing all of it.

### 4. Write each module to the template
Follow `references/module-template.md` exactly (stamp block, sense-of-place, plain-words layer,
optional under-the-hood layers in collapsible blocks, a "why" for every choice, diagrams, sparing
callouts, the built-vs-designed honesty panel and markers, learning outcomes, self-check, feedback
prompt, glossary additions, licence footer). Write the **plain-words layer for the beginner floor**;
put expert depth in opt-in collapsible sections so the floor never rises.

### 5. Apply the depth standard
Teach **failure modes, not only concepts** (`house-style.md` Section 5). For every technique and
choice, name what goes wrong and why, give a worked example, then show how the design addresses it.
Mark anything not yet built with `[designed, not yet built]`; label illustrative numbers "proposed,
not yet locked"; cite field facts and label project facts.

**The depth bar, made concrete (use this as the worked standard, especially for AI modules).** "Name
the failure modes" is not a slogan — here is the bar it has to clear, taking retrieval as the
exemplar. For each technique, a module must be able to answer at this level:
- *Did it find the right material?* (for retrieval: the hit-rate — were the right chunks retrieved at
  all).
- *Is the produced answer correct?* (retrieving the right thing and using it correctly are two
  different checks — keep them separate).
- *Where does the obvious approach quietly fail?* For retrieval: an exact error message or flag name
  can be missed because semantic search is not word-matching (the case for sparse and hybrid search);
  a chunk from the middle of a page does not know which page or section it came from (the case for
  contextual retrieval and metadata); a question shaped "how do I do X given constraint Y" breaks
  naive retrieval differently; a follow-up question loses the earlier turns unless the query is
  rewritten against the conversation.
- *The honest-builder thread, on every such module:* start simple, measure on **your own** data, and
  watch the cost — the fancy option is not automatically better.

Apply the same bar to every distinctive technique the project uses (for an AI project: prompting,
retrieval, tools, agents, safety, evaluation, monitoring). A module that only teaches the happy path
has not cleared it.

### 6. Run the authoring loop, then verify
Run the critic passes in `house-style.md` Section 10 (beginner critic is the gate). **For an AI
project, extend that loop with a distinct AI-accuracy critic** — folding it into the general "expert
critic" lets a subtly-wrong explanation through. The full order:

1. **Writer** — draft to the template and the house style.
2. **Beginner critic (the clarity gate, priority 1)** — every term defined; no unexplained jargon;
   analogies land; nothing assumed. Nothing passes until this is clean.
3. **Other-field critic** — bridges from everyday or professional life; "why it matters" is explicit.
4. **Software-professional-new-to-AI critic** — AI explained without hand-waving; a real escape hatch
   to depth.
5. **AI-accuracy / depth critic** — AI claims are correct, complete, and not oversimplified into
   something false; failure modes are named. Bites hardest in the deep-dive and trust modules; in the
   foundations it validates and adds pointers. (Fold this into step 4 only when the project uses no
   AI.)
6. **IP / copyright critic** — no third-party text, images, or logos; trademarks nominative and
   acknowledged; sources cited and verifiable; assets original.
7. **Verifier** — run the automated checks below.
8. **Owner review** — calibrate tone and depth early (a few iterations), then spot-check.

Then run the verifier over the modules. Pass `--skill learning-track` so it reads the grade target
and scope from the profile (a CLI flag still overrides if you give one). Add `--license LICENSE` so
the same run confirms the `LICENSE` carries the warranty disclaimer and names the content licence —
the check the CI gate runs, kept in your own pre-present pass:
```bash
python3 scripts/verify.py docs/learning --format md --skill learning-track --profile docs/project-profile.md --license LICENSE
```
Fix every FAIL. Treat a high reading grade as a signal to simplify, not a number to game. A glossary
is a definitions list and will read denser than the teaching target — the verifier treats that as a
warning, not a failure, so do not strip necessary terms to lower its score.

### 7. Publish (repo-first — a separate, later step)
Write the verified Markdown to the repository first. That is always the default and the source of
truth; a wiki is only a published mirror, and you never author in the wiki. Publishing is a separate
step that runs after this loop, performed by the **publish-mirror** skill: it renders each module to
every destination configured in `docs/publish-targets.yaml` (a wiki, a portal), following
`references/render-contract.md` — the single source for how each renderable part of a page (its
collapsible depth blocks, callouts, on-this-page line, diagrams, status markers, and licence footer)
is converted to each target's idiom. This skill writes those parts and hands them off; it does not
restate the conversion. Publish module by module as each clears the loop, and update the glossary
page each time.

---

## Output structure

Derive the module count and the slugs from the project (Step 3). The shape below is the file layout,
not a fixed syllabus.

```
docs/learning/
├─ M0-read-this-first.md        # orientation: who it is for, how to read, the map
├─ M1-<slug>.md                 # one objective per module
├─ M2-<slug>.md
├─ ...                          # as many as the project's concepts require
├─ glossary.md                  # every term, one place; grows per module
├─ about-and-credits.md         # author, licence, trademark acknowledgements
├─ LICENSE
└─ assets/                      # exported diagrams + GIFs (+ .png fallbacks)
```

## Quality bar (self-check before presenting)
- A beginner in the target audience can follow **every** plain-words sentence; every term is defined
  on first use.
- Each module covers one objective and reads in roughly its stated time.
- Every choice has a "why"; failure modes are taught, not just concepts, and the depth bar in Step 5
  is cleared on the distinctive techniques.
- Built-vs-designed honesty is correct; nothing unbuilt is implied to be live; volatile specifics are
  linked, not copied.
- The worked example threads through and deepens toward the later modules.
- The verifier passes (no FAIL); diagrams have alt text and static fallbacks.


**Licensing and credits (required).** Every page carries the licence footer; the document set ships a `LICENSE` and an **About & credits** page, and the warranty disclaimer appears in the LICENSE — all per `references/licensing-and-credits.md`, using the public or internal variant per the profile's scope. The verifier fails a public page that lacks the footer.

## References
- `references/licensing-and-credits.md` — the licensing + credits standard; applies to every document this skill produces.
- `references/house-style.md` — the shared writing standard (read first).
- `references/information-architecture-method.md` — how to derive the module map from any project,
  including the AI-project deep-dive shape and the practice-ladder blueprint.
- `references/module-template.md` — the exact per-module page template.
- `references/render-contract.md` — the single source for how a page is converted to each publish
  target; Step 7 hands off to it (and to `assets/publish-targets.yaml`, the per-project manifest of
  destinations) rather than restating the conversion.
- `assets/project-profile.md` — copy into the repo and fill once per project.
- `scripts/verify.py` — run before presenting (pass `--skill learning-track`).
- `ci/` — a ready pre-commit hook and CI job that run the verifier (docs-as-code, in lockstep).

## Versioning
This skill is versioned like code. Record every change in `CHANGELOG.md` (Keep a Changelog format)
and bump the version in this file's header. A learning track that drifts from the project is worse
than none — the link-back rule and a stamped, changelogged skill are how the two stay in step.
