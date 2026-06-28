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
         coverage-vs-advertising, self-description-drift, fixture-requirement) PLUS a
         Findings section — five required headings in total,
       - the replay section carries a real 'Coverage: N/M' fraction (M>0, N<=M) — the
         evidence the failure was reproduced and measured, not a date or a stray mention,
       - the Findings section carries file:line anchors, or an explicit 'none' (evidence, not
         a bare heading over a PASS line),
       - its EFFECTIVE (last) 'Verdict:' line is exactly PASS.
     PROPORTIONALITY: a declared 'Tier: light' verdict may use 'Coverage: N/A' with a 'Light-path
     justification:' line instead of a fraction — but ONLY when every changed gate path is docs-only
     ('*.md'); a code/config gate change (*.py/*.sh/*.yml/.github/gate-paths) refuses the light path
     and demands the full review. Tier defaults to 'full' (and a mixed full+light resolves to full),
     so the lighter bar is never granted by omission or by a stray later 'Tier: light' line.
     A record that is malformed, whose effective verdict is BLOCK/FAIL, or that only quotes
     'PASS' in prose, FAILS this check. A co-committed BLOCK record blocks even if a PASS
     record is also present (a blocking review is not overridden by adding a passing one).

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
from typing import NoReturn

ROOT = Path(__file__).resolve().parent
GATE_PATHS_FILE = ROOT / ".github" / "gate-paths"
VERDICT_DIR = "gate-reviews"
# Files under gate-reviews/ that are scaffolding, not a verdict for a specific PR.
VERDICT_NON_RECORDS = {"TEMPLATE.md", "README.md"}

# A verdict's required shape. Each is a low-false-positive structural marker; together
# they require the reviewer to have produced EVIDENCE, so a one-line rubber stamp fails.
PROMPT_VERSION_RE = re.compile(r"gate-review-prompt\.md\s+v\d+\.\d+\.\d+", re.IGNORECASE)
# A "Coverage: N/M" line: the literal word, then ':'/'=', then the fraction — so a date ("6/29") or a
# passing prose mention ("we discussed coverage on 6/29") does NOT satisfy it. It is searched only
# WITHIN the replay section (see shape_problems), and N<=M with M>0 is enforced there.
# NB: every line-anchored field below tolerates an optional Markdown bullet ('- '/'* '), because the
# verdict template writes these as list items ('- Tier: ...', '- Light-path justification: ...').
# Missing that silently dropped the template's OWN light path (a different-vendor review caught it).
COVERAGE_LINE_RE = re.compile(r"^\s*[-*]?\s*coverage\s*[:=]\s*\(?\s*(\d+)\s*/\s*(\d+)",
                              re.IGNORECASE | re.MULTILINE)
# The EFFECTIVE verdict is the LAST "Verdict: <token>" line, so a PASS quoted in prose mid-document
# cannot satisfy a record whose actual conclusion is BLOCK. The token must be exactly PASS/BLOCK/FAIL.
VERDICT_LINE_RE = re.compile(r"^\s*[-*]?\s*verdict:\s*([A-Za-z][A-Za-z-]*)", re.IGNORECASE | re.MULTILINE)
ANY_HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)
# The four mandated lens sections PLUS a Findings section — five required headings in total. Matched at
# TOP level only ('#'/'##'), so a '###' decoy subsection carrying a trigger word cannot hijack the
# section anchor (e.g. a "### Prior findings recap" must not stand in for the real "## Findings").
REQUIRED_SECTIONS = {
    "replay-the-real-failure": re.compile(r"^#{1,2}\s.*replay", re.IGNORECASE | re.MULTILINE),
    "coverage-vs-advertising": re.compile(r"^#{1,2}\s.*coverage\s+vs", re.IGNORECASE | re.MULTILINE),
    "self-description-drift": re.compile(r"^#{1,2}\s.*self-description", re.IGNORECASE | re.MULTILINE),
    "fixture-requirement": re.compile(r"^#{1,2}\s.*fixture", re.IGNORECASE | re.MULTILINE),
    "findings": re.compile(r"^#{1,2}\s.*findings", re.IGNORECASE | re.MULTILINE),
}
# Proportionality: the review TIER scales the evidence to the change. 'full' (the default — never
# granted by omission) needs a real coverage fraction; 'light' is allowed ONLY for a declared
# non-behavioral change and must carry an explicit justification in place of a fraction.
TIER_LINE_RE = re.compile(r"^\s*[-*]?\s*tier:\s*(light|full)\b", re.IGNORECASE | re.MULTILINE)
COVERAGE_NA_RE = re.compile(r"^\s*[-*]?\s*coverage\s*[:=]\s*n/?a\b", re.IGNORECASE | re.MULTILINE)
JUSTIFICATION_RE = re.compile(r"^\s*[-*]?\s*light-path justification:\s*\S", re.IGNORECASE | re.MULTILINE)
# Evidence, not a stamp: the Findings section must carry a real path anchor (file:line — a token with a
# '/' or a '.ext' of 2-8 letters before ':N'), or an explicit 'none' on its own leading line. The path
# requirement rejects a clock time ('2:30'), a bare port, or a version ('x.y:1') masquerading as proof.
FINDING_ANCHOR_RE = re.compile(r"(?=[\w./-]*(?:/|\.[A-Za-z]{2,8}))[\w./-]+:\d+")
FINDINGS_NONE_RE = re.compile(r"^\s*[-*]?\s*(none|no findings)\b", re.IGNORECASE | re.MULTILINE)
# Unfilled verdict-template placeholders: their presence means the reviewer copied the template without
# filling the provenance, so the record proves nothing about THIS PR. Rejected (catches the lazy
# rubber-stamp — a template copy with only the Verdict line changed). A determined fabrication that
# fills them is the irreducible good-faith residual, stated plainly in CONTRIBUTING's honest ceiling.
PLACEHOLDER_DENY = ("[pr_ref]", "[base..head]", "[changed_gate_paths]")


