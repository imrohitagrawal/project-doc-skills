#!/usr/bin/env python3
"""
revert-battery.py — prove that every guard in the skill-enumeration gate BITES when reverted.

CONTRIBUTING requirement (ii) says a gate check must ship with a fixture that fails if the check is
reverted to a no-op. "Ships with a fixture" is not the same as "the fixture bites", and this repository
has now paid for that distinction three times:

  - rounds 4-7: guards that worked but were unfixtured, and one check that had silently become a no-op;
  - round 7: the author's hand-rolled battery reported "11/11 biting" while its scratch copy was
    INCOMPLETE — `tests/run-golden.py` aborted with "required path missing" before running a single
    assertion, so every stub looked like it bit;
  - round 8: this script reported "19/19" while TWO load-bearing guards had no stub at all — the
    denominator was self-declared, so the missing guards were invisible. Loosening either one character
    admitted a reader-visible decoy *inside* a marked region with the suite fully green.

So the oracle here is deliberately narrow, and the inventory is derived from the SOURCE, not declared:

  1. HARNESS SANITY (fail closed). Run the golden suite unpatched and require that it actually executed
     (a real summary line), is green, and ran at least MIN_ASSERTIONS assertions — a suite that silently
     degraded to a handful of cases must not be accepted as a usable oracle.
  2. COVERAGE (derived). Parse the generator with `ast` and find every function that can produce a
     finding (raises MarkerError, returns None/False as a verdict, or appends to a findings list). Every
     such function must be claimed by at least one stub. An unclaimed function is OWED — this is what
     catches "a guard nobody is proving", which no self-declared count ever could.
  3. MUTATION QUALITY. Each stub must apply at EXACTLY ONE site (a stub that matches two places, or a
     stale one that patches dead code, proves nothing), and all mutants must be pairwise distinct.
  4. VERDICT. A mutant counts as BITTEN only if the suite RAN and reported assertion failures. A crash,
     a syntax error, a timeout, a signal, or a missing-fixture abort is CRASH/HARNESS — never a bite,
     because "the child exited non-zero" is not "the guard's assertion caught the escape".

A guard whose revert is genuinely covered by another guard cannot be "proven" by this method; declare it
`REDUNDANT` with a reason. Those are reported separately and are NOT counted as proven — the honest
denominator is guards proven, not guards listed.

Run before requesting any review of this gate:
    python3 tests/revert-battery.py            # exit 0 only if nothing is OWED and every RED stub bit
    python3 tests/revert-battery.py -v         # also print each run's summary line
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN = "generate-skill-enumerations.py"
GOLDEN = "tests/run-golden.py"
TIMEOUT_S = 300
MIN_ASSERTIONS = 100          # the unpatched suite must run at least this many; guards degraded-green


# ---- scratch tree ------------------------------------------------------------------------------

def _tracked_files() -> list[str]:
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, text=True)
    return [p for p in out.stdout.split("\0") if p]


def _materialize(dst: Path) -> None:
    """Copy the TRACKED files only. copytree() would drag in untracked and ignored working-tree content,
    so a fixture that was forgotten in the commit could still make the battery pass locally."""
    for rel in _tracked_files():
        src = ROOT / rel
        if not src.is_file():
            continue
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst / rel)


def _child_env() -> dict:
    """A child that imports the checker from the developer's tree instead of the scratch tree would be
    measuring the wrong code."""
    env = dict(os.environ)
    for k in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
        env.pop(k, None)
    return env


def _classify(p: subprocess.CompletedProcess) -> tuple[str, str]:
    out = p.stdout + p.stderr
    summary = next((l for l in out.splitlines() if l.startswith("--- golden")), "")
    if "required path missing" in out:
        return "HARNESS", "the suite aborted before asserting (required path missing)"
    if "Traceback (most recent call last)" in out or not summary:
        first = next((l for l in out.splitlines() if l.strip()), "")
        return "CRASH", f"the suite did not complete: {first[:70]}"
    if p.returncode == 0:
        return "GREEN", summary
    return ("RED", summary) if " 0 failed" not in summary else ("CRASH", summary)


def _run(patch=None) -> tuple[str, str, str]:
    """Returns (verdict, detail, mutant-fingerprint)."""
    tmp = Path(tempfile.mkdtemp(prefix="revert-battery-"))
    try:
        dst = tmp / "repo"
        dst.mkdir()
        _materialize(dst)
        fingerprint = ""
        if patch is not None:
            target = dst / GEN
            src = target.read_text(encoding="utf-8")
            patched = patch(src)
            if patched == src:
                return "PATCH-MISS", "the stub did not apply — the source moved", ""
            target.write_text(patched, encoding="utf-8")
            fingerprint = hashlib.sha256(patched.encode()).hexdigest()[:12]
            try:
                compile(patched, GEN, "exec")
            except SyntaxError as e:
                return "CRASH", f"the stub produced invalid Python: {e}", fingerprint
        try:
            p = subprocess.run([sys.executable, GOLDEN], cwd=dst, capture_output=True, text=True,
                               timeout=TIMEOUT_S, env=_child_env())
        except subprocess.TimeoutExpired:
            return "HARNESS", f"the suite did not finish within {TIMEOUT_S}s", fingerprint
        if p.returncode < 0:
            return "HARNESS", f"the suite was killed by signal {-p.returncode}", fingerprint
        verdict, detail = _classify(p)
        return verdict, detail, fingerprint
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---- stubs -------------------------------------------------------------------------------------

def _stub(fn: str, ret: str):
    def apply(s: str) -> str:
        i = s.find(f"def {fn}(")
        if i < 0:
            return s
        j = s.index("\n", i) + 1
        return s[:j] + f"    return {ret}\n" + s[j:]
    return apply


def _sub(old: str, new: str):
    """Exact-once replacement: a stub that matches zero or several places proves nothing about the guard
    it names, so it is reported as PATCH-MISS rather than quietly mutating something else."""
    def apply(s: str) -> str:
        if s.count(old) != 1:
            return s
        return s.replace(old, new, 1)
    return apply


# name -> (stub, functions it claims to cover, expectation)
GUARDS: list[tuple] = [
    ("marker: duplicate pair rejected",
     _sub("if len(begins) != 1 or len(ends) != 1:", "if len(begins) < 1 or len(ends) < 1:"),
     ("_marker_token_span",), "RED"),
    ("marker: end-after-begin required",
     _sub("if ends[0] <= begins[0]:", "if False and ends[0] <= begins[0]:"),
     ("_marker_token_span",), "RED"),
    ("marker: identity allowlist", _stub("_marker_only_html_block", "True"),
     ("_marker_only_html_block",), "RED"),
    ("raw HTML: block ban", _stub("_stray_html_block", "None"), ("_stray_html_block",), "RED"),
    ("raw HTML: inline/image ban", _stub("_doc_raw_inline", "None"), ("_doc_raw_inline",), "RED"),
    ("count: whole check", _stub("check_count_phrases", "[]"), ("check_count_phrases",), "RED"),
    ("count: empty-phrase-set guard", _sub("    if not phrases:\n", "    if False:\n"),
     ("check_count_phrases",), "RED"),
    ("count: number-only slot",
     _sub('_COUNT = rf"(?P<count>\\d{{1,3}}|(?:{_NUM_ALT})(?:-(?:{_NUM_ALT}))?)"',
          '_COUNT = r"(?P<count>[A-Za-z0-9][A-Za-z0-9-]{0,20}?)"'),
     ("check_count_phrases",), "RED"),
    ("count: left boundary", _sub('_L = r"(?<![A-Za-z0-9_-])"', '_L = r""'),
     ("check_count_phrases",), "RED"),
    ("count: right boundary", _sub('_R = r"(?![A-Za-z0-9_-])"', '_R = r""'),
     ("check_count_phrases",), "RED"),
    ("count: missing-doc finding",
     _sub('            findings.append(f"{fname}: governed doc not found — its count phrases cannot '
          'be verified")', "            pass"),
     ("check",), "RED"),
    ("count: rendered-visible-text input",
     _sub('        if t.type == "inline":\n            parts.append(_inline_text(t))',
          '        if t.type == "inline":\n            parts.append(t.content)'),
     ("_visible_text",), "RED"),
    ("competing: whole scan", _stub("_competing", "False"), ("_competing",), "RED"),
    ("competing: code-block scan",
     _sub('t.content if t.type in ("fence", "code_block") else ""', '""'), ("_competing",), "RED"),
    ("table: stray names outside column one", _stub("_table_stray_names", "False"),
     ("_table_stray_names",), "RED"),
    ("table: no competing skill table", _stub("_extra_skill_table", "False"),
     ("_extra_skill_table",), "RED"),
    ("table: region is exactly one table",
     _sub("    if inner[0].type != \"table_open\" or inner[-1].type != \"table_close\" "
          "or inner[0].level != 0:", "    if False:"), ("_table_names",), "RED"),
    ("pure region: exactly one paragraph",
     _sub('if len(inner) == 3 and inner[0].type == "paragraph_open"',
          'if len(inner) >= 3 and inner[0].type == "paragraph_open"'), ("_pure_source",), "RED"),
    ("fence region: exactly one fence",
     _sub('if len(inner) == 1 and inner[0].type == "fence"',
          'if len(inner) >= 1 and inner[0].type == "fence"'), ("_fence_body",), "RED"),
    ("site: tree comparison",
     _sub("if body != _tree_body(order):", "if False and body != _tree_body(order):"),
     ("check",), "RED"),
    ("source: empty skills/ fails closed", _sub("    if not canonical:\n", "    if False:\n"),
     ("check", "canonical_skills"), "RED"),
    ("source: skills-order permutation", _stub("validate_order", "[]"), ("validate_order",), "RED"),
    ("renderers: generated bytes", _stub("render_improve_order", '"**decoy.**"'),
     ("render_improve_order", "render_pick_list", "render_tree", "_tree_body"), "RED"),
    # A real guard (absent parser -> MarkerError -> FAIL, never "clean") that cannot be proven by source
    # mutation: simulating it means removing an installed dependency, which is an environment change, not
    # a one-line revert. Declared, reported separately, and deliberately NOT counted as proven.
    ("parser-absent fail-closed", _stub("_md", "None"), ("_md",), "REDUNDANT"),
]

# Functions the AST rule flags that are NOT verdict guards. Listed explicitly, with the reason, so the
# exemption is reviewable — narrowing the rule instead would hide the same judgement in a regex.
NON_GUARD = {
    "_inline_text": "accumulates rendered text; its `out` is data, not findings",
    "main": "CLI exit-code plumbing; the verdict comes from check()",
}


# ---- coverage, derived from the source ----------------------------------------------------------

def _finding_producers(src: str) -> set[str]:
    """Every function that can decide 'this document is wrong': it raises MarkerError, returns None/False
    as a verdict, or appends to a findings list. Derived from the AST so the inventory is not a number
    the battery declares about itself."""
    tree = ast.parse(src)
    out: set[str] = set()
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        for node in ast.walk(fn):
            if isinstance(node, ast.Raise):
                exc = node.exc
                name = getattr(getattr(exc, "func", exc), "id", None)
                if name == "MarkerError":
                    out.add(fn.name)
            elif isinstance(node, ast.Return) and isinstance(node.value, ast.Constant) \
                    and node.value.value in (None, False):
                out.add(fn.name)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "append" and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id in ("findings", "out"):
                out.add(fn.name)
    return {n for n in out if not n.startswith("__")}


def main() -> int:
    ap = argparse.ArgumentParser(description="Prove every skill-enumeration guard bites when reverted.")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    print("1. harness sanity — the unpatched suite must run, be green, and not be degraded")
    verdict, detail, _ = _run(None)
    if verdict != "GREEN":
        print(f"   HARNESS UNUSABLE ({verdict}): {detail}")
        print("   Refusing to report on the guards — a battery whose oracle cannot fail measures nothing.")
        return 2
    ran = int(detail.split("/")[1].split()[0]) if "/" in detail else 0
    if ran < MIN_ASSERTIONS:
        print(f"   HARNESS DEGRADED: only {ran} assertions ran (expected >= {MIN_ASSERTIONS}): {detail}")
        return 2
    print(f"   ok — {detail}")

    print("\n2. coverage — every finding-producing function must be claimed by a stub (derived by ast)")
    producers = _finding_producers((ROOT / GEN).read_text(encoding="utf-8"))
    for fn, why in sorted(NON_GUARD.items()):
        print(f"   [exempt]  {fn} — {why}")
    producers -= set(NON_GUARD)
    claimed = {fn for _, _, covers, _ in GUARDS for fn in covers}
    owed = sorted(producers - claimed)
    for fn in sorted(producers):
        mark = "claimed" if fn in claimed else "UNCLAIMED"
        if args.verbose or fn in owed:
            print(f"   [{mark}] {fn}")
    print(f"   {len(producers) - len(owed)}/{len(producers)} finding-producing functions claimed")

    print("\n3. mutation quality + verdict")
    failures, redundant, seen = [], [], {}
    for name, patch, _covers, expect in GUARDS:
        verdict, detail, fp = _run(patch)
        if fp and fp in seen:
            failures.append((name, f"DUPLICATE MUTANT — identical to '{seen[fp]}'"))
            print(f"   [DUPLICATE] {name}")
            continue
        if fp:
            seen[fp] = name
        if expect == "REDUNDANT":
            redundant.append(name)
            print(f"   [REDUNDANT] {name} — {detail if args.verbose else 'declared, not counted as proven'}")
            continue
        if verdict == "RED":
            print(f"   [BITES] {name}" + (f" — {detail}" if args.verbose else ""))
        else:
            failures.append((name, f"{verdict}: {detail}"))
            print(f"   [{verdict}] {name} — {detail}")

    proven = len(GUARDS) - len(failures) - len(redundant)
    print(f"\n--- revert battery: {proven}/{len(GUARDS) - len(redundant)} stubs bite; "
          f"{len(producers) - len(owed)}/{len(producers)} guard functions claimed ---")
    for fn in owed:
        print(f"    OWED STUB: {fn}() can produce a finding but no stub claims it")
    for name, why in failures:
        print(f"    NOT PROVEN: {name} — {why}")
    return 1 if (owed or failures) else 0


if __name__ == "__main__":
    sys.exit(main())
