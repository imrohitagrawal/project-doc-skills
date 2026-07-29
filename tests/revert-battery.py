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


def _failed_names(out: str) -> set[str]:
    """The set of golden assertion NAMES that FAILED (parsed from run-golden's `  [FAIL] <name> — …` lines),
    so a mutant can be checked to redden the INTENDED assertion, not merely SOME assertion (gate-reviews/0018:
    a GPT review found the battery treated any red summary as a bite)."""
    names = set()
    for l in out.splitlines():
        if l.startswith("  [FAIL] "):
            names.add(l[len("  [FAIL] "):].split(" — ", 1)[0].strip())
    return names


def _classify(p: subprocess.CompletedProcess) -> tuple[str, str, set[str]]:
    out = p.stdout + p.stderr
    failed = _failed_names(out)
    summary = next((l for l in out.splitlines() if l.startswith("--- golden")), "")
    if "required path missing" in out:
        return "HARNESS", "the suite aborted before asserting (required path missing)", failed
    if "Traceback (most recent call last)" in out or not summary:
        first = next((l for l in out.splitlines() if l.strip()), "")
        return "CRASH", f"the suite did not complete: {first[:70]}", failed
    if p.returncode == 0:
        return "GREEN", summary, failed
    return (("RED", summary, failed) if " 0 failed" not in summary
            else ("CRASH", summary, failed))


def _run(patch=None) -> tuple[str, str, str, set]:
    """Returns (verdict, detail, mutant-fingerprint, failed-assertion-names)."""
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
                return "PATCH-MISS", "the stub did not apply — the source moved", "", set()
            target.write_text(patched, encoding="utf-8")
            fingerprint = hashlib.sha256(patched.encode()).hexdigest()[:12]
            try:
                compile(patched, GEN, "exec")
            except SyntaxError as e:
                return "CRASH", f"the stub produced invalid Python: {e}", fingerprint, set()
        try:
            p = subprocess.run([sys.executable, GOLDEN], cwd=dst, capture_output=True, text=True,
                               timeout=TIMEOUT_S, env=_child_env())
        except subprocess.TimeoutExpired:
            return "HARNESS", f"the suite did not finish within {TIMEOUT_S}s", fingerprint, set()
        if p.returncode < 0:
            return "HARNESS", f"the suite was killed by signal {-p.returncode}", fingerprint, set()
        verdict, detail, failed = _classify(p)
        return verdict, detail, fingerprint, failed
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


def _returned_names(fn: ast.FunctionDef) -> set[str]:
    """The local names a function hands back as its verdict: a bare `return NAME` or a NAME element of a
    returned tuple (e.g. load_order's `return [], errs` -> {errs}). Used to keep the finding-branch
    inventory SEMANTIC — an accumulator counts only if the function RETURNS it."""
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Return) and node.value is not None:
            v = node.value
            if isinstance(v, ast.Name):
                names.add(v.id)
            elif isinstance(v, ast.Tuple):
                names.update(e.id for e in v.elts if isinstance(e, ast.Name))
    return names


