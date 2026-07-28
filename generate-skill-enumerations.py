#!/usr/bin/env python3
"""
generate-skill-enumerations.py — keep the five skill enumerations consistent with skills-order.

The suite enumerates its skills in five places (README skill table, README repo tree, README
improve-order list; per-skill-review-prompt {SKILL_NAME} pick-list and attachment table). This gate
GENERATES each enumeration from one source of truth (skills-order) and verifies it against the PARSED
Markdown token stream (markdown-it-py, CommonMark + GFM tables), so accidental drift and casual markup
mistakes are caught at the location a reader actually reads.

WHAT THIS GATE GUARANTEES (its real job):
  - **Accidental drift is caught, 5/5 sites.** Add/reorder/drop a skill without updating a marked block
    and the check fails: pure sites (improve-order, pick-list, tree) must match the generated run
    byte-for-byte in the parse tree; tables must have body rows whose first-cell RENDERED TEXT is the
    skills in order. `skills-order` is validated as an exact permutation of `skills/`; an empty/missing
    source fails closed (never a false "clean").
  - **Each site is pinned to its lead-in, uniquely.** The markers are HTML comments that travel WITH the
    block, so identity alone cannot bind a block to a location — a correct block relocated to an appendix
    (its site now empty) would still be "found". Every site is anchored to a stable phrase in the paragraph
    that introduces it, counted over the JOINED reader-visible text of ALL units — every paragraph, cell
    AND fenced/indented code block — so it must occur EXACTLY ONCE (see _anchor_missing /
    _anchor_occurrences): moving a block away from its lead-in, cloning the lead-in phrase (even inside a
    fence, or split across a paragraph break) next to a relocated block, trips the anchor. LIMIT: the gate
    pins the block to WHERE ITS ANCHOR IS, so removing the lead-in from the old site ENTIRELY and giving
    the block a fresh unique lead-in elsewhere is treated as legitimate reorganization (the block and its
    lead-in moved together); a below-threshold partial list left at the abandoned site is then the
    disclosed competing residual (below all-but-one), not a caught decoy.
  - **Casual decoys are caught.** A hidden-comment row, a code-span comment delimiter, a spanning-comment
    marker, or a competing enumeration is caught by the parse-tree checks and the competing scan
    (_competing_findings). A *competing enumeration* is a near-complete run of the skill names (>=
    all-but-one) matched at name boundaries, detected in ANY rendered unit OUTSIDE all five marked blocks —
    NO separator required — and AGGREGATED across structure so it cannot hide by distribution: a
    comma-separated paragraph, a separator-free fence, a bullet/ordered list (one name per item, even split
    across two lists or one fenced name per item), a second table with the run down any column, and a
    marked table with the run scattered across the header or diagonally across non-first columns. Every
    legitimate enumeration lives inside a marked block (excluded); an incidental one/two-name
    cross-reference ("reviewed by doc-critic") is legitimate prose and is deliberately NOT flagged.
  - **Count phrases are anchor-bound, exactly once.** Each scalar count ("a suite of <N> ... skills",
    "build all <N> + emit dist/MANIFEST.sha256", …) is a CLOSED combined pattern that binds the count slot
    to a distinctive ADJACENT anchor, and must match EXACTLY ONCE across the rendered units, value-exact
    (see check_count_phrases). So rewording the site's sentence drops the match to zero (a finding) — it
    cannot be masked by a bare count fragment placed elsewhere in the same unit — and an unrelated sentence
    sharing the fragment, not next to the anchor, is neither required nor flagged (no false positive).
  - **Raw HTML is banned document-wide in the governed docs** (README.md, per-skill-review-prompt.md): a
    non-comment raw-HTML block (`<details>`, `<div>`, `<ol>`, …) anywhere, or any inline HTML / image
    token anywhere, is rejected — raw HTML is the enabler for a reader-visible decoy that renders
    differently than it reads. Only HTML comments (the markers) are allowed.

WHAT IT DOES NOT GUARANTEE (honest scope — see CONTRIBUTING "Skill-enumeration gate: scope"):
  This is a drift-catcher and casual-decoy guard, NOT a proof of "no reader-visible decoy" against a
  determined adversary. Three gate-reviews (`gate-reviews/0005`-`0007`) showed that fully closing an
  adversarial reader-visible decoy over arbitrary Markdown would require rendering to HTML and verifying
  the DOM (visibility, ancestry) against GitHub's own engine (cmark-gfm) — deliberately out of scope for
  this internal tooling. The raw-HTML ban removes the main adversarial surface cheaply; residuals
  (markdown-it-py vs cmark-gfm parse edge cases; a competing run split across SEPARATE top-level containers
  — e.g. four names in a paragraph and four in a list — so that no single container is near-complete, which
  cannot be aggregated further without false-positiving on the ordinary prose that legitimately names
  several skills; anything the ban does not cover) are the disclosed, accepted limit, tracked for a future
  render-DOM pass if the threat model ever warrants it. (Both governed files are now scanned in full, so a
  competing run in either file is caught — the former cross-file gap is closed.)

Source of truth: SET = skills/<name>/ with a SKILL.md; ORDER = the root `skills-order` file, validated
as an exact permutation of the set (fail closed).

Usage:
    python3 generate-skill-enumerations.py [root]            # WRITE: fill the three pure blocks in place
    python3 generate-skill-enumerations.py [root] --check    # CHECK: assert all five sites + the count
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

try:
    from markdown_it import MarkdownIt
except ImportError:  # fail closed: the gate cannot verify anything without the parser
    MarkdownIt = None

NUM_WORDS = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight",
    9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen",
    16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty",
}
WORD_TO_NUM = {word: n for n, word in NUM_WORDS.items()}

# The count slot matches ONLY a number token — a digit run, a number word, or a hyphenated compound
# ("twenty-one"). It is deliberately NOT "any word": an open slot captured ordinary prose ("now review
# skills" → "review") and reported it as a wrong count, and it also swallowed surrounding text
# ("ONE skill in an eight"). Anything that is not a number makes the phrase not match at all, which trips
# the PRESENCE half below — reported as "reworded / stale", which is what it actually is.
_NUM_ALT = "|".join(sorted(NUM_WORDS.values(), key=len, reverse=True))
# ASCII digits only ([0-9], not \d): the canonical phrases use ASCII, and \d would also match a fullwidth
# "８" a reader reads as 8, reporting a spurious "reads ８ but there are 8 skills" (gate-reviews/0015).
_COUNT = rf"(?P<count>[0-9]{{1,3}}|(?:{_NUM_ALT})(?:-(?:{_NUM_ALT}))?)"
# Whole-template boundaries. `\b` is not enough: it let "rebuild all eight" satisfy "build all <N>",
# "know eight skills" satisfy "now <N> skills", and suffixed rewordings ("skillsets", "independently",
# "stylesheet", "suites") pass while the canonical phrase was gone.
_L = r"(?<![A-Za-z0-9_-])"
_R = r"(?![A-Za-z0-9_-])"

# Count phrases are checked with a CLOSED COMBINED pattern that binds the count slot to a distinctive
# adjacent anchor phrase, matched over the rendered visible units; each canonical count must occur EXACTLY
# ONCE across the document, read the canonical value (gate-reviews/0015). Each is (combined_pattern, label).
#
# Why combined-and-exactly-one, not "locate the anchor unit then scan it for a bare template" (the round-11
# design, which was maskable): the older form ran the bare template over the WHOLE anchored paragraph/fence,
# so rewording the real sentence and dropping the correct template ANYWHERE ELSE IN THE SAME UNIT still
# passed, and an unrelated wrong count in that unit falsely fired. Binding the count to its adjacent anchor
# (`build-skills.sh # build all <N> …`, `suite of <N> independent Claude skills … software project into
# documentation`) within a small bounded gap means:
#   - MASKING is closed: a decoy count not sitting next to its anchor does not match, so rewording the real
#     sentence drops the match to zero -> a finding; you cannot satisfy it with a fragment placed elsewhere.
#   - FALSE POSITIVES are closed: an unrelated sentence that merely shares the count fragment is not next to
#     the anchor, so it neither satisfies nor trips the check.
#   - RELOCATION/DUPLICATION is caught: two matches (a real one plus a restated canonical sentence) trip the
#     exactly-one rule. `.{0,N}?` is a bounded, non-greedy gap over the collapsed single-line unit text.
# `_COUNT` is number-only so the captured slot is a number (value-exact reports a wrong count precisely);
# the anchor+gap binding is what makes the location guarantee, not the slot.
# `.{0,N}?` is a bounded non-greedy gap between the count and its adjacent anchor. `{_R}` guards every
# literal that abuts the gap (or ends the pattern) so the gap cannot absorb a SUFFIX — e.g. "skillsets"
# must not satisfy "skills" (gate-reviews/0015). `{_L}`/`{_R}` also bound the count-template so a prefix
# ("resuite") / suffix likewise cannot sneak in.
README_COUNT_PHRASES = [
    (re.compile(rf"{_L}suite of {_COUNT} independent Claude skills{_R}"
                rf".{{0,60}}?software project into documentation{_R}", re.IGNORECASE),
     "a suite of <N> independent Claude skills … software project into documentation"),
    (re.compile(rf"self-contained packages{_R}.{{0,60}}?{_L}{_COUNT} copies of the house style{_R}",
                re.IGNORECASE),
     "self-contained packages … <N> copies of the house style"),
    (re.compile(rf"{_L}build-skills\.sh{_R}.{{0,60}}?build all {_COUNT} \+ emit dist/MANIFEST\.sha256{_R}",
                re.IGNORECASE),
     "./build-skills.sh # build all <N> + emit dist/MANIFEST.sha256"),
]
PROMPT_COUNT_PHRASES = [
    (re.compile(rf"You are improving ONE skill in an {_COUNT}-skill documentation suite{_R}", re.IGNORECASE),
     "You are improving ONE skill in an <N>-skill documentation suite"),
    (re.compile(rf"What changed in the suite{_R}.{{0,60}}?The suite is now {_COUNT} skills{_R}",
                re.IGNORECASE),
     "What changed in the suite … The suite is now <N> skills"),
]

README = "README.md"
PROMPT = "per-skill-review-prompt.md"


class MarkerError(Exception):
    """Raised when a site's markers are absent, embedded (not a standalone top-level token), duplicated,
    or out of order — always fail closed."""


def _md() -> "MarkdownIt":
    if MarkdownIt is None:
        raise MarkerError("markdown-it-py is not installed — the enumeration gate cannot run "
                          "(pip install markdown-it-py)")
    return MarkdownIt("commonmark").enable("table")


def canonical_skills(root: Path) -> set[str]:
    """The source of truth for the SET: every skills/<name>/ that holds a SKILL.md."""
    sk = root / "skills"
    if not sk.is_dir():
        return set()
    return {p.name for p in sk.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()}


def validate_order(order: list[str], canonical: set[str]) -> list[str]:
    """Validate `order` is an EXACT permutation of `canonical`. Returns error strings (empty = valid)."""
    errs: list[str] = []
    dups = sorted({x for x in order if order.count(x) > 1})
    if dups:
        errs.append(f"skills-order has duplicate line(s): {', '.join(dups)}")
    missing = sorted(canonical - set(order))
    if missing:
        errs.append(f"skills-order is missing skill(s) present in skills/: {', '.join(missing)}")
    extra = sorted(set(order) - canonical)
    if extra:
        errs.append(f"skills-order names unknown skill(s) not in skills/: {', '.join(extra)}")
    return errs


def load_order(root: Path, canonical: set[str]) -> tuple[list[str], list[str]]:
    """Read `skills-order` (skip blank lines and # comments) and validate it. Returns (order, errors).
    A missing file is a fail-closed finding — accumulated in `errs` (not a bare list literal) so this
    finding-producing function is visible to the revert battery's AST inventory (gate-reviews/0015)."""
    errs: list[str] = []
    p = root / "skills-order"
    if not p.is_file():
        errs.append(f"skills-order not found at {p}")
        return [], errs
    order = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.strip().startswith("#")]
    return order, validate_order(order, canonical)


