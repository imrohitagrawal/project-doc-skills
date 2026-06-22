# Module page template — use this order for every module

Filename: `docs/learning/MN-<slug>.md`. Assets in `docs/learning/assets/`. Cross-link siblings with
relative links. Values in `{{double curly braces}}` are filled from the project profile (the matching
key in `project-profile.md`, the same convention the whole suite uses); `<angle-bracket>` slots are
filled per module by the author (the title, the slug) and are not profile keys. The **last-reviewed
date** is written as an ISO `YYYY-MM-DD` literal — a fixed shape, not an `<angle-bracket>` slot —
because the verifier's staleness check reads that exact form (the same rule operations-runbook and
onboarding-companion follow); a human-month form like "12 June 2026" is silently unread.

1. **H1** — `# Module N — <title>`.
2. **Stamp block** (blockquote):
   ```
   > Reading time: about X minutes (core), plus any optional deep-dive sections · Last reviewed: YYYY-MM-DD
   > Concepts on this page are stable; current specifics are linked to {{decision_log}} and roadmap.
   ```
3. **Sense-of-place** — `**Module N of <total> · Part X — <part name>**`.
4. **On this page** — a one-line table of contents linking the main sections (skip headings with an
   em dash; their anchors are fragile).
5. **Plain-words layer** (always visible) — beginner-first; define every term on first use. This
   layer alone must tell the whole story. **Carry the worked example and an everyday analogy:** every
   explanatory module must include at least one concrete *in-project* example — the worked example
   threaded through the track — **and** an everyday-life analogy (or a short per-audience "why it
   matters" bridge), so a non-expert can *picture* the idea, not just read the definition. (House
   style Section 6. A pure definitions list — the glossary — is the only place this does not apply.)
6. **Under-the-hood layer(s)** — optional depth, in collapsible blocks:
   ```
   <details>
   <summary><strong>Under the hood: ...</strong></summary>

   ... deeper detail for readers who want it ...

   </details>
   ```
   Where a deeper layer could mislead a reader who already knows the field, close it with a short
   **"Two honest notes for readers who already know <X>"** — the caveats, the trade-offs, and what is
   genuinely the project's own contribution versus standard practice. Honesty about what is *not*
   novel builds trust.
7. **A "why" for every choice or claim.** Never assert a design choice without the reason.
8. **Diagrams / GIFs** per `house-style.md` Section 7 — themed Mermaid or a conceptual sketch; a GIF
   only when motion adds meaning. Every visual has alt text and a static fallback.
9. **Callouts** — sparing (about two per module), as bold-label blockquotes that render on plain
   Markdown and map to wiki panels. Use: `**Key idea.**`, `**Tip.**`, `**Try it.**`, `**In plain
   words.**`, `**Status.**`. Do **not** use alert-style tokens like `> [!NOTE]` — some viewers show
   the raw token.
10. **Built-vs-designed honesty** — a `**Status.**` note where capabilities are described; a
    `[designed, not yet built]` marker on any specific a reader would assume is already live. Never
    put phase status in prose — link {{status_link}} instead.

    Place a **one-time global honesty panel** early in the track (in M0, or the first module that
    describes what the system does): a `**What's built versus what's designed**` blockquote that says
    the project is built in stages, that these pages teach the *design*, that a `[designed, not yet
    built]` marker flags anything a reader might otherwise assume is already live, and that the live
    status of each part is at {{status_link}}. State the rule once, prominently; then rely on the
    per-page `**Status.**` notes and the markers. This stops the whole track from reading as if an
    unfinished system is fully shipped.
11. **Authoritative-source link** for volatile specifics (the roadmap / decision log).
12. **Learning outcomes** — "After this page you should be able to: …".
13. **Self-check** — 2–3 questions after a `**Try it.**` callout, with answers in a `<details>`.
14. **Feedback prompt** — invite corrections; clarity for the first-time reader is the goal.
15. **Glossary additions** — add any new terms to `glossary.md` (and define them inline too).
16. **Licence footer** — `{{licence_footer}}`.

## Worked tone (match this register)

Plain, concrete, honest. For example, an opening that defines as it goes:

> Building a piece of software is more than writing it. First you decide what it should do and write
> that down — that description is a **requirement**. Then you build it (the instructions a computer
> follows are the **code**). Then you check it does what was asked — that is **testing**, and a person
> who does it is a **quality engineer**.

Notice: every bold term is defined the moment it appears, sentences are short, and nothing is assumed.

When you cite a general field fact, cite it precisely and keep the honest caveat. For example, a
foundational cost-of-defects finding is worth citing — *and* worth noting that the exact multiplier
varies with the size and criticality of the project, and is gentler on small projects. State the
direction with confidence and the precise figure with care; never round a hedge up into a hard fact.

## Glossary entry format (in `glossary.md`)

```
**Term** — a plain-language definition in one or two sentences, no jargon.
```

A glossary is a definitions list, so it reads denser than the teaching modules and will score above
the grade target — that is expected, because it must name the domain's terms. The verifier treats a
high glossary grade as a **warning, not a failure**; keep each definition plain, but do not strip
necessary terms to chase the number.

## About & credits page (write once, update as modules grow)

Build this page from `references/licensing-and-credits.md` Section 4 — the single source for what the
credits page carries (what the companion is and where to start; the author/maintainer with `{{github}}`
and `{{linkedin}}`; the licence `{{licence_id}}` and the `{{attribution_line}}`; trademark
acknowledgements; the originality/assets note; and the no-personal-data rule) — in the public or
internal variant the profile's `scope` selects. Reference it; do not restate that list here or on the
page, so it stays complete and current rather than a copy that can drift (the same single-source rule
the licence footer and the render contract follow).
