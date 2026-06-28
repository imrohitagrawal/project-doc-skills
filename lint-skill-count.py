#!/usr/bin/env python3
"""
lint-skill-count.py — suite-level skill-enumeration guard (WARN by default).

README.md and per-skill-review-prompt.md are root scaffolding: NOT bundled into any .skill, so they
are invisible to validate_skill.py, the render/placeholder lints, and check-version.py. That blind
spot let the suite's skill ENUMERATION drift twice (both fixed in the doc-critic PR, b65041f) — and
the drift touched SEVERAL sites, not just a count. This lint closes the blind spot: it derives the
canonical skill set from skills/<name>/ and asserts that EVERY enumeration site in both files lists
exactly that set.

What it checks (each an exact directory-vs-document set comparison):
  README.md
    - the skill TABLE        — first-column bolded names: | **name** | ... |
    - the repo TREE          — the skills/ block's child entries: │  ├─ name/
    - the improve-order LIST — the "→"-separated producer-before-consumer order
  per-skill-review-prompt.md
    - the {SKILL_NAME} PICK-LIST — the "·"-separated enumeration
    - the attachment TABLE       — first-column names: | name | attach... |
  Plus the suite COUNT (word OR digit) in specific canonical phrases only — "a suite of N ... skills",
  "N copies of the house style", "build all N"; "N-skill ... suite", "now **N** skills" — with EVERY
  occurrence checked, not just the first.

Why it is low-false-positive by design:
  - Every site check is an exact set comparison (no prose heuristics); the "→"/"·" lists are picked as
    the run that best matches the skill set, and the two tables are scoped by their row shape, so an
    unrelated list/table cannot pollute them.
  - The count checks are anchored to SPECIFIC suite-count phrases, so the legitimate "the other seven
    skills" (N-1), "Six [authoring skills] turn ..." (a sub-count), and a dated "all seven skills were
    clean" history line never match. A non-numeric capture and a reworded-away phrase are skipped — a
    wrong count can only exist if its phrase exists, and the exact set checks remain the real guard.

WARN by default (exit 0). --strict exits 1 on any finding; build-skills.sh runs it with --strict so a
drift fails the suite gate. Running by hand defaults to WARN.

Usage:
    python3 lint-skill-count.py [repo_root] [--strict]
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

# Canonical suite-count phrases, anchored so a sub-count / N-1 / history line never matches.
README_COUNT_PHRASES = [
    (re.compile(r"suite of (\w+) independent", re.IGNORECASE), "a suite of <N> independent ... skills"),
    (re.compile(r"(\w+) copies of the house style", re.IGNORECASE), "<N> copies of the house style"),
    (re.compile(r"build all (\w+)", re.IGNORECASE), "build all <N>"),
]
PROMPT_COUNT_PHRASES = [
    (re.compile(r"(\w+)-skill documentation suite", re.IGNORECASE), "<N>-skill documentation suite"),
    (re.compile(r"now \*\*(\w+)\*\* skills", re.IGNORECASE), "now **<N>** skills"),
]


def canonical_skills(root: Path) -> set[str]:
    """The source of truth: every skills/<name>/ that holds a SKILL.md."""
    sk = root / "skills"
    if not sk.is_dir():
        return set()
    return {p.name for p in sk.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()}


# ---- per-site extractors: each takes (text, canonical) and returns the set of skill names it finds
#      (an empty set means "site not locatable" — itself a finding) -------------------------------

def readme_table_skills(text: str, _canonical: set[str]) -> set[str]:
    """Bolded skill names in the README skill table's first column: | **name** | ... |."""
    return set(re.findall(r"^\|\s*\*\*([a-z0-9][a-z0-9-]*)\*\*\s*\|", text, re.MULTILINE))


def readme_tree_skills(text: str, _canonical: set[str]) -> set[str]:
    """Child dir entries of the skills/ node in the repo tree: │  ├─ name/ (scoped to that block so
    the sibling shared/ block cannot pollute it)."""
    out: set[str] = set()
    in_block = False
    for line in text.splitlines():
        if re.match(r"^[├└]─\s+skills/", line):
            in_block = True
            continue
        if in_block:
            if re.match(r"^[├└]─\s", line):      # next top-level tree node ends the skills block
                break
            m = re.match(r"^│\s+[├└]─\s+([a-z0-9][a-z0-9-]*)/", line)
            if m:
                out.add(m.group(1))
    return out