# ---- renderers: the EXACT source bytes the three pure sites must contain -------------------------

def render_improve_order(order: list[str]) -> str:
    """README improve-order list: a top-level paragraph, bold-wrapped, ` → `-joined, trailing period."""
    return "**" + " → ".join(order) + ".**"


def render_pick_list(order: list[str]) -> str:
    """per-skill-prompt {SKILL_NAME} pick-list: a single backtick code span, ` · `-joined."""
    return "`" + " · ".join(order) + "`"


def _tree_body(order: list[str]) -> str:
    nodes = [("└─" if i == len(order) - 1 else "├─") + f" {n}/" for i, n in enumerate(order)]
    return "skills/\n" + "\n".join(nodes)


def render_tree(order: list[str]) -> str:
    """README repo-tree skills/ block: its OWN fenced code block (so its markers are standalone HTML
    comments), the body being skills/ + one node per skill (└─ on the last)."""
    return "```\n" + _tree_body(order) + "\n```"


def _canon_markers(site_id: str) -> tuple[str, str]:
    return f"<!-- skills:{site_id}:begin -->", f"<!-- skills:{site_id}:end -->"


# ---- token helpers (the check operates on parsed tokens, not bytes) ------------------------------

def _inline_text(tok) -> str:
    """The rendered plain text of an `inline` token: its text + code-span children concatenated (so a
    bold/code-wrapped name yields the bare name, and malformed/relocated markup yields something else)."""
    out = []
    for c in (tok.children or []):
        if c.type in ("text", "code_inline"):
            out.append(c.content)
        elif c.type in ("softbreak", "hardbreak"):
            out.append(" ")
    return "".join(out)


