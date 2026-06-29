# Different-vendor pass — ready-to-paste blind prompt

`doc-critic`'s strongest decorrelation is a **different vendor's frontier model**, and the skill is
honest that this **cannot be automated from inside it**. The same-family run in `REVIEW.md` achieved
context-isolation but not model-weight decorrelation — its own adjudicator flagged that all three axes
stayed inside the "prose ↔ code" triangle and never used the glossary or the filesystem as an arbiter.
That is exactly the blind spot a different vendor tends to cover.

**How to use:** open a frontier model from a *different vendor*, paste everything in the box below,
then paste the four documents from `docs/` (`M0`, `M1`, `M2`, `glossary.md`) where marked. Run it
**cold** — do **not** show it `REVIEW.md` or any prior finding (that would anchor it). When its
findings come back, verify every `[NEEDS-CODE-CHECK]` item against `sample_app/lru_cache.py` before
acting.

---

```
You are an INDEPENDENT reviewer auditing a short beginner learning track titled "How a small cache
works" — a tutorial on a small least-recently-used (LRU) cache, for a reader new to caches and to
programming (about grade 9). The four documents are pasted at the bottom. You do not have the source
code or the repository.

THE WRITING CONTRACT (judge against these):
- The plain-words floor must be BOTH clear for a beginner AND technically true.
- A simplification may be incomplete but never false.
- Define every term on first use; the glossary is meant to be the single reference — treat it as the
  canonical definition of record and check the modules against it.
- One everyday analogy per concept, and the analogy must teach the RIGHT shape and DIRECTION.
- Honesty: a feature must not be called "works today" on one page and "not yet built" on another.

MINDSET: adversarial. Assume the docs are flawed until your read proves otherwise. Hold the WHOLE set
at once and hunt the failures that only show when you cross-reference pages: a claim made on one page
and disowned on another; an analogy whose direction is inverted or that contradicts the rule it
illustrates; a term used before it is defined or missing from the glossary; built-vs-unbuilt markers
that disagree across pages; a forward-reference a later page never delivers.

You CANNOT see the code, so for every claim about what the code does (return values, behaviour on a
miss, default numbers), tag it [NEEDS-CODE-CHECK] and state what you would verify, rather than
asserting. For everything checkable from the prose and the glossary, verify it yourself.

OUTPUT (markdown):
## Verdict — one paragraph + the single biggest risk
## Findings — each as: [SEVERITY] file · section — "exact quote" / Problem / Fix
   (BLOCKER = a reader is left believing something false, or two pages contradict; MAJOR; MINOR; NIT)
## Glossary completeness — terms used but not defined, and definitions that disagree with usage
## If you fix one thing

=== PASTE THE FOUR DOCUMENTS BELOW (docs/M0-what-a-cache-is.md, docs/M1-get-and-set.md,
=== docs/M2-eviction.md, docs/glossary.md) ===

[paste here]
```

---

When the findings return, map each one to the register in `REVIEW.md`: a finding the same-family axes
**missed** is the high-value catch (especially anything needing the glossary or the code as arbiter),
and any `[NEEDS-CODE-CHECK]` item should be confirmed against `sample_app/lru_cache.py` — where, in
this example, the planted code-vs-doc defects (`get` raises `KeyError` not `None`; default capacity is
100 not 128) are waiting to be confirmed.
