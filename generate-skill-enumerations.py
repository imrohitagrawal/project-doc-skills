#!/usr/bin/env python3
"""
generate-skill-enumerations.py — the skill-enumeration gate, checked against RENDERED Markdown.

The suite enumerates its skills in five places (README skill table, README repo tree, README
improve-order list; per-skill-review-prompt {SKILL_NAME} pick-list and attachment table). Two earlier
designs — a regex parser (`lint-skill-count.py`), then a byte-stream marker check — were each defeated
by a markup-hidden decoy: independent gate-reviews (`gate-reviews/0002`, `0005`, `0006`) showed that any
check operating on the raw BYTES cannot tell the enumeration a reader SEES from one hidden in markup
(an HTML comment, a spanning comment, a `<details>` fold, a code fence, a code-span comment delimiter).

This design closes that class by checking against the **parsed Markdown token stream** (markdown-it-py,
CommonMark + GFM tables — a close proxy for GitHub's renderer), not the bytes:

  - The site markers must be STANDALONE top-level `<!-- skills:<id>:begin -->` / `:end` HTML-comment
    tokens. A marker wrapped in `<details>`, a code fence, or any raw-HTML block is NOT a standalone
    token (the wrapper swallows it into one block token) → the site is "not found" → fail closed.
  - The content BETWEEN the markers must be exactly the generated enumeration, read from the PARSED
    tokens: a top-level paragraph whose source equals the generated run (improve-order, pick-list); a
    single fenced code block whose body equals the generated tree; or a single table whose body rows'
    first-cell RENDERED TEXT equals the skills, in order (a decoy row hidden in a comment is a real
    table row to the parser, so it is read and fails the check; a code-span comment delimiter is a
    code span, not a comment, so nothing is silently stripped).
  - No COMPETING rendered enumeration of the same shape may appear elsewhere in the file (closes
    relocation of a correct block while a broken un-marked list occupies the reader-facing location, and
    the stray-second-list gap).

Source of truth: SET = skills/<name>/ with a SKILL.md; ORDER = the root `skills-order` file, validated
as an exact permutation of the set (fail closed). Residual (honest): the gate checks against
markdown-it-py, not GitHub's cmark-gfm; a construct those two parse differently is the remaining, much
smaller, disclosed gap (see ADR 0001).

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
    inner = [t for t in tokens[b + 1:e] if t.type not in ("html_block",) or t.content.strip()]
    if len(inner) == 1 and inner[0].type == "fence":
        return inner[0].content.rstrip("\n")
    return None


def _table_names(tokens, b: int, e: int) -> list[str] | None:
    """First-cell rendered text of each body row of the SINGLE table between the markers (in order), or
    None if the marked content is not exactly one table (any smuggled paragraph/fence/html/heading, or a
    second table, returns None -> a finding)."""
    inner = tokens[b + 1:e]
    if sum(1 for t in inner if t.type == "table_open") != 1:
        return None
    if any(t.type in ("paragraph_open", "fence", "code_block", "html_block", "heading_open",
                      "bullet_list_open", "blockquote_open") for t in inner):
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

def _competing(tokens, b: int, e: int, kind: str, order: list[str]) -> bool:
    """True if a competing rendered enumeration appears OUTSIDE the marked block [b, e] — closing
    relocation (a correct block moved away while a broken un-marked list holds the reader-facing spot)
    and the stray-second-list gap. Keyed on ACTUAL skill names + the site's separator, so a differently
    FORMATTED broken list (no trailing period, etc.) is still caught: to be mistakable for this
    enumeration a reader-facing run must use the skill names and the separator."""
    names = set(order)
    sep = {"arrow": " → ", "dot": " · "}.get(kind)
    for i, t in enumerate(tokens):
        if b <= i <= e:
            continue
        if sep is not None and t.type == "inline":
            txt = _inline_text(t)
            if sep in txt and sum(1 for nm in names if nm in txt) >= 2:
                return True
        if kind == "tree" and t.type == "fence" and t.content.lstrip().startswith("skills/") \
                and "─" in t.content:
            return True
    return False


def _extra_skill_table(tokens, b: int, e: int, order: list[str]) -> bool:
    """True if a SECOND table (outside the marked block [b, e]) has >= 2 body rows whose first cell is a
    skill name — a relocated/competing table."""
    names = set(order)
    depth_open = None
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
        names = _table_names(tks, b, e)
        if names != order:
            findings.append(f"{fname}: '{site_id}' rendered table first column {names} does not equal "
                            f"the order {order} (fix the table to match skills-order)")
        if _extra_skill_table(tks, b, e, order):
            findings.append(f"{fname}: a competing skill table renders OUTSIDE the '{site_id}' marked "
                            f"block (relocation / stray table) — there must be exactly one")

    for fname, phrases in COUNT_PHRASES.items():
        if texts.get(fname) is not None:
            findings += check_count_phrases(texts[fname], phrases, n, fname)

    return findings


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
    print(f"--- skill-enumerations: clean ({n} skills; 3 pure sites + 2 tables verified against the "
          f"parsed Markdown, and the count phrases hold) ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
