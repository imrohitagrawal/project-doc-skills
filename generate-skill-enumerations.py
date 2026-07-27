#!/usr/bin/env python3
"""
generate-skill-enumerations.py — the skill-enumeration gate, by GENERATION not parsing.

The suite enumerates its skills in five places (README skill table, README repo tree, README
improve-order list; per-skill-review-prompt {SKILL_NAME} pick-list and attachment table). The previous
guard, lint-skill-count.py, EXTRACTED each enumeration from raw Markdown with regex and set-compared it,
and was defeated four times by a markup-hidden decoy. This replaces parsing with generation: each
enumeration is generated from one source of truth and checked at a FAIL-CLOSED marked location.

Source of truth:
  - SET   = skills/<name>/ holding a SKILL.md  (canonical_skills()).
  - ORDER = the root `skills-order` file (one skill per line), validated as an EXACT PERMUTATION of the
            set (missing / extra / duplicate / unknown -> fail closed). All five sites share this order.

Per-site strategy (ADR 0001, Plan B):
  - Three PURE sites (improve-order, pick-list, repo tree) are generated in FULL and checked
    BYTE-IDENTICAL.
  - Two TABLE sites keep their editorial columns authored inline; only the NAME column is checked, from
    the RENDERED table rows (HTML comments stripped first; each name is the WHOLE first cell).
  - The scalar COUNT phrases are checked by anchored regex (a scalar has no "which list is real"
    ambiguity, so it is not part of the decoy class).

Marker discipline — THREE properties, each fail-closed, together closing the decoy class the old parser
could not (a gate-review reproduced all three bypasses against a substring-only earlier version):
  1. EXACTNESS: each marker token occurs EXACTLY ONCE in the file, on a line BYTE-EQUAL to the canonical
     self-closing comment `<!-- skills:<id>:begin -->`. HTML comments do not nest, so a marker cannot be
     hidden inside a spanning comment, duplicated on one line, or otherwise embedded in markup.
  2. ANCHORING: the block must sit within a few lines after its unique section anchor, so a correct
     marked block cannot be RELOCATED to an appendix while a broken un-marked list occupies the real
     location.
  3. RENDERED-ONLY table rows: the table name column is read from rows that survive comment-stripping and
     whose whole first cell is exactly a skill name — a decoy row hidden in `<!-- -->` is never read.

Usage:
    python3 generate-skill-enumerations.py [root]            # WRITE: fill the three pure blocks in place
    python3 generate-skill-enumerations.py [root] --check    # CHECK: assert all five sites + the count
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

NUM_WORDS = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight",
    9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen",
    16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty",
}
WORD_TO_NUM = {word: n for n, word in NUM_WORDS.items()}

README_COUNT_PHRASES = [
    (re.compile(r"suite of (\w+) independent", re.IGNORECASE), "a suite of <N> independent ... skills"),
    (re.compile(r"(\w+) copies of the house style", re.IGNORECASE), "<N> copies of the house style"),
    (re.compile(r"build all (\w+)", re.IGNORECASE), "build all <N>"),
]
PROMPT_COUNT_PHRASES = [
    (re.compile(r"(\w+)-skill documentation suite", re.IGNORECASE), "<N>-skill documentation suite"),
    (re.compile(r"now \*\*(\w+)\*\* skills", re.IGNORECASE), "now **<N>** skills"),
]

README = "README.md"
PROMPT = "per-skill-review-prompt.md"

# The begin marker must sit within this many lines after its section anchor (relocation guard).
MARKER_GAP = 3


class MarkerError(Exception):
    """Raised when a site's markers are absent, embedded, duplicated, malformed, or relocated — always
    fail closed."""


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


# ---- renderers: the EXACT output bytes for the three pure sites ---------------------------------

def render_improve_order(order: list[str]) -> str:
    """README improve-order list: bold-wrapped, ` → `-joined, trailing period inside the bold."""
    return "**" + " → ".join(order) + ".**"


def render_pick_list(order: list[str]) -> str:
    """per-skill-prompt {SKILL_NAME} pick-list: a single backtick code span, ` · `-joined."""
    return "`" + " · ".join(order) + "`"


def render_tree(order: list[str]) -> str:
    """README repo-tree skills/ block, its OWN fenced code block (so its markers are exact self-closing
    HTML comments OUTSIDE the fence, like the other pure sites — not an in-fence sentinel that could be
    forged in a comment elsewhere)."""
    nodes = []
    for i, name in enumerate(order):
        glyph = "└─" if i == len(order) - 1 else "├─"
        nodes.append(f"{glyph} {name}/")
    return "```\nskills/\n" + "\n".join(nodes) + "\n```"


# ---- markers (fail closed: exactness + anchoring) -----------------------------------------------

# Each site's unique section anchor: the block must sit just after it (relocation guard). A substring
# that occurs exactly once in the site's file.
ANCHORS = {
    "improve-order": "producers before consumers",
    "pick-list": "with exactly one of these",
    "tree": "generated from `skills-order`):",
    "table": "| Skill | Diátaxis mode | Scope | Reading grade |",
    "attach-table": "| `{SKILL_NAME}` | Attach these",
}


def _canon_markers(site_id: str) -> tuple[str, str]:
    return f"<!-- skills:{site_id}:begin -->", f"<!-- skills:{site_id}:end -->"


def _marker_span(text: str, site_id: str) -> tuple[int, int]:
    """Indices of `site_id`'s begin/end marker lines, or MarkerError (never a silent skip). Fail closed on:
    a token that does not occur EXACTLY ONCE in the file; a token not present as the exact standalone
    self-closing marker line; out-of-order markers; or a block not anchored within MARKER_GAP lines of its
    unique section anchor."""
    lines = text.split("\n")
    begin_tok, end_tok = f"skills:{site_id}:begin", f"skills:{site_id}:end"
    begin_marker, end_marker = _canon_markers(site_id)

    if text.count(begin_tok) != 1 or text.count(end_tok) != 1:
        raise MarkerError(f"site '{site_id}': each marker token must occur exactly once in the file "
                          f"(found begin×{text.count(begin_tok)}, end×{text.count(end_tok)}) — a marker "
                          f"embedded in markup or duplicated is rejected")
    begins = [i for i, ln in enumerate(lines) if ln == begin_marker]
    ends = [i for i, ln in enumerate(lines) if ln == end_marker]
    if len(begins) != 1 or len(ends) != 1:
        raise MarkerError(f"site '{site_id}': marker token present but not as the exact standalone line "
                          f"{begin_marker!r} / {end_marker!r}")
    b, e = begins[0], ends[0]
    if e <= b:
        raise MarkerError(f"site '{site_id}': end marker is not after the begin marker")

    anchor = ANCHORS[site_id]
    ahits = [i for i, ln in enumerate(lines) if anchor in ln]
    if len(ahits) != 1:
        raise MarkerError(f"site '{site_id}': section anchor {anchor!r} must appear exactly once "
                          f"(found {len(ahits)})")
    if not (0 < b - ahits[0] <= MARKER_GAP):
        raise MarkerError(f"site '{site_id}': begin marker must be within {MARKER_GAP} lines after its "
                          f"anchor (gap {b - ahits[0]}) — the block may have been relocated")
    return b, e


def extract_marked_block(text: str, site_id: str) -> str:
    """The exact bytes strictly between `site_id`'s begin and end markers. Fail closed via _marker_span."""
    lines = text.split("\n")
    b, e = _marker_span(text, site_id)
    return "\n".join(lines[b + 1:e])