def attach_table_skills(text: str, _canonical: set[str]) -> set[str]:
    """First-column (un-bolded) skill names in the per-skill-prompt attachment table: | name | ... |."""
    return set(re.findall(r"^\|\s*([a-z][a-z0-9-]+)\s*\|", text, re.MULTILINE))


def _separated_run(text: str, sep: str, canonical: set[str]) -> set[str]:
    """The <sep>-separated run of kebab names that best matches the canonical set (so an unrelated list
    of the same shape cannot pollute it). Empty set if no run with >= 2 known skills is found."""
    esep = re.escape(sep)
    best: set[str] = set()
    best_overlap = 1   # require >= 2 known skills to treat a run as the skill list
    for run in re.findall(rf"[a-z][a-z0-9-]+(?:\s*{esep}\s*[a-z][a-z0-9-]+)+", text):
        names = set(re.split(rf"\s*{esep}\s*", run.strip()))
        overlap = len(names & canonical)
        if overlap > best_overlap:
            best, best_overlap = names, overlap
    return best


def improve_order_skills(text: str, canonical: set[str]) -> set[str]:
    return _separated_run(text, "→", canonical)   # "→"


def pick_list_skills(text: str, canonical: set[str]) -> set[str]:
    return _separated_run(text, "·", canonical)   # "·"


# file, human label, extractor
SITES = [
    ("README.md", "skill table", readme_table_skills),
    ("README.md", "repo tree (skills/ block)", readme_tree_skills),
    ("README.md", "improve-order list", improve_order_skills),
    ("per-skill-review-prompt.md", "{SKILL_NAME} pick-list", pick_list_skills),
    ("per-skill-review-prompt.md", "attachment table", attach_table_skills),
]
COUNT_PHRASES = {
    "README.md": README_COUNT_PHRASES,
    "per-skill-review-prompt.md": PROMPT_COUNT_PHRASES,
}


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


def main() -> int:
    ap = argparse.ArgumentParser(description="Suite lint: README/per-skill-prompt skill-enumeration guard (WARN-only).")
    here = Path(__file__).resolve().parent
    ap.add_argument("root", nargs="?", default=str(here),
                    help="Repo root (default: the directory containing this script).")
    ap.add_argument("--strict", action="store_true",
                    help="Exit 1 on any finding (gate use; default is WARN/exit 0).")
    args = ap.parse_args()
    root = Path(args.root)

    canonical = canonical_skills(root)
    if not canonical:
        print(f"lint-skill-count: no skills found under {root / 'skills'}")
        return 0  # absence of the tree is not this lint's failure to report
    n = len(canonical)

    # Read each scaffolding file once.
    texts: dict[str, str | None] = {}
    for fname in {f for f, _, _ in SITES} | set(COUNT_PHRASES):
        p = root / fname
        texts[fname] = p.read_text(encoding="utf-8", errors="ignore") if p.is_file() else None

    findings: list[str] = []

    for fname, label, extractor in SITES:
        text = texts[fname]
        if text is None:
            findings.append(f"{fname}: not found at {root / fname}")
            continue
        found = extractor(text, canonical)
        if not found:
            findings.append(f"{fname}: could not locate the {label} "
                            f"(its shape changed — re-confirm it lists every skill)")
        elif found != canonical:
            missing = ", ".join(sorted(canonical - found)) or "none"
            extra = ", ".join(sorted(found - canonical)) or "none"
            findings.append(f"{fname}: {label} does not match skills/ "
                            f"(missing: {missing}; not a skill: {extra})")

    for fname, phrases in COUNT_PHRASES.items():
        text = texts[fname]
        if text is not None:
            findings += check_count_phrases(text, phrases, n, fname)

    for f in findings:
        print(f"   warn  skill-count: {f}")
    if findings:
        print(f"--- skill-count lint: {len(findings)} warning(s) "
              f"(every enumeration site in README + per-skill-review-prompt must list the {n} skills "
              f"in skills/) ---")
    else:
        print(f"--- skill-count lint: clean (all 5 enumeration sites + the count phrases name the "
              f"{n} skills in skills/) ---")
    return 1 if (args.strict and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
