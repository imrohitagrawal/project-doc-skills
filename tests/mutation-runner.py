#!/usr/bin/env python3
"""
mutation-runner.py — prove the record-checker guards BITE, deterministically and reproducibly.

WHY THIS EXISTS (0024, round-1 MINOR-5). The first version of the verdict-cell change proved its guards by
reverting them BY HAND and pasting the resulting failure counts into the review record. The independent
review could not reproduce one of them: the record published "12 failed" for a revert described only as
"_verdict_kind returns its input unnormalised", and three reasonable readings of that sentence produce 11,
12 and 13 failures. A number nobody else can reproduce is exactly the class of claim this repository
exists to catch, so the mutations now live in source, as EXACT before/after strings.

WHY IT IS SEPARATE FROM tests/revert-battery.py. The battery patches only `dst / GEN` — it hardcodes
`GEN = "generate-skill-enumerations.py"` and its coverage/provenance passes parse that one file, so a
GUARDS entry cannot target a check that lives in `tests/run-golden.py` (the stub returns the source
unchanged: PATCH-MISS, plus a provenance MIS-CLAIM). Supporting those would mean giving the battery a
per-mutation target path, which is a redesign of a file six review rounds have deliberately left alone.
This runner is the narrow, honest alternative: same oracle (run the real suite, require a RED with the
NAMED fixtures failing), different target file.

The verdict is deliberately narrow, matching the battery's:
  - the mutation must apply at EXACTLY ONE site (a stub matching two places, or a stale one patching dead
    code, proves nothing) and every mutant must be pairwise distinct;
  - the suite must RUN and report a summary line — a crash, a syntax error or a missing-fixture abort is
    CRASH/HARNESS, never a bite, because "the child exited non-zero" is not "the guard caught it";
  - and it must redden the fixtures the mutation DECLARES, not merely some fixture. A mutant that reddens
    something else has proven nothing about the guard it claims to cover.

Run before requesting any review of the record checker:
    python3 tests/mutation-runner.py           # exit 0 only if every mutation bit its declared fixtures
    python3 tests/mutation-runner.py -v        # also print each run's summary line
"""
from __future__ import annotations
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = "tests/run-golden.py"
CHECKER = "gate-review-check.py"
TIMEOUT_S = 300
MIN_ASSERTIONS = 200      # the unpatched suite must run at least this many; guards a degraded-green suite