def extract_table_names(block: str) -> list[str]:
    """The first-column skill names of the RENDERED table rows in `block`, in order. HTML comment regions
    are stripped first (a decoy row hidden in `<!-- -->` is non-rendered and never read), and each name
    must be the WHOLE first cell (bold/code wrapping allowed) — a cell like `alpha/NOT-THE-NAME` or a
    non-row line is POISONED so it can never equal a skill name."""
    rendered = re.sub(r"<!--.*?-->", "", block, flags=re.DOTALL)
    names: list[str] = []
    for line in rendered.split("\n"):
        s = line.strip()
        if not s:
            continue
        if not s.startswith("|"):
            names.append("¬nonrow:" + s[:24])            # a stray non-row line in the region -> poison
            continue
        first = s.strip("|").split("|")[0].strip()
        m = re.fullmatch(r"\*{0,2}`?([a-z0-9][a-z0-9-]*)`?\*{0,2}", first)
        names.append(m.group(1) if m else "¬cell:" + first)   # non-exact first cell -> poison
    return names


def check_count_phrases(text: str, phrases, n: int, file_label: str) -> list[str]:
    """Flag EVERY occurrence (finditer) of each canonical phrase whose count — word OR digit — != n."""
    out = []
    for pat, label in phrases:
        for m in pat.finditer(text):
            tok = m.group(1).lower()
            if tok.isdigit():
                val = int(tok)
            elif tok in WORD_TO_NUM:
                val = WORD_TO_NUM[tok]
            else:
                continue
            if val != n:
                out.append(f"{file_label}: \"{label}\" says \"{tok}\" ({val}) "
                           f"but there are {n} skills in skills/")
    return out


