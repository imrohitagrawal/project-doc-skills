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
import difflib
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


# (name, stub, units-it-claims-to-cover, expectation). `covers` must be EXACTLY the syntactic units the
# stub mutates — functions OR module-level assignment targets (e.g. _L / _R / _COUNT) — and is verified
# against the patch by _units_touched (round-10: no stub may claim a unit it does not touch).
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
    # _doc_raw_inline has TWO independent arms (html_inline AND image); the whole-function stub above bites
    # via the html_inline fixtures alone, so the image arm was a load-bearing branch with no biting fixture
    # (gate-reviews/0017, same class as the _table_names guard-a gap). Isolate it: reverting only the image
    # arm reddens the new inline-image golden fixture.
    ("raw HTML: inline IMAGE arm (isolated from html_inline)",
     _sub('if c.type in ("html_inline", "image"):', 'if c.type in ("html_inline",):'),
     ("_doc_raw_inline",), "RED"),
    # --- COUNT sites (marked regions; the number is checked only inside its marker pair) ---
    ("count: whole site check", _stub("check_count_site", "[]"), ("check_count_site",), "RED"),
    ("count: exactly-one in the marked region",
     _sub("if len(matches) != 1:", "if len(matches) < 1:"), ("check_count_site",), "RED"),
    ("count: value-exact in the region",
     _sub("if tok not in accepted:", "if False and tok not in accepted:"), ("check_count_site",), "RED"),
    # the count region must not itself be an enumeration site (gate-reviews/0017): a near-complete run of
    # skill names in the count sentence is caught here, since its marked span excludes it from the general
    # competing scan. Reverting this branch reddens the in-count-region enumeration golden fixture.
    ("count: region is not an enumeration site",
     _sub("if _competing_run(text, order):", "if False and _competing_run(text, order):"),
     ("check_count_site",), "RED"),
    ("count: region is a single paragraph", _stub("_count_region_text", "None"),
     ("_count_region_text",), "RED"),
    ("count: empty registry guard (no vacuous success)",
     _sub("    if not COUNT_SITES:\n", "    if False:\n"), ("check",), "RED"),
    ("count: missing-doc finding",
     _sub("            findings.append(f\"{fname}: governed doc not found — count site '{site_id}' "
          "cannot be verified\")", "            pass"), ("check",), "RED"),
    ("count/name: left boundary", _sub('_L = r"(?<![a-z0-9_-])"', '_L = r""'), ("_L",), "RED"),
    ("count/name: right boundary", _sub('_R = r"(?![a-z0-9_-])"', '_R = r""'), ("_R",), "RED"),
    # count-suite captures the MULTI-TOKEN number phrase (_COUNT_RUN) so a continuation ("eight hundred",
    # "eight to twelve") is value-checked, not left in the tolerant filler where only the leading token
    # would be read (gate-reviews/0017). Reverting the continuation to a single token reddens the
    # number-word-continuation golden fixtures.
    ("count: number-phrase continuation captured (no 'eight hundred' masking)",
     _sub("(?:[\\s-]+(?:{_NUM_CONT}))*", ""), ("_COUNT_RUN",), "RED"),
    # --- NORMALIZATION (kills case / Unicode-dash / compatibility variants) at every match point ---
    ("normalize: casefold + dash fold", _stub("_norm", "s"), ("_norm",), "RED"),
    # --- ANCHOR adjacency (the begin marker must be immediately preceded by its lead-in) ---
    ("anchor: begin marker must follow its lead-in", _stub("_anchor_missing", "False"),
     ("_anchor_missing",), "RED"),
    # _anchor_missing's FAIL-CLOSED branch (a site id absent from ANCHORS returns True) is separate from the
    # adjacency check the whole-function stub bites via; reverting it to `return False` silently accepts an
    # unregistered marked site. Isolated (gate-reviews/0017), proven by the unregistered-site unit lock.
    ("anchor: unregistered site id fails closed",
     _sub("    if not anchor:\n        return True", "    if not anchor:\n        return False"),
     ("_anchor_missing",), "RED"),
    ("anchor: preceding-unit adjacency", _stub("_preceding_visible", '""'),
     ("_preceding_visible",), "RED"),
    # _preceding_visible has a second branch: a lead-in formatted as a blockquote/list (not a bare
    # paragraph) is still read, so an intact-but-reformatted lead-in is not a false "moved away"
    # (gate-reviews/0017). Reverting only the container branch reddens the blockquote/list lead-in fixtures.
    ("anchor: blockquote/list lead-in recognized (container branch)",
     _sub("    if prev.type in _CONTAINER_CLOSE:", "    if False and prev.type in _CONTAINER_CLOSE:"),
     ("_preceding_visible",), "RED"),
    # --- COMPETING scan + its aggregation/boundary helpers ---
    ("competing: whole scan", _stub("_competing_findings", "[]"), ("_competing_findings",), "RED"),
    ("competing: near-complete run required (not any two names)",
     _sub("_run_hits(text, order) >= max(2, len(order) - 1)", "_run_hits(text, order) >= 2"),
     ("_competing_run",), "RED"),
    ("competing: scans code blocks too (separator-free fence)",
     _sub('t.content if t.type in ("fence", "code_block") else ""', '""'),
     ("_competing_findings",), "RED"),
    # the two arms above cover FENCES; the code_block (indented) arm is separately load-bearing and, until
    # 0017, unproven (every fixture used a fence). Isolate each: phase-1 single-unit and phase-2 container
    # aggregation must both read code_block tokens, proven by the indented + blockquote-split golden fixtures.
    ("competing: phase-1 reads INDENTED code blocks (code_block arm)",
     _sub('t.content if t.type in ("fence", "code_block") else ""',
          't.content if t.type in ("fence",) else ""'), ("_competing_findings",), "RED"),
    ("competing: phase-2 aggregates INDENTED code blocks (code_block arm)",
     _sub('for x in tokens[i:j + 1] if x.type in ("inline", "fence", "code_block")',
          'for x in tokens[i:j + 1] if x.type in ("inline", "fence")'), ("_competing_findings",), "RED"),
    ("competing: aggregate within each container (list / blockquote)",
     _sub("if _competing_run(agg, order):", "if False and _competing_run(agg, order):"),
     ("_competing_findings",), "RED"),
    ("competing: aggregate outside-table cells",
     _sub("if _competing_run(allcells, order):", "if False and _competing_run(allcells, order):"),
     ("_competing_findings",), "RED"),
    ("competing: name-boundary hit count", _stub("_run_hits", "0"), ("_run_hits",), "RED"),
    ("competing: outside-block exclusion", _stub("_in_any_span", "False"), ("_in_any_span",), "RED"),
    ("competing: container span", _stub("_container_close", "start"), ("_container_close",), "RED"),
    ("competing: table span", _stub("_table_span_close", "start"), ("_table_span_close",), "RED"),
    ("competing: table cell reconstruction", _stub("_table_cells", "([], [])"), ("_table_cells",), "RED"),
    # --- TABLE first-column + PURE/FENCE region grammar. _table_names has TWO independent return-None
    #     guards (round-12 found only one was proven): a) the region holds EXACTLY ONE table; b) the region
    #     BEGINS and ENDS with it. Each has its own stub + biting fixture.
    ("table: region holds exactly one table",
     _sub("    if sum(1 for t in inner if t.type == \"table_open\") != 1:",
          "    if False:"), ("_table_names",), "RED"),
    ("table: region begins/ends with the table",
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
    # --- SOURCE of truth + renderers ---
    ("source: empty skills/ fails closed", _sub("    if not canonical:\n", "    if False:\n"),
     ("check",), "RED"),
    ("source: skills-order permutation", _stub("validate_order", "[]"), ("validate_order",), "RED"),
    ("source: missing skills-order fails closed", _stub("load_order", "([], [])"),
     ("load_order",), "RED"),
    ("renderer: improve-order bytes", _stub("render_improve_order", '"**decoy.**"'),
     ("render_improve_order",), "RED"),
    ("renderer: pick-list bytes", _stub("render_pick_list", '"decoy"'), ("render_pick_list",), "RED"),
    ("renderer: tree body bytes", _stub("_tree_body", '"decoy"'), ("_tree_body",), "RED"),
    # REDUNDANT (VALIDATED, round-12 F9): the mutant must leave the golden suite GREEN, confirming its
    # revert is genuinely covered by another guard. If it reddens, the "redundant" claim is FALSE and the
    # battery fails (make it a real RED guard). number-only-slot: under marked count sites, a non-number in
    # the count position fails value-exact (wrong value) or presence (no match) — value-exact covers it.
    ("count: number-only slot (redundant; value-exact covers a non-number)",
     _sub('_COUNT = rf"(?P<count>[0-9]{{1,3}}|(?:{_NUM_ALT})(?:-(?:{_NUM_ALT}))?)"',
          '_COUNT = r"(?P<count>[a-z0-9][a-z0-9-]{0,20}?)"'),
     ("_COUNT",), "REDUNDANT"),
]

