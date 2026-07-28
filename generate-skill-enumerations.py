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
    that introduces it, and that phrase must occur EXACTLY ONCE (see _anchor_missing): moving a block away
    from its lead-in, OR cloning the lead-in phrase next to a relocated block, trips the anchor. (Moving
    the sole lead-in and its block together is legitimate reorganization, not drift, and is not targeted.)
  - **Casual decoys are caught.** A hidden-comment row, a code-span comment delimiter, a spanning-comment
    marker, or a competing enumeration is caught by the parse-tree checks and the competing scan. A
    *competing enumeration* is a near-complete run of the skill names (>= all-but-one) matched at name
    boundaries, and it is AGGREGATED across structure so it cannot hide by distribution: across the items
    of a bullet/ordered list (one name per item) and down a table column (one name per cell), not only
    within a single paragraph or cell. An incidental one/two-name cross-reference ("reviewed by
    doc-critic") is legitimate prose and is deliberately NOT flagged.
  - **Count phrases are LOCATION-BOUND.** Each scalar count ("a suite of <N> ... skills", "build all <N>
    + emit dist/MANIFEST.sha256", …) is checked, presence-required and value-exact, ONLY inside the one
    rendered unit carrying its site anchor. So rewording the sentence at its site trips presence (it cannot
    be masked by the count still matching a fragment elsewhere), and an unrelated sentence sharing the
    template is neither required nor flagged. Templates are CLOSED (no wildcard bridge).
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
  (markdown-it-py vs cmark-gfm parse edge cases; anything the ban does not cover) are the disclosed,
  accepted limit, tracked for a future render-DOM pass if the threat model ever warrants it.

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
_COUNT = rf"(?P<count>\d{{1,3}}|(?:{_NUM_ALT})(?:-(?:{_NUM_ALT}))?)"
# Whole-template boundaries. `\b` is not enough: it let "rebuild all eight" satisfy "build all <N>",
# "know eight skills" satisfy "now <N> skills", and suffixed rewordings ("skillsets", "independently",
# "stylesheet", "suites") pass while the canonical phrase was gone.
_L = r"(?<![A-Za-z0-9_-])"
_R = r"(?![A-Za-z0-9_-])"

# Count phrases are LOCATION-BOUND, not scanned document-wide (gate-reviews/0014). Each is a triple
# (site_anchor, closed_template, label): the template is matched, PRESENCE-REQUIRED and VALUE-EXACT, ONLY
# inside the single rendered unit (paragraph / blockquote / fenced block) that carries the site_anchor — a
# distinctive phrase co-located with the count at its canonical site. Two failure modes a document-wide
# scan could not close (both reproduced in review):
#   MASKING: reword the real sentence's noun away ("... independent reviewers evaluates skills.") and a
#     document-wide regex still matched a fragment elsewhere / a loose bridge (`{0,3}` words) still spanned
#     it — clean while the canonical count was gone. Now the template is CLOSED (no wildcard bridge) and
#     is required to appear AT its anchored site, so rewording that site's sentence trips presence.
#   FALSE POSITIVE: an unrelated sentence sharing a fragment ("build all three + emit diagnostic records")
#     was value-checked against the skill count. Now only the anchored site's unit is inspected, so an
#     occurrence anywhere else is neither required nor flagged.
# The templates carry the FULL distinguishing text (e.g. `build all <N> + emit dist/MANIFEST.sha256`,
# `independent Claude skills`) — deliberately not a shortenable prefix.
README_COUNT_PHRASES = [
    ("software project into documentation",
     re.compile(rf"{_L}suite of {_COUNT} independent Claude skills{_R}", re.IGNORECASE),
     "a suite of <N> independent Claude skills"),
    ("self-contained packages",
     re.compile(rf"{_L}{_COUNT} copies of the house style{_R}", re.IGNORECASE),
     "<N> copies of the house style"),
    ("then upload/install",
     re.compile(rf"{_L}build all {_COUNT} \+ emit dist/MANIFEST\.sha256{_R}", re.IGNORECASE),
     "build all <N> + emit dist/MANIFEST.sha256"),
]
PROMPT_COUNT_PHRASES = [
    ("You are improving ONE skill in",
     re.compile(rf"{_L}{_COUNT}-skill documentation suite{_R}", re.IGNORECASE),
     "<N>-skill documentation suite"),
    ("What changed in the suite",
     re.compile(rf"{_L}now {_COUNT} skills{_R}", re.IGNORECASE), "now <N> skills"),
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
    """Read `skills-order` (skip blank lines and # comments) and validate it. Returns (order, errors)."""
    p = root / "skills-order"
    if not p.is_file():
        return [], [f"skills-order not found at {p}"]
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
    and excluded. The count-phrase check inspects only the ONE unit carrying a phrase's site anchor, so a
    count elsewhere in the document is neither required nor flagged — location-bound, not document-wide.
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
    """How many rendered inline blocks (paragraph / heading / blockquote line / table cell) contain
    `anchor`, whitespace-normalized. Used to require the anchor be UNIQUE — see _anchor_missing."""
    return sum(1 for t in tokens if t.type == "inline"
               and anchor in re.sub(r"\s+", " ", _inline_text(t)).strip())


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


def _competing(tokens, b: int, e: int, kind: str, order: list[str]) -> bool:
    """True if a competing rendered enumeration appears OUTSIDE the marked block [b, e]. Two shapes:

    (1) A separator run in a SINGLE unit — a paragraph or fenced block whose text carries the site's
        separator plus a near-complete run of the names (see _competing_run). A differently formatted
        broken run (no trailing period, etc.) is still caught.
    (2) A stray ENUMERATION LIST — a bullet/ordered list whose items are the skill names, one name per
        item. Each list item is its own inline token, so the per-unit check in (1) never sees the whole
        run; the run must be AGGREGATED across the list's items (gate-reviews/0014). The docstring's
        "a stray second list is caught" promise depends on this aggregation.

    Scope, honestly: this scans the site's OWN file. A competing run planted in the other governed doc is
    a disclosed residual (CONTRIBUTING "Skill-enumeration gate: scope"), not a claim made here."""
    sep = {"arrow": " → ", "dot": " · "}.get(kind)
    # (2) aggregate each list container that lies entirely outside the marked block.
    i = 0
    while i < len(tokens):
        if tokens[i].type in ("bullet_list_open", "ordered_list_open"):
            j = _list_close(tokens, i)
            if not (b <= i <= e) and not (b <= j <= e):
                agg = " ".join(_inline_text(x) for x in tokens[i:j + 1] if x.type == "inline")
                if _competing_run(agg, order):
                    return True
            i = j + 1
            continue
        i += 1
    # (1) per-unit separator run in inline prose or a fenced/indented code block.
    for i, t in enumerate(tokens):
        if b <= i <= e:
            continue
        if sep is not None:
            txt = _inline_text(t) if t.type == "inline" else (
                t.content if t.type in ("fence", "code_block") else "")
            if txt and sep in txt and _competing_run(txt, order):
                return True
        if kind == "tree" and t.type == "fence" and t.content.lstrip().startswith("skills/") \
                and "─" in t.content:
            return True
    return False


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
    """True if a NEAR-COMPLETE run of skill names (a reversed/competing enumeration — see _competing_run)
    hides in the marked table OUTSIDE its first body column. Checked at three granularities so a run
    DISTRIBUTED across cells cannot escape a cell-local test (gate-reviews/0014):
      - each header cell, and the header row as one sequence (a reversed order written across the header);
      - each NON-FIRST body column, AGGREGATED down its rows (a reversed order written down a column — the
        exact escape a per-cell check missed: no single cell holds the whole run).
    The first body column is exempt: _table_names already verifies it equals the order. A singleton
    cross-reference (one skill named in a description cell) stays below threshold and is allowed."""
    header, rows = _table_cells(tokens[b + 1:e])
    for cell in header:
        if _competing_run(cell, order):
            return True
    if _competing_run(" ".join(header), order):
        return True
    ncols = max((len(r) for r in rows), default=0)
    for col in range(1, ncols):
        colcat = " ".join(r[col] for r in rows if col < len(r))
        if _competing_run(colcat, order):
            return True
    return False


def _extra_skill_table(tokens, b: int, e: int, order: list[str]) -> bool:
    """True if a SECOND table (outside the marked block [b, e]) has >= 2 body rows whose first cell is a
    skill name — a relocated/competing table."""
    names = set(order)
    hits = 0
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.type == "table_open":
            start = i
            j = i
            first_cells = []
            in_tbody = False
            while j < len(tokens) and tokens[j].type != "table_close":
                if tokens[j].type == "tbody_open":
                    in_tbody = True
                elif tokens[j].type == "tbody_close":
                    in_tbody = False
                elif tokens[j].type == "tr_open" and in_tbody:
                    k = j + 1
                    while k < len(tokens) and tokens[k].type != "tr_close":
                        if tokens[k].type == "inline":
                            first_cells.append(_inline_text(tokens[k]))
                            break
                        k += 1
                j += 1
            inside_marked = b <= start <= e
            if not inside_marked and sum(1 for c in first_cells if c in names) >= 2:
                hits += 1
            i = j
        i += 1
    return hits >= 1


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
        if _competing(tks, b, e, kind, order):
            findings.append(f"{fname}: a competing '{site_id}' enumeration renders OUTSIDE the "
                            f"marked block (relocation / stray list) — there must be exactly one")

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
                            f"outside its first body column (a reversed header / other-column enumeration) "
                            f"— the enumeration belongs only in column one")
        if _extra_skill_table(tks, b, e, order):
            findings.append(f"{fname}: a competing skill table renders OUTSIDE the '{site_id}' marked "
                            f"block (relocation / stray table) — there must be exactly one")

    for fname, phrases in COUNT_PHRASES.items():
        if fname not in tokens:
            # locally fail closed rather than relying on the site loop to have already reported it
            findings.append(f"{fname}: governed doc not found — its count phrases cannot be verified")
            continue
        findings += check_count_phrases(_visible_units(tokens[fname]), phrases, n, fname)

    return findings


def check_count_phrases(units: list[str], phrases, n: int, file_label: str) -> list[str]:
    """PRESENCE-REQUIRED + VALUE-EXACT, LOCATION-BOUND check of the scalar suite-count phrases. `units` is
    the list of per-unit rendered texts (see _visible_units); each phrase is (site_anchor, pattern, label).

    For each phrase: locate the SINGLE unit carrying its site_anchor (exactly one — 0 or >1 is a finding:
    the site moved, was duplicated, or the anchor drifted); then require the template to occur in THAT unit
    (absence => reworded / stale) and every occurrence there to read exactly the canonical count. A match
    ELSEWHERE in the document is neither required nor flagged, which is what makes this both mask-proof and
    FP-proof (gate-reviews/0014).

    FAIL CLOSED, deliberately: the older form only reported when a pattern matched AND parsed a number, so
    a phrase reworded away, a multi-token count, a non-numeric word, or a pattern gone stale all SILENTLY
    SKIPPED while the banner still said "count phrases consistent" (gate-reviews/0010). An empty phrase set
    is itself a finding — vacuous success is exactly the failure mode this check exists to avoid."""
    phrases = tuple(phrases or ())
    if not phrases:
        return [f"{file_label}: no canonical count-phrase checks are configured — the count guard cannot "
                f"verify anything (fail closed, not clean)"]
    accepted = {str(n), NUM_WORDS.get(n, "").lower()} - {""}
    out = []
    for anchor, pat, label in phrases:
        located = [u for u in units if anchor in u]
        if len(located) != 1:
            out.append(f"{file_label}: the count site for \"{label}\" (anchored by \"{anchor}\") was found "
                       f"in {len(located)} rendered unit(s), expected exactly 1 — the site moved, was "
                       f"duplicated, or its anchor drifted; the count cannot be located to verify.")
            continue
        unit = located[0]
        found = 0
        for m in pat.finditer(unit):
            found += 1
            tok = re.sub(r"\s+", " ", m.group("count")).strip().lower()
            if tok not in accepted:
                out.append(f"{file_label}: \"{label}\" reads \"{tok}\" but there are {n} skills in "
                           f"skills/ (expected \"{NUM_WORDS.get(n, n)}\" or \"{n}\")")
        if not found:
            out.append(f"{file_label}: the canonical count phrase \"{label}\" was not found at its site "
                       f"(anchored by \"{anchor}\") — it was reworded, or this pattern is stale. Fix the "
                       f"doc or update the pattern; a count phrase must never go unchecked.")
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
