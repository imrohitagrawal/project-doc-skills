# Gate-review verdict — PR #12 (feat/skill-count-generate)

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: PR #12 · feat/skill-count-generate (issue #7 "generate-don't-lint")
- Diff range: e4bc544..aedddc3   (head SHA aedddc3)
- Gate-layer paths changed: .github/gate-paths, CONTRIBUTING.md, build-skills.sh,
  generate-skill-enumerations.py, lint-skill-count.py (DELETED), release-gate.sh, skills-order,
  tests/run-golden.py   (light_admissible = False)
- Reviewers / instruments: a same-model (Claude) blind multi-lens pass A–E with code-grounded execution
  (it returned PASS), AND a **different-vendor cold pass (GPT)** given the brief + the load-bearing code
  inlined. The GPT pass raised two BLOCKERs the same-model pass missed. The author then **reproduced
  both BLOCKERs against the real code at aedddc3** (outputs below), which is the decisive evidence in
  this record.
- Independence limit honestly stated: the same-model lenses shared this model's blind spots and returned
  a false PASS — they tested only weaker cases (an EXTRA hidden row; a WELL-FORMED missing marker). The
  different-vendor cold pass is what earned its keep here: it found the malformed-marker-embedding and
  broken-visible/matching-hidden-table vectors. The reproduction runs are the real off-axis instrument.

## Replay the real failure

The gate exists to close the **6f66dfa markup-hidden decoy** class (a correct enumeration hidden in
markup, masking a broken visible one) and **b65041f accidental drift**. Replaying the decoy class
against the NEW gate shows it is **NOT closed** — it is re-opened one layer down, at marker recognition.

**Reproduced at aedddc3 (author, code-grounded):**

1. **Marker embedding (improve-order / pick-list / both tables).** `_marker_span` matches any line that
   *contains* the token substring, so wrapping the markers in a spanning HTML comment hides the canonical
   block while the visible list is broken:
   ```
   <!-- skills:improve-order:begin
   **alpha → beta → … → theta.**              <-- canonical, HIDDEN inside the comment
   skills:improve-order:end -->
   **alpha → beta → BROKEN.**                 <-- visible, BROKEN, never checked
   ```
   `extract_marked_block(...) == render_improve_order(order)` → **True → check PASSES**. Confirmed.
2. **Duplicate-on-one-line.** Two `:begin` tokens on one line are counted as one matching line
   (`len(begins) == 1`), so it passes — the comment `# not exactly one each -> fail closed` is false; it
   counts matching *lines*, not well-formed markers. Confirmed.
3. **Table hidden rows.** `extract_table_names` reads any `|`-leading lowercase line, **including inside
   `<!-- -->`**. Canonical rows hidden in a comment + broken visible rows (backtick-wrapped, so the regex
   skips them) → returns exactly `order` → **check PASSES** over a broken visible table. Confirmed.

Coverage: **0/5 sites end-to-end** (the three pure renderers are sound *given trusted marker positions*
— 3/5 at the renderer layer — but marker selection is part of the security property, and it fails
closed for none of the five). The exact decoy class the PR advertises as closed is reproducible.

## Coverage vs advertising

The banner "clean (all 5 sites generated/checked)" and the CHANGELOG/ADR claim "no decoy class, true and
machine-verifiable" are **over-claims**: a markup-hidden decoy passes the check at every site. This is
the same failure mode as the four prior rounds — a success message asserting more than the code
verifies. (Author's own prior PASS review shared the blind spot and must not stand.)

## Self-description drift

Not the failing axis here. The lint→check rename and gate-paths self-inclusion were consistent
(release-gate.sh, build-skills.sh, .github/gate-paths verified). Superseded by the correctness BLOCKERs.

## Fixture requirement

The shipped `skill_enumerations` fixtures do **not** cover the real decoy class at full strength: they
test an EXTRA hidden row and a WELL-FORMED missing marker, but **not** a malformed marker embedded in
markup, nor a broken-visible/matching-hidden table. Required before any PASS: regression fixtures that
encode the three reproduced attacks above and fail if the fix is reverted.

## Findings

- **BLOCKER** — generate-skill-enumerations.py `_marker_span` (substring `in` matching + line-counting):
  a malformed/embedded marker (spanning HTML comment; or duplicate token on one line) selects a hidden
  canonical block while the visible enumeration is broken — the check PASSES. Reproduced. Affects
  improve-order, pick-list, and both tables. Fix: exact self-closing marker-line grammar + exactly-one
  token occurrence in the whole file. Raised by GPT; confirmed by the author.
- **BLOCKER** — generate-skill-enumerations.py `extract_table_names`: reads any `|`-leading lowercase
  line including inside `<!-- -->`, so hidden comment rows satisfy the name-column check over a broken
  visible table. Reproduced. Fix: strip comments, require exactly `len(order)` real rows with the full
  first cell equal to the name. Raised by GPT; confirmed by the author.
- **MAJOR** — a correct marked block anywhere in the file passes even if a broken UN-marked enumeration
  sits at the reader-facing location (relocation to an appendix / alt-fence / `<details>`). The block is
  not anchored to its expected section. Fix: bind each site to its expected anchor/section. Raised by GPT.
- **MINOR** — the scalar count-phrase check remains a raw-markup regex; "no decoy class" is too broad
  while any raw-markup validator remains. Narrow the claim or make the scalar check location-aware.
- **NIT** — success banner says "5 sites generated"; only 3 are generated, 2 are name-checked.

---

Verdict: BLOCK

The "no decoy class" property does not hold. Highest-risk defect: substring-based, line-counted marker
recognition lets a malformed hidden marker pair select a canonical decoy and pass all five sites. Fix
the two BLOCKERs and the relocation MAJOR, land regression fixtures for the three reproduced attacks,
and re-run both a fresh same-model review and a different-vendor cold pass before PASS.