# Load-bearing functions (reachable from check) that are NOT given a source-mutation stub — each is
# EXPLICITLY exempted here with a reason, so the exemption is reviewable rather than hidden (round-12 F8:
# every function on the verdict path must be a stub target OR a reasoned exemption).
NON_GUARD = {
    "_inline_text": "accumulates rendered text; a revert is proven transitively by every check that reads "
                    "it (e.g. stubbing it empties all text, reddening the baseline) — data, not a verdict",
    "_read": "reads a governed doc; a missing/unreadable doc is caught by check()'s per-site 'not found' "
             "guard (its own stubs), not here",
    "_canon_markers": "constructs a site's (begin,end) marker strings from its id — pure formatting",
    "_allowed_marker_comments": "returns the marker allowlist derived from the site registries; its "
                                "content is exercised by the marker-identity stub on _marker_only_html_block",
    "canonical_skills": "derives the skill SET from skills/; an empty result is caught by check()'s "
                        "fail-closed guard and a wrong set by validate_order — both separately stubbed",
    "_md": "fail-closed on a MISSING parser is proven by a golden fixture (MarkdownIt=None), NOT by a "
           "source mutation — stubbing _md=None crashes downstream, which the battery correctly refuses "
           "to count as a bite (a crash is not an assertion catch)",
    "main": "CLI exit-code plumbing; the verdict comes from check()",
}


