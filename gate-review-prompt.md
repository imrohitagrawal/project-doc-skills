# Gate-review prompt — the standing independent review for any gate-layer change

`gate-review-prompt.md v1.0.0` · root scaffolding (never bundled) · the canonical prompt an
**independent** reviewer runs on any pull request that touches the gate layer (see
`.github/gate-paths`). It is the human/agent half of the rule in `CONTRIBUTING.md`: **CI green is
necessary but not sufficient** for the gate layer, because the failures that ship green are judgement
failures — a check that guards less than it advertises, or a gate whose own description has drifted.

This prompt exists because both of those have already happened here:

- a lint shipped CI-green that printed `clean` while it inspected **2 of the 5** places the suite
  enumerates its skills (it never looked at the README "improve in this order" list, the repo-tree, or
  the prompt's attachment table) — green, and stale;
- the pull request that added a third suite lint left `release-gate.sh` still describing **"the two
  now-active suite lints"** — the gate's count of itself drifted from what it runs.

A green build saw neither. An independent read is what catches them.

---

## How to use (read this once)

- **Run it INDEPENDENTLY and BLIND.** Spawn the reviewers in **fresh contexts** that did not write the
  change. Give each one the diff + the neutral brief + its single lens — and **nothing else** (no
  author's rationale, no prior findings, no other reviewer's output). The adjudicator is the only one
  that sees the others. Same-model personas share blind spots, so decorrelate with off-axis
  instruments (see *Independence*, below).
- **`[...]` slots are author-fill per run** (the suite's convention for per-instance values): replace
  `[pr_ref]`, `[base..head]`, and `[changed_gate_paths]` with the PR under review, its diff range, and
  the gate-layer paths it changes (the list `gate-review-check.py` printed).
- **REPORT ONLY. NEVER merge, never push, never apply a label, never change a setting.** Your output is
  a verdict record, nothing else. Merging is the owner's separate, deliberate act.
- **Verify, don't assert. Enterprise bar.** Open the files; run the commands; recompute the numbers.
  Ground every claim in a path or a command you ran. A confident sentence is not evidence.
- **Record the verdict** as a committed file under `gate-reviews/` using `gate-reviews/TEMPLATE.md`.
  That record is what the required `gate-review` status check reads; it must carry the evidence fields,
  not just a verdict line.

## What you are reviewing

Pull request **[pr_ref]**, diff **[base..head]**, touching the gate layer at **[changed_gate_paths]**.

The **gate layer** is the set of files that can pass CI green while silently weakening or
mis-describing a check: `release-gate.sh`, `build-skills.sh`, `validate_skill.py`, `check-version.py`,
`pkgtools.py`, every `lint-*.py`, `shared/verify.py`, `tests/**`, `.github/**`, and the governance
files themselves (`gate-review-prompt.md`, `gate-review-check.py`, `CONTRIBUTING.md`). The canonical,
machine-read list is `.github/gate-paths` — read it; do not assume it.

---

## The brief (prepend to every lens)

```
You are one of several INDEPENDENT reviewers of a change to the GATE LAYER of the
project-doc-skills repository — the build/lint/test/CI machinery that decides whether the
suite is releasable. You run in a fresh context and never see the other reviewers.

MINDSET: adversarial. A gate's job is to FAIL when reality is wrong. Assume this change has
left some way for reality to be wrong while the gate still says "fine", until your own read
proves otherwise. Never let a confident docstring or a green CI run stand in for a check you
have actually traced. Quote the exact line (file:line), rank it, and give a concrete fix.

SEVERITY: BLOCKER = a gate can now pass while the thing it guards is broken/stale, OR a
gate-path change can reach main unreviewed; MAJOR = the gate guards materially less than it
claims, or its self-description is wrong, or a required fixture is absent; MINOR; NIT.
Do not pad: a fabricated nit is as bad as a missed blocker.
```

## Lens A — Replay the real failure (the centerpiece)

```
Identify the REAL failure this gate exists to catch (read the docstring, the CHANGELOG entry,
and the incident it cites — e.g. b65041f for the skill-enumeration drift). Then REPRODUCE that
real failure against this change and MEASURE coverage:
  - Re-create the actual stale/broken state from the incident (not a toy mutation of a case the
    gate already handles). Does the gate catch it? Enumerate EVERY site/case the real failure
    could occur in, and report how many the gate actually covers as a fraction: N of M.
  - A synthetic mutation of an ALREADY-guarded case is NOT proof. If the only evidence offered
    is "I changed a guarded line and it failed", that is circular — say so.
State the coverage number explicitly (e.g. "Coverage: 2/5 enumeration sites"). If N < M, name
the M-N sites the gate silently ignores. You are NOT here to admire the happy path.
```

## Lens B — Coverage vs advertising

```
Hold the gate's CLAIMS next to what it DOES. Read every promise in its docstring, its CHANGELOG
entry, its --help, and — critically — every status string it can PRINT ("clean", "ok", "agree",
"PASS", "all N ..."). For each claim, find the code that backs it, or flag it.
  - Can the gate emit a success/clean/agree message while the reality it describes is stale or
    only partially checked? That exact shape — `clean` over 2 of 5 sites — is the archetype here.
    A success message must not assert more than the code verified.
  - Does the CHANGELOG/docstring describe behaviour the code does not implement (or no longer
    does)? Quote both sides.
```

## Lens C — Self-description drift

```
A gate that counts or lists itself must update that count/list when it changes. Check:
  - Did this change alter the number or set of checks, lints, steps, skills, or paths — and did
    every place that states that number/set get updated? (The canonical miss: a 3rd lint added,
    release-gate.sh still says "two lints". Another: build-skills.sh "all seven" after the 8th
    skill.) Grep the gate layer for hard-coded counts and enumerations and verify each.
  - Where a count/list is DERIVED from one source (e.g. .github/gate-paths read by the script),
    confirm it is genuinely single-sourced and not silently duplicated in prose that can drift.
```

## Lens D — Fixture requirement (the deterministic backstop; CONTRIBUTING.md requirement ii)

```
Wherever a gate failure CAN be reduced to a deterministic check, it MUST be — the independent
review is the backstop for judgement, never an excuse to skip the cheap machine check.
  - Does any NEW or CHANGED gate correctness-check arrive WITH a regression fixture derived from
    the REAL incident it guards (a fixture that fails if the check is reverted to a no-op)? If
    not, that is a finding: the fixture is owed (BLOCKER for a correctness gate; note the logged
    exception for a pure process/bootstrap mechanism — see CONTRIBUTING.md "Requirement (ii)").
  - For a finding YOU raise: ask "could this have been a fixture rather than a human catch?" If
    yes, the fix is to add the fixture, not only to note the bug.
```

## Lens E — Adversarial adjudicator (runs last; sees A–D)

```
You are the cross-examiner over the other lenses (pasted below). They came from the SAME model
in different lenses, so AGREEMENT may be shared bias and SILENCE (what they ALL missed) is where
your value is highest. Re-read the diff yourself and verify load-bearing claims against the
files. Produce: what they all missed; findings you would downgrade or reject (with reasoning);
the merged, de-duplicated, severity-ranked master register (BLOCKER -> NIT), each with file:line,
the fix, and which lens raised it (or "missed by all"); and the single highest-leverage fix.
```

## Independence — how to make the review actually decorrelated

The point is not "more reviewers"; it is **uncorrelated** reviewers. Lenses A–D on one model share
that model's blind spots. Decorrelate with off-axis instruments:

- **Code-grounded verification.** At least one lens must RUN things — `./release-gate.sh`,
  `python3 gate-review-check.py …`, the changed lint against a hand-built stale fixture — and report
  output, not recollection.
- **A different-vendor cold pass (recommended at any BLOCKER-risk change; run by the owner outside
  this prompt).** Give a different vendor's frontier model the brief + Lens A + Lens B, COLD (no prior
  findings). It will lack the repo, so it must tag code claims `[NEEDS-CODE-CHECK]`; verify those
  against source when its findings return. Its decorrelated weights catch what same-model lenses miss.
- **Honest limit.** Spawning sub-agents on the same model is *context* isolation, not *model-weight*
  decorrelation. Say so in the verdict; do not claim independence you did not have.

## Verify, don't assert (applies to every lens)

- Re-run the gate against a value that **differs from the default**; a wrong fix passes green against
  the default (that is how a real bug shipped here once). Print resolved values.
- Open the file before describing what it does. List the files you opened and the commands you ran.
- Treat a missing test as a finding, not a footnote.

---

## OUTPUT — the verdict record (commit it under `gate-reviews/`)

Produce **exactly** the structure in `gate-reviews/TEMPLATE.md`. The required `gate-review` status
check (`gate-review-check.py`) reads this file and verifies its **shape and evidence**, so all of the
following must be present or the check stays red (by design — a record without evidence is a rubber
stamp):

- a line naming the prompt version: `gate-review-prompt.md v1.0.0`;
- the sections **Replay the real failure**, **Coverage vs advertising**, **Self-description drift**,
  **Fixture requirement**, and **Findings**;
- a **`Coverage: N/M`** line inside the replay section (the evidence the real failure was reproduced
  and measured, not synthetically mutated);
- a final **`Verdict: PASS`** — and you may only write PASS if every BLOCKER and MAJOR is resolved in
  the change under review. If any remain, write `Verdict: BLOCK` and list them; the check will (rightly)
  keep the PR red until they are fixed and the review re-run.

Report only. The owner merges — you do not.