def die(msg: str, code: int = 2) -> NoReturn:
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
    if base == head:
        die(f"--base equals --head ({base}); cannot compute a PR diff — failing closed.")
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


def _section_text(text: str, heading_re: re.Pattern[str]) -> str:
    """The body of the section whose heading matches heading_re, up to the next heading (or EOF)."""
    m = heading_re.search(text)
    if not m:
        return ""
    nxt = ANY_HEADING_RE.search(text, m.end())
    return text[m.end(): nxt.start()] if nxt else text[m.end():]


def effective_verdict(text: str) -> str | None:
    """The LAST 'Verdict: <token>' in the file, upper-cased (the effective conclusion), or None.
    Using the last line means a PASS quoted in prose cannot override a real BLOCK conclusion."""
    matches = VERDICT_LINE_RE.findall(text)
    return matches[-1].upper() if matches else None


def effective_tier(text: str) -> str:
    """The review tier — 'full' (default) or 'light'. Light only when light is the SOLE declared tier:
    absence defaults to full, and a mix of 'full' and 'light' lines resolves to full (the safe choice),
    so a stray later 'Tier: light' cannot silently downgrade a verdict the template pre-fills as full."""
    tiers = {t.lower() for t in TIER_LINE_RE.findall(text)}
    return "light" if tiers == {"light"} else "full"


def shape_problems(text: str, allow_light: bool = True) -> list[str]:
    """Structural/evidence problems with a verdict record (independent of the verdict VALUE).
    Empty list == the record carries the required evidence shape. allow_light is False when the change
    touches gate-layer code/config, in which case the light path is refused (the machine cross-check
    that 'Tier: light' cannot wave a behavioral change through with no coverage)."""
    problems: list[str] = []
    if not PROMPT_VERSION_RE.search(text):
        problems.append("does not name the gate-review-prompt.md version it ran "
                        "(expected e.g. 'gate-review-prompt.md v1.0.0')")
    left = [p for p in PLACEHOLDER_DENY if p in text]
    if left:
        problems.append(f"unfilled template placeholder(s) {', '.join(left)} — fill the provenance "
                        f"(PR, diff range, changed gate paths); a copied-but-unfilled template proves "
                        f"nothing about this PR")
    for name, rx in REQUIRED_SECTIONS.items():
        if not rx.search(text):
            problems.append(f"missing the '{name}' section")
    # The coverage figure must be a real fraction on a 'Coverage:' line INSIDE the replay section, so a
    # date or a passing mention elsewhere cannot stand in as 'evidence the real failure was replayed'.
    # Proportionality: a declared 'Tier: light' (non-behavioral change) may use 'Coverage: N/A' instead,
    # but only when the change is docs-only (allow_light) and it carries a 'Light-path justification:'.
    tier = effective_tier(text)
    if tier == "light" and not allow_light:
        problems.append("a 'Tier: light' verdict is not permitted here: this change touches gate-layer "
                        "code/config — only a docs-only ('*.md') gate change may use the light path. "
                        "Run the full review with a real 'Coverage: N/M'.")
    light_ok = tier == "light" and allow_light
    replay = _section_text(text, REQUIRED_SECTIONS["replay-the-real-failure"])
    cm = COVERAGE_LINE_RE.search(replay)
    if cm:
        n, m = int(cm.group(1)), int(cm.group(2))
        if m == 0 or n > m:
            problems.append(f"coverage figure {n}/{m} is not a real fraction (need M>0 and N<=M)")
    elif light_ok and COVERAGE_NA_RE.search(replay):
        if not JUSTIFICATION_RE.search(text):
            problems.append("a 'Tier: light' verdict needs a 'Light-path justification:' line stating "
                            "why the change is non-behavioral (no change to any check's logic, the "
                            "gated set, a count/threshold, or the policy's meaning)")
    else:
        problems.append("no 'Coverage: N/M' line in the replay section (a real fraction proving the "
                        "real failure was replayed; or, for a docs-only non-behavioral change, "
                        "'Tier: light' + 'Coverage: N/A' + a 'Light-path justification:' line)")
    # Evidence, not a stamp: the Findings section must carry file:line anchors, or an explicit 'none' —
    # a bare heading over a PASS line is not a review. The section may use '###' subsections, so scan
    # from its heading to the next TOP-LEVEL ('#'/'##') heading (not any heading) or EOF.
    fh = REQUIRED_SECTIONS["findings"].search(text)
    findings = ""
    if fh:
        rest = text[fh.end():]
        stop = re.search(r"^#{1,2}\s", rest, re.MULTILINE)
        findings = rest[: stop.start()] if stop else rest
    if not (FINDING_ANCHOR_RE.search(findings) or FINDINGS_NONE_RE.search(findings)):
        problems.append("the Findings section carries no evidence (need file:line findings, or an "
                        "explicit 'none' if the review genuinely found nothing)")
    return problems