def _finding_branches(src: str):
    """Every finding-EMITTING statement in the generator — a `raise MarkerError(...)`, or an
    `accumulator.append(...)` where the ENCLOSING function RETURNS that accumulator as its verdict — as
    (label, patch) where the patch neuters that ONE statement with `pass`. The curated GUARDS above prove
    each NAMED branch bites; this sweep proves EXHAUSTIVELY that NO finding-branch is a silent no-op-revert
    (the guard-a class). It is committed (gate-reviews/0018) so this is a durable part of the battery.

    SEMANTIC inventory (gate-reviews/0019). An append counts ONLY when BOTH hold: (i) the accumulator is one
    of the codebase's FINDINGS accumulators — named `findings` / `errs` / `out` (the exact set
    `_finding_producers` keys on), which hold verdict STRINGS; AND (ii) the enclosing function RETURNS that
    accumulator by name. Condition (ii) excludes `_inline_text`, which appends to a local `out` but RETURNS
    `"".join(out)` (a string, not the list) — its two DATA appends are not finding-branches, and neutering
    them reddens golden for an unrelated reason (all rendered text emptied). Condition (i) excludes returned
    DATA lists that are not findings — `_table_names` returns `names`, `_table_cells` returns `rows` — which
    (ii) alone would wrongly admit. Together they leave the denominator holding real verdicts only, which the
    sweep's RED requirement (below) needs to stay honest. Raises of MarkerError are always verdicts and are
    always included. NOTE: this sweep covers append + raise statements, which can be safely neutered to
    `pass`; a finding-emitting RETURN (`return findings` / `if errs: return errs` / the empty-skills return
    literal) cannot be pass-neutered without returning None and crashing its callers, so those are covered
    by curated GUARDS with explicit benign-value reverts, not by this sweep (gate-reviews/0019)."""
    tree = ast.parse(src)
    funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    returns = {fn: _returned_names(fn) for fn in funcs}
    FINDING_ACCUMS = ("findings", "errs", "out")

    def enclosing(line: int) -> ast.FunctionDef | None:
        cands = [fn for fn in funcs if fn.lineno <= line <= (fn.end_lineno or fn.lineno)]
        return max(cands, key=lambda fn: fn.lineno) if cands else None   # innermost

    spans = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "append" and isinstance(node.func.value, ast.Name) \
                and node.func.value.id in FINDING_ACCUMS:
            fn = enclosing(node.lineno)
            if fn is not None and node.func.value.id in returns[fn]:   # returned by name = a verdict list
                spans.append((node.lineno, node.end_lineno,
                              f"{node.func.value.id}.append @L{node.lineno}"))
        elif isinstance(node, ast.Raise) and "MarkerError" in (ast.get_source_segment(src, node) or ""):
            spans.append((node.lineno, node.end_lineno, f"raise MarkerError @L{node.lineno}"))
    out = []
    for lo, hi, label in sorted(spans):
        def patch(s, lo=lo, hi=hi):
            ls = s.split("\n")
            indent = len(ls[lo - 1]) - len(ls[lo - 1].lstrip())
            return "\n".join(ls[:lo - 1] + [" " * indent + "pass  # MUTATED"] + ls[hi:])
        out.append((label, patch))
    return out


def _branch_functions(src: str) -> set[str]:
    """The set of function names that OWN at least one inventoried finding-branch — for the oracle
    self-test that _inline_text (data appends) is excluded and check() (verdict appends) is included."""
    tree = ast.parse(src)
    funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]

    def enclosing(line: int):
        cands = [fn for fn in funcs if fn.lineno <= line <= (fn.end_lineno or fn.lineno)]
        return max(cands, key=lambda fn: fn.lineno).name if cands else "?"
    return {enclosing(int(lab.split("@L")[1])) for lab, _ in _finding_branches(src)}


def _appends_to_finding_accum(src: str) -> set[str]:
    """Every function that appends to a findings accumulator (a Name in {findings, errs, out}) — the
    SUPERSET of the sweep's verdict-append functions PLUS the data-append exceptions (_inline_text appends
    to `out`). The oracle asserts each of these is EITHER inventoried by the sweep OR an explicit
    DATA_APPEND exception, so a return-wrapping refactor that quietly drops a verdict function from the
    sweep (condition (ii) unmet — a red-team finding, gate-reviews/0019) is caught."""
    tree = ast.parse(src)
    funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    hits: set[str] = set()
    for fn in funcs:
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "append" and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id in ("findings", "errs", "out"):
                hits.add(fn.name)
    return hits