def _visible_units(tokens) -> list[str]:
    """Each reader-visible rendered unit's text SEPARATELY — one entry per inline token (a paragraph,
    heading, blockquote line, or table cell, emphasis/code unwrapped, soft/hard breaks → space) and one
    per fenced/indented code block, each whitespace-collapsed. HTML comments (the markers) are invisible
    and excluded. The count-phrase check scans the combined patterns across ALL units and requires EXACTLY
    ONE match document-wide — a count is bound to its adjacent anchor by the pattern, not by which unit it
    sits in, so a bare count fragment elsewhere neither satisfies nor trips the check, while a second FULL
    canonical restatement (count + anchor) IS flagged (the canonical count is stated once, deliberately).
    A count that is bold, in a code span, or split by a line wrap / backslash hard-break is still checked
    as the reader sees it (the rendering is per unit, unchanged)."""
    units = []
    for t in tokens:
        if t.type == "inline":
            units.append(re.sub(r"\s+", " ", _inline_text(t)).strip())
        elif t.type in ("fence", "code_block"):
            units.append(re.sub(r"\s+", " ", t.content).strip())
    return units


def _marker_token_span(tokens, site_id: str) -> tuple[int, int]:
    """Indices of the site's begin/end markers as STANDALONE top-level html_block tokens. Fail closed if
    a marker is absent, duplicated, embedded in a wrapper (a code fence / <details> / raw-HTML block
    swallows it, so it is not a standalone token), or out of order."""
    begin_m, end_m = _canon_markers(site_id)
    begins = [i for i, t in enumerate(tokens)
              if t.type == "html_block" and t.level == 0 and t.content.strip() == begin_m]
    ends = [i for i, t in enumerate(tokens)
            if t.type == "html_block" and t.level == 0 and t.content.strip() == end_m]
    if len(begins) != 1 or len(ends) != 1:
        raise MarkerError(f"site '{site_id}': need exactly one standalone begin and end marker in the "
                          f"rendered token stream (found begin×{len(begins)}, end×{len(ends)}) — a marker "
                          f"wrapped in a fence, <details>, or raw HTML is not standalone and is rejected")
    if ends[0] <= begins[0]:
        raise MarkerError(f"site '{site_id}': end marker is not after the begin marker")
    return begins[0], ends[0]


