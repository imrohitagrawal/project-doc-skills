# gate-reviews/ — the committed record of every independent gate-review

Each file here is the verdict of an independent gate-review run with `gate-review-prompt.md` on a
pull request that touched the gate layer (see `.github/gate-paths`). The verdict is recorded in the
repository — not as an ephemeral label or a chat message — because the record is the evidence: it
carries the replayed-failure coverage number and the findings, which is what resists a rubber stamp.

- `TEMPLATE.md` — copy this per review, fill every `[...]`, commit it in the PR.
- The required `gate-review` status check (`gate-review-check.py`) reads the verdict you commit and
  verifies its shape and evidence. A gate-layer PR cannot go green without a well-formed `Verdict: PASS`
  record here. CI green is necessary, not sufficient — see `CONTRIBUTING.md`.

`TEMPLATE.md` and this `README.md` are scaffolding, not verdicts; the check ignores them.

**One record per pull request, updated in place — not one file per review round.** `gate-review-check.py`
is deliberately fail-safe: a `BLOCK` record blocks *even if a `PASS` is added later*, and it reads every
verdict record the PR touches. So a PR that needs a second round must **update its existing record** (the
current verdict on the last line, earlier rounds summarised inside it) rather than add a second file —
otherwise the first `BLOCK` makes that PR permanently unmergeable however good the later review is. PR
#12 hit exactly this and its per-round files were consolidated into one. The append-only rule in
`CONTRIBUTING.md` binds a record **once merged**; iterating a record inside its own open PR is expected.
