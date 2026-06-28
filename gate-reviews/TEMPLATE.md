# Gate-review verdict — [pr_ref]

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full   <!-- 'full' (default) for any behavioral change; 'light' ONLY for a declared
                    non-behavioral change — see gate-review-prompt.md "Proportionality" -->
- PR / branch: [pr_ref]
- Diff range: [base..head]
- Gate-layer paths changed: [changed_gate_paths]   (the list gate-review-check.py printed)
- Reviewers / instruments: [e.g. 3 blind same-model lenses + adjudicator; + different-vendor cold pass]
- Independence limit honestly stated: [e.g. same-model = context isolation, not weight decorrelation]
<!-- LIGHT path only: uncomment the next line and set Coverage: N/A below.
- Light-path justification: [comment/doc/whitespace only; no change to any check's logic, the gated
  set, a count/threshold, or the policy's meaning] -->

> Copy this file to `gate-reviews/<short-name>.md`, fill every `[...]`, and commit it in the PR.
> The required `gate-review` check reads it and verifies the shape AND the evidence — a blind copy of
> this template FAILS on purpose (the coverage line has no digits and the verdict is bracketed), so a
> rubber stamp cannot pass. Fill real values.

## Replay the real failure

[Which real failure does the changed gate exist to catch? Reproduce the ACTUAL stale/broken state
from the incident — not a toy mutation of an already-guarded case — and measure coverage. List every
site/case the failure can occur in, and how many the gate actually covers.]

Coverage: [N]/[M] [units, e.g. enumeration sites]   <!-- replace [N]/[M] with real digits, e.g. 5/5;
                                                         a LIGHT-tier verdict uses 'Coverage: N/A' -->
[If N < M: name the M-N sites the gate silently ignores.]

## Coverage vs advertising

[Does the gate do everything its docstring / CHANGELOG / --help / printed status strings claim? Can it
emit a success/clean/agree/PASS message while the reality it describes is stale or only partially
checked? Quote both the claim and the code.]

## Self-description drift

[Did this change alter a count or list of checks/lints/steps/skills/paths, and did EVERY place that
states that number/set get updated? Grep the gate layer for hard-coded counts. Confirm any derived
list is genuinely single-sourced, not duplicated in prose that can drift.]

## Fixture requirement

[Does any new or changed gate correctness-check arrive WITH a regression fixture derived from the real
incident it guards (one that fails if the check is reverted to a no-op)? If not, the fixture is owed —
record it as a finding, or note the logged exception for a pure process/bootstrap mechanism.]

## Findings

[Severity-ranked: BLOCKER / MAJOR / MINOR / NIT. Each with file:line, the problem, the concrete fix,
and which lens raised it (or "missed by all"). "No findings" is allowed only if the lenses genuinely
found none — say what you checked.]

---

Verdict: [PASS or BLOCK]
[You may only write PASS once every BLOCKER and MAJOR is resolved in the change under review.
If any remain, write BLOCK and list them; the check will keep the PR red until they are fixed.]
