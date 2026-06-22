# Integration note — publish-mirror is wired into the suite

This is the **complete, drop-in** suite. The publish step the suite was missing is added, and the
authoring skills already point to it. There are **no manual edits left to make.**

## What changed in this drop

New:
- `shared/render-contract.md`        — canonical, target-agnostic conversion (source primitives,
  per-target adapters, graceful degradation). The conversion is defined here once.
- `shared/publish-targets.yaml`      — per-project manifest: the single home of every target
  coordinate, secrets by reference, a stable per-page id that prevents duplicates.
- `skills/publish-mirror/`           — the new publish skill (SKILL.md + CHANGELOG.md). Validated:
  description 974/1024, no angle brackets.
- `build-skills.sh`                  — patched to copy the two new shared files into every skill at
  build time (no drift).

Edited (already applied — nothing for you to do):
- `skills/learning-track/SKILL.md`   — Step 7 inline conversion **replaced** with a pointer to
  publish-mirror + render-contract; repo-first kept explicit.
- `skills/architecture-and-decisions/SKILL.md`, `skills/operations-runbook/SKILL.md`,
  `skills/onboarding-companion/SKILL.md` — each gains the same short repo-first publish step.

HTML-source path (optional publish):
- `skills/usage-guide/SKILL.md`, `skills/project-faq/SKILL.md` — these emit a finished HTML page,
  so they do not use the Markdown primitive mapping. Each gains an **optional** repo-first publish
  step that hands the page to publish-mirror via the HTML-source path in `render-contract.md`
  Section 1a (faithful on a portal that hosts HTML; degraded to native structure on a wiki).

## The behaviour, stated plainly (answering the repo-first question)

Every authoring skill **always writes its verified source to the repository first** — Markdown for
the four Markdown skills, a finished HTML page for the FAQ and an HTML usage guide. That is the
default and the source of truth. **Publishing is a separate, later step**, performed by
`publish-mirror`, which renders the repo source to each target in `docs/publish-targets.yaml` per
`render-contract.md` — the Markdown primitive path for `.md`, the HTML-source path for `.html`.
You never author in the target. Repo-first is not optional and is not bypassed.

## Build
`./build-skills.sh` (validates each skill, then packages `dist/<name>.skill`). The pre-built packages
are in `dist/`.

## Per project
Copy `publish-targets.yaml` into the repo as `docs/publish-targets.yaml`, fill the coordinates
(space, parent, base URL, the per-page ids, the secret *references*). Build only the adapters whose
targets are real; leave the rest marked designed-not-yet-built.
