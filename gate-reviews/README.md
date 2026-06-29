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