def _preceding_visible(tokens, begin_idx: int) -> str:
    """Collapsed visible text of the paragraph/heading block IMMEDIATELY before the begin marker at
    `begin_idx` — the marked block's lead-in — or '' when the marker is not directly preceded by one
    (another html_block, a fence, a table/list close, an hr, or the top of the document)."""
    if begin_idx >= 2 and tokens[begin_idx - 1].type in ("paragraph_close", "heading_close") \
            and tokens[begin_idx - 2].type == "inline":
        return re.sub(r"\s+", " ", _inline_text(tokens[begin_idx - 2])).strip()
    return ""


def _anchor_occurrences(tokens, anchor: str) -> int:
    """How many TEXTUAL occurrences of `anchor` there are in the doc's reader-visible text — the
    concatenation of ALL rendered units (paragraphs, headings, cells, AND fenced/indented code blocks;
    see _visible_units), joined so a phrase is counted even if a paragraph break SPLITS it. Used to require
    the anchor be UNIQUE (_anchor_missing).

    Both properties are load-bearing (gate-reviews/0015): counting fences (not just inline tokens) closes a
    relocation that hid the abandoned-site lead-in in a code block; counting over the JOINED text — not
    per-unit — closes a relocation that SPLIT the abandoned-site lead-in across a paragraph break (which a
    per-unit count would miss) while a clean copy beside the relocated block became the sole counted one."""
    return " ".join(_visible_units(tokens)).count(anchor)


def _anchor_missing(tokens, begin_idx: int, site_id: str) -> bool:
    """True if the site's begin marker is NOT immediately preceded by its UNIQUE lead-in context (the
    ANCHOR). The marker comments travel WITH the block, so identity alone cannot pin a block to a place:
    relocating a correct block to another section (an appendix, a fold) leaves the real site empty while
    the check still finds the markers and passes.

    Two conditions, both required (gate-reviews/0014): the anchor must occur EXACTLY ONCE in the document,
    AND the begin marker must immediately follow that occurrence. Uniqueness is what defeats CLONING the
    anchor — dropping a second copy of the lead-in phrase next to a relocated block would otherwise satisfy
    a mere adjacency test while the real site sits empty. Moving the SOLE lead-in and its block together
    still passes (one occurrence, marker still follows it): that is legitimate reorganization, not drift.
    Fail closed if the site has no anchor registered, or the anchor is absent / duplicated."""
    anchor = ANCHORS.get(site_id)
    if not anchor:
        return True
    if _anchor_occurrences(tokens, anchor) != 1:
        return True
    return anchor not in _preceding_visible(tokens, begin_idx)


def _pure_source(tokens, b: int, e: int) -> str | None:
    """The source of the single top-level paragraph between the markers, or None if the marked content
    is not exactly one paragraph."""
    inner = tokens[b + 1:e]
    if len(inner) == 3 and inner[0].type == "paragraph_open" and inner[1].type == "inline" \
            and inner[2].type == "paragraph_close":
        return inner[1].content
    return None


def _fence_body(tokens, b: int, e: int) -> str | None:
    """The body of the single fenced code block between the markers, or None if it is not exactly one."""
    inner = tokens[b + 1:e]
    if len(inner) == 1 and inner[0].type == "fence" and inner[0].level == 0 \
            and inner[0].info.strip() == "" and inner[0].markup == "```":
        return inner[0].content.rstrip("\n")
    return None


def _table_names(tokens, b: int, e: int) -> list[str] | None:
    """First-cell rendered text of each body row of the SINGLE table between the markers (in order), or
    None if the marked content is not exactly one table (any smuggled paragraph/fence/html/heading, or a
    second table, returns None -> a finding)."""
    inner = tokens[b + 1:e]
    if sum(1 for t in inner if t.type == "table_open") != 1:
        return None
    # POSITIVE grammar, single guard: the region must BEGIN with the table and END with it, at top level.
    # Anything smuggled before or after the table (a paragraph, fence, list, hr, raw HTML …) moves the
    # first or last token and is rejected here. A blacklist of forbidden token types used to sit
    # alongside this and made it redundant — so neither branch could be proven by a revert, which is
    # exactly how an unproven load-bearing guard hides (gate-review round 8). One guard, one proof.
    # (Link-reference definitions produce no token at all; they are invisible, not a reader-facing decoy.)
    if inner[0].type != "table_open" or inner[-1].type != "table_close" or inner[0].level != 0:
        return None
    names: list[str] = []
    in_tbody = False
    i = 0
    while i < len(inner):
        t = inner[i]
        if t.type == "tbody_open":
            in_tbody = True
        elif t.type == "tbody_close":
            in_tbody = False
        elif t.type == "tr_open" and in_tbody:
            j = i + 1
            cell = None
            while j < len(inner) and inner[j].type != "tr_close":
                if inner[j].type == "inline":
                    cell = inner[j]
                    break
                j += 1
            names.append(_inline_text(cell) if cell is not None else "")
        i += 1
    return names