# (name, target file, EXACT before, EXACT after, [substrings of the fixture names that must go RED])
MUTATIONS: list[tuple[str, str, str, str, list[str]]] = [
    (
        "B1-prefix-parser: _verdict_kind returns the first recognised word, ignoring the rest",
        GOLDEN,
        '    m = _VERDICT_PAREN_RE.fullmatch(cell) or _VERDICT_CELL_RE.fullmatch(cell)',
        '    head = [w for w in re.sub(r"[*_`]", "", cell).casefold().split() if w in _VERDICT_KINDS]\n'
        '    if head:\n'
        '        return head[0]\n'
        '    m = _VERDICT_PAREN_RE.fullmatch(cell) or _VERDICT_CELL_RE.fullmatch(cell)',
        ["unconsumed-suffix cell", "MULTI-LINE verdict cell"],
    ),
    (
        "B3-closure: a claimed passing review is not checked against its own table row",
        GOLDEN,
        '            if mc is m_review and _verdict_kind(verdicts.get(kp, "")) != "pass":',
        '            if False:',
        ["over a BLOCK row is CAUGHT"],
    ),
    (
        "M4-sweep: the round table is found by any integer-leading row again, not by its header",
        GOLDEN,
        '    h = _ROUND_HEADER_RE.search(record)\n'
        '    if not h:\n'
        '        return None\n',
        '    h = _ROUND_HEADER_RE.search(record)\n'
        '    if not h:\n'
        '        class _Z:\n'
        '            def end(self):\n'
        '                return 0\n'
        '        h = _Z()\n',
        ["non-round table is NOT read as round history"],
    ),
    (
        "0024-pending: the PASS-state pending invariant goes back to the exact literal",
        GOLDEN,
        '    pend = [r for r, v in verdicts.items() if _verdict_kind(v) == "pending"]',
        '    pend = [r for r, v in verdicts.items() if v.lower() == "pending"]',
        ["ANNOTATED pending newest row is CAUGHT"],
    ),
    (
        "0024-unknown: the unrecognised-cell finding is dropped (the fail-closed half)",
        GOLDEN,
        '    if unknown:',
        '    if False:',
        ["unrecognised verdict cell"],
    ),
    (
        "0024-selfcount: the author-count arm goes back to a substring test",
        GOLDEN,
        '        selfr = sum(1 for r, v in verdicts.items() if _verdict_kind(v) == "self")',
        '        selfr = sum(1 for r, v in verdicts.items() if "self" in v.lower())',
        ["counts as an INDEPENDENT round"],
    ),
    (
        "R3-hws: the verdict-line matcher narrows its leading class back to ASCII-only whitespace",
        CHECKER,
        '_HWS = r"[^\\S\\r\\n]"',
        '_HWS = r"[ \\t]"',
        ["NBSP-indented must NOT clear", "EM-SPACE-indented must NOT clear"],
    ),
    (
        "R3-comments: a commented-out verdict becomes a declaration again",
        CHECKER,
        '    matches = VERDICT_LINE_RE.findall(HTML_COMMENT_RE.sub("", text))',
        '    matches = VERDICT_LINE_RE.findall(text)',
        ["'PASS <!-- BLOCK -->' clears (the comment does not render)"],
    ),
    (
        "R3-across: a record that is not a clean PASS stops gating the PR",
        CHECKER,
        '        if verdict != "PASS":\n            unreadable = True',
        '        if verdict != "PASS":\n            pass',
        ["ANNOTATED BLOCK blocks even with a clean PASS", "NO verdict line blocks even with a clean PASS"],
    ),
    (
        "R2-membership: _verdict_kind returns a non-member instead of None (homoglyph escape)",
        GOLDEN,
        '    kind = word.casefold()\n    return kind if kind in _VERDICT_KINDS else None',
        '    return word.casefold()',
        ["classifies as NOTHING", "homoglyph verdict cell under Verdict: PASS"],
    ),
    (
        "R2-tornrow: an unparseable line inside the round table is silently dropped again",
        GOLDEN,
        '            probs.append(f"a line inside the round-history table is not a parseable round row: "\n'
        '                         f"{stripped[:80]!r}")',
        '            pass',
        ["unparseable line inside the round table is CAUGHT"],
    ),
    (
        "R2-sweep: the live-record sweep stops asserting it covers more than one record",
        GOLDEN,
        '        if _round_rows(text) is None:\n            continue',
        '        if True:\n            continue',
        ["record sweep actually covers"],
    ),
    (
        "R3-delegate: the in-suite checker stops reporting a malformed final verdict declaration",
        GOLDEN,
        '    if decls and final_verdict is None:',
        '    if False:',
        ["'Verdict: PASS pending' is CAUGHT", "ANNOTATED final BLOCK does not fall back"],
    ),
]


def _tracked() -> list[str]:
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, text=True)
    return [p for p in out.stdout.split("\0") if p]


def _materialize(dst: Path) -> None:
    """Copy TRACKED files only — copytree() would drag in untracked working-tree content, so a fixture
    forgotten in the commit could still make this pass locally."""
    for rel in _tracked():
        src = ROOT / rel
        if not src.is_file():
            continue
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst / rel)


