#!/usr/bin/env python3
"""
run-golden.py — the regression that guards the gates themselves (root scaffolding; never bundled).

This whole workstream exists because a generator once shipped a page that failed its own gate, and a
gate could be quietly weakened to a no-op without anyone noticing. Two unit tests of a doc gate are not
enough on their own: you also need fixtures that lock BOTH directions, so a future refactor that turns a
check into a no-op is caught.

What it locks
  golden-good (must pass with 0 FAIL):
    - an FAQ HTML page produced by the LIVE faq_generator        -> verify.py 0 FAIL  (internal scope)
    - a usage-guide HTML page produced by the LIVE generator     -> verify.py 0 FAIL  (public scope)
    - a hand-written learning-track Markdown module              -> verify.py 0 FAIL  (public scope)
    The two HTML goldens are GENERATED here from the committed generators (not stored), so if a
    generator regresses and stops emitting its © footer / credits / ISO stamp, this test fails — the
    exact original-sin failure.
  golden-bad (each must be CAUGHT by the right gate):
    - a public page with no © footer            -> verify.py FAIL (licensing gate)
    - a real-shaped AWS access key on a page     -> verify.py FAIL (secret/PII scan)
    - a years-old ISO last-reviewed stamp        -> verify.py WARN (staleness; WARN-only by design)
    - a SKILL.md publish step restating the map  -> render-restatement lint CAUGHT
  Deterministic pins (today-pinned / non-default threshold, so a silent fallback cannot pass green):
    - staleness boundary at --max-age-months 3 and a pinned today (old->WARN, recent->INFO,
      future->WARN, and BOTH bold-label forms still read — the regression lock for the bold-label fix)
    - a Flesch-Kincaid grade pin on a fixed string (so "simplify until green" cannot game the gate by
      turning readability into a no-op)

Run by hand or from the release gate:
    python3 tests/run-golden.py            # exit 0 if every assertion holds, 1 otherwise
    python3 tests/run-golden.py -v         # also print each verifier's resolved-values line

Self-contained: drives the REAL shared/verify.py CLI (what CI runs) for the produced-doc checks, and
imports verify.py / lint-render-restatement.py for the function-level pins. No third-party deps.
"""
from __future__ import annotations
import argparse
import datetime as _dt
import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED_VERIFY = ROOT / "shared" / "verify.py"
PROFILE = ROOT / "shared" / "project-profile.md"
LRR = ROOT / "lint-render-restatement.py"
FAQ_GEN = ROOT / "skills" / "project-faq" / "assets" / "faq_generator.py"
UG_GEN = ROOT / "skills" / "usage-guide" / "assets" / "usage_guide_generator.py"
GOLDEN_GOOD = ROOT / "tests" / "golden-good"
GOLDEN_BAD = ROOT / "tests" / "golden-bad"

# Pinned so a stamp-bearing golden stays "within window" regardless of when the suite is built; the
# golden-good assertion is 0 FAIL (a staleness WARN would still be allowed), and the EXACT staleness
# boundary is pinned separately in the function-level tests below.
PINNED_REVIEW_DATE = "2026-06-15"
GOLDEN_MAX_AGE = "12"   # non-default threshold (built-in is 6), so the verifier must READ the flag

# A fixed string whose Flesch-Kincaid grade is pinned. If a future edit turns the readability gate into
# a no-op, or the FK maths drifts materially, this band breaks. The band is tight but tolerant of a
# rounding-level tweak (measured 2.1 on the current implementation).
READABILITY_PIN_TEXT = (
    "A request comes in at one end and a result goes out at the other. In "
    "between, it passes through five steps. Each step does one job and hands "
    "the work to the next. You do not need to read any code to follow it. If "
    "you can name the five steps, you can trace a request from start to end."
)
READABILITY_BAND = (1.5, 2.7)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Results:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def check(self, ok: bool, name: str, detail: str = "") -> None:
        tag = "PASS" if ok else "FAIL"
        if ok:
            self.passed += 1
        else:
            self.failed += 1
        line = f"  [{tag}] {name}"
        if detail:
            line += f" — {detail}"
        print(line)


