# Gate-review verdict — PR #12 (feat/skill-count-generate), RENDER-BASED revision

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- Diff range: e4bc544..74d7d22  (round 3 — supersedes gate-reviews/0005, 0006)
- Reviewers / instruments: a same-model (Claude) pass A–E with a cmark-gfm differential oracle, AND a
  different-vendor (GPT) cold pass. BOTH returned BLOCK and CONVERGED again. Author reproduced the
  headline bypasses against the real code at 74d7d22 (outputs below).

## Replay the real failure

The eight prior (0005/0006) bypasses all fail closed on 74d7d22 (verified) — real progress. But the
decoy class is **still open, one layer up at DOM visibility**, and both reviews converged on the root
cause: the design infers "the reader can see this" from `markdown-it` token nesting (`t.level == 0`),
which is NOT DOM nesting. A blank line ends a CommonMark raw-HTML block, so a `<details>` / `<div>` /
`<span>` / `<figure>` wrapper leaves the markers as top-level `level==0` tokens while the browser keeps
the marked content nested (and, for `<details>`, collapsed). Author-reproduced at 74d7d22 (all print
`clean`):

- **blank-line `<details>` + ordered-list decoy (improve-order)** → exit 0 `clean`. The correct list is
  collapsed inside `<details>`; a visible reversed `1.…8.` list (each item one name, no separator)
  evades the competing scan. Claude reproduced the same on all five sites, and confirmed via cmark-gfm
  (GitHub's own engine) that the canonical block renders INSIDE `<details>` and the decoy outside — so
  it is a design defect, not the disclosed parser-parity residual.
- **table header decoy** (GPT CRITICAL 1) → exit 0 `clean`. Only body first-cells are checked; a
  reversed enumeration in the header (or any other cell/column) is unchecked and reader-visible.
- **bolded count phrase** `A suite of **seven** independent` → exit 0 `clean`. `check_count_phrases`
  still runs `\w+` regexes over RAW BYTES; `\w+` cannot cross `**`, so the stale count renders visibly
  while the gate is clean — a render-based gate whose count clause is not render-based.

Additional converged findings (from the reviews, credible): `_competing` false-negatives (a decoy in a
fenced block, an ordered/bullet list, or a tree rooted at `project-doc-skills/`); `_inline_text` ignores
`html_inline`/`image`/tagfilter so a name hidden in `<details>`/`<script data-...>`/image-alt in a table
cell passes; markdown-it vs cmark-gfm table parse differentials (form-feed/VT delimiter, backslash-pipe);
"exactly one table/fence/paragraph" is a blacklist not a positive grammar (ordered-list-wrapped table,
`hr`/`---` sibling, `mermaid` fence info, tokenless link-ref definitions all slip through); and a no-op
**revert battery** shows six of eight load-bearing guards — including the `level==0` test that IS the
pivot — leave the golden suite 103/103 green (CONTRIBUTING requirement ii unmet for them).

Coverage: 0/5 sites for the `6f66dfa` decoy class; 5/5 for `b65041f` accidental drift (sound
drift-catcher, not yet a decoy-closer).

## Coverage vs advertising

"No decoy class" / "a marker wrapped in `<details>`/raw HTML … fails closed" (generate-*.py:15-17;
CHANGELOG; build-skills.sh:110; CONTRIBUTING:164) is falsified. The success banner asserts "the count
phrases hold" while the count check is raw-byte regex. The **disclosed residual is misidentified**: the
hole is DOM nesting, not parser parity — Claude found markdown-it matches cmark-gfm on 16/16 table
constructs, so the parser proxy is adequate; the gap is that neither `level` nor a token check models the
rendered DOM.

## Self-description drift

Stale post-pivot: `.github/gate-paths:37` and `build-skills.sh:106,109` still say "BY GENERATION (no
parse) / byte-identical"; ADR 0001 §3/§5/Residual still describe the byte model and even say a competing
scan is "deliberately not added" while `_competing` ships it.

## Fixture requirement

The `<details>` regression encodes the TIGHT (non-bypassing) form — circular. Six of eight guards survive
a no-op revert with the suite green. Owed: the blank-line raw-HTML nesting attack at all five sites; the
`_competing` false-negatives; the bolded count phrase; a revert-bite assertion per guard.

## Findings

- **BLOCKER** — `_marker_token_span` `t.level == 0` is the wrong signal for reader-visibility; raw-HTML
  containers (blank-line `<details>`/`<div>`/…) nest the marked block in the DOM without moving the token
  level. Reproduced at all five sites, confirmed in cmark-gfm. (Both reviewers; missed by rounds 1–2.)
- **CRITICAL/BLOCKER** — table check validates only body first-cells; header/other cells carry an
  unchecked, reader-visible decoy. (GPT.)
- **MAJOR** — count-phrase check is raw-byte `\w+`, not render-based; `**seven**` bypasses.
- **MAJOR** — `_competing` false-negatives (fence, list, alternate tree root) — relocation not closed.
- **MAJOR** — `_inline_text` ignores html_inline/image/tagfilter; hidden/decoy names in table cells pass.
- **MAJOR** — positive-grammar gaps ("one table/fence/paragraph"): ordered-list-wrapped table, `hr`
  sibling, `mermaid` fence info, tokenless ref-defs.
- **MAJOR** — fixtures don't bite: `<details>` fixture tests the guarded form; 6/8 guards survive revert.
- **MINOR** — stale self-descriptions + ADR §3/§5/Residual contradict the shipped code.

---

Verdict: BLOCK

Three independent review rounds (0005, 0006, 0007) have each closed the previous vectors and found a new
one at the next layer — regex → bytes → token nesting → DOM nesting. The converged lesson: an
adversarial "no reader-visible decoy" claim over arbitrary Markdown+HTML cannot be established by checks
that stop short of the rendered DOM, and cannot be honestly made at all while arbitrary raw HTML/images
are permitted in governed docs. The durable path both reviews describe is: enforce a SAFE SUBSET in
governed docs (reject raw HTML except the marker comments, images, control chars, ref-defs, backslashed
table cells), validate the FULL AST (whole table incl. header/columns, fence info/markup, exact source),
render and check the HTML **DOM** for visibility/ancestry, use cmark-gfm as the oracle, and check the
count phrase against rendered text — then re-state the claim as scoped-and-honest, not absolute. This is
a design decision (and a design-first effort), not a fourth in-place patch.
