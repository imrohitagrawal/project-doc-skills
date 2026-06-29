# Project documentation skills — source

A suite of eight independent Claude skills. Six turn a software project into documentation, each in a
distinct Diátaxis mode; **doc-critic** is the independent review gate that critiques those docs before
they publish; and **publish-mirror** is a separate publish step that mirrors the finished pages to a
wiki or portal without re-authoring them:

| Skill | Diátaxis mode | Scope | Reading grade |
|---|---|---|---|
| **learning-track** | tutorial + explanation | public | ~9 |
| **architecture-and-decisions** | explanation / reference | public | ~11 |
| **project-faq** | reference | internal | ~8 |
| **usage-guide** | how-to | public | ~2 |
| **operations-runbook** | reference (operations) | internal | ~10 |
| **onboarding-companion** | tutorial (contributors) | internal | ~7 |
| **doc-critic** | review gate (no Diátaxis mode) | internal | — |
| **publish-mirror** | publish step (no Diátaxis mode) | mirrors the source | — |

## Why this structure (independent skills, one source of truth)

Each skill ships **self-contained** — when installed it carries its own copy of the shared writing
standard, the project-profile template, the render contract, the publish-targets manifest, the
verifier, and the CI snippet, so it works on its own with no dependency on the others. That
independence is the point.

The risk with self-contained packages is **drift**: eight copies of the house style slowly diverge.
This repo removes that risk by keeping the shared files in **one canonical place** and copying them
into each package **at build time**:

```
project-doc-skills/
├─ shared/                     # THE canonical shared files — edit here, nowhere else
│  ├─ house-style.md           #   the shared writing standard
│  ├─ licensing-and-credits.md #   how every document is licensed + credited (public/internal)
│  ├─ render-contract.md       #   how a repo page converts to each publish target (one source for the conversion)
│  ├─ project-profile.md       #   the per-project profile template (filled once per project)
│  ├─ publish-targets.yaml     #   the per-project manifest of publish destinations + their coordinates
│  ├─ verify.py                #   the documentation verifier
│  └─ ci/                      #   ready pre-commit + CI snippet
├─ skills/                     # bespoke files per skill (SKILL.md + that skill's own references)
│  ├─ learning-track/
│  ├─ architecture-and-decisions/
│  ├─ project-faq/
│  ├─ usage-guide/
│  ├─ operations-runbook/
│  ├─ onboarding-companion/
│  ├─ doc-critic/              #   the independent review gate (critiques produced docs before publish)
│  └─ publish-mirror/          #   the publish step (mirrors verified pages out; never authors)
├─ build-skills.sh             # assembles dist/<name>.skill = skills/<name>/ + shared/ (deterministic)
├─ pkgtools.py                 # deterministic packer + SHA-256 integrity manifest writer
├─ lint-placeholders.py        # every {{...}} resolves to a profile key / manifest slot / runtime token
├─ check-version.py            # VERSION is SemVer and the changelogs name it
├─ release-gate.sh             # the one composed gate a release must pass
├─ VERSION                     # the suite's SemVer (skills keep their own numbers)
├─ tests/                      # golden-good / golden-bad fixtures + run-golden.py (the gates that guard the gates)
└─ dist/                       # the built .skill packages + MANIFEST.sha256 (generated)
```

**The one rule that keeps this scalable:** never hand-edit a shared file inside a built `.skill` or
inside `skills/<name>/`. Edit `shared/`, then run `./build-skills.sh`. The copies are generated, so
they cannot drift.

## Build

```bash
./build-skills.sh            # rebuild every .skill into dist/ (validates each first)
./build-skills.sh faq        # rebuild only matching skills
```

Every skill is checked against the platform upload rules by `validate_skill.py` before it is
packaged. The build **fails** rather than produce a `.skill` that would be rejected on upload
(description must be <= 1024 chars with no angle brackets; frontmatter keys limited to
name/description/license/allowed-tools/metadata/compatibility; name kebab-case <= 64 chars; exactly
one SKILL.md). To check a single skill by hand: `python3 validate_skill.py skills/<name>`.


## Releasing: reproducible build, integrity manifest, versioning

The build is **deterministic**: `pkgtools.py` packs each `.skill` with file entries sorted, every
timestamp pinned, and fixed permissions, so identical source produces a **byte-identical** `.skill`
(within one toolchain). Two consequences:

- `./build-skills.sh --check` rebuilds every `.skill` and asserts it is byte-identical to the committed
  `dist/<name>.skill`; a one-character source change shows up as **DRIFT** and fails. This is how you
  prove an artifact still matches its source.
- A clean full build writes `dist/MANIFEST.sha256` — a SHA-256 over every `.skill` and every `shared/`
  file, plus the suite version. The per-file hashes are the integrity guarantee, so the manifest is
  byte-stable: rebuilding on unchanged content reproduces it exactly.

**Consumer flow — build, verify the manifest, then install:**

```bash
./build-skills.sh                          # build all eight + emit dist/MANIFEST.sha256
sha256sum -c dist/MANIFEST.sha256          # from the repo root: verify the bytes before trusting them
# then upload/install the dist/<name>.skill you want
```

Paths in the manifest are relative to the repo root, so run `sha256sum -c dist/MANIFEST.sha256` from
there and every line (the `.skill` files and the `shared/` sources) resolves. A mismatch means the
artifact was changed or rebuilt on a different toolchain — rebuild and re-verify rather than installing
it.

**One gate for a release.** `./release-gate.sh` composes everything a release must pass: the build
(validation + the render-restatement and placeholder lints), the golden fixtures
(`tests/run-golden.py` — produced docs must pass with 0 FAIL and every deliberately-broken fixture must
be caught), the `--check` reproducibility assertion, the manifest, and `check-version.py`. CI runs the
same script (`.github/workflows/release-gate.yml`).

**Versioning (SemVer).** The suite has a single `VERSION` (SemVer). Skills are versioned
**independently** — each keeps its own number in `skills/<name>/CHANGELOG.md`, and they do **not** share
the suite number. The rule stays as above: shared/suite changes go in the root `CHANGELOG.md`,
skill-specific changes in that skill's changelog. `check-version.py` enforces that `VERSION` is SemVer,
that the root changelog names it, and that every skill is versioned.

Improve a skill in its own focused session, in this order (producers before consumers):
**learning-track → architecture-and-decisions → project-faq → usage-guide → operations-runbook →
onboarding-companion → doc-critic → publish-mirror.** (doc-critic is the review gate and publish-mirror
the publish step, both downstream of the authoring skills, so they are reviewed last.) When a change belongs to a shared file, make it in `shared/` (it benefits
every skill) rather than forking the bundled copy; then rebuild. Record skill-specific changes in
`skills/<name>/CHANGELOG.md` and shared/suite changes in the root `CHANGELOG.md`.

## The verifier, in one line

Every skill runs the same verifier the same way; the skill name resolves the grade target and scope
from the profile, so those values live in exactly one place:

```bash
python3 scripts/verify.py <docs> --skill <skill-name> --profile docs/project-profile.md
```
