# Repository settings to apply by hand (not committable)

Branch protection lives in GitHub settings, not in the repo, so it cannot ship in a PR. This file is
the **record** of the settings the governance rule needs; the maintainer applies them once with the
commands below. (Per [`CONTRIBUTING.md`](../CONTRIBUTING.md) "Governance".)

## The branch ruleset on `main`

One ruleset enforces everything — a single surface, so there is no second place to drift (do **not**
also add a classic branch-protection rule). It requires both status checks, blocks force-push and
deletion, and has **no bypass actors** so it applies to the owner too.

```bash
gh api --method POST repos/imrohitagrawal/project-doc-skills/rulesets --input - <<'JSON'
{
  "name": "gate-layer-protection",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "pull_request", "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false
    }},
    { "type": "required_status_checks", "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          { "context": "release-gate" },
          { "context": "gate-review" }
        ]
    }}
  ]
}
JSON
```

Notes on the choices:

- **`bypass_actors: []`** — nobody bypasses, including the owner. This is the line between real
  enforcement and decoration for a solo repo. (Honest ceiling: you can still *edit or delete this
  ruleset* — that is a deliberate, logged action, which is the point. See CONTRIBUTING.md.)
- **`required_approving_review_count: 0`** — a PR is required (no direct pushes to `main`), but no
  human approval is, because a solo maintainer cannot approve their own PR. Enforcement is the
  `gate-review` check, not an approval.
- **`required_status_checks`: `release-gate` and `gate-review`** — both must pass. The context strings
  must match the check names exactly; confirm them with `gh pr checks <PR>` (they are the job names
  `release-gate` and `gate-review`).
- **`strict_required_status_checks_policy: true`** — the branch must be up to date with `main` before
  merge, so a PR cannot pass against a stale base. Slightly more friction (update-branch then the
  checks re-run); drop to `false` if that friction outweighs the safety for you.
- **`non_fast_forward` + `deletion`** — no force-pushes that rewrite `main`, no deleting it.

## Rollout order (avoids the chicken-and-egg)

A required check that has never run would block every PR. The governance PR adds `gate-review.yml`, and
GitHub runs a new workflow from the PR's own head — so `gate-review` reports on the governance PR
itself before the ruleset exists. Therefore:

1. Open the governance PR. Confirm **both** `release-gate` and `gate-review` are green on it
   (`gh pr checks <PR>`). This proves the mechanism before it is required.
2. Apply the ruleset (command above).
3. Merge the governance PR — it becomes the **first** merge enforced by the new rule (true
   self-application, end to end).

## Verify / inspect / undo

```bash
gh api repos/imrohitagrawal/project-doc-skills/rulesets                       # list rulesets (find the id)
gh api repos/imrohitagrawal/project-doc-skills/rulesets/<id>                  # inspect one
gh api repos/imrohitagrawal/project-doc-skills/rules/branches/main           # what rules apply to main now
# To change or remove (a logged, deliberate act — the honest bypass path):
# gh api --method PUT    repos/imrohitagrawal/project-doc-skills/rulesets/<id> --input <edited>.json
# gh api --method DELETE repos/imrohitagrawal/project-doc-skills/rulesets/<id>
```