def _child_env() -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def _run(target: str | None = None, before: str = "", after: str = "") -> tuple[str, str, str, list[str]]:
    """Run the suite on a scratch copy, optionally with one exact substitution applied.

    Returns (verdict, detail, fingerprint, failed-fixture-names). verdict is GREEN / RED / CRASH /
    HARNESS / PATCH-MISS / PATCH-AMBIGUOUS."""
    tmp = Path(tempfile.mkdtemp(prefix="mutrun-"))
    try:
        dst = tmp / "repo"
        dst.mkdir()
        _materialize(dst)
        fingerprint = ""
        if target is not None:
            path = dst / target
            src = path.read_text(encoding="utf-8")
            hits = src.count(before)
            if hits == 0:
                return "PATCH-MISS", f"the mutation did not apply to {target} — the source moved", "", []
            if hits > 1:
                return "PATCH-AMBIGUOUS", f"the mutation matches {hits} sites in {target}", "", []
            patched = src.replace(before, after, 1)
            path.write_text(patched, encoding="utf-8")
            fingerprint = hashlib.sha256(patched.encode()).hexdigest()[:12]
        try:
            proc = subprocess.run([sys.executable, GOLDEN], cwd=dst, capture_output=True, text=True,
                                  timeout=TIMEOUT_S, env=_child_env())
        except subprocess.TimeoutExpired:
            return "CRASH", f"the suite timed out after {TIMEOUT_S}s", fingerprint, []
        out = proc.stdout + proc.stderr
        summary = [ln for ln in out.splitlines() if "assertions passed," in ln]
        if not summary:
            tail = "; ".join(out.strip().splitlines()[-2:]) or "(no output)"
            return "HARNESS", f"the suite never reported a summary — {tail}", fingerprint, []
        failed_names = [ln.split("]", 1)[1].split("—")[0].strip()
                        for ln in out.splitlines() if ln.strip().startswith("[FAIL]")]
        verdict = "RED" if failed_names else "GREEN"
        return verdict, summary[-1].strip(), fingerprint, failed_names
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verbose", action="store_true", help="print each run's summary line")
    args = ap.parse_args()

    print("1. harness sanity (the unpatched suite must be a usable oracle)")
    verdict, detail, _, _ = _run()
    if verdict != "GREEN":
        print(f"   [{verdict}] the UNPATCHED suite is not green — {detail}")
        return 1
    ran = int(detail.split("golden:", 1)[1].split("/", 1)[0].strip()) if "golden:" in detail else 0
    if ran < MIN_ASSERTIONS:
        print(f"   [DEGRADED] the unpatched suite ran only {ran} assertions (< {MIN_ASSERTIONS})")
        return 1
    print(f"   ok — {detail}")

    print("\n2. mutation quality + verdict (each must redden its DECLARED fixtures, not merely some red)")
    failures: list[tuple[str, str]] = []
    seen: dict[str, str] = {}
    for name, target, before, after, expect_fx in MUTATIONS:
        verdict, detail, fp, failed = _run(target, before, after)
        if fp and fp in seen:
            failures.append((name, f"DUPLICATE MUTANT — identical to '{seen[fp]}'"))
            print(f"   [DUPLICATE] {name}")
            continue
        if fp:
            seen[fp] = name
        if verdict != "RED":
            failures.append((name, f"{verdict}: {detail}"))
            print(f"   [{verdict}] {name} — {detail}")
            continue
        missing = [fx for fx in expect_fx if not any(fx in f for f in failed)]
        if missing:
            failures.append((name, f"MIS-TARGETED — went red, but not on {missing}; red were: {failed}"))
            print(f"   [MIS-TARGETED] {name} — expected {missing}")
            continue
        print(f"   [BITES] {name}")
        if args.verbose:
            print(f"            {detail}")
            for f in failed:
                print(f"            RED: {f}")

    # DENOMINATOR RULE. An empty (or gutted) MUTATIONS list used to print
    # "0/0 mutations bite" and exit 0 — a mutation harness reporting success
    # while killing nothing, which is the one failure it exists to make
    # impossible. The floor is deliberately a real number, not >0: deleting all
    # but one mutation would otherwise still pass.
    MIN_MUTATIONS = 13
    if len(MUTATIONS) < MIN_MUTATIONS:
        print(f"\n--- mutation runner: REFUSED — {len(MUTATIONS)} mutation(s) declared, "
              f"floor is {MIN_MUTATIONS}. A harness that runs no mutations proves nothing, so "
              f"an empty or thinned list is a failure, not a pass. Lower MIN_MUTATIONS only "
              f"alongside a written reason. ---")
        return 1

    proven = len(MUTATIONS) - len(failures)
    print(f"\n--- mutation runner: {proven}/{len(MUTATIONS)} mutations bite their declared fixtures ---")
    for name, why in failures:
        print(f"    FAILED: {name} — {why}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
