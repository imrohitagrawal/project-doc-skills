# Gate-review verdict — PR #12 (feat/skill-count-generate), HARDENED revision

- Prompt: gate-review-prompt.md v1.0.0
- Tier: full
- PR / branch: PR #12 · feat/skill-count-generate (issue #7)
- Diff range: e4bc544..60dcc8d   (head SHA 60dcc8d; supersedes gate-reviews/0005, which BLOCKed aedddc3)
- Reviewers / instruments: a same-model (Claude) blind multi-lens pass A–E AND a different-vendor (GPT)
  cold pass, EACH run independently against 60dcc8d. **Both returned BLOCK and converged on the same root
  cause.** The author then reproduced the load-bearing bypasses against the real code (outputs below).
- Independence limit: the two AI passes plus the author's own reproduction are the instruments; the
  reproduction commands are the decisive evidence.

## Replay the real failure

The three 0005 attacks + relocation are **genuinely closed** on 60dcc8d (verified; also locked in
`tests/run-golden.py` `skill_enumerations`, 113/113). But the DECOY CLASS the gate advertises closing is
**not** closed. Both reviewers, independently, found the checker validates the BYTE STREAM and never the
RENDERED Markdown, and every remaining bypass lives in that gap. Reproduced by the author against
`generate-skill-enumerations.py --check` on scratch copies of the REAL docs:

- **Rendering-context wrapper (all 5 sites)** — wrap the correct marked block in `<details>` (or a
  fenced code block) and put a broken un-marked list below → **exit 0, "clean"**. The canonical list
  renders hidden/as-literal; the reader sees the broken list. This is the 6f66dfa incident re-opened one
  layer up from 0005.
- **Code-span comment asymmetry (both tables)** — a row containing `` `<!--` `` … a visible decoy row …
  `` `-->` `` → `re.sub` strips it as a comment though the renderer shows it → **exit 0, "clean"** while
  a `NOT-A-SKILL` row is reader-facing. 0005 ATTACK 3 inverted.
- **Fail-open on empty source of truth** — `rm -rf skills/ && --check` → **exit 0, "clean (3 sites
  generated … + the count phrases hold)"** — every clause false, nothing checked (`if not canonical:
  return []`). The retired lint printed a truthful "no skills found" instead.
- **Anchor uniqueness bug** — `_marker_span` counts LINES containing the anchor, not occurrences, so two
  anchors on one line pass the "exactly once" guard.

Coverage: against the three specific 0005 attacks, 5/5 fail closed. Against the **decoy class the gate
advertises**, **0/5 sites** are genuinely decoy-closed.

## Coverage vs advertising

`generate-skill-enumerations.py:24` claims the three properties "close the decoy class the old parser
could not." Verified false: the properties constrain WHERE the marked block sits in the byte stream,
never HOW it renders. The `main()` success banner asserts five checks ran even when `skills/` is empty
and none did. "No decoy class" (ADR/CHANGELOG) does not hold.

## Self-description drift

Clean (both reviewers): gate-paths self-inclusion correct and golden-locked; release-gate derives its
step count; anchors grep unique; no stale lint-skill-count references beyond retirement prose. One NIT:
the ILLUSTRATIVE gate-path prose in CONTRIBUTING/gate-review-prompt still says "every lint-*.py" and does
not name the generator/skills-order (the machine list is correct and labelled authoritative).

## Fixture requirement

The four 0005 regressions are present, incident-derived, and bite on a substring-match revert (verified).
Owed: fixtures for the rendering-context wrapper, the code-span comment asymmetry, and the empty-source
fail-open (a one-line `check(root_with_no_skills) != []`).

## Findings

- **BLOCKER — no rendering-context validation** (`generate-skill-enumerations.py` `_marker_span`, spec
  `:24-34`). A marked block wrapped in `<details>` / a fenced block / hidden HTML passes byte-identical
  and anchored while rendering invisibly. Reproduced on all 5 sites. The byte-stream marker model cannot
  see this. (Raised by both reviewers; Claude via Lens E, GPT as BLOCKER 1.)
- **BLOCKER — `re.sub` comment-strip ≠ renderer** (`extract_table_names`). Code-span/escaped comment
  delimiters make the stripper delete reader-visible rows. Reproduced on both tables. (Both reviewers.)
- **MAJOR — fail-open + false success string on empty `skills/`** (`check()` `if not canonical: return
  []`; `main()` banner). Reproduced; reachable via the documented standalone command (the composed build
  fails first). Fix: return a finding, and derive the banner from what ran.
- **MAJOR — anchor "exactly once" counts lines, not occurrences**; the free-text anchor is not bound to
  a heading/AST, so adversarial relocation (move anchor+block together) is not prevented. (GPT MAJOR 4.)
- **MAJOR — table row parsing diverges from Markdown**: `strip("|")` eats doubled leading pipes; blank
  lines / indented code / multiple table-like blocks are accepted; the first-cell regex accepts
  asymmetric `**alpha*` / `` `alpha ``. (GPT MAJOR 3 + MINOR; Claude MINOR 1.)

## Root cause and recommendation

Every bypass is the gap between what Python reads and what a renderer shows. Adding more byte-stream
properties keeps approximating a renderer and losing. The durable fix is one of: (a) check against
RENDERED output (parse with the production Markdown engine; locate the site by heading/AST; assert the
rendered enumeration) — but that adds a third-party dependency the suite currently forbids; (b) enforce
strict CONTAINMENT in stdlib (track fence parity from the top of file; reject any enclosing
fence/HTML-block/`<details>`/comment around the marked region; reject any competing rendered-enumeration
shape anywhere outside the marked block; poison-don't-strip any `<!--` in a table block; fix the
anchor-count and pipe parsing) AND disclose the residual honestly; or (c) re-scope the claim to
"accidental drift + known decoy vectors" (as PR #2 did) rather than "no decoy class". This is a design
decision for the owner, not another in-PR patch.

---

Verdict: BLOCK

The hardening genuinely closed the three 0005 bypasses and relocation — that work is sound and its
fixtures are real. It did NOT close the decoy class it claims to close: two rendering-context vectors
defeat all five sites, plus a fail-open and several table-parse divergences. Resolve by choosing a
direction (render-based check / strict containment + honest residual / honest re-scope), implement, add
the owed fixtures, and re-review before PASS.
