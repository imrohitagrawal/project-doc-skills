# Project documentation skills — source

A suite of eight independently packaged documentation skills.

Six turn a software project into documentation, each in a
distinct Diátaxis mode; **doc-critic** is the independent review gate that critiques those docs before
they publish; and **publish-mirror** is a separate publish step that mirrors the finished pages to a
wiki or portal without re-authoring them:

<!-- skills:table:begin -->
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
<!-- skills:table:end -->

## Why this structure (independent skills, one source of truth)

Each skill ships **self-contained** — when installed it carries its own copy of the shared writing
standard, the project-profile template, the render contract, the publish-targets manifest, the
verifier, and the CI snippet, so it works on its own with no dependency on the others. That
independence is the point.

The risk with self-contained packages is **drift**: eight copies of the house style can diverge.
This repository reduces that risk by keeping shared files in **one canonical place**, copying them
into each package **at build time**, and using release checks to detect and block unreconciled drift:

```text
project-doc-skills/
├─ shared/                     # THE canonical shared files — edit here, nowhere else
│  ├─ house-style.md           #   the shared writing standard
│  ├─ licensing-and-credits.md #   how generated documents are licensed + credited
│  ├─ render-contract.md       #   how a repo page converts to each publish target
│  ├─ project-profile.md       #   the per-project profile template
│  ├─ publish-targets.yaml     #   destinations and coordinates
│  ├─ verify.py                #   the documentation verifier
│  └─ ci/                      #   ready pre-commit + CI snippet
├─ skills/                     # bespoke files per skill
├─ build-skills.sh             # assembles dist/<name>.skill deterministically
├─ pkgtools.py                 # deterministic packer + SHA-256 manifest writer
├─ lint-placeholders.py        # validates {{...}} placeholders
├─ check-version.py            # VERSION and changelog checks
├─ release-gate.sh             # composed release gate
├─ VERSION                     # suite SemVer
├─ tests/                      # golden-good / golden-bad fixtures
└─ dist/                       # generated .skill packages + MANIFEST.sha256
```

The skills under `skills/` are generated from `skills-order`:

<!-- skills:tree:begin -->
```text
skills/
├─ learning-track/
├─ architecture-and-decisions/
├─ project-faq/
├─ usage-guide/
├─ operations-runbook/
├─ onboarding-companion/
├─ doc-critic/
└─ publish-mirror/
```
<!-- skills:tree:end -->

**The rule that keeps this scalable:** never hand-edit a shared file inside a built `.skill` or
inside `skills/<name>/`. Edit `shared/`, then run `./build-skills.sh`. Generated copies can still be
changed manually or become stale outside the governed build path, so the release gate detects and
blocks unreconciled drift rather than claiming that drift is impossible.

## Build

```bash
./build-skills.sh            # rebuild every .skill into dist/ (validates each first)
./build-skills.sh faq        # rebuild only matching skills
```

Before packaging, `validate_skill.py` checks each skill against the repository's currently encoded
package constraints, including description length, frontmatter keys, kebab-case names, and the
required `SKILL.md` layout. These checks demonstrate compliance with the rules encoded in this
repository at the inspected commit. Compatibility with any external platform's current upload rules
is time-sensitive and must be revalidated against that platform's official documentation before a
release claim is reused.

To check a single skill by hand:

```bash
python3 validate_skill.py skills/<name>
```

## Releasing: reproducible build, integrity manifest, versioning

The build is **deterministic**: `pkgtools.py` packs each `.skill` with file entries sorted, every
timestamp pinned, and fixed permissions, so identical source produces a **byte-identical** `.skill`
**within one toolchain**. Two consequences:

- `./build-skills.sh --check` rebuilds every `.skill` and asserts it is byte-identical to the committed
  `dist/<name>.skill`; a source or artifact mismatch is reported as **DRIFT** and fails the check.
- A clean full build writes `dist/MANIFEST.sha256` — a SHA-256 over every `.skill` and every `shared/`
  file, plus the suite version. The manifest is designed to be byte-stable for unchanged content
  within the same governed toolchain.

**Consumer flow — build, verify the manifest, then install:**

```bash
./build-skills.sh                          # build all eight + emit dist/MANIFEST.sha256
sha256sum -c dist/MANIFEST.sha256          # verify the bytes before trusting them
# then upload/install the dist/<name>.skill you want
```

Paths in the manifest are relative to the repository root, so run
`sha256sum -c dist/MANIFEST.sha256` from there. A mismatch means the artifact differs from the
registered source/toolchain result; rebuild and investigate rather than installing it.

**One composed gate for a release.** `./release-gate.sh` runs the build, validation, render and
placeholder checks, skill-enumeration checks, golden fixtures, reproducibility assertion, manifest
checks, and version checks. CI runs the same script in
`.github/workflows/release-gate.yml`.

A passing gate demonstrates that the repository's configured checks passed for that commit and
toolchain. It does not by itself establish external-platform acceptance, adoption, or unrestricted
redistribution rights.

**Versioning (SemVer).** The suite has a single `VERSION`. Skills are versioned independently in
`skills/<name>/CHANGELOG.md`; shared or suite changes belong in the root `CHANGELOG.md`.
`check-version.py` enforces the registered versioning rules.

Improve a skill in its own focused session, in this order:

<!-- skills:improve-order:begin -->
**learning-track → architecture-and-decisions → project-faq → usage-guide → operations-runbook → onboarding-companion → doc-critic → publish-mirror.**
<!-- skills:improve-order:end -->

`doc-critic` is the review gate and `publish-mirror` is the publish step, both downstream of the
authoring skills. When a change belongs to a shared file, make it in `shared/`, rebuild, and record
the change in the applicable changelog.

## The verifier, in one line

Every skill runs the same verifier. The skill name resolves the grade target and scope from the
profile, so those values live in one place:

```bash
python3 scripts/verify.py <docs> --skill <skill-name> --profile docs/project-profile.md
```

## Licensing boundary

`shared/licensing-and-credits.md` governs licensing and attribution guidance for generated
documents. It does **not** establish the licence for this repository's source code or distributed
`.skill` packages. Repository and package redistribution terms remain unresolved until an
authoritative source/package licence is selected and added through a separate reviewed decision.