# site_id, filename, renderer — the three fully-generated pure sites; kind for the competing scan
PURE_SITES = [
    ("improve-order", README, render_improve_order, "arrow"),
    ("pick-list", PROMPT, render_pick_list, "dot"),
    ("tree", README, None, "tree"),
]
TABLE_SITES = [("table", README), ("attach-table", PROMPT)]
COUNT_PHRASES = {README: README_COUNT_PHRASES, PROMPT: PROMPT_COUNT_PHRASES}

# Each site is PINNED to a stable phrase in the lead-in block that introduces it (see _anchor_missing).
# A relocated block (markers and all) lands after a different lead-in, so its anchor no longer precedes
# it and the move is caught. The anchors are the semantic "here is the block" clause of each lead-in,
# chosen to survive incidental copyediting; editing a lead-in away is a deliberate act that updates the
# anchor here too. Every site_id in PURE_SITES + TABLE_SITES must appear (fail closed otherwise).
ANCHORS = {
    "improve-order": "in this order (producers before consumers)",
    "tree": "generated from skills-order",
    "table": "without re-authoring them",
    "pick-list": "with exactly one of these",
    "attach-table": "no separate attachment is needed",
}

def _competing_run(text: str, order: list[str]) -> bool:
    """True if `text` holds a NEAR-COMPLETE run of DISTINCT skill names — at least len(order)-1 of them
    (minimum 2) — each matched at name boundaries (so 'project-faq' does not count 'project-faq-notes').

    The bar is 'near-complete run', not 'two names', deliberately (gate-reviews/0013). A competing
    ENUMERATION is a second copy of the ordering; an ordinary one- or two-name cross-reference
    ('architecture-and-decisions → project-faq is the normal handoff', 'reviewed by doc-critic') is
    legitimate prose and must not be read as one. The old '>= 2 substring' bar flagged both of those."""
    threshold = max(2, len(order) - 1)
    hits = sum(1 for nm in order if re.search(_L + re.escape(nm) + _R, text))
    return hits >= threshold


def _list_close(tokens, start: int) -> int:
    """Index of the matching close for the bullet/ordered list opening at `start` (handles nesting)."""
    depth = 0
    for j in range(start, len(tokens)):
        if tokens[j].type in ("bullet_list_open", "ordered_list_open"):
            depth += 1
        elif tokens[j].type in ("bullet_list_close", "ordered_list_close"):
            depth -= 1
            if depth == 0:
                return j
    return len(tokens) - 1


def _in_any_span(idx: int, spans: list[tuple[int, int]]) -> bool:
    return any(b <= idx <= e for b, e in spans)


def _run_hits(text: str, order: list[str]) -> int:
    return sum(1 for nm in order if re.search(_L + re.escape(nm) + _R, text))


def _table_span_close(tokens, start: int) -> int:
    """Index of the matching table_close for the table_open at `start` (GFM tables do not nest)."""
    for j in range(start, len(tokens)):
        if tokens[j].type == "table_close":
            return j
    return len(tokens) - 1


