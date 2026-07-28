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
  - **Each site is pinned to its lead-in (ADJACENCY).** The markers are HTML comments that travel WITH the
    block, so identity alone cannot bind a block to a location — a correct block relocated to an appendix
    (its site now empty) would still be "found". Every site is anchored to a stable phrase in the block that
    introduces it — a paragraph, heading, blockquote, or list (normalized) — and the begin marker must be
    IMMEDIATELY PRECEDED by it (see _anchor_missing): moving a block AWAY from its lead-in (leaving the
    lead-in behind, or into an appendix under a different heading) trips the anchor. Moving the lead-in AND
    the block together is legitimate reorganization. LIMIT: this is adjacency only — deliberately CLONING
    the lead-in phrase beside a relocated block satisfies adjacency and is a disclosed determined-adversary
    residual (a uniqueness rule would catch it but false-positived when a maintainer innocently repeated an
    anchor phrase in prose).
  - **All text matching is NORMALIZED** (see _norm): NFKC + strip zero-width/format chars + Unicode-dash →
    ASCII '-' + whitespace-collapse + casefold + fold COMMON Cyrillic/Greek homoglyphs, applied to both the
    rendered text and every needle (anchor, skill name, count phrase). A reader-visible variant that
    differs only by case, a Unicode dash, a soft hyphen, a compatibility form, or a common homoglyph
    (`оperations` with a Cyrillic о) is matched as the canonical ASCII form. LIMIT: this folds the casual
    confusables, not the FULL Unicode confusables table — an obscure-homoglyph / heavy-mixed-script
    adversary is a disclosed residual.
  - **Casual decoys are caught.** A hidden-comment row, a code-span comment delimiter, a spanning-comment
    marker, or a competing enumeration is caught by the parse-tree checks and the competing scan
    (_competing_findings). A *competing enumeration* is a near-complete run of the skill names (>=
    all-but-one) matched at name boundaries over normalized text, detected in ANY rendered unit OUTSIDE all
    marked blocks — NO separator required — and AGGREGATED per TOP-LEVEL CONTAINER so it cannot hide by
    distribution WITHIN one structure: a comma-separated paragraph, a separator-free fence, a bullet/ordered
    list (one name per item, even a fenced name per item), a blockquote (one name per quoted paragraph,
    incl. a nested list), and a second table (all cells). Every legitimate enumeration lives inside a
    marked block (excluded); an incidental one/two-name cross-reference ("reviewed by doc-critic") is
    legitimate prose and is deliberately NOT flagged. LIMIT: a run deliberately split across SEPARATE
    top-level containers, and a decoy in a non-first column of a MARKED table, are disclosed residuals (see
    below) — aggregating either further would false-positive on ordinary cross-referencing content.
  - **Scalar counts are FIRST-CLASS MARKED SITES** (not document-wide regex). Each count sentence sits in
    its own marker pair; the number is verified ONLY inside that designated region (see check_count_site),
    so it cannot be masked by a restatement elsewhere, false-positive on unrelated prose, or leak through a
    gap window — the failure classes a regex-over-prose count check kept reproducing. The WHOLE number
    phrase is captured, so a compound ("eight hundred") or a range ("eight to twelve") reads as the count
    and fails the value check — the leading token cannot slip past it. Ordinary copyediting is tolerated
    symmetrically: a qualifier BEFORE the count ("a suite of exactly/at least eight …") and adjectives
    AFTER it, including a numeric-leading hyphenated one ("eight one-click …"), keep the value readable. The
    count region is a count SENTENCE,
    not an enumeration site: a near-complete run of the skill names there is flagged (it would otherwise be
    excluded from the competing scan yet never verified against skills-order). Two HEADLINE counts
    are gated (README "a suite of <N> … skills"; the prompt's "an <N>-skill documentation suite"); the
    lower-value prose numbers (the "eight copies" line, the build-command comment, the "now eight skills"
    note) are deliberately NOT gated — a disclosed scope choice.
  - **Raw HTML is banned document-wide in the governed docs** (README.md, per-skill-review-prompt.md): a
    non-comment raw-HTML block (`<details>`, `<div>`, `<ol>`, …) anywhere, or any inline HTML / image
    token anywhere, is rejected — raw HTML is the enabler for a reader-visible decoy that renders
    differently than it reads. Only HTML comments (the markers) are allowed.

WHAT IT DOES NOT GUARANTEE (honest scope — see CONTRIBUTING "Skill-enumeration gate: scope"):
  This is a drift-catcher and casual-decoy guard, NOT a proof of "no reader-visible decoy" against a
  determined adversary. Closing an adversarial decoy over arbitrary Markdown would require rendering to HTML
  and verifying the DOM against GitHub's own engine (cmark-gfm) — out of scope for this internal tooling.
  The disclosed, accepted residuals (each left because closing it would false-positive on ordinary content
  or needs the render-DOM pass): (1) a competing run split across SEPARATE top-level containers so no one
  container is near-complete; (2) a decoy enumeration in a NON-FIRST column of a marked table (`_table_names`
  verifies column one; another column naming several skills is an ordinary cross-reference); (3) relocating
  a marked block while CLONING its lead-in phrase beside the new position (adjacency is satisfied; a
  uniqueness rule would catch it but false-positived on innocent repeats of an anchor phrase); (4) an
  obscure-homoglyph / heavy-mixed-script variant beyond the common-confusables fold; (5) markdown-it-py vs
  cmark-gfm parse edge cases; (6) the three ungated prose counts above; (7) an unusual count PHRASING the
  pattern does not recognize (e.g. punctuation between "suite of" and the number) reports "the count phrase
  appears 0 times" rather than reading the value — reword to the canonical "a suite of <N> … skills"; the
  count VALUE is always verified when the phrase IS recognized, never silently wrong. Both governed files
  are scanned in full, so a competing run in either file is caught.

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
import unicodedata
from pathlib import Path

# ONE normalization applied at EVERY text-match point (anchors, count sites, competing names), so a
# reader-visible variant that differs only by case, a Unicode dash, a zero-width/format character, a
# compatibility form, whitespace, or a COMMON Latin/Cyrillic/Greek homoglyph is matched the same as the
# canonical ASCII form (gate-reviews/0016). Without this, `rebuild`-style prefixes, a U+2011 non-breaking
# hyphen, a soft hyphen, an UPPERCASE name, or a Cyrillic-`о` in a skill name slipped past ASCII checks.
_DASH_MAP = {ord(c): "-" for c in "‐‑‒–—―−⁃˗﹘﹣－⹀֊־᠆"}
# Common Latin-lookalike Cyrillic + Greek letters (applied AFTER casefold, so lowercase only). This folds
# the CASUAL confusables; an EXHAUSTIVE Unicode-confusables table (obscure homoglyphs, full mixed-script)
# is out of scope — a determined adversary is the disclosed residual (see the module docstring).
_CONFUSABLE = {
    # Cyrillic → Latin
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s",
    "ё": "e", "һ": "h", "ԁ": "d", "ԛ": "q", "ԝ": "w", "ө": "o", "к": "k", "м": "m", "т": "t", "н": "h",
    "ѵ": "v", "ԍ": "g", "ӏ": "l", "ⅰ": "i",
    # Greek → Latin
    "ο": "o", "α": "a", "ρ": "p", "ε": "e", "ι": "i", "κ": "k", "ν": "v", "τ": "t", "χ": "x", "υ": "u",
    "μ": "u", "β": "b", "η": "n", "ϲ": "c",
}
_CONFUSABLE_MAP = {ord(k): v for k, v in _CONFUSABLE.items()}


def _norm(s: str) -> str:
    """NFKC → strip zero-width/format (Cf) chars → Unicode-dash → ASCII '-' → whitespace-collapse →
    casefold → fold common Cyrillic/Greek homoglyphs. Idempotent; used on BOTH the rendered text and every
    needle (anchor, skill name, count phrase), so a case / dash / zero-width / compatibility / common-
    homoglyph variant is matched as the canonical form."""
    s = unicodedata.normalize("NFKC", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Cf")   # soft hyphen, ZWSP/ZWJ/ZWNJ, BOM, …
    s = re.sub(r"\s+", " ", s.translate(_DASH_MAP)).strip().casefold()
    # A final NFKC pass makes _norm genuinely idempotent: casefold can emit a DECOMPOSED sequence (e.g. a
    # few Greek codepoints → i/u + combining diaeresis + accent) that a later NFKC would recompose, so
    # without this norm(norm(x)) != norm(x) for those. Re-composing here has no effect on ASCII/common-fold
    # text and never re-introduces a dash or format char (gate-reviews/0017).
    return unicodedata.normalize("NFKC", s.translate(_CONFUSABLE_MAP))

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
# ("twenty-one"). Applied over normalized (casefolded) text, so lowercase alternatives suffice.
_NUM_ALT = "|".join(sorted(NUM_WORDS.values(), key=len, reverse=True))
_COUNT = rf"(?P<count>[0-9]{{1,3}}|(?:{_NUM_ALT})(?:-(?:{_NUM_ALT}))?)"
# A MULTI-TOKEN number phrase: the leading number token plus any number-bearing continuation
# ("eight hundred", "eight to twelve", "eight or nine"), so a continuation is CAPTURED as the count and
# value-checked — not left in a tolerant filler where only the leading token would be read
# (gate-reviews/0017: "a suite of eight hundred … skills" rendered 800 yet passed because the value check
# saw only "eight"). A continuation is a MULTIPLIER ("hundred"), a further number token, or a RANGE word
# that is itself followed by a number ("to twelve") — the range word must LEAD TO a number, so an ordinary
# "eight or so"/"eight to fit" (a correct count in casual prose) is NOT swallowed and stays clean. The
# conjunction "and" is excluded so "eight and only eight" is not misread as one compound number.
_NUM_TOK = rf"(?:{_NUM_ALT})|[0-9]{{1,3}}"
# A number-token continuation must NOT be the head of a HYPHENATED adjective: "eight one-click skills" has
# eight skills, and "one" heads "one-click", not a compound number — so `(?!-[a-z])` stops it being read as
# "eight one" (gate-reviews/0017). Multipliers ("hundred") and range words keep their number arms.
_NUM_CONT = (rf"hundred|thousand|million|billion|dozen|(?:{_NUM_TOK})(?!-[a-z])|"
             rf"(?:to|or|through)[\s-]+(?:{_NUM_TOK})(?!-[a-z])")
_COUNT_RUN = rf"(?P<count>(?:{_NUM_TOK})(?:[\s-]+(?:{_NUM_CONT}))*)"
# Identifier boundaries (over normalized text, where Unicode dashes are already ASCII '-'): `\b` is not
# enough — it let "rebuild all eight" satisfy "build all", and suffixes ("skillsets") pass.
_L = r"(?<![a-z0-9_-])"
_R = r"(?![a-z0-9_-])"

README = "README.md"
PROMPT = "per-skill-review-prompt.md"

# Scalar counts are FIRST-CLASS MARKED SITES (gate-reviews/0016), not document-wide regex. Each count
# sentence sits in its own marker pair; the check verifies the number ONLY inside that designated region,
# so it cannot be masked by a restatement elsewhere, false-positive on unrelated prose, or leak through a
# gap window (the failure classes that a regex-over-prose count check kept reproducing). The pattern below
# is applied to the NORMALIZED region text; `{_L}`/`{_R}` bound the count so a prefix/suffix cannot sneak
# in. Two headline counts are gated; the lower-value prose numbers (the "eight copies" line, the build
# command comment, the "now eight skills" note) are deliberately NOT gated — see CONTRIBUTING scope.
# site_id -> (filename, in-region count pattern over normalized text, human label)
# The pattern is TOLERANT of ordinary copyediting inside the region — the count number and its noun
# ("suite of <N> … skills", "an <N>-skill") with any adjectives between — but rejects a changed number or a
# changed count-noun (gate-reviews/0016: a rigid full-phrase pattern false-positived a good-faith
# "Claude" → "Claude Code" edit). `[^.]*` stays within the one sentence (it cannot cross a period).
COUNT_SITES = {
    # count-suite: the count is followed by a tolerant `[^.]*?` filler, so it uses the MULTI-TOKEN
    # _COUNT_RUN — a continuation ("eight hundred") is captured into `count` and fails the value check,
    # instead of hiding in the filler. count-nskill binds the count directly to a literal "-skill", so a
    # continuation there yields zero matches (fail closed) already; plain _COUNT suffices.
    # `(?:[a-z]+ )*?` tolerates a qualifier before the count ("a suite of exactly/at least/just eight …"),
    # symmetric with the `[^.]*?` filler AFTER it — the count still binds to the FIRST number (non-greedy),
    # so a wrong number in the qualifier position becomes the read value and fails, never a mask
    # (gate-reviews/0017).
    "count-suite": (README, re.compile(rf"{_L}suite of (?:[a-z]+ )*?{_COUNT_RUN}\b[^.]*?\bskills{_R}"),
                    "a suite of <N> … skills"),
    "count-nskill": (PROMPT, re.compile(rf"{_L}an {_COUNT}-skill{_R}"),
                     "an <N>-skill …"),
}


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
    """Collapsed, normalized visible text of the reader-visible block IMMEDIATELY before the begin marker at
    `begin_idx` — the marked block's lead-in. A lead-in may be a paragraph/heading OR a blockquote/list: a
    maintainer may legitimately format the introducing sentence as a quote or a bulleted line, and an intact
    lead-in reformatted that way must still anchor the block (gate-reviews/0017: it used to yield '' and
    false-positive as "moved away"). '' when the marker is not directly preceded by any reader-visible block
    (another html_block, a fence, a table close, an hr, or the top of the document)."""
    if begin_idx < 1:
        return ""
    prev = tokens[begin_idx - 1]
    if prev.type in ("paragraph_close", "heading_close") and begin_idx >= 2 \
            and tokens[begin_idx - 2].type == "inline":
        return _norm(_inline_text(tokens[begin_idx - 2]))
    if prev.type in _CONTAINER_CLOSE:
        # the lead-in was formatted as a blockquote or list — gather that container's inline text, from its
        # matching open up to the marker, so the anchor phrase is found wherever it sits in the container.
        depth = 0
        start = 0
        for k in range(begin_idx - 1, -1, -1):
            if tokens[k].type in _CONTAINER_CLOSE:
                depth += 1
            elif tokens[k].type in _CONTAINER_OPEN:
                depth -= 1
                if depth == 0:
                    start = k
                    break
        return _norm(" ".join(_inline_text(t) for t in tokens[start:begin_idx] if t.type == "inline"))
    return ""


def _anchor_missing(tokens, begin_idx: int, site_id: str) -> bool:
    """True if the site's begin marker is NOT immediately preceded by its lead-in ANCHOR (normalized). The
    marker comments travel WITH the block, so identity alone cannot pin a block to a place: a maintainer
    who moves a marked block AWAY from its lead-in (leaving the lead-in behind, or dropping it into an
    appendix under a different heading) trips this — the block is then preceded by some other text, not the
    anchor. Moving the lead-in AND the block together is legitimate reorganization and still passes.

    SCOPE (gate-reviews/0016): this is ADJACENCY only. An earlier version also required the anchor to occur
    EXACTLY ONCE document-wide, to defeat an adversary who CLONES the lead-in phrase beside a relocated
    block — but the anchors are ordinary descriptive clauses ("generated from skills-order"), so a
    maintainer who innocently repeats one in prose tripped a uniqueness check on a perfectly correct doc (a
    false positive). Since a legitimate repeat and an adversarial clone are indistinguishable by count, the
    uniqueness rule was dropped: casual relocation is caught here; the deliberate anchor-clone relocation is
    a disclosed determined-adversary residual. Fail closed if the site has no anchor registered."""
    anchor = ANCHORS.get(site_id)
    if not anchor:
        return True
    return _norm(anchor) not in _preceding_visible(tokens, begin_idx)


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

def _run_hits(text: str, order: list[str]) -> int:
    """How many DISTINCT skill names occur in `text`, matched at name boundaries over NORMALIZED text (so
    an UPPERCASE or Unicode-dash variant still counts, and 'project-faq' does not count 'project-faq-notes'
    — gate-reviews/0016)."""
    t = _norm(text)
    return sum(1 for nm in order if re.search(_L + re.escape(_norm(nm)) + _R, t))


def _competing_run(text: str, order: list[str]) -> bool:
    """True if `text` holds a NEAR-COMPLETE run of the skill names — at least len(order)-1 (minimum 2).
    A competing ENUMERATION is a second copy of the ordering; an ordinary one- or two-name cross-reference
    ('reviewed by doc-critic') is legitimate prose and is deliberately NOT read as one (gate-reviews/0013)."""
    return _run_hits(text, order) >= max(2, len(order) - 1)


_CONTAINER_OPEN = ("bullet_list_open", "ordered_list_open", "blockquote_open")
_CONTAINER_CLOSE = ("bullet_list_close", "ordered_list_close", "blockquote_close")


def _container_close(tokens, start: int) -> int:
    """Index of the matching close for the block CONTAINER (bullet/ordered list OR blockquote) opening at
    `start`, tracking depth across all container types so a nested list-in-blockquote is contained within
    the outer container's span."""
    depth = 0
    for j in range(start, len(tokens)):
        if tokens[j].type in _CONTAINER_OPEN:
            depth += 1
        elif tokens[j].type in _CONTAINER_CLOSE:
            depth -= 1
            if depth == 0:
                return j
    return len(tokens) - 1


def _in_any_span(idx: int, spans: list[tuple[int, int]]) -> bool:
    return any(b <= idx <= e for b, e in spans)


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
    # (2) each top-level CONTAINER (bullet/ordered list OR blockquote) outside the marked spans, aggregated
    #     over ITS OWN reader-visible descendants — a run written one name per list item, or one name per
    #     quoted paragraph in a blockquote, or across a nested list-in-blockquote, is caught within that
    #     container (gate-reviews/0016 closed the blockquote gap). The outermost container is processed and
    #     its span skipped, so nested containers are folded into it, not double-scanned.
    i = 0
    while i < len(tokens):
        if tokens[i].type in _CONTAINER_OPEN:
            j = _container_close(tokens, i)
            if not _in_any_span(i, spans) and not _in_any_span(j, spans):
                agg = " ".join((_inline_text(x) if x.type == "inline" else x.content)
                               for x in tokens[i:j + 1] if x.type in ("inline", "fence", "code_block"))
                if _competing_run(agg, order):
                    out.append(f"{fname}: a competing enumeration ({_run_hits(agg, order)} of {len(order)} "
                               f"skill names) is distributed across a container (list/blockquote) outside "
                               f"the marked blocks — there must be exactly one enumeration per site")
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


# NOTE: there is deliberately NO check for a decoy enumeration hidden in a NON-FIRST column of a MARKED
# table (a "stray names" guard). Any such check flags a legitimate cross-reference column — a "Handoff"
# or "Reviewed by" column naming several skills is ordinary content, not a competing enumeration — so it
# false-positives on good-faith tables (gate-reviews/0016). `_table_names` verifies the first column IS
# the order; a reader-visible decoy in another column is a disclosed residual (see CONTRIBUTING scope).


def _allowed_marker_comments() -> set[str]:
    """The ONLY raw HTML permitted in a governed doc: this suite's exact begin/end marker comments."""
    out: set[str] = set()
    for site_id in [s[0] for s in PURE_SITES] + [s[0] for s in TABLE_SITES] + list(COUNT_SITES):
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
                            f"its lead-in anchor does not immediately precede it (a block moved away "
                            f"from its lead-in requires a gate update)")
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
                            f"its lead-in anchor does not immediately precede it (a block moved away "
                            f"from its lead-in requires a gate update)")
            continue
        names = _table_names(tks, b, e)
        if names != order:
            findings.append(f"{fname}: '{site_id}' rendered table first column {names} does not equal "
                            f"the order {order} (fix the table to match skills-order)")

    # Count sites are MARKED blocks too, so collect their spans BEFORE the competing scan — a near-complete
    # run rendered INSIDE a count region is inside a marked block, so the general scan must not label it
    # "outside every marked block" (until 0017 the scan ran first and did exactly that). Excluding it here is
    # not a hole: check_count_site verifies the count region is a count SENTENCE and flags a near-complete
    # enumeration in it directly (a run there is not generated/verified, so it would silently rot). The
    # value check runs after the scan, from the spans collected here.
    count_checks: list[tuple] = []
    if not COUNT_SITES:
        # vacuous success is exactly the failure this check exists to avoid — an emptied registry would
        # disable the count guard while the banner still said "count phrases consistent".
        findings.append("no count sites are configured — the count guard cannot verify anything "
                        "(fail closed, not clean)")
    for site_id, (fname, pat, label) in COUNT_SITES.items():
        if fname not in tokens:
            findings.append(f"{fname}: governed doc not found — count site '{site_id}' cannot be verified")
            continue
        try:
            b, e = _marker_token_span(tokens[fname], site_id)
        except MarkerError as ex:
            findings.append(f"{fname}: {ex}")
            continue
        marked_spans[fname].append((b, e))
        count_checks.append((fname, b, e, site_id, pat, label))

    # Competing-enumeration scan, once per file: any near-complete run OUTSIDE all marked spans (now
    # including the two count blocks collected above).
    for fname in (README, PROMPT):
        if fname in tokens:
            findings += _competing_findings(tokens[fname], marked_spans[fname], order, fname)

    # Count VALUE checks, using the spans gathered before the scan.
    for fname, b, e, site_id, pat, label in count_checks:
        findings += check_count_site(tokens[fname], b, e, site_id, fname, pat, label, n, order)

    return findings