# ---- coverage, derived from the source ----------------------------------------------------------

def _finding_producers(src: str) -> set[str]:
    """Every function that can decide 'this document is wrong'. Derived from the AST so the inventory is
    NOT a number the battery declares about itself (round-8 lesson). A function qualifies if it:
      - raises MarkerError; OR
      - returns the literal None or False as a verdict; OR
      - returns a BOOLEAN-VALUED EXPRESSION — a comparison or `and`/`or`/`not` — i.e. a predicate verdict
        (round-10: `_competing_run` returns `hits >= threshold`); OR
      - appends to a findings / out / errs accumulator (validate_order builds `errs`; load_order too); OR
      - FORWARDS a verdict: returns a bare call to a function ALREADY identified as a producer (round-11:
        `_table_stray_names` returns `_competing_run(blob, order)` — a Call, which the direct rules miss;
        the fixpoint below re-adds it, so a delegating verdict cannot slip out of the denominator)."""
    tree = ast.parse(src)
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    out: set[str] = set()
    for name, fn in fns.items():
        for node in ast.walk(fn):
            if isinstance(node, ast.Raise):
                exc = node.exc
                if getattr(getattr(exc, "func", exc), "id", None) == "MarkerError":
                    out.add(name)
            elif isinstance(node, ast.Return) and node.value is not None:
                v = node.value
                if isinstance(v, ast.Constant) and v.value in (None, False):
                    out.add(name)
                elif isinstance(v, (ast.Compare, ast.BoolOp, ast.UnaryOp)):
                    out.add(name)
                elif isinstance(v, ast.Call) and isinstance(v.func, ast.Name) \
                        and v.func.id in ("any", "all", "bool"):   # a boolean verdict through a builtin
                    out.add(name)
                elif isinstance(v, ast.List) and any(isinstance(el, ast.JoinedStr) for el in v.elts):
                    out.add(name)                                  # returns a finding-list literal
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "append" and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id in ("findings", "out", "errs"):
                out.add(name)
    # Fixpoint: pull in verdict-forwarders — a function whose RETURN is a bare call to a known producer.
    changed = True
    while changed:
        changed = False
        for name, fn in fns.items():
            if name in out:
                continue
            for node in ast.walk(fn):
                if isinstance(node, ast.Return) and isinstance(node.value, ast.Call) \
                        and isinstance(node.value.func, ast.Name) and node.value.func.id in out:
                    out.add(name)
                    changed = True
                    break
    return {n for n in out if not n.startswith("__")}