def _competing_findings(tokens, spans: list[tuple[int, int]], order: list[str], fname: str) -> list[str]:
    """Findings for any competing enumeration rendered OUTSIDE all marked blocks in this file. A competing
    enumeration is a NEAR-COMPLETE run of the skill names (see _competing_run); it is detected wherever it
    renders and however it is distributed within a single structure — NO separator is required
    (gate-reviews/0015; the old per-site scan only looked when the site's `→`/`·` separator was present,
    so a comma-separated paragraph or a separator-free fence escaped):
      (1) any inline unit (paragraph/heading/cell) or fenced/indented code block;
      (2) each bullet/ordered LIST container, aggregated over ITS OWN items (a run written one name per
          item — even one fenced name per item — is caught within that list);
      (3) every OUTSIDE table, all its cells aggregated — a second table with the run down any column.
    The legitimate enumerations all live inside `spans` (excluded). Aggregation is PER container, not
    across the whole document, so ordinary prose that legitimately names several skills across separate
    lists/paragraphs is not false-positived; the price is that a run deliberately SPLIT across separate
    containers so no one container is near-complete is a disclosed residual (see the module docstring)."""
    out: list[str] = []
    # (1) single units outside every marked span.
    for i, t in enumerate(tokens):
        if _in_any_span(i, spans):
            continue
        txt = _inline_text(t) if t.type == "inline" else (
            t.content if t.type in ("fence", "code_block") else "")
        if txt and _competing_run(txt, order):
            out.append(f"{fname}: a competing enumeration ({_run_hits(txt, order)} of {len(order)} skill "
                       f"names) renders in a unit outside every marked block — there must be exactly one "
                       f"enumeration per site")
            return out
    # (2) each list container outside the marked spans, aggregated over its own items.
    i = 0
    while i < len(tokens):
        if tokens[i].type in ("bullet_list_open", "ordered_list_open"):
            j = _list_close(tokens, i)
            if not _in_any_span(i, spans) and not _in_any_span(j, spans):
                agg = " ".join((_inline_text(x) if x.type == "inline" else x.content)
                               for x in tokens[i:j + 1] if x.type in ("inline", "fence", "code_block"))
                if _competing_run(agg, order):
                    out.append(f"{fname}: a competing enumeration ({_run_hits(agg, order)} of {len(order)} "
                               f"skill names) is distributed across a list outside the marked blocks — "
                               f"there must be exactly one enumeration per site")
                    return out
            i = j + 1
        else:
            i += 1
    # (3) every table outside the marked spans, all cells aggregated.
    i = 0
    while i < len(tokens):
        if tokens[i].type == "table_open":
            j = _table_span_close(tokens, i)
            if not _in_any_span(i, spans) and not _in_any_span(j, spans):
                header, rows = _table_cells(tokens[i:j + 1])
                allcells = " ".join(header + [c for r in rows for c in r])
                if _competing_run(allcells, order):
                    out.append(f"{fname}: a competing skill table renders outside the marked blocks (its "
                               f"cells hold a near-complete enumeration) — there must be exactly one")
                    return out
            i = j + 1
        else:
            i += 1
    return out


def _table_cells(inner) -> tuple[list[str], list[list[str]]]:
    """Reconstruct a table's cells from its token span: (header_cells, body_rows) where body_rows is a
    list of rows, each a list of cell rendered-texts by column. Cells are the inline tokens inside each
    tr, in column order."""
    header: list[str] = []
    rows: list[list[str]] = []
    section = None          # "thead" | "tbody" | None
    cur: list[str] | None = None
    for t in inner:
        if t.type == "thead_open":
            section = "thead"
        elif t.type == "thead_close":
            section = None
        elif t.type == "tbody_open":
            section = "tbody"
        elif t.type == "tbody_close":
            section = None
        elif t.type == "tr_open":
            cur = []
        elif t.type == "tr_close":
            if section == "thead":
                header.extend(cur or [])
            elif section == "tbody":
                rows.append(cur or [])
            cur = None
        elif t.type == "inline" and cur is not None:
            cur.append(_inline_text(t))
    return header, rows


def _table_stray_names(tokens, b: int, e: int, order: list[str]) -> bool:
    """True if a NEAR-COMPLETE run of skill names (a reversed/competing enumeration) hides in the marked
    table OUTSIDE its first body column. ALL header cells and ALL non-first body cells are aggregated into
    ONE blob and tested with _competing_run, so no DISTRIBUTION escapes — a run written across the header,
    down any single column, or scattered DIAGONALLY across different columns/rows (each cell below the
    threshold) is caught alike (gate-reviews/0015). The first body column is excluded: _table_names
    verifies it equals the order exactly. A singleton cross-reference (one skill named in a description
    cell) stays below the near-complete threshold and is allowed."""
    header, rows = _table_cells(tokens[b + 1:e])
    blob = " ".join(header + [c for r in rows for c in r[1:]])
    return _competing_run(blob, order)


def _allowed_marker_comments() -> set[str]:
    """The ONLY raw HTML permitted in a governed doc: this suite's exact begin/end marker comments."""
    out: set[str] = set()
    for site_id in [s[0] for s in PURE_SITES] + [s[0] for s in TABLE_SITES]:
        out.update(_canon_markers(site_id))
    return out


def _marker_only_html_block(content: str) -> bool:
    """True iff the html_block is nothing but this suite's EXACT marker comments and whitespace.

    Deliberately an identity allowlist, not "any complete HTML comment": the claim is "the comment
    MARKERS are the sole exception", and a comment-syntax allowlist would make that claim false (an
    arbitrary comment would pass) — gate-reviews/0010. A block whose comment is followed by a real tag
    (`<!-- ok --><div>`) is likewise rejected, since the remainder is not an allowed marker."""
    allowed = _allowed_marker_comments()
    rest = content.strip()
    if not rest or not allowed:
        return False        # "one or more exact markers", literally: empty is not an allowed block
    while rest:
        if not rest.startswith("<!--"):
            return False
        end = rest.find("-->", 4)
        if end < 0:
            return False
        if rest[:end + 3] not in allowed:
            return False
        rest = rest[end + 3:].strip()
    return True


def _stray_html_block(tokens) -> str | None:
    """The first RAW-HTML BLOCK token that is not one of this suite's exact marker comments. Governed docs
    ban raw HTML (`<details>`, `<div>`, `<ol>`, …) because it is the enabler for reader-visible decoys a
    token check cannot see (a `<details>` fold nests the marked block in the DOM without moving the token
    level). The markers are HTML comments — invisible, and they cannot nest following content."""
    for t in tokens:
        if t.type == "html_block" and not _marker_only_html_block(t.content or ""):
            s = (t.content or "").strip()
            return s.splitlines()[0][:50] if s else "(empty)"
    return None


