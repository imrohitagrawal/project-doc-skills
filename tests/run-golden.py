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
        ("a co-committed BLOCK blocks even with a PASS", [("b.md", prose_block), ("g.md", good)], False, True),
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

    # 1. Renderers + validate_order + count phrases (incl. the bolded form the raw \w+ regex missed).
    res.check(g.render_improve_order(order) == "**alpha → beta → gamma.**", "render improve-order")
    res.check(g.render_pick_list(order) == "`alpha · beta · gamma`", "render pick-list")
    res.check(g.render_tree(order) == "```\nskills/\n├─ alpha/\n├─ beta/\n└─ gamma/\n```", "render tree")
    canon = {"alpha", "beta", "gamma"}
    res.check(g.validate_order(["alpha", "beta", "gamma"], canon) == [], "order: permutation ok")
    res.check(g.validate_order(["alpha", "beta"], canon) != [], "order: missing rejected")
    res.check(g.validate_order(["alpha", "alpha", "beta", "gamma"], canon) != [], "order: dup rejected")
    # check_count_phrases operates on per-unit RENDERED VISIBLE text (produced by _visible_units); the
    # render step is what makes a bold / code-span / hard-break count checkable. Test both halves.
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

    # CONTRACT (0010 + 0015): each phrase is (combined_pattern, label); the pattern binds the count slot to
    # a distinctive ADJACENT anchor. check_count_phrases counts the pattern's matches across ALL units:
    # exactly-one required, then value-exact. A bare fragment not adjacent to the anchor neither satisfies
    # nor trips. A synthetic pattern keeps the mechanism test independent of the live docs' wording.
    COMB = re.compile(rf"widget site has {g._COUNT} gadgets", re.IGNORECASE)
    one = [(COMB, "widget site has <N> gadgets")]
    res.check(g.check_count_phrases(["the widget site has three gadgets today", "unrelated noise"],
                                    one, 3, "x") == [], "count: exactly one correct combined match passes")
    res.check(len(g.check_count_phrases(["widget site has two gadgets"], one, 3, "x")) == 1,
              "count: wrong value at the combined match caught")
    res.check(any("expected exactly 1" in f for f in g.check_count_phrases(["nothing relevant here"],
              one, 3, "x")), "count: zero matches -> finding (reworded/stale, cannot be masked elsewhere)")
    res.check(any("expected exactly 1" in f for f in g.check_count_phrases(
        ["widget site has three gadgets", "a second widget site has three gadgets"], one, 3, "x")),
        "count: duplicated/relocated combined match (>1) -> finding")
    # THE FP/MASK LOCK (0015): the pattern requires the count NEXT TO its anchor, so a bare count fragment
    # elsewhere (wrong or right) is neither required nor flagged — closes both the same-unit mask and the
    # unrelated-prose false positive that a bare-template scan had.
    res.check(g.check_count_phrases(
        ["widget site has three gadgets", "the shed nearby has nine gadgets"], one, 3, "x") == [],
        "count: a bare fragment not adjacent to the anchor is ignored (mask + FP closed)")
    res.check(g.check_count_phrases(["anything"], [], 3, "x") != [],
              "count: an EMPTY phrase set is a finding (no vacuous success)")
    res.check(len(g.check_count_phrases(["widget site has twenty-one gadgets"], one, 3, "x")) == 1,
              "count: hyphenated multi-token value caught")
    md = g._md()
    res.check(all(any("suite of seven independent" in u for u in g._visible_units(md.parse(s))) for s in
                  ["suite of **seven** independent", "suite of `seven` independent",
                   "suite of ` seven ` independent", "suite of **seven**\\\nindependent"]),
              "_visible_units renders bold / code-span (padded) / backslash-hard-break count to visible")

    # 2. End-to-end on scratch copies of the REAL docs. Baseline clean; every CLAIMED guard bites.
    FULL = ("<!-- skills:improve-order:begin -->\n"
            "**learning-track → architecture-and-decisions → project-faq → usage-guide → "
            "operations-runbook → onboarding-companion → doc-critic → publish-mirror.**\n"
            "<!-- skills:improve-order:end -->")
    PUB = "| **publish-mirror** | publish step (no Diátaxis mode) | mirrors the source | — |"
    HDR = "| Skill | Diátaxis mode | Scope | Reading grade |"
    LT = "| **learning-track** | tutorial + explanation | public | ~9 |"
    # A NEAR-COMPLETE differently-formatted run (all 8 names, no bold, no trailing period) — a competing
    # ENUMERATION, as opposed to an incidental one/two-name mention. The competing/stray-name guards fire
    # only on a run this complete (gate-reviews/0013), so the decoy fixtures below use it.
    BROKEN_RUN = ("learning-track → architecture-and-decisions → project-faq → usage-guide → "
                  "operations-runbook → onboarding-companion → doc-critic → publish-mirror")

    def scratch(mutate):
        tmp = Path(tempfile.mkdtemp(prefix="genenum-"))
        for rel in ["README.md", "per-skill-review-prompt.md", "skills-order",
                    "generate-skill-enumerations.py"]:
            shutil.copy(ROOT / rel, tmp / rel)
        shutil.copytree(ROOT / "skills", tmp / "skills")
        if mutate:
            mutate(tmp)
        gg = _load("gg", tmp / "generate-skill-enumerations.py")
        f = gg.check(tmp)
        shutil.rmtree(tmp, ignore_errors=True)
        return f

    def repl(rel, a, b):
        return lambda t: (t / rel).write_text((t / rel).read_text(encoding="utf-8").replace(a, b),
                                              encoding="utf-8")

    res.check(scratch(None) == [], "real-docs scratch: baseline is clean", "; ".join(scratch(None)) or "clean")

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
            "A suite of eight independent", "A suite of <span>eight</span> independent")),
        ("raw-HTML ban: tagfilter <script> in a cell", repl("README.md", LT,
            '| <script data-x="publish-mirror">learning-track</script> | tutorial + explanation | public | ~9 |')),
        ("table header/other-column decoy (near-complete run in the header cell)", repl("README.md", HDR,
            "| Skill (canonical order: learning-track architecture-and-decisions project-faq usage-guide "
            "operations-runbook onboarding-companion doc-critic publish-mirror) | Diátaxis mode | Scope "
            "| Reading grade |")),
        ("bolded count phrase **seven**", repl("README.md", "A suite of eight independent",
            "A suite of **seven** independent")),
        ("code-span count `seven` (0008 GPT-3)", repl("README.md", "A suite of eight independent",
            "A suite of `seven` independent")),
        ("backslash hard-break count (0009 GPT-F2)", repl("README.md", "A suite of eight independent",
            "A suite of **seven**\\\nindependent")),
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
                 + "\n".join(f"| {i+1} | {nm} |" for i, nm in enumerate(
                     ["learning-track", "architecture-and-decisions", "project-faq", "usage-guide",
                      "operations-runbook", "onboarding-companion", "doc-critic", "publish-mirror"])) + "\n")),
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
        # 0010 BLOCKER (a regression I shipped): the PROMPT count phrase had no fixture, so a pattern
        # that could never match rendered text passed CI green. Both halves are now locked.
        ("prompt count phrase wrong value (0010 BLOCKER)",
            repl("per-skill-review-prompt.md", "now **eight** skills", "now **seven** skills")),
        ("prompt count phrase reworded away (presence-required)",
            repl("per-skill-review-prompt.md", "now **eight** skills", "reworded away entirely")),
        ("README count phrase reworded away (presence-required)",
            repl("README.md", "A suite of eight independent", "A collection of eight independent")),
        ("hyphenated count value (0010 GPT-MAJOR)",
            repl("README.md", "A suite of eight independent", "A suite of twenty-one independent")),
        # 0011 GPT-BLOCKER-2: a suffix rewording must not satisfy the phrase. Now caught by the noun
        # requirement (0013): "independently maintained ..." has no " skills" clause after "independent",
        # so PRESENCE-REQUIRED fires — the canonical "... skills" phrase is genuinely gone.
        ("suffix-reworded count phrase (whole-template, noun required)",
            repl("README.md", "A suite of eight independent",
                 "A suite of eight independently maintained")),
        # 0013: the NOUN of a count phrase must itself be whole-word bounded — a suffixed noun
        # ("... skillsets") must not satisfy "... skills". This isolates the _R right boundary (with it
        # relaxed, "skills" matches inside "skillsets" and the stale phrase passes value-exact).
        ("noun-suffixed count phrase (locks the _R right boundary on the noun)",
            repl("README.md", "A suite of eight independent Claude skills.",
                 "A suite of eight independent Claude skillsets.")),
        # …and a PREFIX evasion: "know eight skills" contains "now eight skills". Without the left
        # boundary that substring satisfies the phrase while the canonical sentence is gone.
        ("prefix-substring count evasion (locks the left boundary)",
            repl("per-skill-review-prompt.md", "now **eight** skills", "know eight skills")),
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
        # deliberately name-free: a decoy naming skills would be caught by _table_stray_names instead,
        # leaving the region grammar unproven (which is how it hid for eight rounds).
        ("in-region smuggle: stray paragraph inside the table region",
            repl("README.md", "<!-- skills:table:end -->",
                 "\nNote: an unrelated sentence smuggled inside the marked region.\n\n"
                 "<!-- skills:table:end -->")),
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
        # 0013 BLOCKER-1 (FALSE NEGATIVE): the count template stopped at "independent", so rewording the
        # sentence's NOUN away ("... independent reviewers.") kept the right number in a truncated match
        # and reported clean. Requiring the noun makes this trip presence-required.
        ("count phrase reworded, noun dropped (FN closed)",
            repl("README.md", "A suite of eight independent Claude skills.",
                 "A suite of eight independent reviewers.")),
        # the build-all phrase, now bound to its "+ emit" site, still value-checks its own occurrence.
        ("build-all count wrong value (bound to its + emit site)",
            repl("README.md", "build all eight + emit", "build all seven + emit")),
    ]
    for name, mut in cases:
        f = scratch(mut)
        res.check(len(f) >= 1, f"real-docs scratch: {name} -> caught",
                  (f[0][:66] if f else "NOT CAUGHT (clean!)"))

    # 0011 GPT-BLOCKER-1 (a NEGATIVE case — must stay CLEAN): ordinary prose that merely resembles a
    # count phrase must not be read as a count. An open "any word" slot captured "review"/"make" and
    # reported a wrong count; the number-only slot is what prevents that, so this locks it.
    benign = scratch(repl("README.md", "## Build",
                          "We can now review skills before publishing, and should not make copies of "
                          "the house style.\n\n## Build"))
    res.check(benign == [], "benign prose is NOT misread as a count phrase (locks the number-only slot)",
              "; ".join(benign)[:70] or "clean")

    # 0013 NEGATIVE cases — the false positives the round-9 review reproduced must now stay CLEAN. Each is
    # ordinary, legitimate content that the pre-fix over-broad guards flagged; the assertion is that the
    # doc is clean, so a future re-broadening of any of these guards turns it red.
    #  (a) FINDING #1 FP: an unrelated "build all <N>" in prose is not the quickstart build command.
    fp_build = scratch(lambda t: (t / "README.md").write_text(
        (t / "README.md").read_text(encoding="utf-8").rstrip()
        + "\n\nFor the quickstart, do not build all three sample containers.\n", encoding="utf-8"))
    res.check(fp_build == [], "ordinary 'build all three' prose is NOT read as the build-count phrase",
              "; ".join(fp_build)[:70] or "clean")
    #  (b) FINDING #3 FP: a two-skill handoff in prose is a legitimate cross-reference, not a competing
    #      enumeration (only a near-complete run is).
    fp_handoff = scratch(lambda t: (t / "README.md").write_text(
        (t / "README.md").read_text(encoding="utf-8").rstrip()
        + "\n\nFor this workflow, architecture-and-decisions → project-faq is the normal handoff.\n",
        encoding="utf-8"))
    res.check(fp_handoff == [], "two-skill handoff prose is NOT flagged as a competing enumeration",
              "; ".join(fp_handoff)[:70] or "clean")
    #  (c) FINDING #4 FP: a singleton skill reference in a non-first table column is a legitimate
    #      cross-reference, not a header/other-column decoy (only a near-complete run is).
    fp_cell = scratch(repl("README.md", LT,
        "| **learning-track** | tutorial + explanation; reviewed by doc-critic | public | ~9 |"))
    res.check(fp_cell == [], "singleton skill reference in a description cell is NOT flagged as a decoy",
              "; ".join(fp_cell)[:70] or "clean")

    # ============================ 0014 (round-10 GPT BLOCKERs) ============================
    # The round-10 review reproduced four class-level escapes that per-instance fixtures had not exercised.
    # These are DATA-DRIVEN over every site, so the class — not one instance — is locked.
    ORDER8 = ["learning-track", "architecture-and-decisions", "project-faq", "usage-guide",
              "operations-runbook", "onboarding-companion", "doc-critic", "publish-mirror"]

    # --- 0014 BLOCKER-2: count checks must be LOCATION-BOUND. For EACH of the five count sites: masking
    #     the real sentence (dropping its closed template) is CAUGHT; an unrelated sentence elsewhere that
    #     shares the template with a WRONG number stays CLEAN (no document-wide scan → no FP, no mask).
    #     (label, file, real_substring_to_break, replacement, unrelated_prose_appended)
    COUNT_SITES = [
        ("suite-count", "README.md", "A suite of eight independent Claude skills.",
         "A suite of eight independent reviewers evaluate the docs.",
         "Aside: a suite of nine independent Claude skills lives in some other repo."),
        ("copies-count", "README.md", "eight copies of the house style", "many copies of the house style",
         "Aside: keeping nine copies of the house style would be wasteful."),
        ("build-count", "README.md", "build all eight + emit dist/MANIFEST.sha256",
         "build all the skills and emit the manifest",
         "Aside: a fork might build all nine + emit dist/MANIFEST.sha256 instead."),
        ("N-skill-suite", "per-skill-review-prompt.md", "eight-skill documentation suite",
         "multi-skill documentation suite",
         "Aside: a nine-skill documentation suite is purely hypothetical."),
        ("now-N-skills", "per-skill-review-prompt.md", "now **eight** skills", "now a larger set of skills",
         "Aside: some roadmap says now nine skills, hypothetically."),
    ]
    def _append(fname, extra):
        return lambda t: (t / fname).write_text(
            (t / fname).read_text(encoding="utf-8").rstrip() + "\n\n" + extra + "\n", encoding="utf-8")
    for label, fname, old, new, unrelated in COUNT_SITES:
        caught = scratch(repl(fname, old, new))
        res.check(len(caught) >= 1, f"count site '{label}': masking the real sentence is CAUGHT",
                  (caught[0][:60] if caught else "NOT CAUGHT (clean!)"))
        clean = scratch(_append(fname, unrelated))
        res.check(clean == [], f"count site '{label}': unrelated prose sharing the template is NOT flagged",
                  "; ".join(clean)[:70] or "clean")
    # The BRIDGE bypass specifically (locks the CLOSED template): a sentence that keeps a `{0,3}`-word
    # path from "independent" to "skills" but counts something else ("independent reviewers evaluates
    # skills") must be CAUGHT — a wildcard-bridge template would have matched it and passed.
    bridge = scratch(repl("README.md", "A suite of eight independent Claude skills.",
                          "A suite of eight independent reviewers evaluates skills."))
    res.check(len(bridge) >= 1, "count: a wildcard-bridge rewording is CAUGHT (closed template)",
              (bridge[0][:60] if bridge else "NOT CAUGHT (clean!)"))

    # --- 0014 BLOCKER-3: anchors must be UNIQUE. For EACH of the five sites: CLONING the anchor next to a
    #     relocated block (original site left empty) is caught (uniqueness branch); RELOCATING the block
    #     away from its lead-in is caught (adjacency branch). Both isolate _anchor_missing (the moved block
    #     still matches its renderer; _competing skips the in-region run).
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
    def _clone_anchor(fname, anchor, bm):
        def m(t):
            pre, block, post = _cut_block((t / fname).read_text(encoding="utf-8"), bm)
            new = pre + "(block relocated to the appendix below)" + post
            new = new.rstrip() + f"\n\n## Appendix\n\nReminder — {anchor}:\n\n{block}\n"
            (t / fname).write_text(new, encoding="utf-8")
        return m
    def _relocate(fname, anchor, bm):
        def m(t):
            pre, block, post = _cut_block((t / fname).read_text(encoding="utf-8"), bm)
            new = pre + "(block relocated to the appendix below)" + post
            new = new.rstrip() + f"\n\n## Appendix: generated sequence\n\n{block}\n"
            (t / fname).write_text(new, encoding="utf-8")
        return m
    for site, fname, anchor, bm in ANCHOR_SITES:
        cloned = scratch(_clone_anchor(fname, anchor, bm))
        res.check(len(cloned) >= 1, f"anchor '{site}': cloning the anchor by a relocated block is CAUGHT",
                  (cloned[0][:60] if cloned else "NOT CAUGHT (clean!)"))
        moved = scratch(_relocate(fname, anchor, bm))
        res.check(len(moved) >= 1, f"anchor '{site}': relocating the block away from its lead-in is CAUGHT",
                  (moved[0][:60] if moved else "NOT CAUGHT (clean!)"))

    # --- 0014 BLOCKER-4a: a competing enumeration formatted as a NATIVE Markdown list (one name per item)
    #     must be AGGREGATED across items — no single item reaches threshold, so a per-token check misses it.
    stray_list = "\n".join(f"- {nm}" for nm in ORDER8)
    caught = scratch(repl("README.md", "## Build", "Restated order:\n\n" + stray_list + "\n\n## Build"))
    res.check(len(caught) >= 1, "stray native Markdown list of all skills is CAUGHT (list aggregation)",
              (caught[0][:60] if caught else "NOT CAUGHT (clean!)"))
    # a native list of TWO skills is a legitimate cross-reference, still CLEAN (below threshold).
    ok = scratch(repl("README.md", "## Build",
                      "See also:\n\n- learning-track\n- project-faq\n\n## Build"))
    res.check(ok == [], "a two-item skill list is NOT flagged (list aggregation respects the threshold)",
              "; ".join(ok)[:70] or "clean")

    # --- 0014 BLOCKER-4b: a competing enumeration written DOWN a non-first table column (one name per
    #     cell) must be AGGREGATED per column — no single cell reaches threshold.
    def _reverse_col2(t):
        import re as _re
        rev = list(reversed(ORDER8))
        lines = (t / "README.md").read_text(encoding="utf-8").split("\n")
        ri = 0
        for i, ln in enumerate(lines):
            m = _re.match(r"\| \*\*([a-z-]+)\*\* \| ([^|]*)\|(.*)", ln)
            if m and m.group(1) in ORDER8:
                lines[i] = f"| **{m.group(1)}** | {rev[ri]} |{m.group(3)}"
                ri += 1
        (t / "README.md").write_text("\n".join(lines), encoding="utf-8")
    caught = scratch(_reverse_col2)
    res.check(len(caught) >= 1, "reversed order written down table column 2 is CAUGHT (column aggregation)",
              (caught[0][:60] if caught else "NOT CAUGHT (clean!)"))

    # --- 0014: _competing_run boundaries — look-alike names that merely CONTAIN a skill name as a
    #     substring ("project-faq-notes") are NOT the skills, so a full run of look-alikes stays CLEAN.
    suffixed = "\n".join(f"- {nm}-notes" for nm in ORDER8)
    ok = scratch(repl("README.md", "## Build", "Unrelated notes index:\n\n" + suffixed + "\n\n## Build"))
    res.check(ok == [], "suffix look-alikes ('name-notes') are NOT a competing run (locks the _R boundary)",
              "; ".join(ok)[:70] or "clean")
    prefixed = "\n".join(f"- draft-{nm}" for nm in ORDER8)
    ok = scratch(repl("README.md", "## Build", "Unrelated drafts index:\n\n" + prefixed + "\n\n## Build"))
    res.check(ok == [], "prefix look-alikes ('draft-name') are NOT a competing run (locks the _L boundary)",
              "; ".join(ok)[:70] or "clean")

    # ============================ 0015 (round-11 GPT BLOCKERs) ============================
    def _app(fname, extra):
        return lambda t: (t / fname).write_text(
            (t / fname).read_text(encoding="utf-8").rstrip() + "\n\n" + extra + "\n", encoding="utf-8")

    # --- 0015 BLOCKER-1: count checks bind the count to its ADJACENT anchor. Rewording the site's count
    #     so NO count sits next to the anchor -> zero matches -> CAUGHT, for EACH of the five sites. (A
    #     decoy placed ADJACENT to the anchor is a valid canonical restatement, not a mask — see the
    #     exactly-one duplicate case below; a bare count FAR from the anchor cannot rescue it — see next.)
    MASK_SITES = [
        ("suite", "README.md", "A suite of eight independent Claude skills.",
         "A suite of eight independent reviewers evaluate the docs."),
        ("copies", "README.md", "eight copies of the house style", "many copies of the house style"),
        ("build", "README.md", "build all eight + emit dist/MANIFEST.sha256",
         "build every skill and emit the manifest"),
        ("n-skill", "per-skill-review-prompt.md", "eight-skill documentation suite",
         "multi-skill documentation suite"),
        ("now-n", "per-skill-review-prompt.md", "now **eight** skills", "now a larger set of skills"),
    ]
    for label, fname, old, new in MASK_SITES:
        caught = scratch(repl(fname, old, new))
        res.check(len(caught) >= 1, f"count site '{label}': rewording the count away from its anchor -> CAUGHT",
                  (caught[0][:60] if caught else "NOT CAUGHT (clean!)"))
    # reword the site's count AND append a BARE correct-count fragment FAR from any anchor -> still CAUGHT
    # (the far fragment is not adjacent to the anchor, so it cannot mask the drift — the BLOCKER-1 escape).
    masked = scratch(lambda t: (t / "README.md").write_text(
        (t / "README.md").read_text(encoding="utf-8")
        .replace("A suite of eight independent Claude skills.", "A suite of eight independent reviewers.")
        .rstrip() + "\n\nElsewhere: a suite of eight independent Claude skills, unrelated.\n", encoding="utf-8"))
    res.check(len(masked) >= 1, "count: reword site + a bare decoy FAR from the anchor is still CAUGHT",
              (masked[0][:60] if masked else "NOT CAUGHT (clean!)"))
    # duplicating the FULL canonical count sentence (count + anchor) -> >1 match -> CAUGHT (exactly-one).
    dup = scratch(_app("README.md",
        "Note: a suite of nine independent Claude skills. Six turn a software project into documentation."))
    res.check(len(dup) >= 1, "count: a duplicated/relocated full canonical sentence (>1 match) is CAUGHT",
              (dup[0][:60] if dup else "NOT CAUGHT (clean!)"))
    # same-unit WRONG count that is NOT adjacent to the anchor -> NOT flagged (FP closed).
    fp = scratch(repl("README.md", "each in a distinct Diátaxis mode",
        "each in a distinct Diátaxis mode (unlike a suite of nine independent Claude skills)"))
    res.check(fp == [], "count: a same-unit wrong count not adjacent to the anchor is NOT flagged (FP)",
              "; ".join(fp)[:70] or "clean")
    # a legit rewording that WIDENS the gap within tolerance stays CLEAN (the gap window is generous
    # enough for ordinary editing — "Six of them turn ..." rather than "Six turn ...").
    widegap = scratch(repl("README.md", "skills. Six turn a software project",
                           "skills. Six of them turn a software project"))
    res.check(widegap == [], "count: a legit wider-gap rewording (correct count) stays CLEAN",
              "; ".join(widegap)[:70] or "clean")

    # --- 0015 BLOCKER-2: _anchor_occurrences counts textual matches across ALL visible units, INCLUDING
    #     fences. For EACH site: a fenced copy of the anchor makes it non-unique -> CAUGHT (an inline-only
    #     count would miss the fenced copy and pass).
    for site, fname, anchor, bm in ANCHOR_SITES:
        fenced = scratch(_app(fname, "```\n" + anchor + "\n```"))
        res.check(len(fenced) >= 1, f"anchor '{site}': a fenced copy of the anchor is counted -> CAUGHT",
                  (fenced[0][:60] if fenced else "NOT CAUGHT (clean!)"))
    # the full escape for improve-order: lead-in hidden in a fence at the abandoned site + a plain clone
    # beside the relocated block. Both copies are reader-visible; occ==2 -> CAUGHT.
    def _fenced_reloc(t):
        pre, block, post = _cut_block((t / "README.md").read_text(encoding="utf-8"),
                                      "<!-- skills:improve-order:begin -->")
        lead = "Improve a skill in its own focused session, in this order (producers before consumers):"
        pre2 = pre.replace(lead, "```\n" + lead + "\n```")
        new = pre2.rstrip() + "\n\n(block moved to appendix)" + post
        new = new.rstrip() + f"\n\n## Appendix\n\nReminder: {lead}\n\n{block}\n"
        (t / "README.md").write_text(new, encoding="utf-8")
    res.check(len(scratch(_fenced_reloc)) >= 1,
              "anchor: fenced lead-in at abandoned site + plain clone beside relocated block -> CAUGHT")
    # a lead-in SPLIT across a paragraph break (so a per-unit anchor count would miss it) at the abandoned
    # site, with a clean anchor copy beside the relocated block -> CAUGHT (anchor counted over joined text).
    def _split_reloc(t):
        lead = "Improve a skill in its own focused session, in this order (producers before consumers):"
        pre, block, post = _cut_block((t / "README.md").read_text(encoding="utf-8"),
                                      "<!-- skills:improve-order:begin -->")
        pre2 = pre.replace(lead, "Improve a skill in its own focused session, in this order\n\n"
                                 "(producers before consumers):")
        new = pre2.rstrip() + "\n\n**learning-track → project-faq → doc-critic.**" + post
        new = new.rstrip() + f"\n\n## Appendix\n\n{lead}\n\n{block}\n"
        (t / "README.md").write_text(new, encoding="utf-8")
    res.check(len(scratch(_split_reloc)) >= 1,
              "anchor: lead-in SPLIT across a paragraph break + clone beside relocated block -> CAUGHT")

    # --- 0015 BLOCKER-3: competing enumerations in ANY shape outside the marked blocks, no separator.
    #     (A run split across SEPARATE containers so no one is near-complete is a DISCLOSED residual —
    #     aggregating across unrelated containers would FP on legit prose; the negative below locks that.)
    ROUTES = [
        ("comma paragraph", "README.md", "The full order: " + ", ".join(ORDER8) + "."),
        ("separator-free fence", "README.md", "```\n" + "\n".join(ORDER8) + "\n```"),
        ("ordered list", "README.md", "\n".join(f"{i+1}. {nm}" for i, nm in enumerate(ORDER8))),
        ("fenced name per list item (one list)", "README.md",
         "\n".join(f"- see\n  ```\n  {nm}\n  ```" for nm in ORDER8)),
        ("comma paragraph in the PROMPT", "per-skill-review-prompt.md", "Order: " + ", ".join(ORDER8) + "."),
    ]
    for label, fname, extra in ROUTES:
        caught = scratch(_app(fname, extra))
        res.check(len(caught) >= 1, f"competing route '{label}' is CAUGHT",
                  (caught[0][:60] if caught else "NOT CAUGHT (clean!)"))
    # FP-SAFETY (the reason aggregation is PER container, not whole-document): legitimate prose that names
    # several skills across SEPARATE lists — the shape a red-team pass flagged as a false positive under
    # whole-file list aggregation — must stay CLEAN.
    legit = scratch(_app("README.md",
        "## Documentation types\n\n- Tutorials come from `learning-track`\n"
        "- Explanations from `architecture-and-decisions`\n- Reference from `project-faq`\n"
        "- How-tos from `usage-guide`\n\nSome prose about the process.\n\n## More types\n\n"
        "- Runbooks from `operations-runbook`\n- Onboarding from `onboarding-companion`\n"
        "- Review from `doc-critic`\n- Publishing from `publish-mirror`"))
    res.check(legit == [], "legit prose naming skills across SEPARATE lists is NOT flagged (per-container)",
              "; ".join(legit)[:70] or "clean")

    # --- 0015 BLOCKER-3 tables: split across non-first columns (diagonal) and across header cells.
    def _split_cols(t):
        import re as _re
        lines = (t / "README.md").read_text(encoding="utf-8").split("\n"); ri = 0
        for i, ln in enumerate(lines):
            m = _re.match(r"\| \*\*([a-z-]+)\*\* \| ([^|]*)\| ([^|]*)\|(.*)", ln)
            if m and m.group(1) in ORDER8:
                c2 = ORDER8[ri] if ri < 4 else m.group(2).strip()
                c3 = ORDER8[ri] if ri >= 4 else m.group(3).strip()
                lines[i] = f"| **{m.group(1)}** | {c2} | {c3} |{m.group(4)}"; ri += 1
        (t / "README.md").write_text("\n".join(lines), encoding="utf-8")
    res.check(len(scratch(_split_cols)) >= 1,
              "table: run split diagonally across cols 2 & 3 (each < threshold) is CAUGHT (blob)")
    def _split_header(t):
        hdr = "| Skill | Diátaxis mode | Scope | Reading grade |"
        new_hdr = ("| Skill (learning-track architecture-and-decisions) | Diátaxis (project-faq usage-guide) "
                   "| Scope (operations-runbook onboarding-companion) | Grade (doc-critic publish-mirror) |")
        (t / "README.md").write_text((t / "README.md").read_text(encoding="utf-8").replace(hdr, new_hdr),
                                     encoding="utf-8")
    res.check(len(scratch(_split_header)) >= 1,
              "table: run split 2-per-cell across the header (each cell < threshold) is CAUGHT (blob)")
    # a genuine 2-row reference table is NOT a competing table (MAJOR-8) -> CLEAN.
    ref = scratch(_app("README.md", "| Skill | Note |\n|---|---|\n| learning-track | a |\n| doc-critic | b |"))
    res.check(ref == [], "a 2-row reference table is NOT flagged as competing (MAJOR-8)",
              "; ".join(ref)[:70] or "clean")

    # --- 0015 BLOCKER-4: a missing skills-order fails closed via load_order's own message.
    no_order = scratch(lambda t: (t / "skills-order").unlink())
    res.check(any("skills-order not found" in f for f in no_order),
              "missing skills-order -> load_order fails closed with its own message",
              (no_order[0][:60] if no_order else "clean!"))

    # --- 0015 MAJOR-5 (a NEGATIVE that stays clean AND underpins the REDUNDANT number-only slot): benign
    #     prose INSIDE the anchored blockquote is not read as a count, because the combined pattern requires
    #     the count next to "The suite is now". This is clean under the number-only slot AND under a broad
    #     slot (the revert-battery declares that redundancy, verified by this fixture staying clean).
    benign_inline = scratch(repl("per-skill-review-prompt.md", "The suite is now **eight** skills:",
        "The suite is now **eight** skills (we now review skills before every release):"))
    res.check(benign_inline == [], "benign 'now review skills' INSIDE the anchored blockquote stays clean",
              "; ".join(benign_inline)[:70] or "clean")

    # 0011 MINOR-2: a missing governed doc must fail the COUNT loop locally (its own message), not merely
    # be caught as a side effect of the site loop — otherwise the fail-closed property is emergent, and a
    # future refactor could decouple the loops and reopen a silent skip.
    missing = scratch(lambda t: (t / "per-skill-review-prompt.md").unlink())
    res.check(any("count phrases cannot be verified" in f for f in missing),
              "missing governed doc -> the count loop fails closed with its own message",
              (missing[0][:60] if missing else "clean!"))

    # empty source fails closed via check()'s OWN guard (0008 F5: isolate — assert the specific message,
    # not just "a finding", since validate_order would also reject an empty set).
    empty = scratch(lambda t: (shutil.rmtree(t / "skills"), (t / "skills").mkdir()))
    res.check(any("no skills found" in x for x in empty),
              "empty skills/ -> check() fails closed with its own message (isolated)",
              (empty[0][:60] if empty else "clean!"))

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
                   GEN, PKGTOOLS, LINT_PLACEHOLDERS):
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
    skill_enumerations(res, args.verbose)
    print()
    total = res.passed + res.failed
    print(f"--- golden: {res.passed}/{total} assertions passed, {res.failed} failed ---")
    return 1 if res.failed else 0


if __name__ == "__main__":
    sys.exit(main())
