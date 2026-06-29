#!/usr/bin/env python3
"""
generate-skill-enumerations.py — the skill-enumeration gate, by GENERATION not parsing.

The suite enumerates its skills in five places (README skill table, README repo tree, README
improve-order list; per-skill-review-prompt {SKILL_NAME} pick-list and attachment table). The previous
guard, lint-skill-count.py, EXTRACTED each enumeration from raw Markdown with regex and set-compared it.
Four independent review rounds each found a silent-pass decoy; the last (6f66dfa) was a markup-hidden
one — a canonical run in an HTML comment / code span right after the introducing anchor, masking a
BROKEN visible list. No regex can distinguish the intended RENDERED enumeration from a markup-hidden
decoy when the docs themselves use markup, because the extractor searches the document for "a run that
looks like the list" and a hidden run can BE the match.

This replaces parsing with generation. Each enumeration is generated from one source of truth and checked
at a FAIL-CLOSED marked location, so there is no "which run is the real one" question to get wrong — the
whole decoy class disappears (see docs/adr/0001-generate-skill-enumerations.md).

Source of truth:
  - SET   = skills/<name>/ holding a SKILL.md  (canonical_skills()).
  - ORDER = the root `skills-order` file (one skill per line), validated as an EXACT PERMUTATION of the
            set (missing / extra / duplicate / unknown -> fail closed). All five sites share this order.

Per-site strategy (ADR 0001, Plan B):
  - Three PURE sites (improve-order, pick-list, repo tree) are generated in FULL and checked
    BYTE-IDENTICAL — zero document parsing.
  - Two TABLE sites keep their editorial columns authored inline; only their NAME column is checked,
    POSITIONALLY within the fail-closed marked region (extraction == a visible |-leading row), so a
    markup-hidden decoy row cannot be read and a broken visible table fails.
  - The scalar COUNT phrases ("a suite of eight", ...) are checked by anchored regex. A scalar has no
    "which list is real" ambiguity, so it is not part of the decoy class.

Markers fail closed: for each site, exactly one begin and one end marker, end after begin, both present —
otherwise the check FAILS (never skips an absent/ambiguous region; skipping is the silent-pass we remove).

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

# Canonical suite-count phrases, anchored so a sub-count / N-1 / history line never matches. Carried
# verbatim from the retired lint-skill-count.py (a scalar count is not subject to the decoy class).
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
    """Raised when a site's begin/end markers are absent, duplicated, or malformed — always fail closed."""


def canonical_skills(root: Path) -> set[str]:
    """The source of truth for the SET: every skills/<name>/ that holds a SKILL.md."""
    sk = root / "skills"
    if not sk.is_dir():
        return set()
    return {p.name for p in sk.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()}


def validate_order(order: list[str], canonical: set[str]) -> list[str]:
    """Validate `order` is an EXACT permutation of `canonical`. Returns a list of error strings (empty =
    valid). Fail-closed inputs: a duplicate line, a missing skill, or an unknown/extra name each error."""
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
    """README repo-tree skills/ block: one `│  ├─ name/` per skill, `└─` on the last node."""
    out = []
    for i, name in enumerate(order):
        glyph = "└─" if i == len(order) - 1 else "├─"
        out.append(f"│  {glyph} {name}/")
    return "\n".join(out)


# ---- markers (fail closed) ----------------------------------------------------------------------

def _marker_span(lines: list[str], site_id: str) -> tuple[int, int]:
    """Indices of the single begin/end marker lines for `site_id`. Fail closed: a missing, duplicated, or
    out-of-order marker raises MarkerError (never silently skips the region)."""
    begin_tok, end_tok = f"skills:{site_id}:begin", f"skills:{site_id}:end"
    begins = [i for i, ln in enumerate(lines) if begin_tok in ln]
    ends = [i for i, ln in enumerate(lines) if end_tok in ln]
    if len(begins) != 1 or len(ends) != 1:
        raise MarkerError(f"site '{site_id}': expected exactly one begin and one end marker, "
                          f"found {len(begins)} begin / {len(ends)} end")
    if ends[0] <= begins[0]:
        raise MarkerError(f"site '{site_id}': end marker is not after the begin marker")
    return begins[0], ends[0]


def extract_marked_block(text: str, site_id: str) -> str:
    """The exact bytes strictly between `site_id`'s begin and end markers. Fail closed via _marker_span."""
    lines = text.split("\n")
    b, e = _marker_span(lines, site_id)
    return "\n".join(lines[b + 1:e])


def extract_table_names(block: str) -> list[str]:
    """First-column skill names of every visible |-leading table row in `block`, in order. A non-|-leading
    line (an HTML comment, a code span, prose) is not a row and is never read — extraction == a rendered
    table row, which is what closes the markup-hidden-decoy class for the tables."""
    out: list[str] = []
    for line in block.split("\n"):
        m = re.match(r"\s*\|\s*\*{0,2}([a-z0-9][a-z0-9-]*)", line)
        if m:
            out.append(m.group(1))
    return out


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
                continue  # phrase present but reworded to a non-count form — nothing to verify
            if val != n:
                out.append(f"{file_label}: \"{label}\" says \"{tok}\" ({val}) "
                           f"but there are {n} skills in skills/")
    return out


# file, human label, renderer — the three fully-generated, byte-identical sites
PURE_SITES = [
    ("improve-order", README, render_improve_order),
    ("pick-list", PROMPT, render_pick_list),
    ("tree", README, render_tree),
]
# file — the two tables: name column checked positionally, editorial columns authored inline
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
    (empty = clean). Fails closed on an invalid skills-order or any malformed/absent marker."""
    canonical = canonical_skills(root)
    if not canonical:
        return []  # absence of skills/ is not this check's job to report
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
            findings.append(f"{fname}: '{site_id}' name column {names} does not equal the order "
                            f"{order} (fix the table to match skills-order)")

    for fname, phrases in COUNT_PHRASES.items():
        text = _read(root, fname)
        if text is not None:
            findings += check_count_phrases(text, phrases, n, fname)

    return findings


def write(root: Path) -> int:
    """Fill the three pure marked blocks in place from skills-order. Tables are left to the author (only
    their name column is checked). Fails closed on an invalid order or a malformed/absent marker."""
    canonical = canonical_skills(root)
    order, errs = load_order(root, canonical)
    if errs:
        raise ValueError("; ".join(errs))
    written = 0
    for site_id, fname, renderer in PURE_SITES:
        p = root / fname
        text = p.read_text(encoding="utf-8")
        lines = text.split("\n")
        b, e = _marker_span(lines, site_id)            # fail closed
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
                    help="Verify every marked site is byte-identical / name-ordered (exit 1 on drift). "
                         "Default (no --check) WRITES the three pure blocks in place.")
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
    print("--- skill-enumerations: clean (all 5 sites generated/checked + the count phrases hold) ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