def _doc_raw_inline(tokens) -> str | None:
    """The first raw inline-HTML or image token ANYWHERE in the doc — governed docs ban these document-wide
    (a name hidden in `<span hidden>`/`<script data-…>`/an image's alt text renders differently than it
    reads). Document-wide so the "no raw HTML in governed docs" claim is literally true, not region-only."""
    for t in tokens:
        if t.type == "inline":
            for c in (t.children or []):
                if c.type in ("html_inline", "image"):
                    return c.type
    return None


def _read(root: Path, fname: str) -> str | None:
    p = root / fname
    return p.read_text(encoding="utf-8") if p.is_file() else None


def check(root: Path) -> list[str]:
    """Regenerate every enumeration and assert each marked site matches in the PARSED token stream.
    Returns findings (empty = clean). Fails closed on an empty/invalid source of truth or any
    malformed/absent/embedded marker."""
    canonical = canonical_skills(root)
    if not canonical:
        return [f"no skills found under {root / 'skills'} — the enumeration gate cannot verify anything "
                f"(fail closed, not clean)"]
    order, errs = load_order(root, canonical)
    if errs:
        return errs
    n = len(canonical)
    md = _md()
    findings: list[str] = []

    texts = {f: _read(root, f) for f in {README, PROMPT}}
    tokens = {f: md.parse(t) for f, t in texts.items() if t is not None}

    # Governed-doc raw-HTML ban (the safe-subset add-on): raw HTML is the enabler for the reader-visible
    # decoys a token check cannot see, so a governed doc may not contain a raw-HTML BLOCK element.
    for fname in (README, PROMPT):
        if fname in tokens:
            stray = _stray_html_block(tokens[fname])
            if stray:
                findings.append(f"{fname}: raw HTML block {stray!r} is not allowed in a governed doc — "
                                f"use Markdown (only the skill markers may be HTML comments)")
            raw_inline = _doc_raw_inline(tokens[fname])
            if raw_inline:
                findings.append(f"{fname}: raw inline {raw_inline} is not allowed in a governed doc — it "
                                f"can render differently than it reads")

    # Marked spans are collected per file so the competing scan below can exclude EVERY legitimate
    # enumeration (all five sites), not just the one site it is called for — the only enumerations that
    # may render are inside these spans; any near-complete run elsewhere is competing.
    marked_spans: dict[str, list[tuple[int, int]]] = {README: [], PROMPT: []}

    for site_id, fname, renderer, kind in PURE_SITES:
        if texts.get(fname) is None:
            findings.append(f"{fname}: not found (needed for site '{site_id}')")
            continue
        tks = tokens[fname]
        try:
            b, e = _marker_token_span(tks, site_id)
        except MarkerError as ex:
            findings.append(f"{fname}: {ex}")
            continue
        marked_spans[fname].append((b, e))
        if _anchor_missing(tks, b, site_id):
            findings.append(f"{fname}: the '{site_id}' marked block is not in its expected location — "
                            f"its unique lead-in anchor is absent or duplicated (a relocated or "
                            f"anchor-cloned block requires a gate update)")
            continue
        if kind == "tree":
            body = _fence_body(tks, b, e)
            if body != _tree_body(order):
                findings.append(f"{fname}: '{site_id}' fenced block is not the generated tree "
                                f"(run generate-skill-enumerations.py)")
        else:
            src = _pure_source(tks, b, e)
            if src != renderer(order):
                findings.append(f"{fname}: '{site_id}' block is not the generated enumeration "
                                f"(run generate-skill-enumerations.py)")

    for site_id, fname in TABLE_SITES:
        if texts.get(fname) is None:
            findings.append(f"{fname}: not found (needed for site '{site_id}')")
            continue
        tks = tokens[fname]
        try:
            b, e = _marker_token_span(tks, site_id)
        except MarkerError as ex:
            findings.append(f"{fname}: {ex}")
            continue
        marked_spans[fname].append((b, e))
        if _anchor_missing(tks, b, site_id):
            findings.append(f"{fname}: the '{site_id}' marked block is not in its expected location — "
                            f"its unique lead-in anchor is absent or duplicated (a relocated or "
                            f"anchor-cloned block requires a gate update)")
            continue
        names = _table_names(tks, b, e)
        if names != order:
            findings.append(f"{fname}: '{site_id}' rendered table first column {names} does not equal "
                            f"the order {order} (fix the table to match skills-order)")
        if _table_stray_names(tks, b, e, order):
            findings.append(f"{fname}: a competing run of skill names appears in the '{site_id}' table "
                            f"outside its first body column (a reversed header / other-column / diagonal "
                            f"enumeration) — the enumeration belongs only in column one")

    # Competing-enumeration scan, once per file: any near-complete run OUTSIDE all marked spans.
    for fname in (README, PROMPT):
        if fname in tokens:
            findings += _competing_findings(tokens[fname], marked_spans[fname], order, fname)

    for fname, phrases in COUNT_PHRASES.items():
        if fname not in tokens:
            # locally fail closed rather than relying on the site loop to have already reported it
            findings.append(f"{fname}: governed doc not found — its count phrases cannot be verified")
            continue
        findings += check_count_phrases(_visible_units(tokens[fname]), phrases, n, fname)

    return findings


