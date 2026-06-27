#!/usr/bin/env python3
"""
lint-skill-count.py — suite-level skill-enumeration guard (WARN by default).

README.md and per-skill-review-prompt.md are root scaffolding: they are NOT bundled into any .skill,
so they are invisible to validate_skill.py, the render/placeholder lints, and check-version.py. That
blind spot let the suite's skill ENUMERATION drift twice — a stale "seven skills" count, and a skill
table / pick-list missing a row — and ship uncaught (both fixed in the doc-critic PR). This lint
closes the blind spot: it derives the canonical skill set from skills/<name>/ and asserts the two
scaffolding files agree with it.

What it checks (against the live skills/*/ directory set):
  README.md
    - the skill TABLE: every skills/<name>/ has a row, and every bolded row names a real skill (exact
      set equality — no prose heuristics).
    - the suite COUNT word, only in specific canonical phrases ("a suite of <word> ... skills",
      "<word> copies of the house style", "build all <word>").
  per-skill-review-prompt.md
    - the {SKILL_NAME} PICK-LIST: the "·"-separated skill enumeration equals the directory set (exact).
    - the suite COUNT word, only in "<word>-skill ... suite" and "now **<word>** skills".

Why it is low-false-positive by design:
  - The set checks are exact directory-vs-document comparisons.
  - The count-word checks are anchored to SPECIFIC suite-count phrases, so they never fire on the
    legitimate "the other seven skills" (N-1), "Six [authoring skills] turn ..." (a sub-count), or a
    dated "all seven skills were clean" history line. A captured token that is not a number word, and
    a phrase reworded away, are both skipped — a wrong count can only exist if its phrase exists, and
    the exact set checks remain the real guard.

WARN by default (exit 0). --strict exits 1 on any finding; build-skills.sh runs it with --strict so a
drift fails the suite gate. Running by hand defaults to WARN.

Usage:
    python3 lint-skill-count.py [repo_root] [--strict]
    (repo_root defaults to the directory containing this script)
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

# Canonical suite-count phrases. Each captures the number word; {f} is the file label for the message.
# Deliberately specific so "the other seven skills", "Six turn ...", and "all seven skills were clean"
# (a dated history line) never match.
README_COUNT_PHRASES = [
    (re.compile(r"suite of (\w+) independent", re.IGNORECASE), "a suite of <word> independent ... skills"),
    (re.compile(r"(\w+) copies of the house style", re.IGNORECASE), "<word> copies of the house style"),
    (re.compile(r"build all (\w+)", re.IGNORECASE), "build all <word>"),
]
PROMPT_COUNT_PHRASES = [
    (re.compile(r"(\w+)-skill documentation suite", re.IGNORECASE), "<word>-skill documentation suite"),
    (re.compile(r"now \*\*(\w+)\*\* skills", re.IGNORECASE), "now **<word>** skills"),
]


def canonical_skills(root: Path) -> set[str]:
    """The source of truth: every skills/<name>/ that holds a SKILL.md."""
    sk = root / "skills"
    return {p.name for p in sk.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()}


def readme_table_skills(text: str) -> set[str]:
    """Bolded skill names in the README skill table's first column: | **name** | ... |."""
    return set(re.findall(r"^\|\s*\*\*([a-z0-9][a-z0-9-]*)\*\*\s*\|", text, re.MULTILINE))


def pick_list_skills(text: str, canonical: set[str]) -> set[str] | None:
    """The "·"-separated {SKILL_NAME} pick-list, identified as the · -run that most resembles the
    skill set (so an unrelated · list cannot pollute it, and a missing/extra name still flags on the
    exact-equality assertion the caller makes). Returns None if no · -run looks like the skill list."""
    best: set[str] | None = None
    best_overlap = 0
    for run in re.findall(r"[a-z][a-z0-9-]+(?:\s*·\s*[a-z][a-z0-9-]+)+", text):
        names = set(re.split(r"\s*·\s*", run.strip()))
        overlap = len(names & canonical)
        if overlap > best_overlap:
            best, best_overlap = names, overlap
    return best if best_overlap >= 2 else None


def check_count_phrases(text: str, phrases, n: int, file_label: str) -> list[str]:
    """For each canonical phrase present with a recognised number word, flag a wrong count."""
    out = []
    for pat, label in phrases:
        m = pat.search(text)
        if not m:
            continue
        word = m.group(1).lower()
        if word not in WORD_TO_NUM:
            continue  # phrase present but reworded to a non-count form — nothing to verify
        if WORD_TO_NUM[word] != n:
            out.append(f"{file_label}: \"{label}\" says \"{word}\" ({WORD_TO_NUM[word]}) "
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

    findings: list[str] = []

    # README.md — table set + count words.
    readme = root / "README.md"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8", errors="ignore")
        table = readme_table_skills(text)
        if table != canonical:
            missing = ", ".join(sorted(canonical - table)) or "none"
            extra = ", ".join(sorted(table - canonical)) or "none"
            findings.append(f"README.md: skill table does not match skills/ "
                            f"(missing rows: {missing}; rows naming no skill: {extra})")
        findings += check_count_phrases(text, README_COUNT_PHRASES, n, "README.md")
    else:
        findings.append(f"README.md not found at {readme}")

    # per-skill-review-prompt.md — pick-list set + count words.
    prompt = root / "per-skill-review-prompt.md"
    if prompt.is_file():
        text = prompt.read_text(encoding="utf-8", errors="ignore")
        picks = pick_list_skills(text, canonical)
        if picks is None:
            findings.append("per-skill-review-prompt.md: could not locate the · -separated skill "
                            "pick-list (its shape changed — re-confirm it lists every skill)")
        elif picks != canonical:
            missing = ", ".join(sorted(canonical - picks)) or "none"
            extra = ", ".join(sorted(picks - canonical)) or "none"
            findings.append(f"per-skill-review-prompt.md: {{SKILL_NAME}} pick-list does not match "
                            f"skills/ (missing: {missing}; not a skill: {extra})")
        findings += check_count_phrases(text, PROMPT_COUNT_PHRASES, n, "per-skill-review-prompt.md")
    else:
        findings.append(f"per-skill-review-prompt.md not found at {prompt}")

    for f in findings:
        print(f"   warn  skill-count: {f}")
    if findings:
        print(f"--- skill-count lint: {len(findings)} warning(s) "
              f"(README + per-skill-review-prompt must enumerate the {n} skills in skills/) ---")
    else:
        print(f"--- skill-count lint: clean (README table + pick-list + count words all name the "
              f"{n} skills in skills/) ---")
    return 1 if (args.strict and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
