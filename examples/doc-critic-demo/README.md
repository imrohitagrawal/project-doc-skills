# doc-critic — worked example (a real run on a real doc set)

This folder is **evidence that the `doc-critic` skill works**: a small learning track was written,
passed the deterministic verifier with **0 FAIL**, then put through `doc-critic`'s full blind
multi-axis critique. The critique caught every defect that a regex/readability verifier cannot see.

It is the honest counterpart to the suite's consistency fixture (`tests/run-golden.py`): that fixture
locks the *method's docs* for consistency; **this** runs the *method itself* on real input and shows
what it finds.

> **Note on the snapshot.** Each sample module under `docs/` carries a ⚠️ banner pointing here so a
> stray reader can never mistake it for real teaching. `REVIEW.md` and the quotes in
> `DIFFERENT-VENDOR-PROMPT.md` were produced against the **pre-banner** module bodies (the banner is
> the only later addition), so the recorded run stays an honest record of exactly what the reviewers saw.

## What is here

| File | What it is |
|---|---|
| `docs/M0…M2`, `glossary.md`, `about-and-credits.md` | The **input** — a deliberately-flawed beginner track on a small LRU cache. Passes `verify.py` 0 FAIL; every flaw is *semantic*, invisible to the verifier. |
| `sample_app/lru_cache.py` | The real, runnable code the prose is checked against (the code-grounded axis runs it). |
| `LICENSE` | The doc + code licence with the warranty disclaimer (so the set is a complete, verifiable doc set). |
| `REVIEW.md` | The **unedited** severity-ranked register `doc-critic` produced. |
| `DIFFERENT-VENDOR-PROMPT.md` | The ready-to-paste blind prompt for the one axis this run could **not** automate. |

## How it was run

1. **`verify.py` first (the deterministic gate):** `python3 shared/verify.py examples/doc-critic-demo/docs --format md --skill learning-track --scope public --grade-target 9 --profile shared/project-profile.md --license examples/doc-critic-demo/LICENSE` → **5 files, 0 FAIL, 0 warn.**
2. **Three blind axes, each an isolated sub-agent** in its own context, given only the docs + a neutralized writing contract + its single lens (whole-document consistency · code-grounded correctness · beginner floor) — no knowledge of each other, of the author, or that defects were planted. (To keep them blind, they reviewed a neutrally-named copy, not this `doc-critic-demo/` path.)
3. **An adversarial adjudicator** saw all three, re-read the docs, reconciled duplicates, corrected severities, and hunted what they all missed → `REVIEW.md`.

## Ground truth — what was planted, and was it caught

Each defect is the *semantic* kind `verify.py` cannot catch, mapped to the axis the taxonomy obligates
to catch it. **The reviewers were not told any of this.**

| Planted defect | Where | Error class | Obligated axis | Caught by the obligated axis? | Register |
|---|---|---|---|---|---|
| "You never lose what you put in" — contradicted by eviction | M0 ↔ M2 | 1 · contradiction | whole-document | ✅ yes | B4 |
| Coat-check analogy drawn with **inverted** direction | M2 | 2 · analogy-shape | whole-document | ✅ yes | B2 |
| `get` "returns `None`" / "default 128" — code raises `KeyError` / default 100 | M2 vs code | 3 · code-vs-doc | code-grounded | ✅ yes — **verified by running the code** | B1, B5 |
| "evict" used before defined + missing from the glossary | M1 / glossary | 4 · term-definition gap | beginner-floor | ✅ yes | N2 |
| Disk persistence "works today" vs "[designed, not yet built]" | M0 ↔ M2 | 6 · honesty drift | whole-document | ✅ yes | B3 |

**Score: 5 / 5 planted defects caught by their obligated axis.** Most were *also* caught by other
axes (a contradiction is visible to several lenses) and the adjudicator de-duplicated them.

## Did it manufacture false positives? (the control)

Class **7 (broken forward-references)** was meant to be a clean control — *no planted defect*. In
practice the reviewers found one **genuine, unplanted** forward-reference gap (M1 promises M2 will show
"how to handle it in your own code"; M2 never does — register `M1`), so it was not a pure control.
But the **kept** forward-references (M0→M1, M0→M2, M1→"the miss result") drew **zero** "broken
reference" findings, and the reviewers explicitly declined to invent findings elsewhere: `T3` was
recorded as **verified-correct, do not fix**, `T4` as a **confirmed non-issue**, and the attribution
check returned **"no fix required."** So the no-false-positive property held by *discrimination* — they
flagged the one unkept promise and stayed silent on the kept ones, rather than padding.

## The honest limit (stated plainly)

All four axes ran on the **same model family** (Claude, Opus 4.8). This run achieved
**context-isolation** decorrelation — separate blind sub-agents — but **not model-weight**
decorrelation. The adjudicator itself named the shared-bias signature: all three same-family reviewers
proved their findings with the nearest witness (M2 prose or the code) and **none reached for the
glossary or the filesystem** as an arbiter.

So this example proves a bounded claim: **the harness reliably catches planted, `verify.py`-invisible
defects.** It is **not** evidence that it discovers everything an independent mind would — the author
and the reviewers share weights. The genuine decorrelation is the **different-vendor pass**, which
`doc-critic` (honestly) says it cannot automate. Run `DIFFERENT-VENDOR-PROMPT.md` on another vendor's
model and feed its findings back for the real flagship gate.

## Gaps this run exposed (recorded, not fixed here)

Per the run's own discipline, defects the method under-handled are findings — recorded, not silently patched. Any real fix is a **separate PR** against the skill.

1. **Single-axis severity is unreliable; the adjudicator is load-bearing.** The disk-persistence drift
   (B3) was filed **MINOR** by two axes and **BLOCKER** by one; only the adjudicator reconciled it to
   BLOCKER. Evidence *for* the method's "adjudicator runs last" design, not against it.
2. **The obligated-axis mapping is leakier than the taxonomy implies.** Cross-page defects surfaced on
   2–3 axes each. Useful (redundancy), but it means the register is duplicate-heavy before
   adjudication — the dedup step is essential, not optional.
3. **A concrete prompt nudge (candidate for `CROSS-SKILL-FINDINGS.md` + a future `reviewer-prompts.md`
   PR):** every same-family axis missed the **glossary-as-arbiter** cross-check and **external-file**
   verification (the LICENSE locator, `T1`). The code-grounded and whole-document lenses could be told
   to "treat the glossary as the canonical definition of record" and "open any file the docs reference."
   This is exactly the class the different-vendor pass is best at — which is itself the lesson.

## Re-run it yourself

`doc-critic` is non-deterministic, so a re-run will not reproduce `REVIEW.md` byte-for-byte (this is
why `REVIEW.md` is **not** a gate fixture). To reproduce the *method*:

1. Run the verifier command above — it must be 0 FAIL.
2. Spawn the three blind axes (the lenses are in `skills/doc-critic/references/reviewer-prompts.md`),
   each in its own fresh context, over the whole `docs/` set; then the adjudicator over their outputs.
3. Compare your register to `REVIEW.md` and to the ground-truth table above.

— Run 2026-06-28 · Claude Opus 4.8 · method: `skills/doc-critic/`.