def decide_verdicts(records: list[tuple[str, str]], allow_light: bool = True) -> tuple[bool, list[str]]:
    """Pure decision over (name, text) verdict records. Returns (ok, message_lines).

    Fail-safe rules: a BLOCK/FAIL record blocks even if a PASS also exists (a blocking review is not
    overridden by adding a passing one); a malformed record blocks; the gate clears only if at least
    one record is a well-formed PASS and none is BLOCK/FAIL. allow_light=False forbids the light path
    (passed through to shape_problems). Pure (no disk/network) so it is unit-tested in run-golden.py."""
    if not records:
        return False, ["No gate-reviews/ verdict was added/modified in this PR."]

    msgs: list[str] = []
    passing: list[str] = []
    blocking = False
    for name, text in records:
        probs = shape_problems(text, allow_light)
        verdict = effective_verdict(text)
        if verdict in {"BLOCK", "FAIL"}:
            blocking = True
            msgs.append(f"{name}: effective verdict is {verdict} — a blocking review must not merge "
                        f"until resolved and re-reviewed")
            continue
        for pr in probs:
            msgs.append(f"{name}: {pr}")
        if verdict != "PASS":
            msgs.append(f"{name}: effective verdict is {verdict or 'absent'} "
                        f"(must be exactly 'Verdict: PASS')")
        elif not probs:
            passing.append(name)

    if blocking:
        return False, ["a blocking verdict is present (it gates regardless of any PASS):", *msgs]
    if passing:
        return True, [f"well-formed PASS verdict present: {passing[0]}"]
    return False, msgs


def evaluate_verdicts(changed: list[str], gate_paths: list[str]) -> tuple[bool, list[str]]:
    """Read the changed gate-reviews/ records from disk and decide (see decide_verdicts). A deleted
    verdict simply isn't a record, so deleting the only verdict blocks via the empty-records path.
    The light path is admissible only when every changed gate path is docs-only ('*.md') — a code or
    config gate change (a *.py / *.sh / *.yml / .github/gate-paths edit) requires the full review."""
    allow_light = bool(gate_paths) and all(p.endswith(".md") for p in gate_paths)
    candidates = [
        c for c in changed
        if c.startswith(VERDICT_DIR + "/")
        and c.endswith(".md")
        and c.rsplit("/", 1)[-1] not in VERDICT_NON_RECORDS
    ]
    records = [(c, (ROOT / c).read_text(encoding="utf-8", errors="ignore"))
               for c in candidates if (ROOT / c).is_file()]
    return decide_verdicts(records, allow_light)


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
        if args.base and args.head:
            die("empty diff for the given --base...--head range; an empty PR diff is anomalous "
                "— failing closed.")
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

    ok, lines = evaluate_verdicts(changed, [c for c, _ in touched])
    if ok:
        print(f"gate-review-check: PASS — {lines[0]}")
        return 0

    print("gate-review-check: BLOCKED — a gate-layer change requires an independent gate-review.")
    for ln in lines:
        print(f"  {ln}")
    print("  To clear this check: run ./gate-review-prompt.md (independent, blind), then commit "
          "the verdict under gate-reviews/ (see gate-reviews/TEMPLATE.md). CI green is necessary, "
          "not sufficient, for the gate layer — see CONTRIBUTING.md.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