# (name, stub, covers, expectation, expect_fx). `covers` must be EXACTLY the syntactic units the stub
# mutates — functions OR module-level assignment targets (e.g. _L / _R) — verified against the patch by
# _units_touched (round-10). `expect_fx` (gate-reviews/0018) is a substring of the golden ASSERTION this
# revert must redden; the runner counts a bite only when THAT assertion fails, so a mutant that merely
# reddens some unrelated assertion (a GPT review found the battery treated any red as a bite) is REJECTED
# as MIS-TARGETED. For a decoy/drift GUARD `expect_fx` names a "-> caught"/"is CAUGHT" fixture; for a
# PRODUCER (a renderer, the order loader) whose only correct-behaviour proof is that the pristine docs
# match its output, it names the live-docs baseline — a distinct, honest signal, not a strengthening red.
BASELINE_FX = "live README + prompt pass"   # the pristine-docs check; a PRODUCER's revert reddens it
GUARDS: list[tuple] = [
    ("marker: duplicate pair rejected",
     _sub("if len(begins) != 1 or len(ends) != 1:", "if len(begins) < 1 or len(ends) < 1:"),
     ("_marker_token_span",), "RED", "raises on a DUPLICATE marker pair"),
    ("marker: end-after-begin required",
     _sub("if ends[0] <= begins[0]:", "if False and ends[0] <= begins[0]:"),
     ("_marker_token_span",), "RED", "raises when end precedes begin"),
    ("marker: identity allowlist", _stub("_marker_only_html_block", "True"),
     ("_marker_only_html_block",), "RED", "arbitrary (non-marker) HTML comment"),
    ("raw HTML: block ban", _stub("_stray_html_block", "None"), ("_stray_html_block",), "RED",
     "raw-HTML ban: raw <ol> decoy"),
    ("raw HTML: inline/image ban", _stub("_doc_raw_inline", "None"), ("_doc_raw_inline",), "RED",
     "inline HTML in prose outside markers"),
    # _doc_raw_inline has TWO independent arms (html_inline AND image); the whole-function stub above bites
    # via the html_inline fixtures alone, so the image arm was a load-bearing branch with no biting fixture
    # (gate-reviews/0017, same class as the _table_names guard-a gap). Isolate it: reverting only the image
    # arm reddens the new inline-image golden fixture.
    ("raw HTML: inline IMAGE arm (isolated from html_inline)",
     _sub('if c.type in ("html_inline", "image"):', 'if c.type in ("html_inline",):'),
     ("_doc_raw_inline",), "RED", "inline image in governed-doc prose"),
    # --- SKILL-NAME identifier boundaries (used by _run_hits in the competing scan): `\b` is not enough —
    #     it let a suffix ("skillsets") or prefix pass. Reverting either reddens the look-alike golden
    #     fixtures ("name-notes" / "draft-name" runs must stay CLEAN). ---
    ("name: left boundary", _sub('_L = r"(?<![a-z0-9_-])"', '_L = r""'), ("_L",), "RED",
     "prefix look-alikes ('draft-name')"),
    ("name: right boundary", _sub('_R = r"(?![a-z0-9_-])"', '_R = r""'), ("_R",), "RED",
     "suffix look-alikes ('name-notes')"),
    # --- NORMALIZATION, ONE mutant PER STAGE (gate-reviews/0018): a whole-function _norm stub bit via a
    #     sibling stage and left each stage unproven (a GPT review reproduced this). Each mutant reverts ONE
    #     stage; its isolating _norm-stage golden unit-lock is the only thing that reddens.
    ("normalize stage: initial NFKC (before whitespace-collapse)",
     _sub('s = unicodedata.normalize("NFKC", s)\n', 's = s\n'), ("_norm",), "RED",
     "the initial NFKC runs BEFORE whitespace-collapse"),
    ("normalize stage: zero-width/format (Cf) strip",
     _sub('s = "".join(c for c in s if unicodedata.category(c) != "Cf")', 's = s'), ("_norm",), "RED",
     "removes a soft hyphen (U+00AD)"),
    ("normalize stage: Unicode-dash fold",
     _sub("s.translate(_DASH_MAP)", "s"), ("_norm",), "RED", "maps a modifier-minus (U+02D7)"),
    ("normalize stage: casefold",
     _sub(".strip().casefold()", ".strip()"), ("_norm",), "RED", "casefold lowers a name"),
    ("normalize stage: confusable (homoglyph) fold",
     _sub("s.translate(_CONFUSABLE_MAP)", "s"), ("_norm",), "RED", "maps a Cyrillic 'о' (U+043E)"),
    ("normalize stage: final NFKC (idempotence)",
     _sub('return unicodedata.normalize("NFKC", s.translate(_CONFUSABLE_MAP))',
          "return s.translate(_CONFUSABLE_MAP)"), ("_norm",), "RED",
     "U+0390 idempotent"),
    # --- ANCHOR adjacency (the begin marker must be immediately preceded by its lead-in) ---
    ("anchor: begin marker must follow its lead-in", _stub("_anchor_missing", "False"),
     ("_anchor_missing",), "RED", "moving the block away from its lead-in is CAUGHT"),
    # _anchor_missing's FAIL-CLOSED branch (a site id absent from ANCHORS returns True) is separate from the
    # adjacency check the whole-function stub bites via; reverting it to `return False` silently accepts an
    # unregistered marked site. Isolated (gate-reviews/0017), proven by the unregistered-site unit lock.
    ("anchor: unregistered site id fails closed",
     _sub("    if not anchor:\n        return True", "    if not anchor:\n        return False"),
     ("_anchor_missing",), "RED", "an unregistered site id (not in ANCHORS) fails closed"),
    # _preceding_visible READS the lead-in text; its correct-behaviour proof is FP-prevention — a valid
    # paragraph lead-in stays recognized. Reverting it to "" over-flags, so the plain-paragraph unit lock
    # (distinct to this function) reddens.
    ("anchor: preceding-unit adjacency", _stub("_preceding_visible", '""'),
     ("_preceding_visible",), "RED", "a plain-paragraph lead-in is recognized"),
    # _preceding_visible has a second branch: a lead-in formatted as a blockquote/list (not a bare
    # paragraph) is still read, so an intact-but-reformatted lead-in is not a false "moved away"
    # (gate-reviews/0017). Reverting only the container branch reddens the blockquote/list lead-in fixtures.
    ("anchor: blockquote/list lead-in recognized (container branch)",
     _sub("    if prev.type in _CONTAINER_CLOSE:", "    if False and prev.type in _CONTAINER_CLOSE:"),
     ("_preceding_visible",), "RED", "a BLOCKQUOTE lead-in (intact anchor, adjacent) is recognized"),
    # --- COMPETING scan + its aggregation/boundary helpers ---
    ("competing: whole scan", _stub("_competing_findings", "[]"), ("_competing_findings",), "RED",
     "competing route 'comma paragraph' is CAUGHT"),
    ("competing: near-complete run required (not any two names)",
     _sub("_run_hits(text, order) >= max(2, len(order) - 1)", "_run_hits(text, order) >= 2"),
     ("_competing_run",), "RED", "a two-item skill list is NOT flagged"),
    ("competing: scans code blocks too (separator-free fence)",
     _sub('t.content if t.type in ("fence", "code_block") else ""', '""'),
     ("_competing_findings",), "RED", "competing route 'separator-free fence' is CAUGHT"),
    # the two arms above cover FENCES; the code_block (indented) arm is separately load-bearing and, until
    # 0017, unproven (every fixture used a fence). Isolate each: phase-1 single-unit and phase-2 container
    # aggregation must both read code_block tokens, proven by the indented + blockquote-split golden fixtures.
    ("competing: phase-1 reads INDENTED code blocks (code_block arm)",
     _sub('t.content if t.type in ("fence", "code_block") else ""',
          't.content if t.type in ("fence",) else ""'), ("_competing_findings",), "RED",
     "stray INDENTED (code_block) list of all skills is CAUGHT"),
    ("competing: phase-2 aggregates INDENTED code blocks (code_block arm)",
     _sub('for x in tokens[i:j + 1] if x.type in ("inline", "fence", "code_block")',
          'for x in tokens[i:j + 1] if x.type in ("inline", "fence")'), ("_competing_findings",), "RED",
     "blockquote split across a paragraph + indented code block is CAUGHT"),
    ("competing: aggregate within each container (list / blockquote)",
     _sub("if _competing_run(agg, order):", "if False and _competing_run(agg, order):"),
     ("_competing_findings",), "RED", "competing route 'ordered list' is CAUGHT"),
    ("competing: aggregate outside-table cells",
     _sub("if _competing_run(allcells, order):", "if False and _competing_run(allcells, order):"),
     ("_competing_findings",), "RED", "competing second table"),
    ("competing: name-boundary hit count", _stub("_run_hits", "0"), ("_run_hits",), "RED",
     "competing route 'comma paragraph' is CAUGHT"),
    # _in_any_span EXCLUDES the five marked enumerations from the competing scan; reverting it makes them
    # self-flag, so a valid doc no longer stays clean (FP-prevention proof).
    ("competing: outside-block exclusion", _stub("_in_any_span", "False"), ("_in_any_span",), "RED",
     "a 2-row reference table is NOT flagged"),
    ("competing: container span", _stub("_container_close", "start"), ("_container_close",), "RED",
     "competing route 'ordered list' is CAUGHT"),
    ("competing: table span", _stub("_table_span_close", "start"), ("_table_span_close",), "RED",
     "competing second table"),
    ("competing: table cell reconstruction", _stub("_table_cells", "([], [])"), ("_table_cells",), "RED",
     "competing second table"),
    # --- TABLE first-column + PURE/FENCE region grammar. _table_names has TWO independent return-None
    #     guards (round-12 found only one was proven): a) the region holds EXACTLY ONE table; b) the region
    #     BEGINS and ENDS with it. Each has its own stub + biting fixture.
    ("table: region holds exactly one table",
     _sub("    if sum(1 for t in inner if t.type == \"table_open\") != 1:",
          "    if False:"), ("_table_names",), "RED", "a second (header-only) table inside the table region"),
    ("table: region begins/ends with the table",
     _sub("    if inner[0].type != \"table_open\" or inner[-1].type != \"table_close\" "
          "or inner[0].level != 0:", "    if False:"), ("_table_names",), "RED",
     "stray paragraph inside the table region"),
    ("pure region: exactly one paragraph",
     _sub('if len(inner) == 3 and inner[0].type == "paragraph_open"',
          'if len(inner) >= 3 and inner[0].type == "paragraph_open"'), ("_pure_source",), "RED",
     "decoy fence inside the improve-order region"),
    ("fence region: exactly one fence",
     _sub('if len(inner) == 1 and inner[0].type == "fence"',
          'if len(inner) >= 1 and inner[0].type == "fence"'), ("_fence_body",), "RED",
     "decoy paragraph inside the tree region"),
    # the PURE/TREE block comparison (`src != renderer(order)` / `body != _tree_body(order)`) is what catches
    # drift in a marked pure block. WEAKENING each (disable the comparison) reddens the drift fixture — the
    # right proof for a rejection guard (gate-reviews/0018; a renderer-BYTES stub only broke the baseline).
    ("site: tree comparison",
     _sub("if body != _tree_body(order):", "if False and body != _tree_body(order):"),
     ("check",), "RED", "drift tree (rename last node)"),
    ("site: pure block comparison (improve-order / pick-list drift)",
     _sub("if src != renderer(order):", "if False and src != renderer(order):"),
     ("check",), "RED", "drift improve-order"),
    # --- SOURCE of truth + renderers ---
    ("source: empty skills/ fails closed", _sub("    if not canonical:\n", "    if False:\n"),
     ("check",), "RED", "empty skills/ -> check() fails closed"),
    ("source: skills-order permutation", _stub("validate_order", "[]"), ("validate_order",), "RED",
     "order: dup rejected"),
    # PRODUCERS: load_order supplies the order, and the three renderers generate the expected block bytes.
    # Their correct-behaviour proof is that the pristine docs MATCH — so each revert reddens the live-docs
    # baseline (an honest producer signal, distinct from a decoy catch). The drift catch itself is proven by
    # the two comparison stubs above.
    ("source: load_order supplies the order every block is checked against",
     _stub("load_order", "([], [])"), ("load_order",), "RED", BASELINE_FX),
    ("renderer: improve-order bytes", _stub("render_improve_order", '"**decoy.**"'),
     ("render_improve_order",), "RED", BASELINE_FX),
    ("renderer: pick-list bytes", _stub("render_pick_list", '"decoy"'), ("render_pick_list",), "RED",
     BASELINE_FX),
    ("renderer: tree body bytes", _stub("_tree_body", '"decoy"'), ("_tree_body",), "RED", BASELINE_FX),
    # ============================ 0019 (round-15 GPT BLOCK) ============================
    # Each mutant is bound (expect_fx) to the golden fixture that must redden and touches EXACTLY its
    # declared unit (verified by _units_touched). Every break-test below was reproduced at HEAD.
    # BLOCKER-2 completeness: the finding-branch SWEEP safely pass-neuters only appends + raises (a
    # finding-emitting RETURN cannot be pass-neutered without returning None and crashing its callers), so
    # the two finding-RETURN branches that lack a curated stub are covered here (the empty-skills return
    # literal is covered by the `if not canonical:` guard above). Each reverts the RETURN to a benign value.
    ("check: validation errors are forwarded (if errs: return errs)",
     _sub("    if errs:\n        return errs\n", "    if errs:\n        pass\n"),
     ("check",), "RED", "a new skill dir absent from skills-order is reported"),
    ("check: the final verdict returns the findings (not always-clean)",
     _sub("    return findings\n", "    return []\n"),
     ("check",), "RED", "drift improve-order"),
    # BLOCKER-1: the CLI VERDICT PATH (main). `if findings:` and its `return 1` are all that separate a
    # drifted doc from a clean-banner exit 0; the scratch (check()-direct) fixtures never exercised main.
    ("cli: findings gate the exit code + banner",
     _sub("    if findings:\n", "    if False and findings:\n"), ("main",), "RED",
     "CLI --check on a DRIFTED doc"),
    ("cli: the findings branch exits nonzero",
     _sub("        return 1\n    n = len(canonical_skills(root))",
          "        return 0\n    n = len(canonical_skills(root))"), ("main",), "RED",
     "CLI --check on a DRIFTED doc"),
    # MAJOR-3: the source-of-truth PRODUCERS must READ their files, not just reproduce today's output.
    ("source: load_order READS skills-order (not a hardcoded order)",
     _sub('    order = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()\n'
          '             if ln.strip() and not ln.strip().startswith("#")]',
          '    order = ["learning-track", "architecture-and-decisions", "project-faq", "usage-guide", '
          '"operations-runbook", "onboarding-companion", "doc-critic", "publish-mirror"]'),
     ("load_order",), "RED", "swapping two order lines"),
    ("source: canonical_skills READS skills/ (a new dir must surface)",
     _sub('    return {p.name for p in sk.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()}',
          '    return {p.name for p in sk.iterdir() if p.is_dir() and (p / "SKILL.md").is_file() '
          'and p.name != "fixture-new-skill"}'),
     ("canonical_skills",), "RED", "a new skill dir absent from skills-order is reported"),
    # MAJOR-4a: the raw-HTML ban scans BOTH governed files. Dropping PROMPT stayed green (every decoy was
    # in README). Bound to the PROMPT-side data-driven fixtures.
    ("raw HTML: ban scans BOTH governed files (not just README)",
     _sub("    for fname in (README, PROMPT):\n        if fname in tokens:\n"
          "            stray = _stray_html_block(tokens[fname])",
          "    for fname in (README,):\n        if fname in tokens:\n"
          "            stray = _stray_html_block(tokens[fname])"),
     ("check",), "RED", "in per-skill-review-prompt.md is CAUGHT"),
    # MAJOR-4b: the marker allowlist is EXACTLY the five CURRENT site ids; re-adding the retired count ids
    # must not be silently accepted. Bound to the retired-marker fixtures.
    ("marker allowlist: exactly the five CURRENT site ids (retired ids rejected)",
     _sub("    for site_id in [s[0] for s in PURE_SITES] + [s[0] for s in TABLE_SITES]:",
          "    for site_id in [s[0] for s in PURE_SITES] + [s[0] for s in TABLE_SITES] "
          "+ ['count-suite', 'count-nskill']:"),
     ("_allowed_marker_comments",), "RED", "retired marker <!-- skills:count-suite:begin -->"),
    # MAJOR-5: _preceding_visible's HEADING arm and its two _norm call sites were unproven (only paragraph /
    # blockquote / list lead-ins, all lowercase-ASCII, were exercised). Three isolated mutants, each bound
    # to its heading / normalized lead-in fixture.
    ("anchor: heading lead-in arm",
     _sub('prev.type in ("paragraph_close", "heading_close")', 'prev.type in ("paragraph_close",)'),
     ("_preceding_visible",), "RED", "a HEADING lead-in is recognized"),
    ("anchor: _norm on the paragraph/heading arm",
     _sub("return _norm(_inline_text(tokens[begin_idx - 2]))",
          "return _inline_text(tokens[begin_idx - 2])"),
     ("_preceding_visible",), "RED", "NORMALIZED paragraph lead-in"),
    ("anchor: _norm on the container arm",
     _sub('return _norm(" ".join(_inline_text(t) for t in tokens[start:begin_idx] if t.type == "inline"))',
          'return " ".join(_inline_text(t) for t in tokens[start:begin_idx] if t.type == "inline")'),
     ("_preceding_visible",), "RED", "NORMALIZED blockquote lead-in"),
]