def _reachable_from(src: str, roots: set[str]) -> set[str]:
    """Every LOCAL function transitively CALLED starting from `roots`, via the static call graph. The
    coverage requirement (gate-reviews/0016 answering round-12 F8): every function on the verdict path from
    check() must be CLAIMED by a stub or EXPLICITLY exempted in NON_GUARD — so a load-bearing helper whose
    behavior changed (e.g. `_anchor_occurrences`, `_in_any_span`, `_norm`) cannot sit outside the measured
    set. Deriving reachability from the source means the inventory is not a hand-kept list."""
    tree = ast.parse(src)
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    calls: dict[str, set[str]] = {name: set() for name in fns}
    for name, fn in fns.items():
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in fns:
                calls[name].add(node.func.id)
    seen: set[str] = set()
    stack = [r for r in roots if r in fns]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(calls[cur])
    return {n for n in seen if not n.startswith("__")}


def _changed_lines(orig: str, patched: str) -> set[int]:
    """The EXACT 0-based orig line indices a patch changes, from difflib's opcodes — NOT the whole
    first..last-diff interval. The interval form wrongly attributed an untouched function sitting BETWEEN
    two edited ones to a two-hunk mutation (gate-reviews/0015 MAJOR-7); real hunks are precise."""
    o, p = orig.splitlines(), patched.splitlines()
    changed: set[int] = set()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=o, b=p, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        if i1 == i2:                       # pure insertion between orig lines i1-1 and i1
            changed.add(min(i1, len(o) - 1))
            if i1 - 1 >= 0:
                changed.add(i1 - 1)
        else:
            changed.update(range(i1, i2))
    return changed


