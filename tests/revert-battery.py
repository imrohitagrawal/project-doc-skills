#!/usr/bin/env python3
"""
revert-battery.py — prove that every guard in the skill-enumeration gate BITES when reverted.

CONTRIBUTING requirement (ii) says a gate check must ship with a fixture that fails if the check is
reverted to a no-op. "Ships with a fixture" is not the same as "the fixture bites", and the difference is
not theoretical: gate-review 0011 found two load-bearing guards whose reverts left the golden suite fully
green, and the author's own hand-rolled battery had reported "11/11 biting" while its scratch copy was
INCOMPLETE — `tests/run-golden.py` aborted with "required path missing" before running a single
assertion, so every stub looked like it bit. A verification harness that cannot fail is worse than none.

So this script does two things, in order:

  1. HARNESS SANITY (fail closed). Copy the whole repo, run the golden suite UNPATCHED, and require that
     it actually executed (no "required path missing") and is green. If not, exit 2 — never report on the
     guards, because the measurement would be meaningless.
  2. For each guard, apply a one-line revert to a scratch copy and require the golden suite to go RED.
     A stub that leaves it green is a missing fixture and is reported as such.

A stub that does not apply (the source moved) is reported as PATCH-MISS — also a failure, since a
silently-skipped stub is the same lie in a different place.

Run before requesting any review of this gate:
    python3 tests/revert-battery.py            # exit 0 only if every guard bites
    python3 tests/revert-battery.py -v         # also print each golden summary line
"""
from __future__ import annotations
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN = "generate-skill-enumerations.py"
GOLDEN = "tests/run-golden.py"


def _run(patch=None) -> tuple[str, str]:
    """Copy the WHOLE repo (a partial copy is what invalidated an earlier battery), optionally patch the
    generator, run the golden suite. Returns (verdict, summary-line)."""
    tmp = Path(tempfile.mkdtemp(prefix="revert-battery-"))
    try:
        dst = tmp / "repo"
        shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
        if patch is not None:
            src = (dst / GEN).read_text(encoding="utf-8")
            patched = patch(src)
            if patched == src:
                return "PATCH-MISS", "the stub did not apply — the source moved"
            (dst / GEN).write_text(patched, encoding="utf-8")
        p = subprocess.run([sys.executable, GOLDEN], cwd=dst, capture_output=True, text=True)
        out = p.stdout + p.stderr
        summary = next((l for l in out.splitlines() if l.startswith("--- golden")), "")
        if "required path missing" in out:
            return "HARNESS-BROKEN", out.strip().splitlines()[-1][:100]
        return ("RED" if p.returncode != 0 else "GREEN"), summary
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _stub(fn: str, ret: str):
    """Make `fn` return a constant immediately (the classic no-op revert)."""
    def apply(s: str) -> str:
        i = s.find(f"def {fn}(")
        if i < 0:
            return s
        j = s.index("\n", i) + 1
        return s[:j] + f"    return {ret}\n" + s[j:]
    return apply


def _sub(old: str, new: str):
    return lambda s: s.replace(old, new, 1)


# Every guard the gate's claims rest on, with the one-line revert that should break it.
GUARDS: dict = {
    "marker: duplicate pair rejected":
        _sub("if len(begins) != 1 or len(ends) != 1:", "if len(begins) < 1 or len(ends) < 1:"),
    "marker: end-after-begin required":
        _sub("if ends[0] <= begins[0]:", "if False and ends[0] <= begins[0]:"),
    "marker: identity allowlist": _stub("_marker_only_html_block", "True"),
    "raw HTML: block ban": _stub("_stray_html_block", "None"),
    "raw HTML: inline/image ban": _stub("_doc_raw_inline", "None"),
    "count: whole check": _stub("check_count_phrases", "[]"),
    "count: empty-phrase-set guard": _sub("    if not phrases:\n", "    if False:\n"),
    "count: number-only slot":
        _sub('_COUNT = rf"(?P<count>\\d{{1,3}}|(?:{_NUM_ALT})(?:-(?:{_NUM_ALT}))?)"',
             '_COUNT = r"(?P<count>[A-Za-z0-9][A-Za-z0-9-]{0,20}?)"'),
    "count: left boundary": _sub('_L = r"(?<![A-Za-z0-9_-])"', '_L = r""'),
    "count: right boundary": _sub('_R = r"(?![A-Za-z0-9_-])"', '_R = r""'),
    "count: missing-doc finding":
        _sub('            findings.append(f"{fname}: governed doc not found — its count phrases cannot '
             'be verified")', "            pass"),
    "count: rendered-visible-text input":
        _sub('        if t.type == "inline":\n            parts.append(_inline_text(t))',
             '        if t.type == "inline":\n            parts.append(t.content)'),
    "competing: whole scan": _stub("_competing", "False"),
    "competing: code-block scan":
        _sub('t.content if t.type in ("fence", "code_block") else ""', '""'),
    "table: stray names outside column one": _stub("_table_stray_names", "False"),
    "table: no competing skill table": _stub("_extra_skill_table", "False"),
    "site: tree comparison": _sub("if body != _tree_body(order):", "if False and body != _tree_body(order):"),
    "source: empty skills/ fails closed": _sub("    if not canonical:\n", "    if False:\n"),
    "source: skills-order permutation": _stub("validate_order", "[]"),
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Prove every skill-enumeration guard bites when reverted.")
    ap.add_argument("-v", "--verbose", action="store_true", help="print each golden summary line")
    args = ap.parse_args()

    print("harness sanity: running the golden suite UNPATCHED (it must actually execute, and be green)")
    verdict, summary = _run(None)
    if verdict != "GREEN":
        print(f"  HARNESS UNUSABLE ({verdict}): {summary}")
        print("  Refusing to report on the guards — a battery whose harness cannot fail measures nothing.")
        return 2
    print(f"  ok — {summary}")
    print()

    failures = []
    for name, patch in GUARDS.items():
        verdict, summary = _run(patch)
        ok = verdict == "RED"
        if not ok:
            failures.append((name, verdict))
        print(f"  [{'BITES' if ok else 'DOES NOT BITE'}] {name}" + (f" — {summary}" if args.verbose else ""))

    print()
    total = len(GUARDS)
    print(f"--- revert battery: {total - len(failures)}/{total} guards bite ---")
    for name, verdict in failures:
        print(f"    OWED FIXTURE ({verdict}): {name}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
