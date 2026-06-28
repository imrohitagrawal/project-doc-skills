#!/usr/bin/env python3
"""
gate-review-check.py — the required status check that enforces an independent gate-review.

WHY THIS EXISTS
  CI passing is necessary but NOT sufficient for the gate layer. A change can be green
  the whole way and still ship a check that guards less than it claims (a lint that
  printed "clean" while it inspected 2 of 5 enumeration sites) or a gate whose own
  self-description drifted (release-gate.sh saying "two lints" once a third was added).
  Those are judgement failures a green build cannot see. So a pull request that touches
  the gate layer (see .github/gate-paths) must additionally carry an independent
  gate-review, run with gate-review-prompt.md and recorded as a committed verdict under
  gate-reviews/. This script is the machine half: it does NOT judge the change — it
  asserts that the independent review was run and recorded, with evidence, before merge.

WHAT IT CHECKS (for the changed-file set of a PR)
  1. Does the PR touch any gate-layer path? (matched against .github/gate-paths)
       no  -> PASS: an independent gate-review is not required for this change.
       yes -> a verdict is required; continue.
  2. Is there a verdict file ADDED/MODIFIED in this PR under gate-reviews/ that is
     well-formed? "Well-formed" requires EVIDENCE, not just a stamp:
       - it names the gate-review-prompt.md version it ran,
       - it carries the four mandated lens sections (replay-the-real-failure,
         coverage-vs-advertising, self-description-drift, fixture-requirement),
       - the replay section carries a coverage figure (N/M) — the evidence that the
         real failure was reproduced and its coverage measured, not a synthetic mutation,
       - it has a Findings section,
       - it ends with an explicit `Verdict: PASS`.
     A verdict that is malformed, or whose verdict line is BLOCK/FAIL, FAILS this check
     (a failed or rubber-stamped review must not merge).

FAIL-CLOSED. Any setup or IO error (missing .github/gate-paths, unreadable diff) exits
NON-ZERO. A gate that errors *open* is itself the silent bypass; this one blocks on doubt.

EXIT CODES
  0  ok      — no gate-layer change, or a well-formed PASS verdict is present.
  1  blocked — gate-layer change without a well-formed PASS verdict (the review is owed).
  2  error   — could not evaluate (treated as blocking by CI; never a silent pass).

USAGE
  # explicit file list (local testing — verify, don't assume):
  python3 gate-review-check.py path/a path/b ...
  # newline-separated paths on stdin:
  git diff --name-only BASE...HEAD | python3 gate-review-check.py --stdin
  # compute the PR diff itself (CI):
  python3 gate-review-check.py --base "$BASE_SHA" --head "$HEAD_SHA"
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GATE_PATHS_FILE = ROOT / ".github" / "gate-paths"
VERDICT_DIR = "gate-reviews"
# Files under gate-reviews/ that are scaffolding, not a verdict for a specific PR.
VERDICT_NON_RECORDS = {"TEMPLATE.md", "README.md"}

# A verdict's required shape. Each is a low-false-positive structural marker; together
# they require the reviewer to have produced EVIDENCE, so a one-line rubber stamp fails.
PROMPT_VERSION_RE = re.compile(r"gate-review-prompt\.md\s+v\d+\.\d+\.\d+", re.IGNORECASE)
COVERAGE_RE = re.compile(r"coverage\b[^\n]*?\b\d+\s*/\s*\d+", re.IGNORECASE)
VERDICT_PASS_RE = re.compile(r"^\s*verdict:\s*pass\b", re.IGNORECASE | re.MULTILINE)
VERDICT_ANY_RE = re.compile(r"^\s*verdict:\s*(\w+)", re.IGNORECASE | re.MULTILINE)
# Required section headings (matched as a heading line, any level), by friendly name.
REQUIRED_SECTIONS = {
    "replay-the-real-failure": re.compile(r"^#{1,6}\s.*replay", re.IGNORECASE | re.MULTILINE),
    "coverage-vs-advertising": re.compile(r"^#{1,6}\s.*coverage\s+vs", re.IGNORECASE | re.MULTILINE),
    "self-description-drift": re.compile(r"^#{1,6}\s.*self-description", re.IGNORECASE | re.MULTILINE),
    "fixture-requirement": re.compile(r"^#{1,6}\s.*fixture", re.IGNORECASE | re.MULTILINE),
    "findings": re.compile(r"^#{1,6}\s.*findings", re.IGNORECASE | re.MULTILINE),
}


def die(msg: str, code: int = 2) -> "NoReturn":  # noqa: F821 - typing.NoReturn without import
    """Fail closed: print a setup/IO error and exit non-zero so CI blocks."""
    print(f"gate-review-check: ERROR — {msg}")
    raise SystemExit(code)


def load_gate_patterns(path: Path) -> list[str]:
    if not path.is_file():
        die(f"{path} not found — the canonical gate-path list is missing; cannot evaluate.")
    patterns: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        patterns.append(s)
    if not patterns:
        die(f"{path} has no patterns — refusing to treat every change as ungated.")
    return patterns


def matches_gate(rel_path: str, patterns: list[str]) -> str | None:
    """Return the pattern that classifies rel_path as gate-layer, or None. Semantics match
    the header of .github/gate-paths: trailing-'/' = subtree, '*' = fnmatch, else exact."""
    base = rel_path.rsplit("/", 1)[-1]
    for pat in patterns:
        if pat.endswith("/"):
            if rel_path == pat[:-1] or rel_path.startswith(pat):
                return pat
        elif "*" in pat:
            if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(base, pat):
                return pat
        elif rel_path == pat:
            return pat
    return None


def changed_from_git(base: str, head: str) -> list[str]:
    """The PR's changed files: diff over merge-base(base, head)..head (GitHub PR semantics)."""
    try:
        r = subprocess.run(
            ["git", "-C", str(ROOT), "diff", "--name-only", f"{base}...{head}"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:  # noqa: BLE001 - any git failure must fail closed
        die(f"could not run git diff {base}...{head}: {e}")
    if r.returncode != 0:
        die(f"git diff {base}...{head} failed: {r.stderr.strip() or 'non-zero exit'}")
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]


def verdict_problems(text: str) -> list[str]:
    """Return the list of shape problems with a verdict file; empty list == well-formed PASS."""
    problems: list[str] = []
    if not PROMPT_VERSION_RE.search(text):
        problems.append("does not name the gate-review-prompt.md version it ran "
                        "(expected e.g. 'gate-review-prompt.md v1.0.0')")
    for name, rx in REQUIRED_SECTIONS.items():
        if not rx.search(text):
            problems.append(f"missing the '{name}' section")
    if not COVERAGE_RE.search(text):
        problems.append("no coverage figure (expected a 'Coverage: N/M' line proving the real "
                        "failure was replayed and its coverage measured)")
    m = VERDICT_ANY_RE.search(text)
    if not m:
        problems.append("no explicit 'Verdict: PASS' line")
    elif not VERDICT_PASS_RE.search(text):
        problems.append(f"verdict is '{m.group(1).upper()}', not PASS — a failed/blocked review "
                        f"must not merge until resolved")
    return problems


def find_verdict(changed: list[str]) -> tuple[str | None, dict[str, list[str]]]:
    """Among changed gate-reviews/*.md records, return (path_of_first_well_formed_PASS, all_problems)."""
    problems_by_file: dict[str, list[str]] = {}
    candidates = [
        c for c in changed
        if c.startswith(VERDICT_DIR + "/")
        and c.endswith(".md")
        and c.rsplit("/", 1)[-1] not in VERDICT_NON_RECORDS
    ]
    for c in candidates:
        p = ROOT / c
        if not p.is_file():
            problems_by_file[c] = ["listed as changed but not present on disk"]
            continue
        probs = verdict_problems(p.read_text(encoding="utf-8", errors="ignore"))
        if not probs:
            return c, problems_by_file
        problems_by_file[c] = probs
    return None, problems_by_file


def get_changed(args: argparse.Namespace) -> list[str]:
    if args.changed:
        return [c.strip() for c in args.changed if c.strip()]
    if args.stdin:
        return [ln.strip() for ln in sys.stdin.read().splitlines() if ln.strip()]
    if args.base and args.head:
        return changed_from_git(args.base, args.head)
    die("no changed-file source given (pass paths as arguments, or use --stdin, or --base & --head).")


def main() -> int:
    ap = argparse.ArgumentParser(description="Required check: enforce an independent gate-review on "
                                             "gate-layer PRs (see CONTRIBUTING.md).")
    ap.add_argument("changed", nargs="*", help="changed file paths (repo-root-relative).")
    ap.add_argument("--stdin", action="store_true", help="read newline-separated paths from stdin.")
    ap.add_argument("--base", help="base ref/SHA (with --head, compute the PR diff via git).")
    ap.add_argument("--head", help="head ref/SHA (with --base).")
    args = ap.parse_args()

    patterns = load_gate_patterns(GATE_PATHS_FILE)
    changed = get_changed(args)
    if not changed:
        print("gate-review-check: no changed files detected — nothing to evaluate. PASS.")
        return 0

    touched = sorted({c: pat for c in changed if (pat := matches_gate(c, patterns))}.items())
    if not touched:
        print(f"gate-review-check: PASS — none of the {len(changed)} changed file(s) are in the "
              f"gate layer; an independent gate-review is not required.")
        return 0

    print(f"gate-review-check: this PR touches the gate layer ({len(touched)} path(s)):")
    for c, pat in touched:
        print(f"    • {c}   (matched: {pat})")

    verdict_path, problems = find_verdict(changed)
    if verdict_path:
        print(f"gate-review-check: PASS — well-formed PASS verdict present: {verdict_path}")
        return 0

    print("gate-review-check: BLOCKED — a gate-layer change requires an independent gate-review.")
    if problems:
        print("  A gate-reviews/ record was changed but is not a well-formed PASS:")
        for f, probs in problems.items():
            for pr in probs:
                print(f"    - {f}: {pr}")
    else:
        print("  No gate-reviews/ verdict was added/modified in this PR.")
    print("  To clear this check: run ./gate-review-prompt.md (independent, blind), then commit "
          "the verdict under gate-reviews/ (see gate-reviews/TEMPLATE.md). CI green is necessary, "
          "not sufficient, for the gate layer — see CONTRIBUTING.md.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