def check_count_phrases(units: list[str], phrases, n: int, file_label: str) -> list[str]:
    """PRESENCE-REQUIRED + VALUE-EXACT + EXACTLY-ONCE check of the scalar suite-count phrases. `units` is
    the list of per-unit rendered texts (see _visible_units); each phrase is (combined_pattern, label),
    where the pattern binds the count slot to a distinctive ADJACENT anchor (see the constants above).

    For each phrase, count the combined pattern's matches across ALL units:
      - 0 matches  -> the canonical sentence was reworded / went stale (a finding); it cannot be masked by
        placing the bare count fragment elsewhere, because a match requires the count NEXT TO its anchor.
      - >1 matches -> the canonical sentence was duplicated / relocated (a finding).
      - exactly 1  -> value-exact: the captured count must read the canonical number.
    Because the pattern is anchor-bound, an unrelated sentence sharing the count fragment neither satisfies
    nor trips the check (no document-wide false positive). An empty phrase set is itself a finding — a
    vacuous 'consistent' is exactly the failure this check exists to avoid (gate-reviews/0010)."""
    phrases = tuple(phrases or ())
    if not phrases:
        return [f"{file_label}: no canonical count-phrase checks are configured — the count guard cannot "
                f"verify anything (fail closed, not clean)"]
    accepted = {str(n), NUM_WORDS.get(n, "").lower()} - {""}
    out = []
    for pat, label in phrases:
        matches = [m for u in units for m in pat.finditer(u)]
        if len(matches) != 1:
            out.append(f"{file_label}: the canonical count phrase \"{label}\" matched {len(matches)} time(s), "
                       f"expected exactly 1 — it was reworded/stale (0) or duplicated/relocated (>1). A "
                       f"count phrase must appear exactly once, next to its anchor, and never go unchecked.")
            continue
        tok = re.sub(r"\s+", " ", matches[0].group("count")).strip().lower()
        if tok not in accepted:
            out.append(f"{file_label}: \"{label}\" reads \"{tok}\" but there are {n} skills in skills/ "
                       f"(expected \"{NUM_WORDS.get(n, n)}\" or \"{n}\")")
    return out


def write(root: Path) -> int:
    """Fill the three pure marked blocks in place from skills-order (a dev convenience; check() is the
    gate). Locates the exact standalone marker lines; fails closed if a marker is absent or not unique."""
    canonical = canonical_skills(root)
    order, errs = load_order(root, canonical)
    if errs:
        raise ValueError("; ".join(errs))
    written = 0
    for site_id, fname, renderer, kind in PURE_SITES:
        p = root / fname
        text = p.read_text(encoding="utf-8")
        lines = text.split("\n")
        begin_m, end_m = _canon_markers(site_id)
        begins = [i for i, ln in enumerate(lines) if ln == begin_m]
        ends = [i for i, ln in enumerate(lines) if ln == end_m]
        if len(begins) != 1 or len(ends) != 1 or ends[0] <= begins[0]:
            raise ValueError(f"site '{site_id}': markers not found as unique standalone lines")
        content = (render_tree if kind == "tree" else renderer)(order)
        new_lines = lines[:begins[0] + 1] + content.split("\n") + lines[ends[0]:]
        if new_lines != lines:
            p.write_text("\n".join(new_lines), encoding="utf-8")
            written += 1
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="Skill-enumeration gate, checked against rendered Markdown.")
    here = Path(__file__).resolve().parent
    ap.add_argument("root", nargs="?", default=str(here),
                    help="Repo root (default: the directory containing this script).")
    ap.add_argument("--check", action="store_true",
                    help="Verify every marked site in the parsed token stream (exit 1 on drift). "
                         "Default WRITES the three pure blocks.")
    args = ap.parse_args()
    root = Path(args.root)

    if not args.check:
        try:
            written = write(root)
        except (MarkerError, ValueError) as e:
            print(f"generate-skill-enumerations: cannot write — {e}")
            return 1
        print(f"generate-skill-enumerations: wrote {written} pure block(s) from skills-order")
        return 0

    try:
        findings = check(root)
    except MarkerError as e:  # e.g. the parser is missing — fail closed, do not print "clean"
        print(f"   FAIL  skill-enum: {e}")
        return 1
    for f in findings:
        print(f"   FAIL  skill-enum: {f}")
    if findings:
        print(f"--- skill-enumerations: {len(findings)} finding(s) — regenerate with "
              f"`python3 generate-skill-enumerations.py` and re-check ---")
        return 1
    n = len(canonical_skills(root))
    print(f"--- skill-enumerations: clean ({n} skills; every marked enumeration matches skills-order in "
          f"the parsed Markdown; governed docs contain no raw HTML except the comment markers; count "
          f"phrases consistent — drift-catcher, see CONTRIBUTING for scope) ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
