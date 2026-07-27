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
    """Lock the generate-don't-lint enumeration gate. Each enumeration is GENERATED from skills-order and
    checked at a FAIL-CLOSED marked location. The headline regressions are the THREE attacks a
    different-vendor (GPT) gate-review reproduced against the first (substring-marker) implementation and
    that the hardened marker model must now reject: (1) a marker embedded in a spanning HTML comment,
    (2) a marker duplicated on one line, (3) a table decoy row hidden in an HTML comment; plus relocation
    of a correct block away from its anchor. Synthetic inputs + a scratch copy of the REAL docs.
    """
    print("skill-enumerations — generated, exact-marked, anchored (no parse, no decoy class):")
    import shutil
    g = _load("genenum", GEN)
    order = ["alpha", "beta", "gamma"]
    canon = {"alpha", "beta", "gamma"}
    IO_ANCHOR = "in this order (producers before consumers):"   # improve-order anchor line

    # 1. Renderers emit the exact documented bytes (the three pure sites).
    res.check(g.render_improve_order(order) == "**alpha → beta → gamma.**", "render improve-order")
    res.check(g.render_pick_list(order) == "`alpha · beta · gamma`", "render pick-list")
    res.check(g.render_tree(order) == "```\nskills/\n├─ alpha/\n├─ beta/\n└─ gamma/\n```",
              "render tree (own fenced block; └─ on last)", repr(g.render_tree(order)))

    # 2. Marker extraction happy path (anchored, exact self-closing marker).
    doc = (f"{IO_ANCHOR}\n<!-- skills:improve-order:begin -->\n**alpha → beta → gamma.**\n"
           "<!-- skills:improve-order:end -->\n")
    res.check(g.extract_marked_block(doc, "improve-order") == "**alpha → beta → gamma.**",
              "extract_marked_block returns the inner bytes")
    res.check(g.extract_marked_block(doc, "improve-order") == g.render_improve_order(order),
              "pure site: correct block is byte-identical")
    dropped = doc.replace("**alpha → beta → gamma.**", "**alpha → beta.**")
    res.check(g.extract_marked_block(dropped, "improve-order") != g.render_improve_order(order),
              "pure site: a dropped skill fails byte-identical")

    def raises_marker(text, site):
        try:
            g.extract_marked_block(text, site)
            return False
        except g.MarkerError:
            return True

    # 3. REAL-INCIDENT REGRESSIONS — the three attacks the GPT gate-review reproduced (0005). Each MUST
    #    now fail closed / not pass.
    # 3a. Marker embedded in a spanning HTML comment (hides canonical, visible list broken).
    a_span = (f"{IO_ANCHOR}\n<!-- skills:improve-order:begin\n**alpha → beta → gamma.**\n"
              "skills:improve-order:end -->\n**alpha → beta.**\n")
    res.check(raises_marker(a_span, "improve-order"),
              "0005 ATTACK 1: spanning-comment marker -> MarkerError (not a hidden decoy)")
    # 3b. Marker token duplicated on one line (line-count would say 'one'; token-count says two).
    a_dup = (f"{IO_ANCHOR}\n<!-- skills:improve-order:begin skills:improve-order:begin\n"
             "**alpha → beta → gamma.**\nskills:improve-order:end skills:improve-order:end -->\n")
    res.check(raises_marker(a_dup, "improve-order"),
              "0005 ATTACK 2: duplicate token on one line -> MarkerError")
    # 3c. Table decoy rows hidden in an HTML comment + broken visible rows (backtick-wrapped, unmatched).
    a_tbl = ("| Skill | Diátaxis mode | Scope | Reading grade |\n"
             "<!-- skills:table:begin -->\n<!--\n| alpha | h |\n| beta | h |\n| gamma | h |\n-->\n"
             "| `gamma` | wrong |\n| `bogus` | missing |\n<!-- skills:table:end -->\n")
    names_tbl = g.extract_table_names(g.extract_marked_block(a_tbl, "table"))
    res.check(names_tbl != order,
              "0005 ATTACK 3: table decoy rows hidden in a comment do not pass",
              f"rendered names={names_tbl} (hidden comment rows stripped; broken visible rows read)")
    # 3d. Relocation — a correct marked block moved away from its anchor, broken un-marked list at anchor.
    a_reloc = (f"{IO_ANCHOR}\n**alpha → beta.**\n\n## Appendix\n<!-- skills:improve-order:begin -->\n"
               "**alpha → beta → gamma.**\n<!-- skills:improve-order:end -->\n")
    res.check(raises_marker(a_reloc, "improve-order"),
              "0005 relocation: correct block far from its anchor -> MarkerError")

    # 4. Marker integrity (fail closed): absent, end-before-begin, and a duplicate proper marker pair.
    res.check(raises_marker(f"{IO_ANCHOR}\nno markers here\n", "improve-order"),
              "fail-closed: absent markers -> MarkerError")
    res.check(raises_marker(f"{IO_ANCHOR}\n<!-- skills:improve-order:end -->\nx\n"
                            "<!-- skills:improve-order:begin -->\n", "improve-order"),
              "fail-closed: end before begin -> MarkerError")
    res.check(raises_marker(f"{IO_ANCHOR}\n<!-- skills:improve-order:begin -->\nx\n"
                            "<!-- skills:improve-order:end -->\n<!-- skills:improve-order:begin -->\n"
                            "y\n<!-- skills:improve-order:end -->\n", "improve-order"),
              "fail-closed: duplicated proper marker pair -> MarkerError")

    # 5. Anchoring: the anchor must appear exactly once, and the block must sit within MARKER_GAP of it.
    two_anchor = (f"{IO_ANCHOR}\n{IO_ANCHOR}\n<!-- skills:improve-order:begin -->\n"
                  "**alpha → beta → gamma.**\n<!-- skills:improve-order:end -->\n")
    res.check(raises_marker(two_anchor, "improve-order"),
              "anchor: a duplicated section anchor -> MarkerError")
    no_anchor = ("nothing relevant here\n<!-- skills:improve-order:begin -->\n"
                 "**alpha → beta → gamma.**\n<!-- skills:improve-order:end -->\n")
    res.check(raises_marker(no_anchor, "improve-order"),
              "anchor: a missing section anchor -> MarkerError")

    # 6. skills-order permutation validation (fail closed).
    res.check(g.validate_order(["alpha", "beta", "gamma"], canon) == [], "order: exact permutation ok")
    res.check(g.validate_order(["alpha", "beta"], canon) != [], "order: missing skill rejected")
    res.check(g.validate_order(["alpha", "beta", "gamma", "delta"], canon) != [],
              "order: extra/unknown name rejected")
    res.check(g.validate_order(["alpha", "alpha", "beta", "gamma"], canon) != [],
              "order: duplicate line rejected")

    # 7. Table name extraction: rendered rows only, whole first cell, comment rows stripped.
    ok_tbl = "| **alpha** | x |\n| **beta** | x |\n| **gamma** | x |\n"
    res.check(g.extract_table_names(ok_tbl) == order, "table: bold rendered rows -> exact names")
    res.check(g.extract_table_names("| alpha | a |\n| beta | b |\n| gamma | c |\n") == order,
              "table: un-bolded rendered rows -> exact names")
    res.check(g.extract_table_names("<!--\n| alpha | h |\n-->\n| **beta** | x |\n") != order,
              "table: a commented decoy row is stripped, not read")
    res.check(g.extract_table_names("| alpha/NOT-THE-NAME | x |\n") != order,
              "table: a non-exact first cell is poisoned (not truncated to 'alpha')")
    res.check(g.extract_table_names("| **beta** | x |\n| **alpha** | x |\n| **gamma** | x |\n") != order,
              "table: a reorder fails the ordered check")

    # 8. Scalar count phrases (carried over): correct passes, wrong caught word+digit.
    good = g.check_count_phrases("a suite of three independent skills", g.README_COUNT_PHRASES, 3, "x")
    bw = g.check_count_phrases("a suite of two independent skills", g.README_COUNT_PHRASES, 3, "x")
    bd = g.check_count_phrases("a suite of 2 independent skills", g.README_COUNT_PHRASES, 3, "x")
    res.check(not good and len(bw) == 1 and len(bd) == 1,
              "count phrase: correct passes, wrong caught (word + digit)")

    # 9. End-to-end on a SCRATCH COPY of the REAL docs: write is idempotent, --check clean, a hand-drop
    #    in a generated block is caught.
    tmp = Path(tempfile.mkdtemp(prefix="genenum-"))
    for rel in ["README.md", "per-skill-review-prompt.md", "skills-order",
                "generate-skill-enumerations.py"]:
        shutil.copy(ROOT / rel, tmp / rel)
    shutil.copytree(ROOT / "skills", tmp / "skills")
    g2 = _load("genenum2", tmp / "generate-skill-enumerations.py")
    g2.write(tmp)
    res.check(g2.check(tmp) == [], "real-docs scratch: write then --check is clean",
              "; ".join(g2.check(tmp)) or "clean")
    rd = (tmp / "README.md").read_text(encoding="utf-8")
    real_order = [ln.strip() for ln in (ROOT / "skills-order").read_text().splitlines()
                  if ln.strip() and not ln.strip().startswith("#")]
    (tmp / "README.md").write_text(
        rd.replace(f"→ {real_order[-1]}.**", ".**"), encoding="utf-8")   # drop last skill from improve-order
    res.check(g2.check(tmp) != [], "real-docs scratch: a hand-drop in a generated block is caught")
    shutil.rmtree(tmp, ignore_errors=True)

    # 10. Self-inclusion: the new gate check + its source of truth are gate-layer.
    grc = _load("grc_si", GATE_REVIEW_CHECK)
    pats = grc.load_gate_patterns(grc.GATE_PATHS_FILE)
    for p in ["generate-skill-enumerations.py", "skills-order"]:
        res.check(grc.matches_gate(p, pats), f"self-inclusion: {p} is gate-layer")

    # 11. LIVE docs: the real README + prompt pass --check via the CLI (proves the migration).
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