# Load-bearing functions (reachable from check) that are NOT given a source-mutation stub — each is
# EXPLICITLY exempted here with a reason, so the exemption is reviewable rather than hidden (round-12 F8:
# every function on the verdict path must be a stub target OR a reasoned exemption).
NON_GUARD = {
    "_inline_text": "accumulates rendered text; a revert is proven transitively by every check that reads "
                    "it (e.g. stubbing it empties all text, reddening the baseline) — data, not a verdict. "
                    "It appends to a local `out` but RETURNS ''.join(out), so the finding-branch sweep's "
                    "semantic inventory (gate-reviews/0019) correctly excludes those DATA appends",
    "_read": "reads a governed doc; a missing/unreadable doc is caught by check()'s per-site 'not found' "
             "guard (its own stubs), not here",
    "_canon_markers": "constructs a site's (begin,end) marker strings from its id — pure formatting",
    "_md": "fail-closed on a MISSING parser: its `raise MarkerError` branch is proven by the golden "
           "absent-parser fixture, which now catches ANY exception and asserts the MarkerError type+message "
           "(gate-reviews/0019), so neutering the raise reddens as an ASSERTION (was a suite-aborting crash "
           "the sweep wrongly accepted). The function as a whole is not source-stubbed — stubbing _md=None "
           "crashes downstream, which is not an assertion catch",
    "render_tree": "wraps _tree_body in a fenced block for the WRITER (write); check() compares _tree_body "
                   "DIRECTLY (its own stub), so the gate verdict does not depend on render_tree",
    "write": "dev-convenience: fills the three pure blocks in place from skills-order. NOT a verdict — the "
             "gate is check(), which re-verifies whatever write produced. Reachable only from main",
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
    verdict, detail, _, _ = _run(None)
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
    # `renderer(order)` call the static call graph cannot resolve to a name), AND main() — the CLI verdict
    # path (exit code + clean banner) is a guard of its own (gate-reviews/0019 BLOCKER-1), so it belongs in
    # the measured set, not exempted as "plumbing". main pulls in write()/render_tree, exempted above as
    # dev-convenience (check() re-verifies their output).
    load_bearing = _reachable_from(gen_src, {"check", "render_improve_order", "render_pick_list", "main"})
    claimed = {fn for entry in GUARDS for fn in entry[2]}
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
    for name, patch, covers, _expect, _fx in GUARDS:
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

    print("\n3. mutation quality + verdict (each RED must redden its DECLARED fixture, not merely some red)")
    failures, redundant, seen = [], [], {}
    for name, patch, _covers, expect, expect_fx in GUARDS:
        verdict, detail, fp, failed = _run(patch)
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
        if verdict != "RED":
            failures.append((name, f"{verdict}: {detail}"))
            print(f"   [{verdict}] {name} — {detail}")
        elif not any(expect_fx in fn for fn in failed):
            # RED, but the wrong assertion(s) reddened — the mutant proves nothing about its guard
            # (gate-reviews/0018). This catches a STRENGTHENING revert whose red is only the baseline
            # breaking, or a mis-authored stub that trips an unrelated fixture.
            failures.append((name, f"MIS-TARGETED — reddened {sorted(failed)[:2]} but NOT its declared "
                                   f"fixture '{expect_fx}'"))
            print(f"   [MIS-TARGETED] {name} — expected '{expect_fx}' to fail; it did not")
        else:
            print(f"   [BITES] {name}" + (f" — reddens '{expect_fx}'" if args.verbose else ""))

    print("\n4. finding-branch sweep — EVERY MarkerError raise + verdict-accumulator append (SEMANTIC "
          "inventory: an append whose accumulator the function RETURNS) reverted to a no-op must redden "
          "golden, and reddening means an assertion FAILURE (RED) — not a crash/timeout (gate-reviews/0019)")
    # Inventory ORACLE self-test: the inventory must be SEMANTIC. _inline_text appends to a local `out` but
    # returns "".join(out), so its DATA appends must be EXCLUDED; check() returns `findings`, so its verdict
    # appends must be INCLUDED. A vacuous inventory that swept data appends would 'cover' them by emptying
    # all rendered text (an unrelated red), and under the RED requirement below that stray red would pass.
    branch_fns = _branch_functions(orig)
    #  - _inline_text appends to `out` but returns "".join(out) (a string) -> EXCLUDED (condition ii);
    #  - _table_cells returns `rows` (a DATA list, not a findings accumulator) -> EXCLUDED (condition i);
    #  - check() appends to `findings` and returns it -> INCLUDED.
    for data_fn in ("_inline_text", "_table_cells"):
        if data_fn in branch_fns:
            print(f"   INVENTORY ORACLE BROKEN: {data_fn}'s DATA appends were inventoried as finding-branches")
            return 2
    if "check" not in branch_fns:
        print("   INVENTORY ORACLE BROKEN: check()'s verdict appends were NOT inventoried")
        return 2
    # INCLUSION for EVERY verdict-append function, not just check(): every function that appends to a
    # findings/errs/out accumulator must be inventoried by the sweep OR be an explicit DATA_APPEND
    # exception. Without this, a return-wrapping refactor (`return sorted(out)`) on validate_order /
    # load_order / _competing_findings would silently drop its branches (condition (ii) unmet) while the
    # oracle stayed green — a red-team finding (gate-reviews/0019).
    DATA_APPEND_FNS = {"_inline_text"}   # appends to `out` but returns "".join(out) — data, not a verdict
    dropped = _appends_to_finding_accum(orig) - branch_fns - DATA_APPEND_FNS
    if dropped:
        print(f"   INVENTORY ORACLE BROKEN: verdict-append function(s) {sorted(dropped)} append to a "
              f"findings accumulator but are NOT inventoried (a wrapped return? add to the sweep or, if "
              f"the append is data, to DATA_APPEND_FNS)")
        return 2
    print("   ok — inventory is semantic (data appends excluded, ALL verdict-append functions included)")
    branches = _finding_branches(orig)
    sweep_fail = []
    for label, patch in branches:
        verdict, detail, _fp, _failed = _run(patch)
        if verdict != "RED":
            # GREEN = no biting fixture; CRASH / HARNESS / PATCH-MISS = the revert does not produce a clean
            # reddening ASSERTION (a crash is not an assertion catch — gate-reviews/0019 BLOCKER-2), so the
            # branch is NOT proven caught.
            tag = "UNCOVERED" if verdict == "GREEN" else verdict
            sweep_fail.append((label, f"revert produced {verdict} (not RED): {detail[:60]}"))
            print(f"   [{tag}] {label}")
        elif args.verbose:
            print(f"   [reddens] {label}")
    if not sweep_fail:
        print(f"   ok — all {len(branches)} finding-branches redden golden (RED) on revert")

    proven = len(GUARDS) - len(failures) - len(redundant)
    print(f"\n--- revert battery: {proven}/{len(GUARDS) - len(redundant)} stubs bite; "
          f"{covered}/{len(load_bearing)} verdict-path functions covered; "
          f"{len(GUARDS) - len(prov_fail)}/{len(GUARDS)} provenance-clean; "
          f"{len(branches) - len(sweep_fail)}/{len(branches)} finding-branches redden ---")
    for fn in owed:
        print(f"    OWED: {fn}() is on the verdict path but is neither stubbed nor exempted")
    for name, why in prov_fail:
        print(f"    MIS-CLAIM: {name} — {why}")
    for name, why in failures:
        print(f"    NOT PROVEN: {name} — {why}")
    for label, why in sweep_fail:
        print(f"    UNCOVERED BRANCH: {label} — {why}")
    return 1 if (owed or failures or prov_fail or sweep_fail) else 0


if __name__ == "__main__":
    sys.exit(main())