def run_verify(target: Path, fmt: str, skill: str, scope: str, grade: str,
               max_age: str = GOLDEN_MAX_AGE):
    """Drive the real shared/verify.py CLI (the path CI runs). Returns (returncode, combined_output)."""
    argv = [sys.executable, str(SHARED_VERIFY), str(target),
            "--format", fmt, "--skill", skill, "--scope", scope,
            "--grade-target", grade, "--profile", str(PROFILE),
            "--max-age-months", max_age]
    p = subprocess.run(argv, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def _fail_count(output: str) -> int | None:
    m = re.search(r"---\s*summary:.*?(\d+)\s+FAIL", output)
    return int(m.group(1)) if m else None


def _resolved_line(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("resolved:"):
            return line
    return "(no resolved line)"


def golden_good(res: Results, verbose: bool) -> None:
    print("golden-good — produced docs must pass with 0 FAIL:")
    tmp = Path(tempfile.mkdtemp(prefix="golden-good-"))

    # 1+2. Generate the two HTML goldens from the LIVE generators (pinned review date), then verify.
    faq = _load("faqgen", FAQ_GEN)
    ug = _load("uggen", UG_GEN)

    faq_doc = faq._demo()
    faq_doc["last_reviewed"] = PINNED_REVIEW_DATE
    faq_out = tmp / "faq.html"
    faq.build_faq(faq_doc, faq_out)

    ug_doc = ug._demo()
    ug_doc["last_reviewed"] = PINNED_REVIEW_DATE
    ug_out = tmp / "usage-guide.html"
    ug.build_usage_guide(ug_doc, ug_out)

    cases = [
        ("FAQ HTML (generated, internal scope)", faq_out, "html", "project-faq", "internal", "8"),
        ("usage-guide HTML (generated, public scope)", ug_out, "html", "usage-guide", "public", "2"),
        ("learning-track module (Markdown, public scope)",
         GOLDEN_GOOD / "learning-track-module.md", "md", "learning-track", "public", "9"),
    ]
    for name, target, fmt, skill, scope, grade in cases:
        rc, out = run_verify(target, fmt, skill, scope, grade)
        fails = _fail_count(out)
        ok = (rc == 0 and fails == 0)
        detail = f"{_resolved_line(out)}" if verbose else f"exit {rc}, {fails} FAIL"
        res.check(ok, name, detail)


def golden_bad(res: Results, verbose: bool) -> None:
    print("golden-bad — each broken doc must be caught by the right gate:")

    # 1. Missing © on a public page -> licensing gate FAIL (exit 1).
    rc, out = run_verify(GOLDEN_BAD / "missing-copyright.html", "html", "project-faq", "public", "8")
    ok = (rc == 1 and "licence footer" in out.lower())
    res.check(ok, "missing-© public page -> licensing FAIL",
              _resolved_line(out) if verbose else f"exit {rc}")

    # 2. Real-shaped AWS access key -> secret/PII scan FAIL (exit 1).
    rc, out = run_verify(GOLDEN_BAD / "leaked-credential.md", "md", "operations-runbook", "internal", "10")
    ok = (rc == 1 and "aws access key" in out.lower())
    res.check(ok, "AWS access key on page -> secret-scan FAIL",
              _resolved_line(out) if verbose else f"exit {rc}")

    # 3. Years-old ISO stamp -> staleness WARN (WARN-only: exit 0, 0 FAIL, a stale warning present).
    rc, out = run_verify(GOLDEN_BAD / "stale-stamp.md", "md", "project-faq", "internal", "8",
                         max_age="6")
    low = out.lower()
    ok = (rc == 0 and _fail_count(out) == 0
          and "last reviewed 2019-03-01" in low and "threshold" in low)
    res.check(ok, "years-old stamp -> staleness WARN (no FAIL)",
              _resolved_line(out) if verbose else f"exit {rc}, {_fail_count(out)} FAIL")

    # 4. Restated render mapping in a SKILL.md -> render-restatement lint CAUGHT.
    lrr = _load("lrr", LRR)
    findings = lrr.scan_skill(GOLDEN_BAD / "restated-mapping" / "SKILL.md")
    ok = len(findings) >= 1
    detail = (", ".join(f"L{ln}:{txt!r}" for ln, txt in findings)) if verbose else f"{len(findings)} finding(s)"
    res.check(ok, "restated render mapping -> render-restatement CAUGHT", detail)


def deterministic_pins(res: Results, verbose: bool) -> None:
    print("deterministic pins — today-pinned, non-default threshold:")
    v = _load("verify", SHARED_VERIFY)
    today = _dt.date(2026, 6, 22)
    age = 3  # non-default threshold (built-in 6); proves the threshold is read, not assumed

    def staleness_level(raw: str) -> str:
        return v.check_staleness(raw, age, today=today)[0][0]

    stale_cases = [
        ("old ISO 2026-01-01 -> WARN", "Last reviewed: 2026-01-01", "WARN"),
        ("recent ISO 2026-05-01 -> INFO (within window)", "Last reviewed: 2026-05-01", "INFO"),
        ("future date 2099-01-01 -> WARN", "Last reviewed: 2099-01-01", "WARN"),
        ("bold-closed '**Last reviewed:** DATE' reads -> INFO",
         "**Last reviewed:** 2026-05-01", "INFO"),
        ("bold-inside '**Last reviewed: DATE**' reads -> INFO",
         "**Last reviewed: 2026-05-01**", "INFO"),
        ("<meta name=last-reviewed> reads -> INFO",
         '<meta name="last-reviewed" content="2026-05-01">', "INFO"),
    ]
    for name, raw, want in stale_cases:
        got = staleness_level(raw)
        res.check(got == want, f"staleness: {name}", f"got {got}")

    # An unrelated bracketed citation must NOT trip the staleness phrase (low-false-positive lock).
    got = staleness_level("See [3] reviewed last quarter by the team. No stamp here.")
    res.check(got == "INFO" and "no machine-readable" in
              v.check_staleness("See [3] reviewed last quarter.", age, today=today)[0][1].lower(),
              "staleness: unrelated 'reviewed' text does not trip", f"got {got}")

    # Readability pin: a fixed string's FK grade must stay in a tight band.
    grade, nwords, _ = v.flesch_kincaid_grade(READABILITY_PIN_TEXT)
    lo, hi = READABILITY_BAND
    ok = grade is not None and lo <= grade <= hi
    res.check(ok, f"readability pin: fixed string grade in [{lo}, {hi}]",
              f"grade={grade} words={nwords}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Golden-fixture regression: the gates that guard the gates.")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print each verifier's resolved-values line / fixture findings")
    args = ap.parse_args()

    for needed in (SHARED_VERIFY, PROFILE, LRR, FAQ_GEN, UG_GEN):
        if not needed.exists():
            print(f"run-golden: required path missing: {needed}")
            return 2

    res = Results()
    golden_good(res, args.verbose)
    print()
    golden_bad(res, args.verbose)
    print()
    deterministic_pins(res, args.verbose)
    print()
    total = res.passed + res.failed
    print(f"--- golden: {res.passed}/{total} assertions passed, {res.failed} failed ---")
    return 1 if res.failed else 0


if __name__ == "__main__":
    sys.exit(main())