# site_id, filename, renderer — the three fully-generated, byte-identical sites
PURE_SITES = [
    ("improve-order", README, render_improve_order),
    ("pick-list", PROMPT, render_pick_list),
    ("tree", README, render_tree),
]
# site_id, filename — the two tables: rendered name column checked, editorial columns authored inline
TABLE_SITES = [
    ("table", README),
    ("attach-table", PROMPT),
]
COUNT_PHRASES = {README: README_COUNT_PHRASES, PROMPT: PROMPT_COUNT_PHRASES}


def _read(root: Path, fname: str) -> str | None:
    p = root / fname
    return p.read_text(encoding="utf-8") if p.is_file() else None


def check(root: Path) -> list[str]:
    """Regenerate every enumeration in memory and assert each marked site matches. Returns findings
    (empty = clean). Fails closed on an invalid skills-order or any malformed/absent/embedded/relocated
    marker."""
    canonical = canonical_skills(root)
    if not canonical:
        return []
    order, errs = load_order(root, canonical)
    if errs:
        return errs
    n = len(canonical)
    findings: list[str] = []

    for site_id, fname, renderer in PURE_SITES:
        text = _read(root, fname)
        if text is None:
            findings.append(f"{fname}: not found (needed for site '{site_id}')")
            continue
        try:
            block = extract_marked_block(text, site_id)
        except MarkerError as e:
            findings.append(f"{fname}: {e}")
            continue
        if block != renderer(order):
            findings.append(f"{fname}: '{site_id}' block is not byte-identical to the generated "
                            f"enumeration (run generate-skill-enumerations.py)")

    for site_id, fname in TABLE_SITES:
        text = _read(root, fname)
        if text is None:
            findings.append(f"{fname}: not found (needed for site '{site_id}')")
            continue
        try:
            block = extract_marked_block(text, site_id)
        except MarkerError as e:
            findings.append(f"{fname}: {e}")
            continue
        names = extract_table_names(block)
        if names != order:
            findings.append(f"{fname}: '{site_id}' rendered name column {names} does not equal the order "
                            f"{order} (fix the table to match skills-order)")

    for fname, phrases in COUNT_PHRASES.items():
        text = _read(root, fname)
        if text is not None:
            findings += check_count_phrases(text, phrases, n, fname)

    return findings


def write(root: Path) -> int:
    """Fill the three pure marked blocks in place from skills-order. Tables are author-owned (only their
    rendered name column is checked). Fails closed on an invalid order or a malformed/absent marker."""
    canonical = canonical_skills(root)
    order, errs = load_order(root, canonical)
    if errs:
        raise ValueError("; ".join(errs))
    written = 0
    for site_id, fname, renderer in PURE_SITES:
        p = root / fname
        text = p.read_text(encoding="utf-8")
        lines = text.split("\n")
        b, e = _marker_span(text, site_id)             # fail closed
        new_lines = lines[:b + 1] + renderer(order).split("\n") + lines[e:]
        if new_lines != lines:
            p.write_text("\n".join(new_lines), encoding="utf-8")
            written += 1
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="Skill-enumeration gate by generation (replaces the parser).")
    here = Path(__file__).resolve().parent
    ap.add_argument("root", nargs="?", default=str(here),
                    help="Repo root (default: the directory containing this script).")
    ap.add_argument("--check", action="store_true",
                    help="Verify every marked site (exit 1 on drift). Default WRITES the pure blocks.")
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

    findings = check(root)
    for f in findings:
        print(f"   FAIL  skill-enum: {f}")
    if findings:
        print(f"--- skill-enumerations: {len(findings)} finding(s) — regenerate with "
              f"`python3 generate-skill-enumerations.py` and re-check ---")
        return 1
    print("--- skill-enumerations: clean (3 sites generated byte-identical + 2 tables name-checked + "
          "the count phrases hold) ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
