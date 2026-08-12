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
    The two HTML goldens are GENERATED here from the committed generators (not stored). Their ©/credits/
    ISO-stamp defaults are asserted DIRECTLY on the regenerated HTML, so a generator that stops emitting
    any one fails this test — the exact original-sin failure (CROSS-SKILL-FINDINGS.md F4). (verify.py's
    0-FAIL catches only the ©; credits is un-gated and a missing ISO stamp is INFO, so the direct marker
    assertions, not the verify pass, are what lock credits + ISO.)
  golden-bad (each must be CAUGHT by the right gate; the lint cases replay the REAL motivating incident):
    - a public page with no © footer            -> verify.py FAIL (licensing gate; F4 verifier-catch half)
    - a real-shaped AWS access key on a page     -> verify.py FAIL (secret/PII scan)
    - a years-old ISO last-reviewed stamp        -> verify.py WARN (staleness; WARN-only by design)
    - a SKILL.md restating the map (F1, verbatim) -> render-restatement lint CAUGHT
    - an unresolved {{...}} placeholder (F5)      -> placeholder lint CAUGHT ({{today}}/key still resolve)
  Deterministic pins (today-pinned / non-default threshold, so a silent fallback cannot pass green):
    - staleness boundary at --max-age-months 3 and a pinned today (old->WARN, recent->INFO,
      future->WARN, and BOTH bold-label forms still read — the regression lock for the bold-label fix)
    - a Flesch-Kincaid grade pin on a fixed string (so "simplify until green" cannot game the gate by
      turning readability into a no-op)
  gate-review-check.py (the enforcement linchpin's own regression, CONTRIBUTING.md requirement ii):
    - matches_gate classifies gate vs non-gate paths AND keeps the enforcement's own files self-included;
      decide_verdicts/effective_verdict accept a clean PASS (full: real coverage fraction; light: N/A +
      justification; findings carry file:line or 'none') and reject the rubber-stamp vectors a review
      caught (PASS in prose over a BLOCK, coverage 0/0 / outside replay, PASS-WITH-NITS, co-committed BLOCK)
    - the evaluate_verdicts SEAM end-to-end against a temp root: one on-disk light verdict held fixed,
      only the changed gate paths flipped — light clears ONLY for the inert allow-listed doc
      (gate-reviews/README.md) and is refused (full review) for code, the .github/ subtree, the behavioral
      governance docs, AND gated markdown under tests/ (the class the old denylist wrongly admitted)
  manifest byte-stability (pkgtools.write_manifest, item 2):
    - two runs on identical content produce byte-identical bytes, with no build-commit / timestamp field
      (a re-added volatile field would reinstate the spurious-diff failure this guards)

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
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED_VERIFY = ROOT / "shared" / "verify.py"
PROFILE = ROOT / "shared" / "project-profile.md"
LRR = ROOT / "lint-render-restatement.py"
LINT_PLACEHOLDERS = ROOT / "lint-placeholders.py"
FAQ_GEN = ROOT / "skills" / "project-faq" / "assets" / "faq_generator.py"
UG_GEN = ROOT / "skills" / "usage-guide" / "assets" / "usage_guide_generator.py"
GOLDEN_GOOD = ROOT / "tests" / "golden-good"
GOLDEN_BAD = ROOT / "tests" / "golden-bad"
REVIEW_PLAYBOOK = ROOT / "skills" / "doc-critic" / "references" / "review-playbook.md"
GATE_REVIEW_CHECK = ROOT / "gate-review-check.py"
GEN = ROOT / "generate-skill-enumerations.py"
GATE_RECORD = ROOT / "gate-reviews" / "0005-skill-enumeration-gate.md"
CONTRIB = ROOT / "CONTRIBUTING.md"
PKGTOOLS = ROOT / "pkgtools.py"

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

# doc-critic is non-deterministic — there is no critique to run as a golden. What CAN be locked is the
# internal consistency of its METHOD docs: review-playbook.md's "Why this shape" evidence paragraph
# cites three highest-severity findings, each attributed to ONE axis, and the taxonomy obligates a
# specific axis to catch that finding's error class. Each tuple: (a stable needle from the evidence
# paragraph, the axis tag that must follow it, the error class the finding exemplifies).
DOC_CRITIC_FINDINGS = [
    ("report output the code did not emit", "(code-grounded axis)", 3),
    ("safeguard it later disowned", "(whole-document axis)", 1),
    ("analogy teaching the wrong shape for a core term", "(whole-document axis)", 2),
]
# The class->axis coverage the playbook documents in its "Catches classes ..." lines, pinned as exact
# (whitespace-normalized) substrings so a coverage edit must update this pin too.
AXIS_COVERAGE = {
    "(whole-document axis)": ("Catches classes 1, 2, 6, 7", {1, 2, 6, 7}),
    "(code-grounded axis)": ("Catches classes 3, 5", {3, 5}),
}


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

    # These two HTML goldens are the GENERATOR-REGRESSION half of CROSS-SKILL-FINDINGS.md F4 (root
    # CHANGELOG 1.0.0): they are regenerated from the LIVE generators, so a generator that stops emitting
    # its ©-footer / credits / ISO-stamp defaults is caught — the original-sin "a page shipped failing
    # its own gate". IMPORTANT: verify.py's 0-FAIL check catches ONLY the © (a missing © footer FAILs on
    # a public page); a missing last-reviewed stamp is INFO and there is no credits gate, so 0-FAIL alone
    # would NOT catch a dropped credits block or ISO stamp. So the ©/credits/ISO defaults are locked by
    # DIRECT marker assertions on the regenerated HTML (below), not by the verify pass. The verifier-catch
    # half (the © specifically) is golden_bad case 1 (missing-© page).
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

    # F4 generator-regression lock (DIRECT): each regenerated page must CONTAIN all three defaults, so a
    # generator that stops emitting any one is caught here — including credits and the ISO stamp, which
    # verify.py treats as no-gate / INFO (so the 0-FAIL cases above catch only the © by themselves).
    for gname, gout in (("FAQ", faq_out), ("usage-guide", ug_out)):
        html = gout.read_text(encoding="utf-8")
        res.check("©" in html, f"F4 generator emits the © footer ({gname})",
                  "©" if "©" in html else "MISSING ©")
        # Marker is the rendered credits-block div ATTRIBUTE, not a bare "credit" substring nor the CSS
        # class name: "credit" appears ~15x incidentally (the licensing-and-credits footer link) and the
        # bare "box-credits" is in the <style> block too — both survived the block being dropped in a
        # break-test. Only the emitted `class="box box-credits"` attribute vanishes when the block does
        # (verified in both generators), so it is the marker that genuinely locks the block's presence.
        has_credits = 'class="box box-credits"' in html
        res.check(has_credits, f"F4 generator emits the credits block ({gname})",
                  "credits block present" if has_credits else "MISSING credits block")
        iso_ok = 'name="last-reviewed"' in html and PINNED_REVIEW_DATE in html
        res.check(iso_ok, f"F4 generator emits the ISO last-reviewed stamp ({gname})",
                  f"stamp {PINNED_REVIEW_DATE}" if iso_ok else "MISSING ISO last-reviewed stamp")


def golden_bad(res: Results, verbose: bool) -> None:
    print("golden-bad — each broken doc must be caught by the right gate:")

    # 1. Missing © on a public page -> licensing gate FAIL (exit 1).
    # Real incident: CROSS-SKILL-FINDINGS.md F4 (root CHANGELOG 1.0.0) — usage-guide's hand-written HTML
    # shipped without the ©-footer/credits/ISO-stamp defaults, and "only the © was caught, by the
    # verifier, after the fact." This replays that verifier catch (the generator-regression direction is
    # locked separately by golden_good, which regenerates from the live generators).
    rc, out = run_verify(GOLDEN_BAD / "missing-copyright.html", "html", "project-faq", "public", "8")
    ok = (rc == 1 and "licence footer" in out.lower())
    res.check(ok, "F4 missing-© public page -> licensing FAIL",
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
    # Real incident: CROSS-SKILL-FINDINGS.md F1 (root CHANGELOG 1.0.0) — project-faq's SKILL.md Step 6
    # restated the per-element HTML->wiki mapping ("each tab or section becomes a heading, callouts
    # become panels"), a second copy of render-contract.md 1a. The fixture carries that verbatim
    # construction, so this replays the actual leak the lint exists to catch (not a synthetic shape).
    lrr = _load("lrr", LRR)
    f1_src = (GOLDEN_BAD / "restated-mapping" / "SKILL.md").read_text(encoding="utf-8")
    findings = lrr.scan_skill(GOLDEN_BAD / "restated-mapping" / "SKILL.md")
    matched = " ".join(txt.lower() for _, txt in findings)
    # The lint matches the connective+idiom span, so F1's "callouts become panels" surfaces as the
    # "become panels" mapping. Assert (a) that exact span is caught AND (b) the fixture still carries F1's
    # verbatim construction — so the case cannot be satisfied by a generic mapping, and the fixture cannot
    # be quietly weakened back to a synthetic shape while staying green. (Ties to the incident, not to a
    # brittle line number — which would just move the anchor-churn problem into the test.)
    ok = (len(findings) >= 1 and "become panels" in matched
          and "callouts become panels" in f1_src.lower())
    detail = (", ".join(f"L{ln}:{txt!r}" for ln, txt in findings)) if verbose else f"{len(findings)} finding(s)"
    res.check(ok, "F1 restated render mapping (verbatim 'callouts become panels') -> CAUGHT", detail)

    # 5. Unresolved {{...}} placeholder -> placeholder lint CAUGHT (the real gap this PR backfills).
    # Real incident: CROSS-SKILL-FINDINGS.md F5 (root CHANGELOG 1.0.0) — project-faq's faq-method
    # reference carried `"{{today}}"`, which backed to no profile key / manifest slot / runtime token.
    # The fix documented a Runtime tokens set and added lint-placeholders.py. The fixture locks BOTH
    # directions: the still-unresolvable `{{todays_date}}` is caught, while the now-documented `{{today}}`
    # and a real profile key resolve cleanly (a regression dropping {{today}} from the runtime set would
    # add it to `flagged` and turn this red). Driven through scan_text — the seam its docstring names.
    lp = _load("lintplaceholders", LINT_PLACEHOLDERS)
    known = lp.known_keys(ROOT)
    p_findings = lp.scan_text((GOLDEN_BAD / "unresolved-placeholder.md").read_text(encoding="utf-8"), known)
    flagged = {tok for _, tok in p_findings}
    ok = bool(p_findings) and flagged == {"todays_date"}
    detail = (f"flagged={sorted(flagged)}" if verbose else f"{len(p_findings)} finding(s)")
    res.check(ok, "F5 unresolved {{todays_date}} -> placeholder lint CAUGHT ({{today}}/key resolve)", detail)


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


def doc_critic_mapping(res: Results, verbose: bool) -> None:
    """Lock review-playbook.md's evidence paragraph to the taxonomy's class->axis mapping.

    doc-critic is non-deterministic, so there is no critique to run as a golden. What is locked here is
    the internal consistency of its METHOD docs (Section "Why this shape"): three highest-severity
    findings, each attributed to one axis, against the taxonomy that obligates a specific axis to catch
    that finding's error class. Whitespace-normalized, so line wrapping is irrelevant; it fails only if
    an evidence attribution or a documented axis-coverage line genuinely drifts.
    """
    print("doc-critic taxonomy↔axis mapping (method docs stay self-consistent):")
    norm = re.sub(r"\s+", " ", REVIEW_PLAYBOOK.read_text(encoding="utf-8"))
    # Scope the evidence findings to the final "Why this shape" section, so a needle that also appears
    # in the taxonomy list above cannot match the wrong occurrence.
    h = norm.find("Why this shape")
    evidence = norm[h:] if h != -1 else ""

    # 1. Each documented "Catches classes ..." coverage line is still present (locks class->axis).
    for tag, (cov_substr, _classes) in AXIS_COVERAGE.items():
        ok = cov_substr in norm
        res.check(ok, f"coverage line present for {tag}",
                  cov_substr if verbose else ("found" if ok else "MISSING"))

    # 2. Each evidence finding appears exactly once in that section, is attributed to its axis, and
    #    that axis is the one the taxonomy obligates to catch the finding's class.
    for needle, tag, klass in DOC_CRITIC_FINDINGS:
        i = evidence.find(needle)
        attributed = i != -1 and tag in evidence[i: i + len(needle) + 60]
        unique = evidence.count(needle) == 1
        obligated = klass in AXIS_COVERAGE[tag][1]
        ok = attributed and unique and obligated
        detail = (f"class {klass} → {tag}" if ok
                  else f"attributed={attributed} unique={unique} obligated={obligated}")
        res.check(ok, f'evidence finding "{needle[:28]}…" mapped', detail)


def gate_review_check(res: Results, verbose: bool) -> None:
    """Regression fixture for gate-review-check.py — the enforcement linchpin (CONTRIBUTING.md
    requirement ii applied to the new mechanism itself). Locks the path classifier, the load-bearing
    SELF-INCLUSION property (the enforcement's own files are gate-layer), the proportional review tiers
    (full needs a real coverage fraction; light is for INERT gated docs only — gate-reviews/README.md —
    via light_admissible, so the behavioral governance docs and code/config take full), findings-evidence
    rule, and the rubber-stamp vectors an independent review caught — so a future no-op revert of any of
    them turns this red. Pure: drives the imported functions, no network, no clock."""
    print("gate-review-check (the enforcement linchpin guards itself):")
    grc = _load("grc", GATE_REVIEW_CHECK)
    patterns = grc.load_gate_patterns(grc.GATE_PATHS_FILE)

    # 1. Path classification: gate-layer vs not.
    gate_paths = ["build-skills.sh", "lint-anything.py", "tests/run-golden.py",
                  ".github/workflows/gate-review.yml", "shared/verify.py", "shared/ci/verify-docs.yml",
                  "check-version.py", "gate-review-check.py", "docs/SETTINGS.md"]
    non_gate = ["README.md", "shared/house-style.md", "skills/doc-critic/SKILL.md",
                "shared/render-contract.md"]
    missed = [p for p in gate_paths if not grc.matches_gate(p, patterns)]
    false_gated = [p for p in non_gate if grc.matches_gate(p, patterns)]
    res.check(not missed, "matches_gate: every gate path is classified gate-layer",
              ", ".join(missed) or "all gated")
    res.check(not false_gated, "matches_gate: non-gate paths are not gated",
              ", ".join(false_gated) or "none gated")

    # 1a. SELF-INCLUSION (load-bearing): the enforcement's OWN files must be gate-layer, or the gate
    # could be weakened in an unreviewed PR and the whole edifice unravels from the inside.
    enforcement = ["gate-review-check.py", "gate-review-prompt.md", ".github/workflows/gate-review.yml",
                   ".github/gate-paths", ".github/CODEOWNERS", "CONTRIBUTING.md", "gate-reviews/TEMPLATE.md"]
    self_missed = [p for p in enforcement if not grc.matches_gate(p, patterns)]
    res.check(not self_missed, "self-inclusion: the enforcement's own files are gated",
              ", ".join(self_missed) or "all self-included")

    # 1b. light_admissible (pure): light is for INERT gated docs only (today: gate-reviews/README.md).
    # The behavioral governance docs (lenses/contract/policy/ruleset) and all code/config take full.
    # REGRESSION (PR #9 gate-review): an earlier denylist predicate ("any '*.md' not in the behavioral
    # set") was open-by-default and admitted any OTHER gated markdown — fixtures under tests/, files under
    # .github/, the shared/ci/ docs-as-code gate — for the light path, though those are gate-layer
    # subtrees. The closed allow-list refuses them; these cases lock that (each was True under the bug).
    # The subtree sample is EXHAUSTIVE over the gated-markdown subtrees in .github/gate-paths (tests/,
    # .github/, shared/ci/) — a partial sample is the 2-of-5 trap (a guard that covers some sites of its
    # class while a re-broadening slips through an unsampled one).
    light_cases = [
        (["gate-review-prompt.md"], False), (["CONTRIBUTING.md"], False),
        (["docs/SETTINGS.md"], False), (["gate-reviews/TEMPLATE.md"], False),
        (["gate-reviews/README.md"], True), (["gate-reviews/README.md", "CONTRIBUTING.md"], False),
        ([], False),
        # gated markdown under a subtree must NOT be light-eligible (the closed-allow-list fix):
        (["tests/golden-bad/leaked-credential.md"], False),
        (["tests/golden-good/learning-track-module.md"], False),
        ([".github/PULL_REQUEST_TEMPLATE.md"], False),
        (["shared/ci/README.md"], False),
        (["gate-reviews/README.md", "tests/golden-bad/leaked-credential.md"], False),
    ]
    for paths, want in light_cases:
        got = grc.light_admissible(paths)
        res.check(got == want, f"light_admissible({paths})", f"got {got} want {want}")

    # 2. Verdict decision — a well-formed PASS clears; the rubber-stamp vectors a review caught block.
    base = ("- Prompt: gate-review-prompt.md v1.0.0\n"
            "## Replay the real failure\nCoverage: {cov}\n{body}"
            "## Coverage vs advertising\nx\n## Self-description drift\nx\n"
            "## Fixture requirement\nx\n## Findings\n{find}\nVerdict: {v}\n")
    good = base.format(cov="5/5 sites", body="", find="none", v="PASS")
    good_anchor = base.format(cov="5/5", body="", find="MAJOR gate-review-check.py:66 — fixed", v="PASS")
    vague = base.format(cov="5/5", body="", find="looks fine to me", v="PASS")
    prose_block = base.format(cov="5/5", body="I may only write Verdict: PASS once clean.\n",
                              find="BLOCKER: x", v="BLOCK")
    zero = base.format(cov="0/0", body="", find="none", v="PASS")
    nits = base.format(cov="5/5", body="", find="none", v="PASS-WITH-NITS")
    full_na = base.format(cov="N/A", body="", find="none", v="PASS")
    misplaced = ("- Prompt: gate-review-prompt.md v1.0.0\n## Replay the real failure\n"
                 "measured coverage on 6/29\n## Coverage vs advertising\nx\n## Self-description drift\n"
                 "x\n## Fixture requirement\nx\n## Findings\nCoverage: 3/5\nVerdict: PASS\n")
    light_base = ("- Prompt: gate-review-prompt.md v1.0.0\nTier: light\n{just}"
                  "## Replay the real failure\nCoverage: N/A\n## Coverage vs advertising\nx\n"
                  "## Self-description drift\nx\n## Fixture requirement\nx\n## Findings\nnone\n"
                  "Verdict: PASS\n")
    light_ok = light_base.format(just="Light-path justification: comment-only; no logic/gated-set change\n")
    light_nojust = light_base.format(just="")
    # Round-3 fixtures (a different-model cold pass found these holes in the round-2 additions):
    time_anchor = base.format(cov="5/5", body="", find="discussed at 2:30, fine", v="PASS")  # not a path
    no_blockers = base.format(cov="5/5", body="", find="No blockers, though MAJOR concerns remain", v="PASS")
    both_tiers = ("- Prompt: gate-review-prompt.md v1.0.0\nTier: full\nTier: light\n"
                  "Light-path justification: x\n## Replay the real failure\nCoverage: N/A\n"
                  "## Coverage vs advertising\nx\n## Self-description drift\nx\n## Fixture requirement\n"
                  "x\n## Findings\nnone\nVerdict: PASS\n")  # mixed tiers -> full -> N/A insufficient
    decoy = ("- Prompt: gate-review-prompt.md v1.0.0\n### Prior findings recap\nold foo.py:42\n"
             "## Replay the real failure\nCoverage: 5/5\n## Coverage vs advertising\nx\n"
             "## Self-description drift\nx\n## Fixture requirement\nx\n## Findings\nclean, ship it\n"
             "Verdict: PASS\n")  # real ## Findings has no anchor; the ### decoy must not stand in
    # Round-4 fixtures (a different-VENDOR cold pass found these): the TEMPLATE writes BULLETED list
    # items ('- Tier: light'), which the unbulleted regexes silently ignored -> the template's own light
    # path defaulted to full; and an unfilled template placeholder must not pass as evidence.
    tmpl_light = ("- Prompt: gate-review-prompt.md v1.0.0\n- Tier: light\n"
                  "- Light-path justification: README wording only; no enforced behavior depends on it\n"
                  "## Replay the real failure\nCoverage: N/A\n## Coverage vs advertising\nx\n"
                  "## Self-description drift\nx\n## Fixture requirement\nx\n## Findings\n- none\n"
                  "Verdict: PASS\n")  # exact TEMPLATE bullet form; inert-doc light -> must clear
    placeholder = base.format(cov="5/5", body="", find="foo.py:1 issue\n[changed_gate_paths]", v="PASS")
    # (name, records, want, allow_light)
    cases = [
        ("well-formed PASS clears", [("good.md", good)], True, True),
        ("full PASS with file:line findings clears", [("ga.md", good_anchor)], True, True),
        ("full PASS with vague findings (no anchor/none) blocks", [("vg.md", vague)], False, True),
        ("time '2:30' is not a path anchor -> blocks", [("t.md", time_anchor)], False, True),
        ("'No blockers, though MAJOR...' is not a clean 'none' -> blocks", [("nb.md", no_blockers)], False, True),
        ("a ### decoy heading cannot stand in for the real ## Findings -> blocks", [("d.md", decoy)], False, True),
        ("PASS-in-prose over an effective BLOCK blocks", [("p.md", prose_block)], False, True),
        ("coverage 0/0 blocks", [("z.md", zero)], False, True),
        ("coverage outside the replay section blocks", [("m.md", misplaced)], False, True),
        ("Verdict: PASS-WITH-NITS blocks", [("n.md", nits)], False, True),
        # 0024 round 2 (BLOCKER-2): VERDICT_LINE_RE had no end anchor, so the REQUIRED status check read
        # PASS out of each of these and CLEARED a gate-layer change over a record whose final line does
        # not say PASS. The suffix is not a comment grammar — it is unconsumed text — so it fails closed.
        ("Verdict: 'PASS pending' blocks (unanchored-suffix bypass)",
         [("s1.md", base.format(cov="5/5", body="", find="none", v="PASS pending"))], False, True),
        ("Verdict: 'PASS garbage' blocks (unanchored-suffix bypass)",
         [("s2.md", base.format(cov="5/5", body="", find="none", v="PASS garbage"))], False, True),
        # 0024 round 3: an HTML comment does NOT render, so the reader of this record sees exactly
        # "Verdict: PASS". Comments are stripped before the verdict is read, which means a comment can
        # neither invent a verdict nor hide one — `Verdict: BLOCK <!-- really fine, PASS -->` still reads
        # BLOCK. The check agrees with the RENDERED document, which is the document a human reviews.
        ("Verdict: 'PASS <!-- BLOCK -->' clears (the comment does not render)",
         [("s3.md", base.format(cov="5/5", body="", find="none", v="PASS <!-- BLOCK -->"))], True, True),
        ("a commented-out PASS cannot override a visible BLOCK",
         [("s7.md", base.format(cov="5/5", body="", find="none", v="BLOCK")
                   + "\n<!-- once fixed this becomes Verdict: PASS -->\n")], False, True),
        ("Verdict: 'PASS [BLOCK](x)' blocks (unanchored-suffix bypass)",
         [("s4.md", base.format(cov="5/5", body="", find="none", v="PASS [BLOCK](x)"))], False, True),
        # ... and the legitimate spellings must still clear, so the anchor is not merely stricter.
        # 0024 round 2 (BLOCKER): anchoring the strict token into the LINE matcher made an annotated
        # verdict line INVISIBLE rather than fatal, so "the last verdict line wins" fell back to an
        # EARLIER, friendlier line. A record ending `Verdict: BLOCK (2 outstanding)` after an earlier
        # `Verdict: PASS` then CLEARED the required check. Both signs must fail closed.
        ("an ANNOTATED final BLOCK after an earlier PASS must NOT clear (mirror hole)",
         [("m1.md", base.format(cov="5/5", body="", find="none", v="PASS")
                   + "\nmore review text\n\nVerdict: BLOCK (2 blockers outstanding)\n")], False, True),
        ("an ANNOTATED final BLOCK alone must NOT clear",
         [("m2.md", base.format(cov="5/5", body="", find="none", v="BLOCK (2 outstanding)"))], False, True),
        # ...and a well-formed later PASS must still win, so the rule itself is unchanged.
        ("a well-formed final PASS after an earlier BLOCK still clears",
         [("m3.md", base.format(cov="5/5", body="", find="none", v="BLOCK") + "\nVerdict: PASS\n")], True, True),
        # 0024 round 3: the DANGEROUS direction is a final BLOCK the matcher cannot see, because
        # last-declaration-wins then falls back to an earlier PASS. Round 3 found seven spellings that did
        # exactly that, one of them (NBSP) a REGRESSION this branch introduced against main. Every ordinary
        # decoration a reviewer might write is pinned here, in the direction that matters.
        *[(f"a final BLOCK written as {label} must NOT clear (fallback-to-PASS class)",
           [(f"fb{i}.md", base.format(cov="5/5", body="", find="none", v="PASS")
                          + f"\nmore text\n\n{line}\n")], False, True)
          for i, (label, line) in enumerate([
              ("**bold**", "**Verdict: BLOCK**"), ("a bold label", "**Verdict:** BLOCK"),
              ("a + bullet", "+ Verdict: BLOCK"), ("a - bullet", "- Verdict: BLOCK"),
              ("a heading", "## Verdict: BLOCK"), ("a blockquote", "> Verdict: BLOCK"),
              ("an ordered item", "1. Verdict: BLOCK"), ("NBSP-indented", "\u00a0Verdict: BLOCK"),
              ("EM-SPACE-indented", "\u2003Verdict: BLOCK"), ("backticked", "`Verdict: BLOCK`")])],
        ("Verdict: lowercase 'pass' still clears",
         [("s5.md", base.format(cov="5/5", body="", find="none", v="pass"))], True, True),
        ("Verdict: 'PASS' with trailing spaces still clears",
         [("s6.md", base.format(cov="5/5", body="", find="none", v="PASS   "))], True, True),
        ("a co-committed BLOCK blocks even with a PASS", [("b.md", prose_block), ("g.md", good)], False, True),
        # 0024 round 3: a record that is NOT a clean PASS must gate the PR, not merely decline to clear
        # it. An ANNOTATED blocking record collapses to an unreadable verdict, and a sibling clean PASS
        # used to clear the gate on its behalf — the fall-back-to-a-friendlier-answer shape, across
        # records this time. The docstring had promised "a malformed record blocks" throughout.
        ("a co-committed ANNOTATED BLOCK blocks even with a clean PASS (across-records fallback)",
         [("ab.md", base.format(cov="5/5", body="", find="none", v="BLOCK (2 blockers outstanding)")),
          ("g2.md", good)], False, True),
        ("a co-committed record with NO verdict line blocks even with a clean PASS",
         [("nv.md", base.format(cov="5/5", body="", find="none", v="PASS").replace("Verdict: PASS", "")),
          ("g3.md", good)], False, True),
        # CONTRACT UPDATE (#6): the light "clears" cases are now grounded in light_admissible with a
        # real inert path (gate-reviews/README.md) — input + expectation aligned to the stricter policy,
        # not a weakened assertion. The expectation (clears) is unchanged; the input is now the ONLY
        # legitimate light member.
        ("light tier clears for an INERT gated doc (gate-reviews/README.md)",
         [("lo.md", light_ok)], True, grc.light_admissible(["gate-reviews/README.md"])),
        ("BULLETED template '- Tier: light' on an inert doc (README) -> clears",
         [("tl.md", tmpl_light)], True, grc.light_admissible(["gate-reviews/README.md"])),
        # THE FLIP (#6): a behavioral governance doc is a gated *.md, but light is now REFUSED for it
        # (previously this exact shape would have cleared, because any *.md set allow_light=True).
        ("light tier is REFUSED for a behavioral governance doc (gate-review-prompt.md)",
         [("lg.md", light_ok)], False, grc.light_admissible(["gate-review-prompt.md"])),
        ("an unfilled '[changed_gate_paths]' placeholder -> blocks", [("ph.md", placeholder)], False, True),
        ("light tier: N/A without justification blocks", [("ln.md", light_nojust)], False, True),
        ("light tier is REFUSED when the change touches code (gate-review-check.py)",
         [("lc.md", light_ok)], False, grc.light_admissible(["gate-review-check.py"])),
        ("mixed Tier full+light resolves to full -> N/A insufficient -> blocks", [("mt.md", both_tiers)], False, True),
        ("full tier: Coverage N/A blocks (full needs a fraction)", [("fn.md", full_na)], False, True),
        ("no verdict record blocks", [], False, True),
    ]
    for name, records, want, allow in cases:
        ok, _ = grc.decide_verdicts(records, allow)
        res.check(ok == want, f"decide_verdicts: {name}", f"ok={ok} want={want}")

    # 3. effective_verdict takes the LAST verdict line (not any PASS mentioned earlier).
    ev = grc.effective_verdict("Verdict: PASS\n...\nVerdict: BLOCK\n")
    res.check(ev == "BLOCK", "effective_verdict: the last verdict line wins", f"got {ev}")


def gate_review_seam(res: Results, verbose: bool) -> None:
    """Integration lock for the evaluate_verdicts -> light_admissible(gate_paths) SEAM.

    The section above pins light_admissible() in isolation and decide_verdicts() with allow_light passed
    in explicitly; neither exercises the WIRING in evaluate_verdicts — that it (a) reads the changed
    gate-reviews/ record from DISK and (b) computes allow_light from the changed gate paths via
    light_admissible and threads it into decide_verdicts. Before this, that seam was proven only by a
    one-off CLI demo. Here evaluate_verdicts runs end-to-end against a temp repo root, holding the
    on-disk verdict FIXED and flipping only gate_paths — so the verdict can change ONLY through the seam.
    A no-op revert (e.g. hard-coding allow_light=True, or dropping the light_admissible call) turns this
    red. Drives the real imported function; the only I/O is a self-contained temp dir.
    """
    print("gate-review-check SEAM (evaluate_verdicts wires gate_paths -> light_admissible -> decide):")
    grc = _load("grc_seam", GATE_REVIEW_CHECK)

    # The SAME on-disk light verdict for every case below: inert-doc shape (Tier: light + Coverage: N/A
    # + justification). It is admissible only when light_admissible(gate_paths) is True.
    light_verdict = ("- Prompt: gate-review-prompt.md v1.0.0\n- Tier: light\n"
                     "- Light-path justification: inert gated doc; no enforced behavior depends on it\n"
                     "## Replay the real failure\nCoverage: N/A\n## Coverage vs advertising\nx\n"
                     "## Self-description drift\nx\n## Fixture requirement\nx\n## Findings\n- none\n"
                     "Verdict: PASS\n")
    full_verdict = ("- Prompt: gate-review-prompt.md v1.0.0\n## Replay the real failure\nCoverage: 5/5\n"
                    "## Coverage vs advertising\nx\n## Self-description drift\nx\n"
                    "## Fixture requirement\nx\n## Findings\nnone\nVerdict: PASS\n")

    tmp = Path(tempfile.mkdtemp(prefix="gate-seam-"))
    (tmp / "gate-reviews").mkdir(parents=True)
    light_rec, full_rec = "gate-reviews/seam-light.md", "gate-reviews/seam-full.md"
    (tmp / light_rec).write_text(light_verdict, encoding="utf-8")
    (tmp / full_rec).write_text(full_verdict, encoding="utf-8")

    # One representative gate path per class the task calls out; light must be REFUSED for all of them.
    # Code by extension (*.py/*.sh/*.yml), the .github/ subtree (no extension), and the behavioral
    # governance docs (the lenses, the verdict contract, the policy, the recorded ruleset) all force full.
    # The gated-markdown-subtree rows (tests/**/*.md, .github/**/*.md) are the class the original denylist
    # let through with light — they are gate-layer subtrees, so they MUST be refused end-to-end too (the
    # different-vendor cold pass on PR #9 found the seam fixture missed exactly this class).
    refuse_full = [
        ["build-skills.sh"], ["pkgtools.py"], ["tests/run-golden.py"],     # *.sh / *.py code
        [".github/workflows/gate-review.yml"],                             # *.yml
        [".github/gate-paths"],                                            # .github/ path, no extension
        ["gate-review-prompt.md"], ["gate-reviews/TEMPLATE.md"],          # behavioral governance docs
        ["CONTRIBUTING.md"], ["docs/SETTINGS.md"],
        ["tests/golden-bad/leaked-credential.md"],                       # gated markdown under tests/
        [".github/PULL_REQUEST_TEMPLATE.md"],                            # gated markdown under .github/
        ["shared/ci/README.md"],                                         # gated markdown under shared/ci/
        ["gate-reviews/README.md", "CONTRIBUTING.md"],                    # mixed inert + behavioral -> full
        ["gate-reviews/README.md", "tests/golden-bad/leaked-credential.md"],  # mixed inert + gated md -> full
    ]
    orig_root = grc.ROOT
    try:
        grc.ROOT = tmp
        # 1. The SAME on-disk light verdict CLEARS for the inert doc, and is REFUSED everywhere else.
        ok_inert, _ = grc.evaluate_verdicts([light_rec], ["gate-reviews/README.md"])
        res.check(ok_inert, "seam: light verdict clears when the sole gate path is gate-reviews/README.md",
                  f"ok={ok_inert}")
        for paths in refuse_full:
            ok, _ = grc.evaluate_verdicts([light_rec], paths)
            res.check(not ok, f"seam: light verdict refused -> full required for {paths}", f"ok={ok}")
        # 2. A full verdict clears regardless of the gate-path class (full is always sufficient).
        ok_full_code, _ = grc.evaluate_verdicts([full_rec], ["build-skills.sh"])
        ok_full_doc, _ = grc.evaluate_verdicts([full_rec], ["gate-reviews/README.md"])
        res.check(ok_full_code and ok_full_doc,
                  "seam: full verdict clears for both a code path and the inert doc",
                  f"code={ok_full_code} doc={ok_full_doc}")
    finally:
        grc.ROOT = orig_root
        shutil.rmtree(tmp, ignore_errors=True)


def manifest_byte_stability(res: Results, verbose: bool) -> None:
    """Lock the item-2 invariant: pkgtools.write_manifest is byte-stable on unchanged content and carries
    NO HEAD/clock-dependent field. The old '# source-commit:' line recorded the build HEAD and flipped on
    every build, producing spurious manifest diffs on content-free changes; a future edit re-adding a
    volatile field (a build commit, an mtime, a build-id) would reinstate exactly that. Drives the REAL
    write_manifest twice on identical fixed inputs; the only I/O is a self-contained temp dir.
    """
    print("manifest byte-stability (item 2: identical content -> identical bytes; no HEAD/clock field):")
    pkg = _load("pkgtools", PKGTOOLS)
    tmp = Path(tempfile.mkdtemp(prefix="manifest-stable-"))
    try:
        dist, shared = tmp / "dist", tmp / "shared"
        dist.mkdir(); shared.mkdir()
        # Fixed inputs: pinned content, so the only way the bytes could differ build-to-build is a
        # volatile manifest field (the failure this guards).
        (dist / "alpha.skill").write_bytes(b"alpha-bytes")
        (shared / "house-style.md").write_text("shared\n", encoding="utf-8")
        out1, out2 = tmp / "M1.sha256", tmp / "M2.sha256"
        pkg.write_manifest(dist, shared, out1, version="9.9.9", root=tmp)
        pkg.write_manifest(dist, shared, out2, version="9.9.9", root=tmp)
        b1, b2 = out1.read_bytes(), out2.read_bytes()
        # The two assertions cover DIFFERENT volatility shapes and are both load-bearing: byte-identity
        # catches a field that VARIES between the two in-process calls (e.g. datetime.now()); the regexes
        # below catch a STATIC volatile field (the exact '# source-commit: <HEAD>' bug — constant within
        # one process, so byte-identity alone stays green on its revert, as the break-test confirms).
        res.check(b1 == b2, "write_manifest is byte-identical across two runs on identical content",
                  f"{len(b1)} vs {len(b2)} bytes")
        text = out1.read_text(encoding="utf-8")
        # A re-added static volatile field shows up as a build-commit token or a date. The 64-hex
        # integrity rows do NOT trip the 40-hex commit pattern (no word boundary mid-run) and carry no
        # '-' dates.
        no_commit = not re.search(r"source-commit|\b[0-9a-f]{40}\b", text)
        no_clock = not re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
        res.check(no_commit, "manifest carries no build-commit field",
                  "clean" if no_commit else "found a commit-like token")
        res.check(no_clock, "manifest carries no date/timestamp field",
                  "clean" if no_clock else "found a date")
        # The integrity rows that replaced the dropped field are still emitted (one per input file).
        rows = re.findall(r"(?m)^[0-9a-f]{64}  ", text)
        res.check(len(rows) == 2, "manifest still emits the per-file SHA-256 rows", f"{len(rows)} rows")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)



# 0024: the CLOSED SET of values a round-table verdict cell may carry. The pending invariants used to
# compare against the exact literal `pending`, in BOTH signs and in both states — so an annotated cell
# like "pending (round 20 running)" escaped the PASS-state "no pending rows" check (a `Verdict: PASS`
# over a genuinely pending newest round returned NO problems) and, in the BLOCK state, made the
# "a non-pending row follows it" check fire on a row that IS pending. Widening to a substring would only
# move the escape one spelling along, which is the recurrence rounds 16-18 each repeated. So the world is
# closed instead: a cell that does not normalise into this set is ITSELF a finding.
_VERDICT_KINDS = frozenset({"block", "pass", "pending", "self"})

# 0024 round 2: the FIRST attempt at this closed set was a PREFIX PARSER, not a recogniser — it deleted
# every `*`, `_` and backtick from ANY position, dropped a trailing parenthetical, split on whitespace and
# returned head[0], never checking that the REST of the cell was consumed. So `BLOCK PASS pending`,
# `BLOCK garbage`, `self BLOCK`, `BLOCK <!-- pending -->` and `B*L*O*C*K` all classified, while ordinary
# `[BLOCK](url)`, `<strong>BLOCK</strong>` and `~~BLOCK~~` were rejected: neither a closed set nor a
# coherent grammar, and the "an unrecognised cell is itself a finding" claim was false whenever the FIRST
# word happened to be recognised. The independent review reproduced a live-shaped record carrying
# `BLOCK PASS pending` over which this checker printed complete agreement.
#
# So the grammar is now matched WHOLE (re.fullmatch) and nothing may be left over. Accepted, exhaustively:
#   BLOCK · pass · Pending                      a bare verdict word, any case
#   **BLOCK** · *pass* · `pending` · _self_     ONE outer emphasis wrapper, correctly paired
#   (self)                                      the wholly-parenthesised form (a live row: 0005 round 13)
#   BLOCK (annotation) · pending (round 20)     at most ONE trailing parenthetical, no nesting
# Everything else is None — a second verdict word, any unconsumed suffix, emphasis INSIDE the word,
# multiple or nested parentheticals, a newline, HTML, or link syntax. Rejecting link/HTML/strikethrough
# spellings is deliberate: this is a narrow grammar for a hand-written control column, and a verdict
# nobody can write plainly is one nobody should write at all.
_VERDICT_WORD = "(?:" + "|".join(sorted(_VERDICT_KINDS)) + ")"   # ONE source: built from the set
_VERDICT_ANNOT = r"(?:[ \t]*\((?:[^()\n]*)\))?"        # at most one, non-nested, single-line
_VERDICT_CELL_RE = re.compile(
    rf"[ \t]*(?:(?P<wrap>\*\*|__|\*|_|`)(?P<wrapped>{_VERDICT_WORD})(?P=wrap)|(?P<plain>{_VERDICT_WORD}))"
    rf"{_VERDICT_ANNOT}[ \t]*",
    re.IGNORECASE,
)
_VERDICT_PAREN_RE = re.compile(rf"[ \t]*\([ \t]*(?P<paren>{_VERDICT_WORD})[ \t]*\)[ \t]*", re.IGNORECASE)


def _verdict_kind(cell: str) -> str | None:
    """Classify a round-table verdict cell as a member of _VERDICT_KINDS, or None if it is not one.

    The WHOLE cell must match the grammar above — this is a recogniser, not a prefix parser, because the
    prefix version accepted `BLOCK PASS pending` (see the comment above). `(self)` is handled by its own
    arm: it is a live row that feeds CONTRIBUTING's author-round count, and a naive strip-the-parens
    would map it to the empty string."""
    # No explicit newline guard: the grammar's horizontal-whitespace classes ([ \t]) already make a
    # multi-line cell unmatchable, and the mutation runner proved an explicit guard was dead code — it
    # could be deleted with the suite still green, i.e. it claimed coverage it did not provide. The
    # behaviour is pinned by a fixture regardless, and reverting the grammar reddens it.
    m = _VERDICT_PAREN_RE.fullmatch(cell) or _VERDICT_CELL_RE.fullmatch(cell)
    if not m:
        return None
    g = m.groupdict()
    word = g["paren"] if g.get("paren") else (g.get("wrapped") or g.get("plain"))
    # The membership test is NOT redundant with the grammar. `re.IGNORECASE` folds U+0131 DOTLESS I and
    # U+0130 CAPITAL I WITH DOT ABOVE onto `i`, so `pendıng` MATCHES — but neither codepoint casefolds to
    # `i`, so the result was `'pendıng'`: not a member, and not None. That defeated BOTH consumers at once
    # (the unrecognised-cell arm did not fire because it was not None; the pending arm did not fire because
    # it was not "pending"), which is exactly the escape this function exists to prevent. Returning only a
    # member makes the docstring and the fail-closed claim true.
    kind = word.casefold()
    return kind if kind in _VERDICT_KINDS else None


# 0024 round 2: the round-history table is identified by its canonical HEADER, not by "any table row whose
# first cell is an integer". A verdict record legitimately contains OTHER tables — this change's own record
# carries a census table whose first column is a source line number (673, 716, 718, 728) — and the old
# row-shaped regex would have read those as rounds the moment the checker was generalised beyond the one
# hardcoded record. Keying on the header makes "has a round history" an explicit, checkable property.
_ROUND_HEADER_RE = re.compile(r"(?mi)^\|[ \t]*#[ \t]*\|[ \t]*head[ \t]*\|[ \t]*verdict[ \t]*\|")
_ROUND_ROW_RE = re.compile(r"^\|[ \t]*(\d+)[ \t]*\|[ \t]*([^|]*?)[ \t]*\|[ \t]*([^|]*?)[ \t]*\|")
_SEPARATOR_ROW_RE = re.compile(r"^\|[\s:|-]*\|$")


def _round_rows(record: str) -> tuple[list[tuple[int, str, str]], list[str]] | None:
    """The record's round rows as (round, head, verdict) plus any problems, or None if it has no round
    table at all.

    None means "this document is not a round-history record" and the sweep skips it. Anything else is a
    round-history record, including one that declares the table and then has no usable rows.

    0024 round 2: an unparseable line INSIDE the table used to be discarded in silence — the loop only
    stopped on a non-table line, so a row that starts with `|` but does not match (an indented row, a row
    whose first cell is not an integer, a row with too few cells) simply vanished from the round history
    and every downstream invariant was computed over a table the reader does not see. Silently reading
    less than the document says is the whole failure class this checker exists to catch, so an
    unparseable table line is now a finding."""
    h = _ROUND_HEADER_RE.search(record)
    if not h:
        return None
    # The header pattern ends mid-line (it only pins the first three columns), so scan from the START OF
    # THE NEXT LINE — not from the match end, which would hand the header's own tail to the row parser.
    nl = record.find("\n", h.end())
    body = "" if nl == -1 else record[nl + 1:]
    rows: list[tuple[int, str, str]] = []
    probs: list[str] = []
    started = False
    for line in body.split("\n"):
        stripped = line.strip()
        if not stripped:
            if started:
                break                  # a blank line ends a Markdown table
            continue
        if not stripped.startswith("|"):
            break                      # the table ended; a later table is not round history
        started = True
        if _SEPARATOR_ROW_RE.match(stripped):
            continue
        mm = _ROUND_ROW_RE.match(line)
        if mm:
            rows.append((int(mm.group(1)), mm.group(2).strip(), mm.group(3).strip()))
        else:
            probs.append(f"a line inside the round-history table is not a parseable round row: "
                         f"{stripped[:80]!r}")
    return rows, probs


def _record_problems(record: str, contrib: str | None = None) -> list[str]:
    """Consistency problems between the PR #12 review record's round-history TABLE, its verdict PROSE, and
    CONTRIBUTING's stated review-round range. PURE (text in, problems out) so it can be self-tested on
    synthetic bad records. 0022 (round-18 MAJOR-4): the table/prose contradiction recurred twice — round 16
    said `pending` in the table while the prose said BLOCK, and the round-17 row repeated the exact same
    mismatch one round later — because the invariant lived in the author's care instead of a check. Now the
    suite reddens on: non-consecutive round numbers, more than one pending row, a pending row that is not
    the newest round, prose naming a round whose table verdict is not BLOCK, a non-pending row after the
    prose's "most recent" round, an awaited-round number that is not most-recent + 1, and a CONTRIBUTING
    range end that disagrees with the table's round count, and — while the record's final verdict line is
    BLOCK — a missing or reworded sentinel sentence (fail closed; the prose checks used to no-op on a
    reworded anchor). NOTE on numbering: the 0005+ IDs are REVIEW IDS continuing the gate-reviews file
    sequence — round 1 is file 0005 and rounds 2+ are recorded INSIDE that consolidated record (its
    'Record convention' note); the IDs also tag code comments. Round N carries ID 0004+N, and that is the
    range end this function DERIVES from the table (below) rather than a literal, so no upper bound is
    written down here to go stale. What does not exist is a separate record FILE per ROUND of the 0005
    record; a later work package does add its own record file under the next free ID, so a
    gate-reviews/00NN-*.md above 0005 is expected and is not a numbering error."""
    parsed = _round_rows(record)
    if parsed is None:
        return ["no round-history table found in the record"]
    rows, probs = parsed
    if not rows:
        return probs + ["the record declares a round-history table but has no parseable round rows"]
    rounds = sorted(r for r, _, _ in rows)
    n = rounds[-1]
    if rounds != list(range(1, n + 1)):
        probs.append(f"round numbers are not consecutive 1..{n}: {rounds}")
    verdicts = {r: v for r, _, v in rows}
    unknown = sorted(r for r, v in verdicts.items() if _verdict_kind(v) is None)
    if unknown:
        probs.append(f"unrecognised verdict cell(s) in round row(s) {unknown}: "
                     f"{[verdicts[r] for r in unknown]} — a round verdict must read one of "
                     f"{', '.join(sorted(_VERDICT_KINDS))} (fail closed: an unrecognised cell is not "
                     f"assumed benign, because that is how an annotated one escaped)")
    pend = [r for r, v in verdicts.items() if _verdict_kind(v) == "pending"]
    if len(pend) > 1:
        probs.append(f"more than one pending row: {sorted(pend)}")
    if pend and max(pend) != n:
        probs.append(f"a pending row ({max(pend)}) is not the newest round ({n})")
    tail = record.split("Why this record is nevertheless BLOCK", 1)[-1]
    m = re.search(r"most recent independent review \(round (\d+)\) returned BLOCK", tail)
    m_awaited = re.search(r"independent round-(\d+) review", tail)
    # FAIL CLOSED on the anchors (0022, a red-team finding): the prose checks used to no-op silently if
    # the sentinel sentences were reworded or deleted — precisely the edit path where the table/prose
    # contradiction recurred twice. While the record's FINAL verdict line is BLOCK, both sentinel
    # sentences MUST be present and parseable, or the record is inconsistent by definition.
    # 0024 round 3: there is now ONE verdict parser, not two. This used to re-implement the required
    # check's grammar "so the two cannot disagree" — a claim that was false twice over, because a
    # re-implementation is exactly a thing that CAN disagree. It now CALLS the required check's own
    # parser, so parity is structural rather than asserted. A `None` result means the record's last
    # verdict declaration is not exactly PASS/BLOCK/FAIL, which is itself a finding.
    _grc = _load("grc_rec", GATE_REVIEW_CHECK)
    decls = _grc.VERDICT_LINE_RE.findall(_grc.HTML_COMMENT_RE.sub("", record))
    final_verdict = _grc.effective_verdict(record)
    if decls and final_verdict is None:
        probs.append(f"the record's last verdict declaration reads {decls[-1]!r} — it must be exactly "
                     f"PASS, BLOCK or FAIL")
    if final_verdict == "BLOCK":
        if not m:
            probs.append("final verdict is BLOCK but the sentinel sentence 'most recent independent "
                         "review (round N) returned BLOCK' is missing or reworded — the table/prose "
                         "cross-check cannot run (fail closed)")
        if not m_awaited:
            probs.append("final verdict is BLOCK but the awaited-round sentence 'independent round-N "
                         "review' is missing or reworded (fail closed)")
    elif final_verdict == "PASS":
        # 0023 (round-19 BLOCKER-2): the checker was silent in the PASS state — `Verdict: PASS` over a
        # newest-BLOCK row or a still-pending row returned no problems, the exact contradiction class on
        # the one edit this checker exists to protect (the eventual flip). PASS invariants: no pending
        # rows anywhere, and the closure sentinel must name the newest round.
        if pend:
            probs.append(f"final verdict is PASS but round(s) {sorted(pend)} are still pending")
        # 0024 round 2: the two closure sentinels were parsed by one alternation and then treated
        # IDENTICALLY — only "is it the newest round?" was checked. So "review (round N) returned PASS"
        # was accepted over a table row N that says BLOCK: the record claimed a passing review that its
        # own table contradicts. The two forms make DIFFERENT claims and are now checked differently.
        m_owner = re.search(r"closed by owner decision after round (\d+)", record)
        m_review = re.search(r"review \(round (\d+)\) returned PASS", record)
        if not (m_owner or m_review):
            probs.append("final verdict is PASS but no closure sentinel names the passing/closing round "
                         "('closed by owner decision after round N' or 'review (round N) returned PASS')")
        for mc, label in ((m_owner, "owner-decision"), (m_review, "review-returned-PASS")):
            if not mc:
                continue
            kp = int(mc.group(1))
            if kp != n:
                probs.append(f"the {label} closure sentinel names round {kp} but the newest table round "
                             f"is {n}")
            # An OWNER decision may legitimately close over a BLOCK row (the 0005 record does exactly
            # that). A claimed PASSING REVIEW may not — row N must itself say PASS.
            if mc is m_review and _verdict_kind(verdicts.get(kp, "")) != "pass":
                probs.append(f"prose says the round-{kp} review returned PASS but table row {kp} says "
                             f"{verdicts.get(kp)!r} — an owner decision may close over a BLOCK row, a "
                             f"passing review may not")
    elif final_verdict is not None:
        probs.append(f"the record's final verdict line is {final_verdict!r} — expected BLOCK or PASS")
    if m:
        k = int(m.group(1))
        if _verdict_kind(verdicts.get(k, "")) != "block":
            probs.append(f"prose says round {k} returned BLOCK but table row {k} says {verdicts.get(k)!r}")
        if any(r > k and _verdict_kind(verdicts[r]) != "pending" for r in verdicts):
            probs.append(f"prose calls round {k} the most recent review, but a non-pending row follows it")
        if m_awaited and int(m_awaited.group(1)) != k + 1:
            probs.append(f"prose awaits round {m_awaited.group(1)}, but the most recent review is round {k}")
    # The checks ABOVE are generic: they hold for ANY round-history record, and the sweep below runs them
    # over every one. The checks BELOW are specific to the 0005 record, because CONTRIBUTING states that
    # record's round counts and ID range and nothing else's. Passing contrib=None runs the generic half
    # alone — 0024 round 2 (MAJOR-4): the invariants were previously reachable only for a single
    # hardcoded file that policy also declares append-only, i.e. the one record least likely to change.
    if contrib is None:
        return probs
    m4 = re.search(r"(\d+) review rounds \(review IDs[^)]*?(\d+) independent[^)]*?(\d+) author",
                   contrib)
    if not m4:
        probs.append("CONTRIBUTING no longer states the digit-based round counts "
                     "('N review rounds (review IDs …; I independent …; A author …)')")
    else:
        selfr = sum(1 for r, v in verdicts.items() if _verdict_kind(v) == "self")
        want = (n, n - selfr, selfr)
        got = tuple(int(x) for x in m4.groups())
        if got != want:
            probs.append(f"CONTRIBUTING's counts {got} (total, independent, author) disagree with the "
                         f"table {want}")
    m3 = re.search(r"review IDs `0005`–`00(\d\d)`", contrib)
    if not m3:
        probs.append("CONTRIBUTING no longer states the review-ID range (`0005`–`00NN`)")
    elif int(m3.group(1)) != n + 4:
        probs.append(f"CONTRIBUTING's review-ID range ends at 00{m3.group(1)} but the record has {n} "
                     f"rounds (round N carries ID 0004+N, so expected 00{n + 4:02d})")
    return probs


def review_record_consistency(res: Results, verbose: bool) -> None:
    """The PR #12 record's table, prose and CONTRIBUTING count must agree — mechanically (0022)."""
    print("review-record consistency (table vs prose vs CONTRIBUTING — checked, not remembered):")
    # Self-tests on synthetic records first: the checker itself must be able to fail (a checker that
    # cannot go red proves nothing about the live files).
    # The canonical round-table HEADER is part of every fixture from 0024 round 2 on: the table is now
    # located by its header rather than by "any row starting with an integer" (MAJOR-4).
    _HDR = "| # | head | verdict | blocking finding | resolution |\n|---|---|---|---|---|\n"
    good_rec = (_HDR + "| 1 | aaa | BLOCK | x | y |\n| 2 | bbb | BLOCK | x | y |\n"
                "Why this record is nevertheless BLOCK: the most recent independent review (round 2) "
                "returned BLOCK ... an independent round-3 review ...\nVerdict: BLOCK\n")
    good_con = ("text 2 review rounds (review IDs `0005`–`0006`; 2 independent cold-pass reviews and "
                "0 author self-red-team rounds) text")
    res.check(_record_problems(good_rec, good_con) == [],
              "checker: a consistent synthetic record passes",
              "; ".join(_record_problems(good_rec, good_con)) or "clean")
    bad_pending = good_rec.replace("| 2 | bbb | BLOCK |", "| 2 | bbb | pending |")
    res.check(any("returned BLOCK but table row" in x for x in _record_problems(bad_pending, good_con)),
              "checker: table `pending` vs prose `BLOCK` on the same round is CAUGHT (the recurring bug)")
    res.check(any("range ends at" in x for x in _record_problems(good_rec, "review IDs `0005`–`0021`")),
              "checker: a stale CONTRIBUTING review-ID range is CAUGHT")
    res.check(any("not consecutive" in x for x in
                  _record_problems(good_rec.replace("| 2 |", "| 4 |"), good_con)),
              "checker: a gap in round numbers is CAUGHT")
    # 0022 (red-team): the prose anchors must FAIL CLOSED while the final verdict is BLOCK — a reworded
    # sentinel used to silently disable every table-vs-prose cross-check, exactly on the edit path where
    # the contradiction recurred twice.
    reworded = good_rec.replace("returned BLOCK", "returned a BLOCK verdict")
    res.check(any("sentinel sentence" in x for x in _record_problems(reworded, good_con)),
              "checker: a REWORDED sentinel under a final BLOCK verdict is CAUGHT (fail closed)")
    no_awaited = good_rec.replace("an independent round-3 review", "a future review")
    res.check(any("awaited-round sentence" in x for x in _record_problems(no_awaited, good_con)),
              "checker: a missing awaited-round sentence under a final BLOCK verdict is CAUGHT")
    # 0023 (round-19 BLOCKER-2): the PASS state must be as constrained as the BLOCK state.
    pass_rec = (_HDR + "| 1 | aaa | BLOCK | x | y |\n| 2 | bbb | BLOCK | x | y |\n"
                "closed by owner decision after round 2 ...\nVerdict: PASS\n")
    res.check(_record_problems(pass_rec, good_con) == [],
              "checker: a consistent PASS-state record (closure sentinel naming the newest round) passes",
              "; ".join(_record_problems(pass_rec, good_con)) or "clean")
    res.check(any("still pending" in x for x in _record_problems(
                  pass_rec.replace("| 2 | bbb | BLOCK |", "| 2 | bbb | pending |"), good_con)),
              "checker: PASS over a still-PENDING newest row is CAUGHT")
    res.check(any("closure sentinel" in x for x in _record_problems(
                  pass_rec.replace("closed by owner decision after round 2 ...", "all done."), good_con)),
              "checker: PASS without a closure sentinel naming the round is CAUGHT")
    res.check(any("names round 1 but" in x for x in _record_problems(
                  pass_rec.replace("after round 2", "after round 1"), good_con)),
              "checker: a closure sentinel naming a NON-newest round is CAUGHT")
    res.check(any("disagree with the table" in x for x in _record_problems(
                  good_rec, good_con.replace("2 independent", "1 independent"))),
              "checker: CONTRIBUTING count drift vs the table (independent-count) is CAUGHT")
    # 0024: the pending invariants compared against the exact literal `pending`, so an ANNOTATED cell
    # escaped in the PASS state and false-positived in the BLOCK state. Both signs are locked here, plus
    # the closed set that makes an unrecognised spelling a finding instead of a silent pass.
    ann = pass_rec.replace("| 2 | bbb | BLOCK |", "| 2 | bbb | pending (round 3 running) |")
    res.check(any("still pending" in x for x in _record_problems(ann, good_con)),
              "checker: PASS over an ANNOTATED pending newest row is CAUGHT (0024; the literal escaped)",
              "; ".join(_record_problems(ann, good_con)) or "clean")
    # ... and the same annotation must NOT trip the BLOCK-state "a non-pending row follows it" arm, which
    # had the identical narrowness with the opposite sign (a false-positive generator).
    ann_block = (_HDR + "| 1 | aaa | BLOCK | x | y |\n| 2 | bbb | pending (round 3 running) | x | y |\n"
                 "Why this record is nevertheless BLOCK: the most recent independent review (round 1) "
                 "returned BLOCK ... an independent round-2 review ...\nVerdict: BLOCK\n")
    ann_block_probs = _record_problems(ann_block, good_con)
    res.check(not any("non-pending row follows it" in x for x in ann_block_probs),
              "checker: an ANNOTATED pending row does NOT false-positive the BLOCK-state arm (0024)",
              "; ".join(ann_block_probs) or "clean")
    # Emphasis and backticks are markup, not a different verdict.
    for cell, why in (("**BLOCK**", "bold"), ("`BLOCK`", "code-span")):
        emph = good_rec.replace("| 2 | bbb | BLOCK |", f"| 2 | bbb | {cell} |")
        res.check(_record_problems(emph, good_con) == [],
                  f"checker: a {why}-marked BLOCK cell still classifies as BLOCK (0024)",
                  "; ".join(_record_problems(emph, good_con)) or "clean")
    # An UNRECOGNISED cell is a finding in its own right — this is the fail-closed half.
    for cell in ("blocked", "PASS-ish", "n/a", "-"):
        odd = good_rec.replace("| 2 | bbb | BLOCK |", f"| 2 | bbb | {cell} |")
        res.check(any("unrecognised verdict cell" in x for x in _record_problems(odd, good_con)),
                  f"checker: an unrecognised verdict cell {cell!r} is CAUGHT (0024, fail closed)")
    # `(self)` MUST keep classifying: it is a live row and it feeds CONTRIBUTING's author-round count.
    # It goes on round 1 so the prose's "most recent independent review (round 2) returned BLOCK" stays
    # true — a self round is not an independent review, so pinning it to the newest row would make the
    # fixture self-contradictory rather than a clean isolation of the classification.
    self_rec = good_rec.replace("| 1 | aaa | BLOCK |", "| 1 | aaa | (self) |")
    self_con = good_con.replace("2 independent cold-pass reviews and 0 author",
                                "1 independent cold-pass reviews and 1 author")
    res.check(_record_problems(self_rec, self_con) == [],
              "checker: a `(self)` verdict cell classifies and counts as an author round (0024)",
              "; ".join(_record_problems(self_rec, self_con)) or "clean")
    res.check(any("disagree with the table" in x for x in _record_problems(self_rec, good_con)),
              "checker: a `(self)` row still drives the CONTRIBUTING author-count cross-check (0024)")
    # The verdict HEAD is authoritative and a parenthetical is commentary — uniformly, in every arm. So an
    # annotated independent BLOCK counts as an independent round, not as an author round. Before 0024 the
    # author-count arm keyed on the substring "self" anywhere in the cell, so this cell was counted as an
    # author round while the prose arm simultaneously refused it as not-"BLOCK".
    ann_self = good_rec.replace("| 2 | bbb | BLOCK |", "| 2 | bbb | BLOCK (self-reported by the author) |")
    res.check(_record_problems(ann_self, good_con) == [],
              "checker: an annotated `BLOCK (self-...)` counts as an INDEPENDENT round, not an author one "
              "(0024; the head is authoritative)",
              "; ".join(_record_problems(ann_self, good_con)) or "clean")
    # 0024 round 2 (BLOCKER-3): the two PASS closure sentinels make DIFFERENT claims. An owner decision
    # may close over a BLOCK row (the live 0005 record does); a claimed passing REVIEW may not.
    rev_pass_bad = ("| # | head | verdict |\n|---|---|---|\n| 1 | aaa | BLOCK | x |\n| 2 | bbb | BLOCK | x |\n"
                    "review (round 2) returned PASS\nVerdict: PASS\n")
    res.check(any("a passing review may not" in x for x in _record_problems(rev_pass_bad, good_con)),
              "checker: 'review (round N) returned PASS' over a BLOCK row is CAUGHT (0024)")
    rev_pass_ok = rev_pass_bad.replace("| 2 | bbb | BLOCK | x |", "| 2 | bbb | PASS | x |")
    res.check(_record_problems(rev_pass_ok, good_con) == [],
              "checker: 'review (round N) returned PASS' over a PASS row passes (0024)",
              "; ".join(_record_problems(rev_pass_ok, good_con)) or "clean")
    # 0024 round 2 (BLOCKER-1): the grammar is a RECOGNISER — the whole cell must match. The first
    # attempt returned the first recognised word and ignored the rest, so these all classified.
    for cell in ("BLOCK PASS pending", "BLOCK garbage", "self BLOCK", "BLOCK <!-- pending -->",
                 "BLOCK [PASS](https://example.invalid)", "B*L*O*C*K", "BLOCK (one) (two)",
                 "BLOCK ((nested))", "BLOCK (note) trailing-junk"):
        odd = good_rec.replace("| 2 | bbb | BLOCK |", f"| 2 | bbb | {cell} |")
        res.check(any("unrecognised verdict cell" in x for x in _record_problems(odd, good_con)),
                  f"checker: unconsumed-suffix cell {cell!r} is CAUGHT (0024; the prefix parser took it)")
    res.check(_verdict_kind("BLOCK\npending") is None,
              "checker: a MULTI-LINE verdict cell is rejected (0024)")
    # 0024 round 2: `re.IGNORECASE` folds U+0131 DOTLESS I onto `i`, so `pendıng` MATCHES the grammar —
    # but it does not casefold to `i`, so without the membership test the function returned 'pendıng':
    # neither a member nor None, defeating the unrecognised-cell arm and the pending arm at once.
    for homoglyph in ("pend\u0131ng", "pend\u0130ng", "**pend\u0131ng**", "pend\u0131ng (round 3)"):
        res.check(_verdict_kind(homoglyph) is None,
                  f"checker: homoglyph cell {homoglyph!r} classifies as NOTHING, not as a non-member (0024)")
    homo_rec = pass_rec.replace("| 2 | bbb | BLOCK |", "| 2 | bbb | pend\u0131ng |")
    res.check(any("unrecognised verdict cell" in x for x in _record_problems(homo_rec, good_con)),
              "checker: a homoglyph verdict cell under Verdict: PASS is CAUGHT (0024, fail closed)")
    # 0024 round 2: an unparseable line INSIDE the round table used to vanish silently, so every invariant
    # was computed over fewer rows than the reader sees.
    torn = good_rec.replace("| 2 | bbb | BLOCK | x | y |", " | 2 | bbb | BLOCK | x | y |")
    res.check(any("not a parseable round row" in x for x in _record_problems(torn, good_con)),
              "checker: an unparseable line inside the round table is CAUGHT, not dropped (0024)")
    # 0024 round 2: the final-verdict line is matched whole, with the same grammar the required check
    # uses — `Verdict: PASS pending` used to read as PASS here and in gate-review-check.py alike.
    res.check(any("must be exactly" in x for x in _record_problems(
                  pass_rec.replace("Verdict: PASS", "Verdict: PASS pending"), good_con)),
              "checker: a final line 'Verdict: PASS pending' is CAUGHT (0024)")
    # 0024 round 2 (BLOCKER): the first attempt anchored the strict token INTO the line matcher, which made
    # an annotated line invisible rather than fatal — "last verdict wins" then fell back to an earlier,
    # friendlier line. A record ending `Verdict: BLOCK (2 outstanding)` after an earlier PASS must NOT read
    # as PASS, here or in the required check.
    mirror = (pass_rec.replace("Verdict: PASS", "Verdict: PASS\n\nmore text\n\nVerdict: BLOCK (2 outstanding)"))
    res.check(any("must be exactly" in x for x in _record_problems(mirror, good_con)),
              "checker: an ANNOTATED final BLOCK does not fall back to an earlier PASS (0024)")
    # 0024 round 2 (MAJOR-4): the round table is found by its HEADER, so a record's OTHER tables are not
    # mistaken for round history — this record's own census table has line numbers in column one.
    res.check(_round_rows("| line | site | was |\n|---|---|---|\n| 673 | a | b |\n") is None,
              "checker: a non-round table is NOT read as round history (0024)")
    res.check([r for r, _, _ in (_round_rows(good_rec) or ([], []))[0]] == [1, 2],
              "checker: a canonical round table IS found by its header (0024)")
    # The LIVE files must be consistent.
    live = _record_problems(GATE_RECORD.read_text(encoding="utf-8"), CONTRIB.read_text(encoding="utf-8"))
    res.check(live == [], "LIVE record + CONTRIBUTING are consistent", "; ".join(live) or "consistent")
    # 0024 round 2 (MAJOR-4): and EVERY record carrying a round history must satisfy the generic half —
    # not just the one hardcoded file, which policy also declares append-only.
    swept = 0
    for rec_path in sorted((ROOT / "gate-reviews").glob("*.md")):
        text = rec_path.read_text(encoding="utf-8")
        if _round_rows(text) is None:
            continue
        swept += 1
        probs = _record_problems(text)
        res.check(probs == [], f"LIVE record {rec_path.name} satisfies the generic round-table rules",
                  "; ".join(probs) or "consistent")
    res.check(swept >= 2, "the record sweep actually covers more than the one hardcoded record (0024)",
              f"{swept} record(s) with a round history")


def skill_enumerations(res: Results, verbose: bool) -> None:
    """Lock the skill-enumeration gate's CLAIMED behaviors (see the generator docstring + CONTRIBUTING
    "Skill-enumeration gate: scope"): it generates each enumeration from skills-order and verifies it
    against the parsed Markdown, catching accidental drift (5/5 sites), casual markup decoys, and — via
    the governed-doc raw-HTML ban — the DOM-nesting / tagfilter / raw-list / image class. It does NOT
    claim to defeat a determined adversary over arbitrary Markdown (that residual is disclosed, out of
    scope). Each claimed guard below is exercised so it BITES if reverted; replayed on scratch copies of
    the REAL docs.
    """
    print("skill-enumerations — drift-catcher + casual-decoy guard + raw-HTML ban (honest scope):")
    import shutil
    g = _load("genenum", GEN)
    order = ["alpha", "beta", "gamma"]

    # 1. Renderers + validate_order (the scalar count phrases were dropped in gate-reviews/0018; this
    #    section locks the renderers and the order-permutation validator only).
    res.check(g.render_improve_order(order) == "**alpha → beta → gamma.**", "render improve-order")
    res.check(g.render_pick_list(order) == "`alpha · beta · gamma`", "render pick-list")
    res.check(g.render_tree(order) == "```\nskills/\n├─ alpha/\n├─ beta/\n└─ gamma/\n```", "render tree")
    canon = {"alpha", "beta", "gamma"}
    res.check(g.validate_order(["alpha", "beta", "gamma"], canon) == [], "order: permutation ok")
    res.check(g.validate_order(["alpha", "beta"], canon) != [], "order: missing rejected")
    res.check(g.validate_order(["alpha", "alpha", "beta", "gamma"], canon) != [], "order: dup rejected")
    # 0017: the EXTRA branch (skills-order names a skill NOT in skills/) had no fixture, so reverting it
    # alone left the suite green. Lock it: an unknown name in the order is rejected.
    res.check(g.validate_order(["alpha", "beta", "gamma", "delta"], canon) != [], "order: extra name rejected")
    # 0011: unit-lock the two _marker_token_span branches that an END-TO-END case cannot isolate (with
    # either relaxed, other guards still catch the doc, so the suite stayed green while the branch was
    # unlocked — found only by a revert battery that actually ran).
    def _tok(src):
        return g._md().parse(src)
    A = "in this order (producers before consumers):"
    B, E = "<!-- skills:improve-order:begin -->", "<!-- skills:improve-order:end -->"
    def _raises(src):
        try:
            g._marker_token_span(_tok(src), "improve-order")
            return False
        except g.MarkerError:
            return True
    res.check(_raises(f"{A}\n\n{B}\n\n**x**\n\n{E}\n\n{B}\n\n**y**\n\n{E}\n"),
              "_marker_token_span raises on a DUPLICATE marker pair (locks the != 1 branch)")
    res.check(_raises(f"{A}\n\n{E}\n\n**x**\n\n{B}\n"),
              "_marker_token_span raises when end precedes begin (locks the order branch)")

    # NORMALIZATION per-STAGE unit-locks (0018): each _norm stage has an ISOLATING input, so reverting that
    # ONE stage changes the output and reddens exactly its assertion. (A whole-function stub alone bit via a
    # sibling stage, leaving each stage unproven — a GPT review reproduced this; the revert-battery now has a
    # matching per-stage mutant for each.)
    res.check(g._norm("¨") == "̈",   # ¨ -> NFKC space+combining; space stripped ONLY if NFKC is first
              "_norm stage: the initial NFKC runs BEFORE whitespace-collapse (U+00A8)")
    res.check(g._norm("a­b") == "ab",      # soft hyphen (a Cf char)
              "_norm stage: zero-width/format (Cf) strip removes a soft hyphen (U+00AD)")
    res.check(g._norm("a˗b") == "a-b",      # U+02D7 modifier minus -> ASCII '-'
              "_norm stage: Unicode-dash fold maps a modifier-minus (U+02D7) to ASCII '-'")
    res.check(g._norm("PUBLISH-MIRROR") == "publish-mirror",
              "_norm stage: casefold lowers a name")
    res.check(g._norm("о") == "o",          # Cyrillic 'о' -> Latin 'o' (NFKC does not fold this)
              "_norm stage: confusable fold maps a Cyrillic 'о' (U+043E) to Latin 'o'")
    res.check(g._norm(g._norm("ΐ")) == g._norm("ΐ"),   # casefold emits a decomposed sequence
              "_norm stage: the final NFKC recomposes casefold's decomposition (U+0390 idempotent)")
    # a realistic compatibility decoy: fullwidth skill-name letters fold to ASCII via NFKC (used by competing).
    res.check(g._norm("ｌｅａｒｎｉｎｇ-track") == "learning-track",
              "_norm: fullwidth (NFKC compatibility) letters fold to ASCII")

    # FAIL-CLOSED unit-lock (backs a battery guard a source mutation alone cannot prove end to end): an
    # ABSENT parser must fail closed with its OWN MarkerError message. 0019: catch ANY exception and assert
    # the type+message, NOT just `except MarkerError`. If _md's `raise MarkerError` is reverted to a no-op,
    # _md() returns `None("commonmark")` -> TypeError; a bare `except MarkerError` would let that escape and
    # ABORT the whole suite (a crash), which the revert battery's finding-branch sweep must NOT count as a
    # bite. Catching Exception turns that no-op revert into a reddening ASSERTION here (crash -> RED).
    saved_md = g.MarkdownIt
    try:
        g.MarkdownIt = None
        err = None
        try:
            g.check(ROOT)
        except Exception as e:   # noqa: BLE001 — deliberately broad; see the comment above
            err = e
        ok = isinstance(err, g.MarkerError) and "markdown-it-py is not installed" in str(err)
        res.check(ok, "absent parser (MarkdownIt=None) -> check() fails closed with MarkerError",
                  f"raised {type(err).__name__}" if err is not None else "did not raise")
    finally:
        g.MarkdownIt = saved_md

    # 2. End-to-end on scratch copies of the REAL docs. Baseline clean; every CLAIMED guard bites.
    # READ FROM skills-order, never retyped. A hardcoded run here is a decoy that
    # stops being planted the day a skill is added, and a fixture that plants
    # nothing reports "clean" — which is how ten of these went dormant.
    _ORDER = [ln.strip() for ln in (ROOT / "skills-order").read_text(encoding="utf-8").splitlines()
              if ln.strip() and not ln.strip().startswith("#")]
    FULL = ("<!-- skills:improve-order:begin -->\n"
            "**" + " → ".join(_ORDER) + ".**\n"
            "<!-- skills:improve-order:end -->")
    PUB = "| **publish-mirror** | publish step (no Diátaxis mode) | mirrors the source | — |"
    HDR = "| Skill | Diátaxis mode | Scope | Reading grade |"
    LT = "| **learning-track** | tutorial + explanation | public | ~9 |"
    # A NEAR-COMPLETE differently-formatted run (all 8 names, no bold, no trailing period) — a competing
    # ENUMERATION, as opposed to an incidental one/two-name mention. The competing/stray-name guards fire
    # only on a run this complete (gate-reviews/0013), so the decoy fixtures below use it.
    BROKEN_RUN = " → ".join(_ORDER)

    class ScratchResult:
        """What a scratch run produced: `findings` (a plain list) and `exc` (the exception check() raised,
        or None). COMPOSITION, not list inheritance (0021, round-17 MAJOR-4).

        The round-16 version subclassed `list`, and the claim that this made crash-as-finding
        "unrepresentable" was FALSE — a review reproduced it: `bool(result)` was true for a crash,
        iteration exposed the crash marker as if it were a finding, and inherited `==` ignored `.exc`
        entirely, so `ScratchResult([], exc) == []` was True. The old bad state was still reachable through
        the ordinary list protocol; only a call-site CONVENTION prevented it. That is a weaker guarantee
        than was advertised, and the advertisement was the defect.

        With composition the list protocol is simply absent: `was_clean(result)`, `len(result)`, `if result:`
        and `for f in result:` are all TypeErrors/False rather than quietly wrong answers, so every read
        MUST go through was_caught() / was_caught_msg() / was_clean(), each of which inspects `exc`."""
        __slots__ = ("findings", "exc")

        def __init__(self, findings, exc=None):
            self.findings = list(findings)
            self.exc = exc

        # 0022 (round-18 MAJOR-3): the round-17 claim that "if result:/len()/iteration are TypeErrors" was
        # FALSE — no dunders were defined, so default OBJECT truthiness made bool(result) True for a crash,
        # a clean run and a finding alike. The loud-failure property is now real: every accidental
        # list-like read raises, so a future assertion that skips the accessors cannot return a quietly
        # wrong answer. (repr/detail stay usable for res.check detail strings.)
        _USE = "read a ScratchResult via was_caught()/was_caught_msg()/was_clean(), never directly"

        def __bool__(self):
            raise TypeError(f"ScratchResult has no truthiness — {self._USE}")

        def __len__(self):
            raise TypeError(f"ScratchResult has no length — {self._USE}")

        def __iter__(self):
            raise TypeError(f"ScratchResult is not iterable — {self._USE}")

        def __eq__(self, other):
            raise TypeError(f"ScratchResult does not support == — {self._USE}")

        __hash__ = None

        def __repr__(self):
            return f"ScratchResult(findings={self.findings!r}, exc={self.exc!r})"

        def detail(self, limit=70):
            """Human-readable detail for a res.check() line (never used as an assertion)."""
            if self.exc is not None:
                return f"[CRASH] {type(self.exc).__name__}: {self.exc}"[:limit]
            return ("; ".join(self.findings) or "clean")[:limit]

    def scratch(mutate):
        tmp = Path(tempfile.mkdtemp(prefix="genenum-"))
        for rel in ["README.md", "per-skill-review-prompt.md", "skills-order",
                    "generate-skill-enumerations.py"]:
            shutil.copy(ROOT / rel, tmp / rel)
        shutil.copytree(ROOT / "skills", tmp / "skills")
        if mutate:
            mutate(tmp)
        gg = _load("gg", tmp / "generate-skill-enumerations.py")
        exc = None
        try:
            f = gg.check(tmp)
        except Exception as e:   # noqa: BLE001 — 0019/0020: a mutated generator whose fail-closed raise
            # was reverted can leave a downstream IndexError (an absent-marker input no longer
            # short-circuits). Capture it SEPARATELY (never as a finding) so it reddens an ASSERTION here
            # instead of aborting the whole suite, and so no assertion can read a crash as a catch. The
            # revert battery's finding-branch sweep requires a RED (assertion) bite, not a crash.
            f, exc = [], e
        shutil.rmtree(tmp, ignore_errors=True)
        return ScratchResult(f, exc)

    def was_caught(result):
        """True iff the fixture was caught by a REAL finding: check() did not raise, and it returned at
        least one finding. EVERY positive (decoy/drift must be CAUGHT) assertion goes through this —
        a crash is never a catch (0020)."""
        return result.exc is None and len(result.findings) >= 1

    def was_caught_msg(result, needle):
        """True iff was_caught() AND some finding contains `needle` — the message-specific form. The
        `exc is None` guard is what stops an exception TEXT that happens to contain the needle (e.g. a
        skill name in a traceback message) from satisfying a substring assertion (0020)."""
        return was_caught(result) and any(needle in f for f in result.findings)

    def was_clean(result):
        """True iff the doc is genuinely CLEAN: check() did not raise AND returned no findings. Every
        NEGATIVE (must-stay-clean) assertion goes through this. 0021: negatives previously read
        `was_clean(result)`, whose crash-rejection depended entirely on scratch() stuffing a sentinel STRING
        into the list — so the moment anyone 'cleaned that up' to an empty list, every negative fixture
        would have read a crash as clean. Now `exc` is consulted directly and no sentinel is needed."""
        return result.exc is None and result.findings == []

    # HARNESS SELF-TEST (0021): the accessors must reject a crash in BOTH directions. Without this, the
    # crash-safety of every fixture below rests on an unproven claim — the exact over-claim a review
    # reproduced when ScratchResult still subclassed list.
    _crash = ScratchResult([], RuntimeError("synthetic"))
    _found = ScratchResult(["a real finding"], None)
    _clean = ScratchResult([], None)
    res.check(not was_caught(_crash) and not was_clean(_crash)
              and was_caught(_found) and not was_clean(_found)
              and was_clean(_clean) and not was_caught(_clean),
              "scratch harness: a CRASH is neither 'caught' nor 'clean' (and real results classify)",
              f"crash=({was_caught(_crash)},{was_clean(_crash)}) found=({was_caught(_found)},"
              f"{was_clean(_found)}) clean=({was_caught(_clean)},{was_clean(_clean)})")
    # 0022: the list protocol must RAISE — for a crash, a clean run AND a finding result — so no future
    # assertion can consume a ScratchResult without going through the exc-aware accessors.
    def _raises_typeerror(op):
        try:
            op()
        except TypeError:
            return True
        except Exception:
            return False
        return False
    _proto_ok = all(_raises_typeerror(op)
                    for r in (_crash, _found, _clean)
                    for op in (lambda r=r: bool(r), lambda r=r: len(r),
                               lambda r=r: iter(r), lambda r=r: r == []))
    res.check(_proto_ok,
              "scratch harness: bool()/len()/iter()/== all raise TypeError on every ScratchResult shape",
              "all raise" if _proto_ok else "some list-protocol read did NOT raise")

    def repl(rel, a, b):
        return lambda t: (t / rel).write_text((t / rel).read_text(encoding="utf-8").replace(a, b),
                                              encoding="utf-8")

    res.check(was_clean(scratch(None)), "real-docs scratch: baseline is clean", scratch(None).detail())

    ol_decoy = "\n".join(f"{i}. {n}" for i, n in enumerate(
        ["publish-mirror", "doc-critic", "onboarding-companion", "operations-runbook",
         "usage-guide", "project-faq", "architecture-and-decisions", "NOT-A-SKILL"], 1))
    cases = [
        # accidental drift at EACH of the 5 sites — locks every site comparison AND the site registry
        # (0008 F1: reverting a site's check, or deleting it from the registry, must redden the suite).
        ("drift improve-order", repl("README.md", "→ publish-mirror.**", ".**")),
        ("drift tree (rename last node)", repl("README.md", "└─ publish-mirror/", "└─ NOT-A-SKILL/")),
        ("drift table (rename a body row)", repl("README.md", PUB,
            "| **NOT-A-SKILL** | publish step (no Diátaxis mode) | mirrors the source | — |")),
        ("drift pick-list (rename last)", repl("per-skill-review-prompt.md", "· publish-mirror`",
            "· NOT-A-SKILL`")),
        ("drift attach-table (rename a row)", repl("per-skill-review-prompt.md", "| publish-mirror |",
            "| NOT-A-SKILL |")),
        # marker + decoy regressions
        ("0005-1 spanning-comment marker", repl("README.md", FULL,
            "<!-- skills:improve-order:begin\n**x → y.**\nskills:improve-order:end -->\n\n"
            "**learning-track → project-faq.**")),
        ("0005-3 hidden-comment table row", repl("README.md", "<!-- skills:table:end -->",
            "<!--\n| learning-track | h | h | h |\n-->\n<!-- skills:table:end -->")),
        ("raw-HTML ban: blank <details> wrapper + list decoy", repl("README.md", FULL,
            "<details>\n<summary>s</summary>\n\n" + FULL + "\n\n</details>\n\n## Order\n\n" + ol_decoy)),
        ("raw-HTML ban: raw <ol> decoy list", repl("README.md", FULL,
            FULL + "\n\n<ol reversed>\n<li>publish-mirror</li>\n<li>NOT-A-SKILL</li>\n</ol>")),
        ("raw-HTML ban: comment-prefixed <div> block (0008 GPT-B1)", repl("README.md", FULL,
            FULL + "\n\n<!-- ok --><div>raw survives</div>")),
        ("raw-HTML ban: inline HTML in prose outside markers (0008 F2)", repl("README.md",
            "independent Claude skills", "<span>independent</span> Claude skills")),
        ("raw-HTML ban: tagfilter <script> in a cell", repl("README.md", LT,
            '| <script data-x="publish-mirror">learning-track</script> | tutorial + explanation | public | ~9 |')),
        # 0017: the IMAGE arm of the inline-HTML/image ban, isolated from the html_inline arm above. A raw
        # inline image in governed-doc prose is banned (its pixels/alt can disagree with the text); dropping
        # the "image" arm alone left this uncaught while the golden stayed green (a battery blind spot the
        # revert battery now also isolates). The image is the ONLY finding here, so this fixture isolates that arm.
        ("raw-HTML ban: inline image in governed-doc prose (0017)", repl("README.md",
            "independent Claude skills", "![doc-critic](x.png) independent Claude skills")),
        # a NEAR-COMPLETE broken run rendered OUTSIDE the block (the real block stays at its lead-in, so
        # this isolates _competing rather than the anchor guard): a relocated/duplicated enumeration.
        ("relocation: near-complete differently-formatted run outside the block", repl("README.md", FULL,
            FULL + "\n\nAlternatively, the same order: " + BROKEN_RUN + ".")),
        # 0009 MINOR 2: lock the two guards that previously had no fixture (they worked, but a no-op
        # revert would have passed CI). Now reverting either reddens the suite.
        # 0015: a second table whose cells hold a NEAR-COMPLETE run (>= n-1) is a competing table. A
        # 2-row reference table is NOT (that negative is locked below) — the fixed ">= 2 first cells" rule
        # that rejected it is gone.
        ("competing second table (all skills down column two after the marked block)",
            repl("README.md", "<!-- skills:table:end -->",
                 "<!-- skills:table:end -->\n\n| Step | Skill |\n|---|---|\n"
                 + "\n".join(f"| {i+1} | {nm} |" for i, nm in enumerate(_ORDER)) + "\n")),
        ("duplicate marker pair (improve-order)", repl("README.md", FULL, FULL + "\n\nagain:\n\n" + FULL)),
        # An EMPTY second marker pair. NOTE (corrected in 0011): this does NOT isolate the duplicate
        # branch — with duplicates admitted, the empty first region fails the pure-source comparison and
        # the displaced real block trips _competing, so the doc is still caught. The duplicate branch is
        # locked by the unit assertion above; this case remains as end-to-end coverage.
        ("duplicate EMPTY marker pair (end-to-end)",
            repl("README.md", FULL,
                 "<!-- skills:improve-order:begin -->\n<!-- skills:improve-order:end -->\n\n" + FULL)),
        # 0011: the WEAPONIZED duplicate — a second, non-empty pair after the real one carrying a decoy
        # with a non-canonical separator. With the duplicate branch relaxed this renders a second wrong
        # enumeration under the site's own markers and the check goes CLEAN.
        ("duplicate NON-EMPTY marker pair carrying a decoy (0011 weaponized)",
            repl("README.md", FULL, FULL +
                 "\n\n<!-- skills:improve-order:begin -->\n"
                 "**publish-mirror ⇒ doc-critic ⇒ learning-track.**\n"
                 "<!-- skills:improve-order:end -->")),
        # 0011 MINOR-1: a competing enumeration inside a FENCED block renders visibly, so the competing
        # scan must read fence content, not only inline tokens.
        ("competing near-complete run inside a fenced block",
            repl("README.md", "## Build",
                 "```\n" + BROKEN_RUN + "\n```\n\n## Build")),
        # 0012 BLOCKER: IN-REGION smuggling. `_competing` deliberately skips [b, e], so the ONLY thing
        # stopping a reader-visible decoy *between the real block and the end marker* is the region's
        # exactly-one-node grammar (_pure_source len==3 / _fence_body len==1). Both were unproven: a
        # one-character loosening (== -> >=) left the suite green while admitting these two decoys.
        ("in-region smuggle: decoy fence inside the improve-order region",
            repl("README.md", "<!-- skills:improve-order:end -->",
                 "\n```\npublish-mirror → doc-critic → learning-track\n```\n\n"
                 "<!-- skills:improve-order:end -->")),
        ("in-region smuggle: decoy paragraph inside the tree region",
            repl("README.md", "<!-- skills:tree:end -->",
                 "\nActually the order is publish-mirror, then doc-critic.\n\n"
                 "<!-- skills:tree:end -->")),
        # deliberately name-free: this isolates _table_names' region grammar (a stray paragraph in the
        # marked table region), independent of the competing scan.
        ("in-region smuggle: stray paragraph inside the table region",
            repl("README.md", "<!-- skills:table:end -->",
                 "\nNote: an unrelated sentence smuggled inside the marked region.\n\n"
                 "<!-- skills:table:end -->")),
        # 0016: a SECOND (header-only) table inside the marked table region — the region no longer holds
        # exactly one table. This isolates _table_names' first guard (a header-only second table adds no
        # tbody rows, so without the "exactly one table" guard the first column would still equal order and
        # the region would pass — the dead-stub gap a red-team pass found).
        ("in-region smuggle: a second (header-only) table inside the table region",
            repl("README.md", "<!-- skills:table:end -->",
                 "\n| Extra | Header |\n|---|---|\n\n<!-- skills:table:end -->")),
        # 0010 GPT-BLOCKER: the HTML allowlist is marker-IDENTITY, not comment-syntax.
        ("arbitrary (non-marker) HTML comment in a governed doc",
            repl("README.md", "## Build", "<!-- a maintainer note -->\n\n## Build")),
        # 0013 BLOCKER-2: SITE RELOCATION. The markers travel WITH the block, so moving a correct block to
        # an appendix leaves its site empty while the check still finds the markers and (pre-fix) passed.
        # _anchor_missing pins each site to its lead-in; the moved block lands after "## Appendix ...",
        # its anchor no longer precedes it, and the move is caught. Isolates the anchor guard (the moved
        # block itself still matches its renderer, and _competing skips the in-region run).
        ("relocation: improve-order block moved to an appendix (anchor lost)",
            lambda t: (t / "README.md").write_text(
                (t / "README.md").read_text(encoding="utf-8")
                .replace(FULL, "(the sequence now lives in the appendix)")
                .rstrip() + "\n\n## Appendix: generated sequence\n\n" + FULL + "\n", encoding="utf-8")),
    ]
    for name, mut in cases:
        f = scratch(mut)
        res.check(was_caught(f), f"real-docs scratch: {name} -> caught",
                  f.detail(66))

    # 0013 NEGATIVE cases — false positives the round-9 review reproduced must stay CLEAN. Each is ordinary,
    # legitimate content that a pre-fix over-broad guard flagged; the assertion is that the doc is clean, so
    # a future re-broadening of the guard turns it red.
    #  (a) FINDING #3 FP: a two-skill handoff in prose is a legitimate cross-reference, not a competing
    #      enumeration (only a near-complete run is).
    fp_handoff = scratch(lambda t: (t / "README.md").write_text(
        (t / "README.md").read_text(encoding="utf-8").rstrip()
        + "\n\nFor this workflow, architecture-and-decisions → project-faq is the normal handoff.\n",
        encoding="utf-8"))
    res.check(was_clean(fp_handoff), "two-skill handoff prose is NOT flagged as a competing enumeration",
              fp_handoff.detail(70))
    #  (c) FINDING #4 FP: a singleton skill reference in a non-first table column is a legitimate
    #      cross-reference, not a header/other-column decoy (only a near-complete run is).
    fp_cell = scratch(repl("README.md", LT,
        "| **learning-track** | tutorial + explanation; reviewed by doc-critic | public | ~9 |"))
    res.check(was_clean(fp_cell), "singleton skill reference in a description cell is NOT flagged as a decoy",
              fp_cell.detail(70))

    # ============================ 0014 (round-10 GPT BLOCKERs) ============================
    # The round-10 review reproduced four class-level escapes that per-instance fixtures had not exercised.
    # These are DATA-DRIVEN over every site, so the class — not one instance — is locked.
    # Named off the count deliberately. This was ORDER8, and when a ninth skill
    # arrived the list stayed at eight - so eight data-driven fixtures quietly
    # stopped catching anything while the suite still reported green. A count in
    # a variable name is a fact that goes stale silently.
    SKILL_ORDER = list(_ORDER)

    def _append(fname, extra):
        return lambda t: (t / fname).write_text(
            (t / fname).read_text(encoding="utf-8").rstrip() + "\n\n" + extra + "\n", encoding="utf-8")

    # 0017: DELETING an entire enumeration marked block (markers + content) must fail closed via the PURE
    # and TABLE loops' MarkerError handlers. Every prior marker-error fixture left the enumeration text in
    # place, so _competing_findings backstopped the catch and hid the handler's bite; a fully-deleted block
    # (no content to trip the competing scan) isolates each handler — reverting it to a no-op reddens here.
    def _delete_block(fname, begin_marker):
        end_marker = begin_marker.replace(":begin", ":end")
        def m(t):
            txt = (t / fname).read_text(encoding="utf-8")
            b = txt.index(begin_marker); e = txt.index(end_marker) + len(end_marker)
            (t / fname).write_text(txt[:b] + txt[e:], encoding="utf-8")
        return m
    del_imp = scratch(_delete_block("README.md", "<!-- skills:improve-order:begin -->"))
    res.check(was_caught_msg(del_imp, "improve-order"),
              "improve-order block DELETED entirely -> fails closed (PURE-loop MarkerError handler)",
              del_imp.detail(66))
    del_tab = scratch(_delete_block("README.md", "<!-- skills:table:begin -->"))
    res.check(was_caught_msg(del_tab, "'table'"),
              "table block DELETED entirely -> fails closed (TABLE-loop MarkerError handler)",
              del_tab.detail(66))
    # --- 0017: anchoring is ADJACENCY-ONLY (the 0014 uniqueness rule was dropped — it false-positived on an
    #     innocent repeat of an anchor phrase). For EACH of the five sites: RELOCATING the block away from
    #     its lead-in is caught (the block is no longer immediately preceded by its anchor); a legit REPEAT
    #     of the anchor phrase with the block left in place stays CLEAN. Both isolate _anchor_missing (the
    #     moved block still matches its renderer; _competing skips the in-region run).
    ANCHOR_SITES = [
        ("improve-order", "README.md", "in this order (producers before consumers)",
         "<!-- skills:improve-order:begin -->"),
        ("tree", "README.md", "generated from skills-order", "<!-- skills:tree:begin -->"),
        ("table", "README.md", "without re-authoring them", "<!-- skills:table:begin -->"),
        ("pick-list", "per-skill-review-prompt.md", "with exactly one of these",
         "<!-- skills:pick-list:begin -->"),
        ("attach-table", "per-skill-review-prompt.md", "no separate attachment is needed",
         "<!-- skills:attach-table:begin -->"),
    ]
    def _cut_block(text, begin_marker):
        end_marker = begin_marker.replace(":begin", ":end")
        b = text.index(begin_marker); e = text.index(end_marker) + len(end_marker)
        return text[:b], text[b:e], text[e:]
    def _relocate(fname, anchor, bm):
        # ADJACENCY: move the block to an appendix under a DIFFERENT heading (lead-in left behind), so the
        # block is no longer immediately preceded by its anchor -> CAUGHT.
        def m(t):
            pre, block, post = _cut_block((t / fname).read_text(encoding="utf-8"), bm)
            new = pre + "(block relocated to the appendix below)" + post
            new = new.rstrip() + f"\n\n## Appendix: generated sequence\n\n{block}\n"
            (t / fname).write_text(new, encoding="utf-8")
        return m
    def _repeat_anchor(fname, anchor):
        # FALSE-POSITIVE lock (0016): a legit SECOND mention of an anchor phrase in ordinary prose, block
        # LEFT IN PLACE, must stay CLEAN (uniqueness was dropped precisely because it flagged this).
        return lambda t: (t / fname).write_text(
            (t / fname).read_text(encoding="utf-8").rstrip()
            + f"\n\n## Notes\n\nFor context, {anchor} — see the section above.\n", encoding="utf-8")
    for site, fname, anchor, bm in ANCHOR_SITES:
        moved = scratch(_relocate(fname, anchor, bm))
        res.check(was_caught(moved), f"anchor '{site}': moving the block away from its lead-in is CAUGHT",
                  moved.detail(60))
        repeat = scratch(_repeat_anchor(fname, anchor))
        res.check(was_clean(repeat), f"anchor '{site}': a legit repeat of the anchor phrase (block in place) is CLEAN",
                  repeat.detail(70))

    # --- 0017: a lead-in reformatted as a BLOCKQUOTE or LIST (anchor intact, still immediately adjacent)
    #     must NOT false-positive the anchor check. _preceding_visible reads the immediately-preceding
    #     container's inline text, so the anchor is still found. Unit-level (a synthetic marked block),
    #     independent of the live docs' exact lead-in wording. Reverting the container branch reddens these.
    A_IMP = "in this order (producers before consumers)"
    BM_IMP, EM_IMP = "<!-- skills:improve-order:begin -->", "<!-- skills:improve-order:end -->"
    def _anchor_found(leadin_md):
        src = f"{leadin_md}\n\n{BM_IMP}\n\n**a → b.**\n\n{EM_IMP}\n"
        tks = g._md().parse(src)
        b, _e = g._marker_token_span(tks, "improve-order")
        return not g._anchor_missing(tks, b, "improve-order")
    res.check(_anchor_found(f"Improve them {A_IMP}:"),
              "anchor: a plain-paragraph lead-in is recognized (baseline)")
    res.check(_anchor_found(f"> Improve them {A_IMP}:"),
              "anchor: a BLOCKQUOTE lead-in (intact anchor, adjacent) is recognized, not a false 'moved away'")
    res.check(_anchor_found(f"- first set up\n- Improve them {A_IMP}:"),
              "anchor: a LIST lead-in (anchor in the final bullet) is recognized, not a false 'moved away'")
    # negative: a NON-lead-in container (no anchor phrase) immediately before the marker is still 'missing'.
    res.check(not _anchor_found("> Some unrelated quoted note about the weather."),
              "anchor: a preceding container WITHOUT the anchor phrase still trips the anchor (adjacency holds)")
    # 0017: an UNREGISTERED site id (absent from ANCHORS) fails closed — _anchor_missing returns True, so a
    # maintainer who adds a marked site but forgets to register its anchor is caught, not silently accepted.
    _tks_ur = g._md().parse(f"lead-in text\n\n{BM_IMP}\n\n**a → b.**\n\n{EM_IMP}\n")
    _b_ur, _ = g._marker_token_span(_tks_ur, "improve-order")
    res.check(g._anchor_missing(_tks_ur, _b_ur, "unregistered-site") is True,
              "anchor: an unregistered site id (not in ANCHORS) fails closed")

    # --- 0014 BLOCKER-4a: a competing enumeration formatted as a NATIVE Markdown list (one name per item)
    #     must be AGGREGATED across items — no single item reaches threshold, so a per-token check misses it.
    stray_list = "\n".join(f"- {nm}" for nm in SKILL_ORDER)
    caught = scratch(repl("README.md", "## Build", "Restated order:\n\n" + stray_list + "\n\n## Build"))
    res.check(was_caught(caught), "stray native Markdown list of all skills is CAUGHT (list aggregation)",
              caught.detail(60))
    # 0017: a run one-name-per-line in a SINGLE paragraph (soft breaks) is caught — _inline_text renders a
    # softbreak as a space (the break->space branch), so the names stay separated and match at boundaries.
    # A mutation sweep found this branch had no fixture; reverting it concatenates the names and misses them.
    softbreak_run = "\n".join(SKILL_ORDER)
    caught_sb = scratch(repl("README.md", "## Build", softbreak_run + "\n\n## Build"))
    res.check(was_caught(caught_sb), "a soft-break-separated run (one name per line, one paragraph) is CAUGHT",
              caught_sb.detail(60))
    # a native list of TWO skills is a legitimate cross-reference, still CLEAN (below threshold).
    ok = scratch(repl("README.md", "## Build",
                      "See also:\n\n- learning-track\n- project-faq\n\n## Build"))
    res.check(was_clean(ok), "a two-item skill list is NOT flagged (list aggregation respects the threshold)",
              ok.detail(70))
    # --- 0017: the competing scan reads INDENTED code blocks (`code_block` tokens), not just ``` fences.
    #     Every prior fixture used a fence, so the code_block arm was load-bearing but unproven (dropping it
    #     left the suite green — the _table_names guard-a class). Two fixtures isolate it:
    #     (a) phase-1: a top-level 4-space indented block of all 8 names is one code_block -> CAUGHT.
    indented = "\n".join("    " + nm for nm in SKILL_ORDER)   # 4-space indent -> a single code_block token
    caught_ind = scratch(repl("README.md", "## Build", "Restated order:\n\n" + indented + "\n\n## Build"))
    res.check(was_caught(caught_ind), "stray INDENTED (code_block) list of all skills is CAUGHT (phase-1 code_block arm)",
              caught_ind.detail(60))
    #     (b) phase-2: a blockquote with 4 names in a paragraph AND 4 in an indented code block — neither
    #     unit reaches threshold, so only the container aggregation (which must include code_block) catches it.
    bq = ("> " + ", ".join(SKILL_ORDER[:4]) + "\n>\n" + "\n".join(">     " + nm for nm in SKILL_ORDER[4:]))
    caught_bq = scratch(repl("README.md", "## Build", bq + "\n\n## Build"))
    res.check(was_caught(caught_bq),
              "blockquote split across a paragraph + indented code block is CAUGHT (phase-2 code_block arm)",
              caught_bq.detail(60))

    # --- 0016: a decoy enumeration in a NON-FIRST table column is deliberately NOT checked — any such
    #     check false-positives on a legitimate cross-reference column (a "Handoff" / "Reviewed by" column
    #     naming several skills). A legit non-first column naming many skills therefore stays CLEAN:
    def _handoff_col(t):
        import re as _re
        lines = (t / "README.md").read_text(encoding="utf-8").split("\n")
        ri = 0
        for i, ln in enumerate(lines):
            m = _re.match(r"\| \*\*([a-z-]+)\*\* \| ([^|]*)\|(.*)", ln)
            if m and m.group(1) in SKILL_ORDER:
                lines[i] = f"| **{m.group(1)}** | hands off to {SKILL_ORDER[(ri+1) % len(SKILL_ORDER)]} |{m.group(3)}"
                ri += 1
        (t / "README.md").write_text("\n".join(lines), encoding="utf-8")
    res.check(was_clean(scratch(_handoff_col)),
              "table: a legit cross-reference column naming skills is NOT flagged (stray-names dropped)")

    # --- 0014: _competing_run boundaries — look-alike names that merely CONTAIN a skill name as a
    #     substring ("project-faq-notes") are NOT the skills, so a full run of look-alikes stays CLEAN.
    suffixed = "\n".join(f"- {nm}-notes" for nm in SKILL_ORDER)
    ok = scratch(repl("README.md", "## Build", "Unrelated notes index:\n\n" + suffixed + "\n\n## Build"))
    res.check(was_clean(ok), "suffix look-alikes ('name-notes') are NOT a competing run (locks the _R boundary)",
              ok.detail(70))
    prefixed = "\n".join(f"- draft-{nm}" for nm in SKILL_ORDER)
    ok = scratch(repl("README.md", "## Build", "Unrelated drafts index:\n\n" + prefixed + "\n\n## Build"))
    res.check(was_clean(ok), "prefix look-alikes ('draft-name') are NOT a competing run (locks the _L boundary)",
              ok.detail(70))

    # ============================ 0015 (round-11 GPT BLOCKERs) ============================
    def _app(fname, extra):
        return lambda t: (t / fname).write_text(
            (t / fname).read_text(encoding="utf-8").rstrip() + "\n\n" + extra + "\n", encoding="utf-8")

    # --- 0016 competing: a near-complete run in a BLOCKQUOTE (one name per quoted paragraph) and an
    #     UPPERCASE run are CAUGHT (container aggregation + normalization); nested list-in-blockquote too.
    bq = "\n".join(f"> {nm}\n>" for nm in SKILL_ORDER)
    res.check(was_caught(scratch(_app("README.md", bq))),
              "competing: a blockquote of one skill per quoted paragraph is CAUGHT (container aggregation)")
    res.check(was_caught(scratch(_app("README.md", "> see:\n> " + "\n> ".join(f"- {nm}" for nm in SKILL_ORDER)))),
              "competing: a nested list inside a blockquote is CAUGHT")
    res.check(was_caught(scratch(_app("README.md", "Order: " + ", ".join(nm.upper() for nm in SKILL_ORDER) + "."))),
              "competing: an UPPERCASE comma run is CAUGHT (normalization)")
    res.check(was_caught(scratch(_app("per-skill-review-prompt.md",
              "Order: " + ", ".join(nm.upper() for nm in SKILL_ORDER) + "."))),
              "competing: an UPPERCASE run in the PROMPT is CAUGHT")
    # names with an invisible SOFT HYPHEN (U+00AD, a Cf char) or a U+2011 non-breaking hyphen read as the
    # real names -> CAUGHT (the Cf-strip + dash-fold in _norm; reverting either reddens this).
    res.check(was_caught(scratch(_app("README.md",
              "Order: " + ", ".join(nm.replace("-", "­-") for nm in SKILL_ORDER) + "."))),
              "competing: soft-hyphen-injected names are CAUGHT (Cf strip in _norm)")
    res.check(was_caught(scratch(_app("README.md",
              "Order: " + ", ".join(nm.replace("-", "‑") for nm in SKILL_ORDER) + "."))),
              "competing: U+2011 non-breaking-hyphen names are CAUGHT (dash fold in _norm)")
    # common Cyrillic/Greek HOMOGLYPHS in the skill names (a reader-visible decoy) are CAUGHT (the
    # confusables fold in _norm). Here every Latin 'o' is a Cyrillic 'о' (U+043E).
    homoglyph = "Order: " + ", ".join(nm.replace("o", "о") for nm in SKILL_ORDER) + "."
    res.check(was_caught(scratch(_app("README.md", homoglyph))),
              "competing: Cyrillic-homoglyph names are CAUGHT (confusables fold in _norm)")
    # a two-skill blockquote is a legit cross-reference -> CLEAN (below threshold).
    res.check(was_clean(scratch(_app("README.md", "> learning-track\n>\n> project-faq"))),
              "competing: a two-skill blockquote is NOT flagged")


    # --- 0015 BLOCKER-3: competing enumerations in ANY shape outside the marked blocks, no separator.
    #     (A run split across SEPARATE containers so no one is near-complete is a DISCLOSED residual —
    #     aggregating across unrelated containers would FP on legit prose; the negative below locks that.)
    ROUTES = [
        ("comma paragraph", "README.md", "The full order: " + ", ".join(SKILL_ORDER) + "."),
        ("separator-free fence", "README.md", "```\n" + "\n".join(SKILL_ORDER) + "\n```"),
        ("ordered list", "README.md", "\n".join(f"{i+1}. {nm}" for i, nm in enumerate(SKILL_ORDER))),
        ("fenced name per list item (one list)", "README.md",
         "\n".join(f"- see\n  ```\n  {nm}\n  ```" for nm in SKILL_ORDER)),
        ("comma paragraph in the PROMPT", "per-skill-review-prompt.md", "Order: " + ", ".join(SKILL_ORDER) + "."),
    ]
    for label, fname, extra in ROUTES:
        caught = scratch(_app(fname, extra))
        res.check(was_caught(caught), f"competing route '{label}' is CAUGHT",
                  caught.detail(60))
    # FP-SAFETY (the reason aggregation is PER container, not whole-document): legitimate prose that names
    # several skills across SEPARATE lists — the shape a red-team pass flagged as a false positive under
    # whole-file list aggregation — must stay CLEAN.
    legit = scratch(_app("README.md",
        "## Documentation types\n\n- Tutorials come from `learning-track`\n"
        "- Explanations from `architecture-and-decisions`\n- Reference from `project-faq`\n"
        "- How-tos from `usage-guide`\n\nSome prose about the process.\n\n## More types\n\n"
        "- Runbooks from `operations-runbook`\n- Onboarding from `onboarding-companion`\n"
        "- Review from `doc-critic`\n- Publishing from `publish-mirror`"))
    res.check(was_clean(legit), "legit prose naming skills across SEPARATE lists is NOT flagged (per-container)",
              legit.detail(70))

    # a genuine 2-row reference table (an OUTSIDE table) is NOT a competing table -> CLEAN.
    ref = scratch(_app("README.md", "| Skill | Note |\n|---|---|\n| learning-track | a |\n| doc-critic | b |"))
    res.check(was_clean(ref), "a 2-row reference table is NOT flagged as competing",
              ref.detail(70))

    # --- a missing skills-order fails closed via load_order's own message.
    no_order = scratch(lambda t: (t / "skills-order").unlink())
    res.check(was_caught_msg(no_order, "skills-order not found"),
              "missing skills-order -> load_order fails closed with its own message",
              no_order.detail(60))

    # a missing governed doc fails closed at each PURE and TABLE site with its own message. A missing PROMPT
    # trips its pick-list (pure) and attach-table (table) not-found; a missing README trips improve-order /
    # tree / table. Assert the specific per-loop messages so each not-found append is isolated (0018: a
    # mutation sweep found reverting either left the suite green when only the removed count check fired).
    missing = scratch(lambda t: (t / "per-skill-review-prompt.md").unlink())
    res.check(was_caught_msg(missing, "not found (needed for site 'pick-list')"),
              "missing PROMPT -> the pick-list (pure) site fails closed with its own not-found message",
              missing.detail(60))
    res.check(was_caught_msg(missing, "not found (needed for site 'attach-table')"),
              "missing PROMPT -> the attach-table (table) site fails closed with its own not-found message")
    delreadme = scratch(lambda t: (t / "README.md").unlink())
    res.check(was_caught_msg(delreadme, "not found (needed for site 'improve-order')"),
              "missing README -> the PURE-site loop fails closed with its own not-found message")
    res.check(was_caught_msg(delreadme, "not found (needed for site 'table')"),
              "missing README -> the TABLE-site loop fails closed with its own not-found message")

    # empty source fails closed via check()'s OWN guard (0008 F5: isolate — assert the specific message,
    # not just "a finding", since validate_order would also reject an empty set).
    empty = scratch(lambda t: (shutil.rmtree(t / "skills"), (t / "skills").mkdir()))
    res.check(was_caught_msg(empty, "no skills found"),
              "empty skills/ -> check() fails closed with its own message (isolated)",
              empty.detail(60))

    # ============================ 0019 (round-15 GPT BLOCK) ============================
    # A different-vendor cold pass reproduced six coverage gaps; each fixture below reddens the exact
    # revert it names, and its matching revert-battery mutant is bound to it by name (expect_fx).

    # --- BLOCKER-1: the CLI VERDICT PATH. main()'s `if findings:` (and its `return 1`) is the ONLY thing
    #     between a drifted doc and a clean-banner exit 0. The scratch fixtures call check() directly and
    #     never exercise main, so reverting `if findings:` passed unseen. Drive the REAL binary end-to-end
    #     on a DRIFTED repo and assert all three: nonzero exit, a FAIL diagnostic, and NO clean banner.
    def _cli_check(mutate, shadow_import_error=False):
        tmp = Path(tempfile.mkdtemp(prefix="genenum-cli-"))
        for rel in ["README.md", "per-skill-review-prompt.md", "skills-order",
                    "generate-skill-enumerations.py"]:
            shutil.copy(ROOT / rel, tmp / rel)
        shutil.copytree(ROOT / "skills", tmp / "skills")
        if mutate:
            mutate(tmp)
        env = dict(os.environ)
        if shadow_import_error:
            # Make `import markdown_it` fail DETERMINISTICALLY in the child: a shadow module earlier on
            # sys.path that raises ImportError. This drives main()'s `except MarkerError` verdict path —
            # the parser-missing arm no fixture reached (0020 BLOCKER-1).
            (tmp / "markdown_it.py").write_text(
                'raise ImportError("shadowed for the parser-missing CLI fixture")\n', encoding="utf-8")
            env["PYTHONPATH"] = str(tmp)
        p = subprocess.run([sys.executable, str(tmp / "generate-skill-enumerations.py"),
                            str(tmp), "--check"], capture_output=True, text=True, env=env)
        shutil.rmtree(tmp, ignore_errors=True)
        # stdout and stderr SEPARATELY (0022): the arms pin stdout exactly AND require stderr empty, so
        # rerouting a diagnostic to stderr cannot satisfy an arm that combined the two streams.
        return p.returncode, p.stdout, p.stderr

    # LINE-BASED oracle (0020 BLOCKER-2): substring tests could not prove the advertised contract — a
    # TRACEBACK containing the word "FAIL" satisfied `"fail" in out`, and the pristine arm never forbade a
    # FAIL line, so a phantom "FAIL" printed beside the clean banner passed. Parse COMPLETE lines instead.
    FAIL_PREFIX = "FAIL  skill-enum:"
    BANNER_PREFIX = "--- skill-enumerations: clean ("
    # The EXACT banner main() must print on a pristine repo, constructed here from this fixture's OWN
    # inventory (len(SKILL_ORDER)), never from the generator — so a corrupted count cannot agree with itself.
    # 0021 (round-17 BLOCKER-1): the previous form checked `all(clause in banner)`, which proves only that
    # three byte-strings appear SOMEWHERE in the line. A review reproduced three survivors: `n = 0`
    # ("clean (0 skills; …)"), a NEGATED clause ("NOT every marked enumeration matches …"), and a
    # DUPLICATED clause. Exact equality admits none of them — wrong count, inserted negation, added or
    # repeated text all differ from this string. This repository exists because "a success message
    # asserted more than the code verified" (CONTRIBUTING), so the success string is pinned exactly.
    EXPECTED_BANNER = (
        f"--- skill-enumerations: clean ({len(SKILL_ORDER)} skills; every marked enumeration matches "
        f"skills-order in the parsed Markdown; governed docs contain no raw HTML except the comment "
        f"markers — drift-catcher, see CONTRIBUTING for scope) ---")

    def _cli_lines(out):
        lines = out.splitlines()
        return ([l for l in lines if l.strip().startswith(FAIL_PREFIX)],
                [l for l in lines if l.strip().startswith(BANNER_PREFIX)],
                any("Traceback (most recent call last)" in l for l in lines))

    # 0022 (round-18 MAJOR-5): the drift arm was materially WEAKER than the pristine arm — it accepted
    # ANY line starting "FAIL  skill-enum:" (a constant phantom passed), never required the failure
    # summary, and could not see truncated findings, a wrong summary count, or a silent SystemExit(1).
    # Every CLI arm now pins the EXACT COMPLETE output (all non-blank lines, in order), constructed from
    # this fixture's OWN knowledge of the drift it introduced — the same standard the pristine banner got
    # in 0021. Exactness subsumes: real diagnostic text, ALL findings printed, correct summary count, no
    # phantom lines, no traceback, and no summary-less early exit.
    def _cli_output_lines(out):
        # Blank/whitespace-only lines are dropped DELIBERATELY: they render nothing and can carry no
        # claim, and pinning them would make the contract brittle to zero-information spacing. Every
        # information-bearing line is pinned exactly, stderr must be empty, and the exit code is pinned.
        return [l for l in out.splitlines() if l.strip()]

    def _echo(lines):
        """Render child-output lines for a res.check DETAIL string. The literal traceback header is
        neutralised so a failing arm's detail cannot be mistaken for the SUITE crashing by anything that
        scans this suite's output (the revert battery's crash signal is the missing summary line, but the
        detail should not carry the magic string either — 0022)."""
        return repr(lines).replace("Traceback (most recent call last)", "<child-traceback>")

    _FAIL_IMPROVE = ("   FAIL  skill-enum: README.md: 'improve-order' block is not the generated "
                     "enumeration (run generate-skill-enumerations.py)")
    _FAIL_PICK = ("   FAIL  skill-enum: per-skill-review-prompt.md: 'pick-list' block is not the "
                  "generated enumeration (run generate-skill-enumerations.py)")
    _FAIL_PARSER = ("   FAIL  skill-enum: markdown-it-py is not installed — the enumeration gate cannot "
                    "run (pip install markdown-it-py)")

    def _summary(n):
        return (f"--- skill-enumerations: {n} finding(s) — regenerate with "
                f"`python3 generate-skill-enumerations.py` and re-check ---")

    # (a) ONE drifted site: exit 1; output is EXACTLY the real diagnostic + the 1-finding summary.
    rc, out, err = _cli_check(repl("README.md", "→ publish-mirror.**", ".**"))
    got = _cli_output_lines(out)
    want = [_FAIL_IMPROVE, _summary(1)]
    res.check(rc == 1 and got == want and err.strip() == "",
              "CLI --check on a DRIFTED doc: exit 1 + EXACT stdout (real diagnostic + 1-finding summary) + empty stderr",
              f"exit {rc}; exact={got == want}" + ("" if got == want else f"; got={_echo(got[:2])}"))
    # (b) TWO drifted sites (one per governed file): BOTH diagnostics, in registry order, + the 2-finding
    #     summary — proves every finding is printed and the count is the real count.
    def _two_drifts(t):
        repl("README.md", "→ publish-mirror.**", ".**")(t)
        repl("per-skill-review-prompt.md", "· publish-mirror`", "· NOT-A-SKILL`")(t)
    rc2, out2, err2 = _cli_check(_two_drifts)
    got2 = _cli_output_lines(out2)
    want2 = [_FAIL_IMPROVE, _FAIL_PICK, _summary(2)]
    res.check(rc2 == 1 and got2 == want2 and err2.strip() == "",
              "CLI --check with TWO drifted sites: exit 1 + EXACT stdout (both diagnostics + 2-finding summary) + empty stderr",
              f"exit {rc2}; exact={got2 == want2}" + ("" if got2 == want2 else f"; got={_echo(got2[:3])}"))
    # (c) PRISTINE: exit 0; output is EXACTLY the expected clean banner and nothing else.
    rc0, out0, err0 = _cli_check(None)
    got0 = _cli_output_lines(out0)
    banner_exact = got0 == [EXPECTED_BANNER]
    res.check(rc0 == 0 and banner_exact and err0.strip() == "",
              "CLI --check on a PRISTINE repo: exit 0 + EXACT stdout (the EXACT clean banner alone) + empty stderr",
              f"exit {rc0}; exact={banner_exact}" + ("" if banner_exact else f"; got={_echo(got0[:2])}"))
    # (d) PARSER MISSING: main()'s `except MarkerError` verdict path — exit 1; output is EXACTLY the
    #     fail-closed diagnostic and nothing else. Reverting that arm's `return 1` to 0 reddens here.
    rcp, outp, errp = _cli_check(None, shadow_import_error=True)
    gotp = _cli_output_lines(outp)
    parser_exact = gotp == [_FAIL_PARSER]
    res.check(rcp == 1 and parser_exact and errp.strip() == "",
              "CLI --check with markdown-it MISSING: exit 1 + EXACT stdout (the fail-closed diagnostic alone) + empty stderr",
              f"exit {rcp}; exact={parser_exact}" + ("" if parser_exact else f"; got={_echo(gotp[:2])}"))

    # --- 0020 MAJOR-5: _inline_text renders BOTH break kinds as a space so adjacent names stay separated
    #     for boundary matching. Only the SOFTBREAK half had a fixture, so dropping "hardbreak" left the
    #     suite green while a two-trailing-space (hard-break) run went unflagged. A realistic run written
    #     with two trailing spaces per line produces hardbreak children — it must be CAUGHT.
    hardbreak_run = "  \n".join(SKILL_ORDER)      # two trailing spaces before each newline -> hardbreak tokens
    caught_hb = scratch(repl("README.md", "## Build", hardbreak_run + "\n\n## Build"))
    res.check(was_caught(caught_hb),
              "a HARD-break-separated run (two trailing spaces per line) is CAUGHT (hardbreak arm)",
              caught_hb.detail(60))

    # --- 0020 MAJOR-6: the producers' declared FILTERING semantics were unlocked — only their file
    #     dependency was. load_order promises to skip blank lines and '#' comments; canonical_skills
    #     promises to count only directories holding a SKILL.md. Neither was fixtured, so removing either
    #     predicate left the suite green while breaking a legitimate source layout.
    #   (a) load_order: a REALISTIC skills-order (a comment, blank lines, indented entries) must parse to
    #       exactly the names, in order. Removing the blank-line predicate yields an empty-string "skill".
    lo2 = Path(tempfile.mkdtemp(prefix="loadorder-filter-"))
    (lo2 / "skills").mkdir()
    for nm in SKILL_ORDER:
        (lo2 / "skills" / nm).mkdir()
        (lo2 / "skills" / nm / "SKILL.md").write_text("x", encoding="utf-8")
    # 0021 (round-17 MAJOR-3): the round-16 fixture used only COLUMN-ZERO comments and GENUINELY EMPTY
    # blank lines, so a regression to `if ln and not ln.startswith("#")` — dropping the whitespace
    # normalisation while keeping both predicates — stayed green, yet would read an INDENTED comment and a
    # WHITESPACE-ONLY line as skill names. The fixture now carries both shapes, so the contract
    # ("skip blank lines and # comments", whitespace-normalised) is locked rather than one formatting of it.
    (lo2 / "skills-order").write_text(
        "# a leading comment\n"
        "   # an INDENTED comment (spaces)\n"
        "\t# an INDENTED comment (tab)\n"
        "\n"                                                     # genuinely empty line
        "   \n"                                                  # WHITESPACE-ONLY line
        "\t\n"                                                   # TAB-ONLY line
        + SKILL_ORDER[0] + "\n\n"
        + "  " + SKILL_ORDER[1] + "  \n"                              # leading/trailing whitespace
        + "\n".join(SKILL_ORDER[2:]) + "\n   \n# a trailing comment\n", encoding="utf-8")
    got2, errs2 = g.load_order(lo2, set(SKILL_ORDER))
    res.check(got2 == SKILL_ORDER and errs2 == [],
              "load_order skips comments/blank lines and strips whitespace (exact order, no empty entry)",
              f"{got2[:2]}… n={len(got2)} errs={errs2}")
    shutil.rmtree(lo2, ignore_errors=True)
    #   (b) canonical_skills: a legitimate helper directory under skills/ WITHOUT a SKILL.md is not a
    #       skill — it must be ignored, and the repo must stay clean. Removing the SKILL.md predicate
    #       misclassifies it as a skill and falsely reports it missing from skills-order.
    def _add_non_skill_dir(t):
        d = t / "skills" / "fixture-not-a-skill"
        d.mkdir()
        (d / "README.md").write_text("a helper directory, not a skill\n", encoding="utf-8")
    non_skill = scratch(_add_non_skill_dir)
    res.check(was_clean(non_skill),
              "canonical_skills ignores a skills/ dir without SKILL.md (helper dir -> still CLEAN)",
              non_skill.detail(70))

    # --- MAJOR-3: the source-of-truth PRODUCERS (load_order, canonical_skills) were only checked against
    #     today's output; their dependency on the source FILES was not locked.
    #   (a) load_order READS skills-order: swap two order lines (docs unchanged) -> the regenerated
    #       enumerations no longer match the docs -> CAUGHT. Bites a mutant that hardcodes the order.
    order_swap = scratch(repl("skills-order", "learning-track\narchitecture-and-decisions",
                              "architecture-and-decisions\nlearning-track"))
    res.check(was_caught(order_swap),
              "load_order reads skills-order: swapping two order lines (docs unchanged) is CAUGHT",
              order_swap.detail(56))
    #       unit: the returned order is EXACTLY the file's order (a hardcoded list would ignore the file).
    lo_tmp = Path(tempfile.mkdtemp(prefix="loadorder-"))
    (lo_tmp / "skills").mkdir()
    for nm in SKILL_ORDER:
        (lo_tmp / "skills" / nm).mkdir()
        (lo_tmp / "skills" / nm / "SKILL.md").write_text("x", encoding="utf-8")
    reordered = list(reversed(SKILL_ORDER))
    (lo_tmp / "skills-order").write_text("\n".join(reordered) + "\n", encoding="utf-8")
    got_order, got_errs = g.load_order(lo_tmp, set(SKILL_ORDER))
    res.check(got_order == reordered and got_errs == [],
              "load_order returns skills-order's exact order (not a hardcoded list)",
              f"{got_order[:2]}… errs={got_errs}")
    shutil.rmtree(lo_tmp, ignore_errors=True)
    #   (b) canonical_skills READS skills/: a new skill DIR absent from skills-order is reported (missing),
    #       and removing a dir while keeping its order entry is reported (extra). validate_order cannot
    #       discover a dir canonical_skills silently omits, so this is NOT covered by validate_order's stub.
    def _add_undeclared_skill(t):
        d = t / "skills" / "fixture-new-skill"
        d.mkdir()
        (d / "SKILL.md").write_text("# fixture-new-skill\n", encoding="utf-8")
    new_skill = scratch(_add_undeclared_skill)
    res.check(was_caught_msg(new_skill, "fixture-new-skill"),
              "canonical_skills reads skills/: a new skill dir absent from skills-order is reported (missing)",
              new_skill.detail(56))
    extra_dir = scratch(lambda t: shutil.rmtree(t / "skills" / "doc-critic"))
    res.check(was_caught_msg(extra_dir, "doc-critic"),
              "canonical_skills reads skills/: removing a skill dir (order entry kept) is reported (extra)",
              extra_dir.detail(56))

    # --- MAJOR-4a: the raw-HTML ban scans BOTH governed files, but every raw-HTML fixture above mutates
    #     only README, so dropping PROMPT from the ban loop stayed green. Data-drive the four raw-HTML
    #     classes over BOTH files so the document-wide ban is proven per-file.
    RAW_DECOYS = [
        ("raw <div> block", "<div>ordinary note</div>"),
        ("inline <span> HTML", "A note with an <span>inline</span> tag."),
        ("inline image", "A note with an image ![alt text](diagram.png) inline."),
        ("arbitrary HTML comment", "<!-- a maintainer note -->"),
    ]
    for fname in ("README.md", "per-skill-review-prompt.md"):
        for label, decoy in RAW_DECOYS:
            caught = scratch(_append(fname, decoy))
            res.check(was_caught(caught),
                      f"raw-HTML ban: {label} in {fname} is CAUGHT (document-wide, both files)",
                      caught.detail(56))

    # --- MAJOR-4b: the marker allowlist is derived from the FIVE current site ids; the count sites were
    #     retired this round, so a standalone RETIRED marker comment must now be REJECTED as raw HTML. No
    #     fixture locked this, so re-adding those ids to the allowlist stayed green.
    for retired in ("<!-- skills:count-suite:begin -->", "<!-- skills:count-suite:end -->",
                    "<!-- skills:count-nskill:begin -->", "<!-- skills:count-nskill:end -->"):
        caught = scratch(_append("README.md", retired))
        res.check(was_caught(caught),
                  f"retired marker {retired} is REJECTED as raw HTML (not in the current allowlist)",
                  caught.detail(56))

    # --- MAJOR-5: the anchor contract permits a HEADING lead-in and promises NORMALIZED matching, but no
    #     fixture exercised the heading arm or either _norm call site in _preceding_visible — dropping
    #     "heading_close" or a _norm wrapper stayed green. Lock the heading arm and normalized paragraph +
    #     container lead-ins (uppercase casefold + a soft-hyphen Cf char + a Cyrillic homoglyph).
    res.check(_anchor_found(f"## Improve them {A_IMP}"),
              "anchor: a HEADING lead-in is recognized (heading arm)")
    A_NORM = A_IMP.upper().replace("O", "О")             # casefold + Cyrillic-О (U+041E) homoglyph
    A_NORM = A_NORM.replace("ОRDER", "ОR­DER", 1)   # + a soft hyphen (Cf) inside "ORDER"
    res.check(g._norm(A_NORM) == g._norm(A_IMP),
              "anchor: the normalized lead-in variant folds to the plain anchor (fixture sanity)")
    res.check(_anchor_found(f"Improve them {A_NORM}:"),
              "anchor: a NORMALIZED paragraph lead-in (uppercase + Cf + homoglyph) is recognized (paragraph _norm)")
    res.check(_anchor_found(f"> Improve them {A_NORM}:"),
              "anchor: a NORMALIZED blockquote lead-in is recognized (container _norm)")

    # 3. Self-inclusion + live docs pass the CLI.
    grc = _load("grc_si", GATE_REVIEW_CHECK)
    pats = grc.load_gate_patterns(grc.GATE_PATHS_FILE)
    for p in ["generate-skill-enumerations.py", "skills-order"]:
        res.check(grc.matches_gate(p, pats), f"self-inclusion: {p} is gate-layer")
    p = subprocess.run([sys.executable, str(GEN), str(ROOT), "--check"], capture_output=True, text=True)
    tail = (p.stdout + p.stderr).strip().splitlines()
    res.check(p.returncode == 0, "live README + prompt pass generate-skill-enumerations.py --check",
              tail[-1] if tail else f"exit {p.returncode}")

def main() -> int:
    ap = argparse.ArgumentParser(description="Golden-fixture regression: the gates that guard the gates.")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print each verifier's resolved-values line / fixture findings")
    args = ap.parse_args()

    for needed in (SHARED_VERIFY, PROFILE, LRR, FAQ_GEN, UG_GEN, REVIEW_PLAYBOOK, GATE_REVIEW_CHECK,
                   GEN, PKGTOOLS, LINT_PLACEHOLDERS, GATE_RECORD, CONTRIB):
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
    doc_critic_mapping(res, args.verbose)
    print()
    gate_review_check(res, args.verbose)
    print()
    gate_review_seam(res, args.verbose)
    print()
    manifest_byte_stability(res, args.verbose)
    print()
    review_record_consistency(res, args.verbose)
    print()
    skill_enumerations(res, args.verbose)
    print()
    total = res.passed + res.failed
    print(f"--- golden: {res.passed}/{total} assertions passed, {res.failed} failed ---")
    return 1 if res.failed else 0


if __name__ == "__main__":
    sys.exit(main())
