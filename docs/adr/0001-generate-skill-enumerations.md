# ADR 0001 — Generate skill enumerations, check byte-identical (replace the parse-based skill-count gate)

- **Status:** Accepted, hardened after review (`feat/skill-count-generate`, issue #7)
- **Date:** 2026-06-29
- **Gate layer:** yes — merges only through an independent gate-review (CONTRIBUTING.md "Governance").
- **Supersedes:** the operational scope of `lint-skill-count.py` (PR #2, suite 1.2.0).

> **Update (gate-review `gate-reviews/0005`).** The first implementation checked the marked block but
> recognised markers by *substring* match, which a different-vendor cold pass showed re-opened the decoy
> class: a marker embedded in a spanning HTML comment (or duplicated on one line) hid a canonical block
> while the visible list was broken, and a table decoy row hidden in a comment satisfied the name check.
> The marker model below (§2) is the **hardened** version: exactness + anchoring + rendered-only table
> rows. The lesson — a "no decoy class" claim must be earned at the *marker* layer, not just the content
> layer — is exactly the over-claim this whole line of work exists to end.

---

## Context

`lint-skill-count.py` (merged on `main` via PR #2) guards that every place the suite enumerates its
eight skills stays consistent with `skills/`. It works by **extracting** each enumeration from raw
Markdown with regex and set-comparing it to `canonical_skills()`.

Four independent review rounds each found a **silent-pass decoy**: a distant decoy run, a no-blank-tail
decoy, an immediate-adjacency decoy, and finally (Round 4, commit `6f66dfa`) a **markup-hidden decoy** —
a *canonical* run placed in an HTML comment / code span / reference definition immediately after the
introducing anchor, masking a *broken* visible list. We accepted this honestly for PR #2: the lint
guards **accidental** drift (its shipped job, which it does), **not** an adversarial decoy. The root
cause is structural and unfixable by parsing:

> A regex cannot distinguish the intended **rendered** enumeration from a **markup-hidden** decoy when
> the real docs themselves use markup. The extractor searches the document for "a run that looks like
> the list", so a hidden run can *be* the match.

**The fix is to stop parsing the document.** Generate each enumeration from a source of truth and check
it **byte-identical at a marked location**. There is then no "which run is the real one" question to
get wrong, so the entire decoy class disappears — *provided* marker handling fails closed.

This redesign reuses a discipline the repo already trusts: `build-skills.sh --check` /
`release-gate.sh` rebuild every `.skill` in a scratch dir and assert it is **byte-identical** to the
committed artifact (`pkgtools.py`, deterministic packaging). We apply the same "regenerate and compare
bytes" stance to the doc enumerations.

### The five enumeration sites (current state)

| # | File | Site | Shape today | Editorial columns? |
|---|---|---|---|---|
| 1 | `README.md` | skill **table** | `\| **name** \| mode \| scope \| grade \|` | yes — Diátaxis mode, scope, reading grade |
| 2 | `README.md` | repo **tree** (`skills/` block) | `│  ├─ name/` (inside a ``` code fence) | 2 trailing `#` comments on the last two |
| 3 | `README.md` | **improve-order** list | `**a → b → … → h.**` (bold, ` → `, trailing `.`) | no |
| 4 | `per-skill-review-prompt.md` | `{SKILL_NAME}` **pick-list** | `` `a · b · … · h` `` (code span, ` · `) | no |
| 5 | `per-skill-review-prompt.md` | attachment **table** | `\| name \| Attach these … \|` | yes — long per-skill prose |

All five share **one** order: `learning-track → architecture-and-decisions → project-faq → usage-guide →
operations-runbook → onboarding-companion → doc-critic → publish-mirror`. Plus scattered **scalar count**
phrases ("a suite of eight", "eight copies", "build all eight", "now **eight** skills", "eight-skill
documentation suite").

The decoy actually bit a **pure list** (improve-order). The two tables were never the bypass vector
(their extractors were row-shape/region scoped), but they are in scope here for completeness.

---

## Decision

### 1. Source of truth

- **Set** = `skills/<name>/` containing a `SKILL.md` — exactly today's `canonical_skills()`. Unchanged.
- **Order** = a new root file **`skills-order`**, one skill name per line, in editorial order. It is
  **validated as an exact permutation** of the set: any missing, extra, duplicate, or unknown name →
  **fail closed** (exit 1), never a partial render. `skills-order` is root scaffolding (not bundled
  into any `.skill`), so editing it needs **no** `.skill` rebuild.
- **Editorial table columns** (Diátaxis/scope/grade; the attachment prose) **stay authored inline** in
  the docs. See decision §3 for why they are *not* relocated to a manifest, and why the enumeration is
  still fully guarded without doing so.

### 2. Marker format — and the one critical property

Each site is wrapped in a **single** begin/end marker pair. Four sites (1, 3, 4, 5 — all outside code
fences) use **non-rendered HTML comments**:

```
<!-- skills:improve-order:begin -->
**learning-track → … → publish-mirror.**
<!-- skills:improve-order:end -->
```

Site IDs: `skills:table:*`, `skills:tree:*`, `skills:improve-order:*`, `skills:pick-list:*`,
`skills:attach-table:*`.

**The tree (site 2) is the documented exception.** It lives inside a ```` ``` ```` code fence, where
HTML comments render as *literal visible text* rather than hiding. So the tree uses **visible sentinel
comments that are part of the rendered tree** — ordinary-looking tree annotations:

```
│  ├─ skills/                  # skills:tree:begin (generated from skills-order — do not hand-edit)
│  ├─ learning-track/
│     … (one line per skill, in order) …
│  └─ publish-mirror/
│                              # skills:tree:end
```

Visibility does **not** weaken the guarantee: the fail-closed property is "exactly one begin and one
end, byte-identical between them", which is independent of whether the markers render. The only honest
deviation is cosmetic (the tree's markers are visible). This is called out so a reviewer is not
surprised that "non-rendered" has one exception forced by Markdown code-fence semantics.

**Marker handling — fail closed (THE load-bearing property; the whole silent-pass class dies here):**
for each of the five sites, in both the target file and any fixture, `--check` computes, per site:

- count of begin markers and end markers;
- **any of {begin ≠ 1, end ≠ 1, end index < begin index}** → **FAIL** (named site, exit 1).
- A site whose markers are **absent** → **FAIL**, never *skip*. (Skipping an absent region is exactly
  the silent-pass we are eliminating.)
- Only when markers are well-formed are the bytes strictly between them extracted for the per-site
  check.

This is the one property the gate-review must attack hardest. If it holds, the silent-pass class is
gone; if it can be made to skip an absent/ambiguous region, the class survives.

### 3. The five renderers + per-site check strategy

Two strategies, chosen per site by feasibility (the task's "(a) where feasible" steer):

**(a) Full byte-identical generation — the three pure sites (no editorial content).** The marked block
is generated in full from `skills-order` and `--check` asserts the block bytes equal the generated
bytes. **Zero document parsing.** Exact output bytes:

| Site | Generated bytes (between markers) |
|---|---|
| improve-order (3) | one line: `**` + `" → ".join(order)` + `.**` |
| pick-list (4) | one line: `` ` `` + `" · ".join(order)` + `` ` `` |
| tree (2) | one line per skill: `│  ├─ <name>/` for all but the last, `│  └─ <name>/` for the last (indent/glyphs matching the surrounding fence) |

**(b) Marker-fenced, positional, exact-ordered name-column check — the two tables (editorial inline).**
The generator emits the **expected ordered name sequence**; `--check` extracts, from the marked region
only, the first-column name of **every table-row line** (a line matching `^\s*\|\s*\*?\*?([a-z0-9-]+)`),
and asserts that ordered sequence **equals** the generated order. The editorial columns are not read and
not generated.

Why (b) is decoy-closed (the crux a reviewer will probe): extraction here is **positional within a
fail-closed marked region** and keys on `|`-leading lines, so **extraction == a visible rendered table
row**. A markup-hidden decoy (an HTML comment, a code span) is *not* a `|`-leading line, so it cannot be
extracted; and a broken visible table changes the extracted ordered sequence → mismatch → FAIL. Unlike
the old lint, there is no whole-document "best match" search, so no hidden run can *be* the match. The
markup-decoy class is closed at the tables too.

**Scalar count phrases** are checked exactly as PR #2's lint does (every occurrence of each specific
anchored phrase, word **or** digit, must equal `N = len(canonical_skills())`), carried into the new
script. This is intentionally a regex check and **not** in scope of the decoy class: a scalar count has
no "which list is the real one" ambiguity — there is nothing to masquerade as. (Honest residual noted
in §Residual.)

### 4. The `--check` contract

```
python3 generate-skill-enumerations.py [root] [--check]
```

- **Load + validate** `skills-order` against `canonical_skills(root)` (permutation; fail closed).
- **Write mode (no `--check`)** — rewrites the **three pure** marked blocks (1-line/per-line generated
  content) in place; leaves the two table regions untouched (their editorial columns are human-owned —
  there is nothing to author, only to check). Fails closed on any malformed/absent marker. Used for the
  one-time migration and for future edits to the skill set/order.
- **`--check` mode** — regenerates in memory and verifies all five sites: the three pure blocks
  **byte-identical**; the two tables **name-column ordered-equal**; the scalar count phrases equal `N`.
  On any failure: print the site, what differed, and the remedy
  — `run: python3 generate-skill-enumerations.py` (pure sites / order) or
  `fix the <site> name column to match skills-order` (tables) — and exit 1.
- **Integration:** `build-skills.sh` **replaces** the `lint-skill-count.py --strict` block (lines
  ~106-114) with `generate-skill-enumerations.py "$ROOT" --check`, folded into `$failed` exactly as the
  current lint is. `release-gate.sh` composes it via build step 1 ("compose, don't re-add") and its
  **prose is updated** ("skill-count lint" → "skill-enumeration check") so the gate's self-description
  does not drift (the §Governance failure-class 2).

### 5. Migration, retirement, and honesty

One-time, in this PR:

1. **Add `skills-order`** (8 lines, canonical order).
2. **Add `generate-skill-enumerations.py`**; run it once in write mode to fill the three pure blocks.
3. **Migrate the five sites to marked blocks**: isolate the improve-order run and the pick-list run each
   on their own line inside HTML-comment markers; convert the tree's `skills/` block to the visible
   begin/end sentinels and **move the two trailing annotations** (doc-critic / publish-mirror
   descriptions) into the prose around the tree (they already appear in the skill table and intro, so
   the tree loses nothing); add HTML-comment markers around the two tables' data rows. Verify order
   matches `skills-order`.
4. **Wire** `--check` into `build-skills.sh`; update `release-gate.sh` prose.
5. **Retire `lint-skill-count.py`**: delete the file, remove its `build-skills.sh` block, remove the
   `skill_count_extractors` section + `LINT_SKILL_COUNT` required-path in `tests/run-golden.py`, and add
   the new `skill_enumerations` golden section (Phase 2).
6. **`.github/gate-paths`**: `lint-*.py` no longer matches the generator (`generate-*.py`), so **add**
   `generate-skill-enumerations.py` and `skills-order` by exact name. (This correctly keeps the new gate
   correctness check and its source of truth in the gate layer — and makes this very PR gate-layer, so
   it takes a gate-review, as intended.)
7. **Honesty / removing the KNOWN LIMITATION disclosure.** The docstring + inline "KNOWN LIMITATION"
   comments disappear with the deleted `lint-skill-count.py`. The **CHANGELOG [1.2.0] entry is shipped
   history** and is left intact (it was true when written; CHANGELOG is append-only and not gated — see
   memory). Instead, an **`## [Unreleased]`** entry records that the structural fix landed and the claim
   is now "no decoy class — generated and checked byte-identical", **true and verifiable**, superseding
   the limitation. Staging under `[Unreleased]` also avoids a VERSION collision with any in-flight PR
   (`check-version.py` ignores `[Unreleased]`). *(If you would rather also strike the wording inside the
   historical [1.2.0] entry, say so at the gate — I default to supersession, not rewriting history.)*

No bundled file changes → **no `.skill` rebuild and no `dist/MANIFEST.sha256` churn** (every changed
file — README, the prompt, `skills-order`, the generator, `build-skills.sh`, `release-gate.sh`,
`run-golden.py`, `gate-paths`, CHANGELOG — is root scaffolding). `--check` and the manifest stay green
with no artifact rebuild.

---

## Residual (stated honestly — do **not** repeat PR #2's over-claim)

The silent-pass decoy class is eliminated **if and only if marker handling fails closed** (§2). Given
that, the residual is smaller and of a different, finite, fail-closable kind:

1. **Marker integrity.** A missing / duplicated / malformed marker must **fail the gate**, not pass it.
   This is finite and fully testable (fixtures in Phase 2), and it is the property the gate-review must
   adversarially confirm. If it ever regresses to "skip on absent marker", the class is back.
2. **A stray un-marked second enumeration.** The check governs only the marked regions, so a second,
   *un-marked* improve-order/pick-list pasted elsewhere is not seen. This is a **doc-authoring error,
   not a lint bypass** — there is no decoy masquerading as the checked enumeration; there is simply a
   second, ungoverned list. We deliberately do **not** add a coarse "no second ` → `/` · ` run anywhere"
   scan: that reintroduces document parsing and false positives, trading the clean property for the mess
   we are removing. Documented, not papered over.
3. **Tables (strategy b): editorial cells are unchecked bytes.** The name-column invariant is checked;
   the Diátaxis/scope/grade and attachment-prose cells are not (they are not enumeration data and have
   no cross-site duplication). Editorial drift in those cells is out of scope by design.
4. **Scalar count phrases remain a regex check.** Not subject to the decoy class (a scalar cannot
   masquerade as a list), but it is honestly a parse, not a generation. It is carried forward unchanged
   from PR #2.

All four are to be adversarially confirmed by the gate-review (Phase 3); 1 is the linchpin.

---

## Consequences

- **Positive:** the headline claim becomes true and machine-verifiable — "every enumeration site is
  generated from one source of truth and checked; no whole-document parse selects the enumeration, so no
  markup-hidden decoy can masquerade as it." Reuses the trusted byte-identical discipline. No `.skill`
  rebuild. `skills-order` becomes the obvious single place to add/reorder a skill.
- **Negative / costs:** five doc sites must carry markers (mild visual cost; the tree's are visible).
  Write mode is asymmetric (it authors the three pure sites but only checks the two tables). The two
  tables keep a *positional* parse (decoy-closed, but still a read) rather than full byte-identical —
  the conscious trade in §Alternatives.

---

## Alternatives considered

- **Plan A — full byte-identical on all five sites (relocate editorial content).** Move the table
  editorial cells (Diátaxis/scope/grade; the attachment prose) into a source-of-truth manifest so both
  tables can be generated and byte-compared like the pure sites. *Rejected as the default* because it
  relocates genuine editorial prose out of its natural home into config for **no enumeration-safety
  gain** — the enumeration invariant is the name column, which strategy (b) already guards decoy-closed;
  byte-identical would additionally lock editorial *cell* bytes, which are not enumeration data and have
  no drift risk (single-occurrence, no cross-site duplication). By the repo's YAGNI / no-over-engineering
  stance, that is unjustified machinery. **Offered for your call:** if you want the strongest uniform
  property (one mechanism, byte-identical everywhere) and accept editorial-in-manifest, I will switch the
  two tables to Plan A. The shared architecture (markers, fail-closed handling, `--check` harness,
  build/release wiring, fixtures, retirement) is identical either way; only the two table renderers
  differ, so this choice does not block starting TDD on the shared parts.
- **Inline count markers (generate the scalar too).** Wrap each count number in inline HTML-comment
  markers and generate it. Rejected: marker noise across scattered prose for a surface with no decoy
  class; the anchored scalar check is sufficient and simpler.
- **Keep parsing, harden further.** Rejected — this is exactly the four-rounds-bypassed path; no regex
  parse can distinguish a rendered list from a markup-hidden one. The whole point of #7.

---

## Phase 2 — test plan (fixtures FIRST, TDD)

New `tests/run-golden.py` section `skill_enumerations` (replacing `skill_count_extractors`), synthetic
inputs so it does not couple to the live docs, **plus** one assertion driving the **live** README +
prompt through `--check` to prove the migration is correct. Fixtures, each written to fail first:

1. **REAL-INCIDENT REGRESSION (headline).** A marked improve-order block with a **dropped** skill, plus
   a **markup-hidden canonical run** (HTML comment containing the full ` → ` list) right after the
   anchor — the exact `6f66dfa` shape. The old parser passed this; the new `--check` must **FAIL**
   (marked block ≠ generated bytes). Mirror for the pick-list (code-span decoy). *This is the coverage
   the gate-review scores on.*
2. **Accidental drift.** A dropped skill inside a marked pure block → byte-identical **FAIL**; a
   dropped/reordered name inside a marked table region → positional name-column **FAIL**.
3. **Marker integrity (the critical property).** For a representative site: **absent** begin marker →
   FAIL (not skip); **duplicated** begin marker → FAIL; **end before begin** → FAIL.
4. **`skills-order` permutation validation.** Missing a skill / extra entry / duplicate line / unknown
   name → **fail closed** (each).
5. **Correct doc passes.** A fully correct, fully marked synthetic doc → `--check` exit 0 (3 pure blocks
   byte-identical + 2 tables name-ordered + count scalar).
6. **Tree specifics.** Visible-sentinel tree block with a dropped node → FAIL; correct order → pass;
   `└─` only on the last node.
7. **Scalar count.** Wrong count caught in **word and digit** form; correct passes (carried from PR #2).
8. **Idempotence.** write-mode then `--check` is clean (generator output is byte-stable).
9. **Self-inclusion.** Assert `matches_gate('generate-skill-enumerations.py')` and
   `matches_gate('skills-order')` are gate-layer (lock the gate-paths addition against silent regression),
   and update the `gate_review_check` path fixtures accordingly.
10. **Live docs.** Drive the real `README.md` + `per-skill-review-prompt.md` through `--check` → exit 0.

`release-gate.sh` must stay green at every commit. The golden assertion total moves from **72**; the new
section adds the above and removes the old `skill_count_extractors` block — the new total is recorded
when Phase 2 lands.

---

## Phase 3 — gate-review + merge

This PR changes gate-layer paths (`build-skills.sh`, `release-gate.sh`, `tests/`, a new `lint`-class
correctness check, `.github/gate-paths`, CHANGELOG), so per CONTRIBUTING "Governance" it requires:

- **(i)** an independent gate-review run with `gate-review-prompt.md`, recorded under `gate-reviews/`;
- **(ii)** the regression fixture derived from the real incident — **fixture #1 above (the `6f66dfa`
  markup-decoy now FAILS)** — which is the gate-review's real-incident coverage.

The review will be run from a fresh `/tmp` clone or a separate worktree (never a `git checkout` in a
shared working dir — concurrency hazard). Merge only on an evidence-bearing `Verdict: PASS`.
