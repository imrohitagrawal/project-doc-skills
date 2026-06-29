# REVIEW.md — doc-critic register for the "How a small cache works" track

- **Run date:** 2026-06-28
- **Reviewed doc set:** `examples/doc-critic-demo/docs/` (M0, M1, M2, glossary, about-and-credits) + `sample_app/lru_cache.py`
- **Models:** all four axes ran on Claude (Opus 4.8) — **same model family** (see [the honest limit](#honest-limit-read-this)).
- **Method:** `verify.py` (0 FAIL) → three **blind, isolated-subagent** axes (whole-document consistency · code-grounded correctness · beginner floor), each in its own context with only the docs + a neutralized writing contract → an **adversarial adjudicator** that saw all three and reconciled.
- **Status:** this register is the **unedited** output of the run. The docs are a deliberately-flawed worked example; the findings below are the critique that caught the flaws. Nothing here was hand-corrected.

> This is what `doc-critic` produces: a severity-ranked register a human acts on. It does **not** auto-edit the docs.

## Verdict

The track is mechanically clean (it passes `verify.py` with 0 FAIL) and pleasant to read, but it ships **five BLOCKER-level defects a regex/readability verifier cannot see** — a miss contract that hands the reader code that crashes, an eviction analogy that teaches the rule backwards, a "your data is safe" promise the cache's own design breaks, a disk-persistence feature claimed as built on one page and disowned on another, and a wrong capacity constant. The single highest-risk item is the miss behaviour (**B1**): the docs say `get` returns `None` and "you do not need to guard the call," but the code raises `KeyError` — a reader who follows the docs writes `if cache.get(k) is None:` and crashes on the first miss.

## Master register

| ID | Sev | Location | Quote | Doc-vs-code | Fix | Lens(es) | Status |
|----|-----|----------|-------|-------------|-----|----------|--------|
| **B1** | BLOCKER | M2 · "What the code gives you on a miss" | "the cache returns `None`. … Nothing is raised, so you do not need to guard the call." | Doc: returns None, no guard needed. **Code (`lru_cache.py:23`):** raises `KeyError`; run confirms `get('b') raised KeyError`. | Rewrite: a miss **raises `KeyError`**; show a `try/except KeyError` guard (also discharges M1's promise). | Code-grounded (verified), Whole-doc, Beginner-floor | open |
| **B2** | BLOCKER | M2 · "The rule: least recently used" | "the attendant takes down the coat you handed over most recently … The newest coat to arrive is the one that goes." | Doc analogy: evicts newest/MRU. **Code (`:33`):** `popitem(last=False)` drops oldest/LRU; run `True False True` confirms `b` evicted. Also contradicts `glossary.md` ("Most recently used … safest from removal") and M2's own prose. | Invert the analogy: remove the coat **untouched the longest**; newest stays. | Code-grounded (verified), Whole-doc, Beginner-floor | open |
| **B3** | BLOCKER | M0 ↔ M2 · disk persistence | M0: "the cache saves itself to disk, so your items are still there after a restart" **vs** M2: "[designed, not yet built] … starts empty every time" | No disk I/O anywhere in the code; in-memory `OrderedDict` only. The most load-bearing fact (does my data survive a restart?) is self-contradictory. | Remove the "shipped" disk claim from M0; apply the existing `[designed, not yet built]` marker there too. | Whole-doc (BLOCKER); Code-grounded + Beginner-floor filed MINOR — **adjudicator upgraded** | open |
| **B4** | BLOCKER | M0 · "Why small is the point" | "you never lose what you put in. Every key you set stays in the cache until you choose to remove it yourself." | False for an LRU; M2 "the cache removes an item by itself"; code auto-evicts (`:33`). | Replace with the truth: the cache may **evict on its own** when full (forward-ref to M2). | Whole-doc, Beginner-floor | open |
| **B5** | BLOCKER | M2 · capacity default | "By default that number is 128." | Doc: 128. **Code (`:12`):** `capacity: int = 100`; run confirms "default capacity is 100." | Change to **100** (or change the code and re-verify — one source of truth). | Code-grounded (verified) — **missed by Whole-doc & Beginner-floor** | open |
| **M1** | MAJOR | M1 · "What a miss is" | "Module 2 shows the exact result … **and how to handle it** in your own code." | Forward-promise unmet: M2 gives the (wrong) result but no handling example. | Add the `try/except KeyError` snippet when fixing B1. | Whole-doc, Beginner-floor | open |
| **M2** | MAJOR | M1 & M2 · "Try it yourself" | "Which item is now the most recently used?" / "Which key is gone, and why?" | Exercises ask the reader to apply recency/eviction order, but no worked trace is shown in either body. | Add one worked trace each; sequence after B2. | Beginner-floor | open |
| **M3** | MAJOR | M2 miss section + glossary | "the cache returns `None`"; no `KeyError` headword in the glossary | First raw code token a non-programmer meets is unglossed — and after B1 the token should be `KeyError`. | Add a glossary entry for **`KeyError`** / "raises"; do not gloss `None`. | Beginner-floor (re-aimed from "None" to `KeyError` by the adjudicator) | open |
| **N1** | MINOR | M0 · "What this cache can do today" | "Three things work right now. … set … get … saves itself to disk" | Inventory wrong both ways: counts non-existent disk persistence and **omits eviction** (the differentiator that works). | List the three real ones: set, get, eviction; drop disk. | Both-directions framing **missed by all** | open |
| **N2** | MINOR | glossary | (no entry) "Eviction" / "Evict" | M2 leans on the term; no headword; M1 uses "evict" before M2 defines it. | Add an **Eviction** headword. | Beginner-floor | open |
| **N3** | MINOR | glossary · "Touch" | "Touch. To get or set an item." | Unconditional, but a **missed** get raises before `move_to_end` — a miss touches nothing. | Qualify: a get **that hits**, or any set, is a touch. | **Missed by all** | open |
| **N4** | MINOR | M1 · "What a miss is" | "how to handle it in your own code" | Assumes the reader writes code; the track is code-optional until M2. | Soften to "what your code should do." | Beginner-floor | open |
| **T1** | NIT | about-and-credits · Licence | "the `LICENSE` file **in this folder**" | Doc is in `docs/`; `LICENSE` is one level up. File + disclaimer verified present. | Repoint to the repository root / `../LICENSE`. | **Missed by all** (no axis checked the file) | open |
| **T2** | NIT | M0 · "Try it yourself" | "why it works better for being small" | Idiom may trip a grade-floor / ESL reader. | "why being small makes it work better." | Beginner-floor | open |
| **T3** | NIT — VERIFIED-CORRECT, do not "fix" | M1 · "Set" | "marks that item as the most recently used" (on re-set of an existing key) | Doc **matches** code (`:30` `move_to_end`); the one recency claim that holds. | No change. Recorded so a fixer does not collateral-damage it. | Verified by adjudicator; unremarked by all | n/a |
| **T4** | NIT — confirmed non-issue | M2 · "Eviction, defined" | "only when the cache is already full and you set a **new** key" | Code inserts then evicts (momentary cap+1), and re-setting an existing key does not evict, so "new key" is accurate. | No change. | Code-grounded (confirmed) | n/a |

## What the adjudicator found that all three axes missed
- **The glossary is the unused arbiter.** It defines "Most recently used … the safest from removal," so the inverted analogy (B2) is wrong against three concurring sources (M2 prose + glossary + code), not just one — the defect is track-wide.
- **The "Touch" definition is doc-vs-code wrong (N3):** a missed `get` raises before it can mark recency, so a missed get touches nothing.
- **The LICENSE locator is wrong (T1):** no single-lens reviewer checked the filesystem.

## Likely shared-bias artifacts (why a different vendor is still needed)
All three reviewers reached the right verdicts but, being the **same model family**, each proved them with the nearest witness (M2 prose or the code) and **none reached for the glossary or the filesystem**. The shape of what they all skipped — anything needing a glossary-as-arbiter cross-check or an external-file/unhappy-path trace — is the shared-bias signature. This is the concrete case for the different-vendor pass: see `DIFFERENT-VENDOR-PROMPT.md`.

## Top fixes (highest leverage first)
1. **B2 + B4 together** — kill the inverted analogy and the "you never lose data" line; one root error about *what survives*, surfacing in M0 and M2.
2. **B1 + M1 + M3 together** — correct the miss contract end to end (`KeyError`, a worked `try/except`, gloss the term). The only finding that ships *broken code*.
3. **B3 + N1** — apply the existing `[designed, not yet built]` marker to M0 and fix the "can do today" inventory.
4. **B5** — reconcile the capacity default to 100.
5. **Sweep N2/N3/T1** — the glossary and LICENSE locator items no single lens caught.

## Honest limit (read this)
All four axes ran on the **same model family**, so this run achieved **context-isolation** decorrelation (separate blind sub-agents) but **not model-weight** decorrelation. The adjudicator itself flagged the shared-bias signature. A genuinely independent gate needs the **different-vendor pass** — run `DIFFERENT-VENDOR-PROMPT.md` on another vendor's model and feed its findings back. This register proves the harness **catches planted, `verify.py`-invisible defects**; it is not evidence that it discovers everything an independent mind would.