def _count_region_text(tokens, b: int, e: int) -> str | None:
    """The NORMALIZED rendered text of the single paragraph in the marked count region [b, e], or None if
    the region is not exactly one paragraph (anything smuggled in is a finding, like the pure sites)."""
    inner = tokens[b + 1:e]
    if len(inner) == 3 and inner[1].type == "inline" and inner[0].type == "paragraph_open" \
            and inner[2].type == "paragraph_close":
        return _norm(_inline_text(inner[1]))
    return None


def check_count_site(tokens, b, e, site_id, fname, pat, label, n, order) -> list[str]:
    """Verify the scalar count in the MARKED region [b, e] reads the skill count. The count is checked ONLY
    inside its designated marker pair (gate-reviews/0016), so — unlike a document-wide regex — it cannot be
    masked by a correct restatement elsewhere, false-positive on unrelated prose, or leak through a gap
    window. Exactly one count phrase must appear in the region, reading the canonical value."""
    text = _count_region_text(tokens, b, e)
    if text is None:
        return [f"{fname}: the '{site_id}' marked count region is not a single paragraph (fix the region)"]
    out: list[str] = []
    # The count region is a count SENTENCE, not an enumeration site. A near-complete run of the skill names
    # here is never generated or verified against skills-order (it silently rots on a reorder), and — since
    # its span is marked — it is excluded from the general competing scan, which would otherwise flag it. So
    # catch it HERE (gate-reviews/0017): enumerations belong in their dedicated, generated marked sites. A
    # one/two-name cross-reference stays below the near-complete threshold and is fine.
    if _competing_run(text, order):
        out.append(f"{fname}: the '{site_id}' count region names {_run_hits(text, order)} of {len(order)} "
                   f"skills — the count sentence must not enumerate the skills; use the dedicated "
                   f"enumeration sites (they are generated from skills-order)")
    matches = list(pat.finditer(text))
    if len(matches) != 1:
        out.append(f"{fname}: the count phrase \"{label}\" appears {len(matches)} time(s) in its '{site_id}' "
                   f"marked region, expected exactly 1 — the region was reworded, or the pattern is stale.")
        return out
    tok = matches[0].group("count")
    accepted = {str(n), _norm(NUM_WORDS.get(n, ""))} - {""}
    if tok not in accepted:
        out.append(f"{fname}: '{site_id}' \"{label}\" reads \"{tok}\" but there are {n} skills in skills/ "
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
