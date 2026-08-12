# Gate-review verdict — PR "watermark: the executor the contract specified, and the fixture lists that went stale behind it"

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: `watermark-rebuild`
- Diff range: `main..watermark-rebuild`
- Gate-layer paths changed: `skills-order`, `tests/run-golden.py`, `tests/revert-battery.py`
- Reviewers / instruments: a four-lens review of the **first** attempt at this skill — an execution
  lens that ran the tool against real fixtures, a contract-fidelity lens, an adversarial lens that
  attacked it as a file-mutating tool, and a **different-vendor cold pass** (Codex,
  `codex exec --sandbox read-only`). All four returned *do not merge*. This rebuild is the response,
  and every finding below is traceable to one of them or to the owner's own visual review of the
  rendered output.
- Independence limit honestly stated: the rebuild was written by the same author the four lenses
  reviewed. The **different-vendor** pass is genuine weight decorrelation; the other three are
  context isolation only. A round against **this** diff at this scope has not run.

## Replay the real failure

Two separate real failures, both reproduced.

**Failure 1 — the gate-layer one. A hardcoded 8-skill list silently disabled ten fixtures.**
`tests/run-golden.py` carried the skill order as literal text in three places: `ORDER8`, the
`FULL` improve-order block, and `BROKEN_RUN`. Those fixtures work by `repl()`-ing a known string
into a scratch copy of a real doc and asserting the checker catches the decoy. When a ninth skill
was added, the literals stopped matching the docs, `repl()` planted **nothing**, and every one of
those fixtures reported **`clean`** — the word for "no defect found" — while testing an empty change.

Reproduced exactly. Adding `watermark` to `skills-order` took the suite from `277/277` to
`267/277`; the ten failures were all `real-docs scratch: … -> caught — clean`. They were not new
breakage; they were fixtures **waking up**. Ten more (`0008 F2`, `0017`) anchored on the literal
`"A suite of eight independent"` and went the same way when the prose count changed.

**The fix is structural, not a re-typed list.** All skill-name runs are now derived from
`skills-order` at test time, and the two prose fixtures re-anchored onto text carrying no count.
A literal that encodes a count is a fact that goes stale silently — which is why `ORDER8` is now
`SKILL_ORDER`, named off the number.

Coverage: 3/3 hardcoded skill-order literals in the gate layer

**Failure 2 — the skill's own.** The contract specifies credit furniture in three shared files and
nothing applied it. The first attempt at an executor was rejected by four lenses; the defects are
listed in `skills/watermark/CHANGELOG.md` and every one is closed here.

## Findings

- **FIXED-1 — the mark was hardcoded white** (`apply_watermark.py`, first version). On a light
  export white-on-near-white changed **zero pixels** while the tool printed `watermarked N of N`.
  Confirmed visually by the owner against a rendered comparison. Ink is now derived from the
  image's own bottom edge.
- **FIXED-2 — the self-test compared bytes, not pixels**, and `SKILL.md` named that assertion as the
  guard against "reports success while changing no pixels". A PNG re-encode changes bytes, so a
  mutant drawing nothing passed. **The first repair also failed**: measuring contrast across the
  whole band passed the same mutant on the strength of the slate rule alone. It now measures the
  rows the text occupies, verified in both directions — healthy `contrast 218/213`, mutant
  `contrast 0, FAIL`.
- **FIXED-3 — the footer check was a raw-bytes grep**, wrong in both directions: it accepted five
  pages whose only `©` sat in a comment, a `<script>` string, a code sample, a CSS `content`
  property or an `alt` attribute, and refused `&#xA9;`, `&#x00A9;` and the word *Copyright*. It now
  parses. Reverting to the grep fails both assertions at once.
- **FIXED-4 — `--in-place` truncated originals.** A 64MB image was measured at 18MB and unreadable
  after an interrupted run. Writes are atomic (temp file in the destination directory, then
  `os.replace`).
- **FIXED-5 — one corrupt file aborted a directory run mid-write** with an uncaught
  `UnidentifiedImageError`, leaving some originals overwritten, the rest untouched, and no summary
  printed. Unreadable images are refusals now.
- **FIXED-6 — nested directories were flattened** onto the base filename, so `a/chart.png` and
  `b/chart.png` overwrote each other while the run reported both done.
- **FIXED-7 — the profile value was interpolated into HTML unescaped**, writing a live `<script>`
  tag into a published page.
- **FIXED-8 — `SKILL.md` cited an `AGENTS.md` and an `RCA-001` that do not exist in this
  repository**, and claimed a rule was stated three times in a file that states it once. Removed.
- **FIXED-9 — the scope paragraph was void.** It read *"the OG card is the whole real case"*, scoped
  to the stackclimb.com site. The owner has since stated the site does not need this skill at all.
  Removed, and the skill is documented as standalone.
- **FIXED-10 — `tests/mutation-runner.py` was vacuously passable.** No minimum-mutant assertion, so
  an empty or thinned `MUTATIONS` list printed `0/0 mutations bite` and exited **0** — a mutation
  harness reporting success while killing nothing, the one failure it exists to make impossible.
  A `MIN_MUTATIONS` floor now refuses. **The floor is a real number, not `> 0`**, because deleting
  all but one mutation would otherwise still pass. Carried from `0024`, closed here.
- **FIXED-11 — nothing invoked the mutation runner, and nothing invoked the watermark self-test.**
  Both were advisory, so CI could go green without either ever running. `0024` recorded this and
  stated what would make them blocking; that is now done. `release-gate.sh` runs **7 steps**, not 5:
  step 6 is the mutation harness, step 7 the watermark executor's self-test. A gate nothing invokes
  is a gate that has never refused anything.
  **Both directions proved:** raising the floor above the declared count makes the runner print
  `REFUSED — 13 mutation(s) declared, floor is 99` and the composed gate stop with
  `release gate FAILED at step 6`; restoring it returns `all 7 steps green`.

## Round history

| # | head | verdict | blocking finding | resolution |
|---|---|---|---|---|
| 1 | 87accd1 | block | Four independent lenses — execution, contract-fidelity, adversarial, and a different-vendor cold pass — all returned *do not merge* against the first attempt. The mark was hardcoded white and changed **zero pixels** on a light export while reporting success; the self-test compared bytes so a mutant drawing nothing passed; the footer check was a raw grep, wrong in both directions; `--in-place` truncated originals; nested directories overwrote each other; the profile value was injected into HTML unescaped | rebuilt: margin band with ink derived from the artifact, pixel-measuring self-test, parsing footer check, atomic writes, tree-preserving output, escaped interpolation. FIXED-1 … FIXED-9 above |
| 2 | pending | pending | pending | pending |

## Why this record is nevertheless BLOCK

The most recent independent review (round 1) returned BLOCK, against the first attempt at this
skill. Every one of its findings is reproduced and fixed above, and each fix was verified by
execution rather than asserted. The round-2 row is `pending` because an independent round-2 review
of THIS diff has not returned, and the author may not certify the author's own fixes. Three
residuals are carried rather than dropped.

The required `gate-review` check stays RED — the correct state for a gate-layer change whose current
round is open, not a defect to route around.

Verdict: BLOCK