def _units_touched(orig: str, patched: str) -> set[str]:
    """The syntactic units — functions OR top-level assignment targets — whose source lines a patch
    genuinely changes (exact hunks, see _changed_lines). The provenance oracle: a guard's declared
    `covers` must equal EXACTLY this set (round-10 found a stub that mutated one renderer yet 'claimed'
    four functions; the check requires ==, not ⊆, so an under-claim is caught too)."""
    changed = _changed_lines(orig, patched)
    tree = ast.parse(orig)
    units: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if any(node.lineno - 1 <= c <= (node.end_lineno or node.lineno) - 1 for c in changed):
                units.add(node.name)
    for node in ast.iter_child_nodes(tree):     # top-level assignments only
        targets = []
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
        if targets and any(node.lineno - 1 <= c <= (node.end_lineno or node.lineno) - 1 for c in changed):
            units.update(targets)
    return units


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

    print("\n2. coverage — every function ON THE VERDICT PATH FROM check() must be a stub target or an")
    print("   explicitly-reasoned exemption (call graph derived by ast, not a hand-kept list)")
    gen_src = (ROOT / GEN).read_text(encoding="utf-8")
    producers = _finding_producers(gen_src)
    # Roots: check() plus the renderers it invokes INDIRECTLY through the PURE_SITES registry (a bare
    # `renderer(order)` call the static call graph cannot resolve to a name) — they are load-bearing
    # entry points too, so seed them explicitly.
    load_bearing = _reachable_from(gen_src, {"check", "render_improve_order", "render_pick_list"})
    claimed = {fn for _, _, covers, _ in GUARDS for fn in covers}
    owed = sorted(load_bearing - claimed - set(NON_GUARD))
    for fn, why in sorted(NON_GUARD.items()):
        if fn in load_bearing:
            print(f"   [exempt]  {fn} — {why}")
    for fn in sorted(load_bearing):
        if fn in NON_GUARD:
            continue
        mark = "claimed" if fn in claimed else "UNCLAIMED"
        prod = " (finding-producer)" if fn in producers else ""
        if args.verbose or fn in owed:
            print(f"   [{mark}] {fn}{prod}")
    covered = len(load_bearing) - len(owed)
    print(f"   {covered}/{len(load_bearing)} verdict-path functions covered "
          f"({len(producers & load_bearing)} are finding-producers)")

    print("\n2b. provenance — each stub's `covers` must EQUAL the units it actually mutates")
    orig = (ROOT / GEN).read_text(encoding="utf-8")
    # Self-check the provenance ORACLE first (a battery whose oracle cannot fail measures nothing):
    #  - a function stub attributes to exactly that function;
    #  - a module-constant stub attributes to exactly that constant;
    #  - a TWO-HUNK mutation of two SEPARATED functions attributes to exactly those two, and NOT to an
    #    untouched function sitting between them (the exact-hunk requirement — gate-reviews/0015 MAJOR-7).
    if _units_touched(orig, _stub("render_pick_list", '"x"')(orig)) != {"render_pick_list"}:
        print("   PROVENANCE ORACLE BROKEN: a function stub did not attribute to that function alone")
        return 2
    if _units_touched(orig, _sub('_R = r"(?![a-z0-9_-])"', '_R = r""')(orig)) != {"_R"}:
        print("   PROVENANCE ORACLE BROKEN: a module-constant stub did not attribute to that constant")
        return 2
    two_hunk = _stub("_tree_body", '"x"')(_stub("render_improve_order", '"y"')(orig))
    touched_two = _units_touched(orig, two_hunk)
    if touched_two != {"render_improve_order", "_tree_body"} or "render_pick_list" in touched_two:
        print(f"   PROVENANCE ORACLE BROKEN: two-hunk attribution wrong (got {sorted(touched_two)}; the "
              f"untouched render_pick_list between them must NOT appear)")
        return 2
    print("   ok — oracle attributes single, module-constant, and two-separated-hunk mutations exactly")
    prov_fail = []
    for name, patch, covers, _expect in GUARDS:
        patched = patch(orig)
        if patched == orig:
            prov_fail.append((name, "stub does not apply to the committed source (it moved)"))
            continue
        touched = _units_touched(orig, patched)
        if set(covers) != touched:   # EXACT: neither over- nor under-claim
            prov_fail.append((name, f"claims {sorted(covers)} but the mutation touches {sorted(touched)}"))
    for name, why in prov_fail:
        print(f"   [MIS-CLAIM] {name} — {why}")
    if not prov_fail:
        print(f"   ok — every stub's covers == the units it mutates ({len(GUARDS)} stubs)")

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
            # VALIDATED (round-12 F9): a REDUNDANT mutant must leave the suite GREEN — that is the proof
            # its revert is covered by another guard. If it BITES (RED) or crashes, the "redundant" claim
            # is false and this is a failure, not a free pass.
            if verdict == "GREEN":
                redundant.append(name)
                print(f"   [REDUNDANT] {name} — revert confirmed covered (suite stayed green)")
            else:
                failures.append((name, f"declared REDUNDANT but its revert produced {verdict} (not GREEN) "
                                       f"— it is load-bearing; make it a RED guard"))
                print(f"   [NOT-REDUNDANT] {name} — {verdict}: {detail}")
            continue
        if verdict == "RED":
            print(f"   [BITES] {name}" + (f" — {detail}" if args.verbose else ""))
        else:
            failures.append((name, f"{verdict}: {detail}"))
            print(f"   [{verdict}] {name} — {detail}")

    proven = len(GUARDS) - len(failures) - len(redundant)
    print(f"\n--- revert battery: {proven}/{len(GUARDS) - len(redundant)} stubs bite; "
          f"{covered}/{len(load_bearing)} verdict-path functions covered; "
          f"{len(GUARDS) - len(prov_fail)}/{len(GUARDS)} provenance-clean ---")
    for fn in owed:
        print(f"    OWED: {fn}() is on the verdict path but is neither stubbed nor exempted")
    for name, why in prov_fail:
        print(f"    MIS-CLAIM: {name} — {why}")
    for name, why in failures:
        print(f"    NOT PROVEN: {name} — {why}")
    return 1 if (owed or failures or prov_fail) else 0


if __name__ == "__main__":
    sys.exit(main())
