#!/usr/bin/env python3
"""
lint-render-restatement.py — suite-level drift guard (WARN by default).

The ONE home for the Markdown/HTML -> publish-target *conversion* is shared/render-contract.md. An
authoring skill's publish step should hand off to publish-mirror and point at the render contract, not
restate the mapping. The recurring cross-skill defect (learning-track v1.2.1; project-faq F1 in
CROSS-SKILL-FINDINGS.md) is a *mapping construction* leaking into a skill: a source primitive joined by
a transformation verb to a TARGET idiom -- "callouts become panels", "collapsible blocks become an
expand macro", "each section becomes a panel". This flags exactly that shape and nothing else.

Why it is low-false-positive by design:
  - It fires only when a transformation connective (become(s) / renders as / maps to / turns into / ->)
    sits ADJACENT (within a few words) to a wiki/portal idiom on one fence-stripped line. Bare idiom
    vocabulary a publisher legitimately names ("a status panel", "the lozenge macro", "info panel")
    never trips it, because nothing turns *into* it on the line. That is the exact distinction the
    cross-skill rule draws: target the mapping construction, not the vocabulary.
  - It scans skills/<name>/SKILL.md only (where publish steps live). It SKIPS publish-mirror (handling
    targets IS its job) and never reads shared/render-contract.md (the legitimate home of the mapping).
  - Fence-stripped first, so a documented example inside a ``` code block is exempt.

WARN by default; exit is 0 unless --strict is passed, when any finding exits 1. As of the 2026-06-20
suite-hardening pass, `build-skills.sh` runs this with --strict and folds a finding into the build's
failure count: the gate is now ACTIVE across the suite. All seven skills were clean at that point, so
a finding here means a session newly restated the mapping — fix it in that skill (state only the
reader-facing consequence and point to render-contract.md). Running this script by hand still defaults
to WARN (exit 0); --strict is what the build uses.

Usage:
    python3 lint-render-restatement.py [skills_dir] [--strict]
    (skills_dir defaults to ./skills relative to this file)
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

# Skills that legitimately handle a publish target, so mapping language there is expected, not a leak.
SKIP_SKILLS = {"publish-mirror"}

# A transformation connective: the tell that a source primitive is being turned INTO something.
CONNECTIVE = r"(?:becomes?|turns?\s+into|turned\s+into|renders?\s+as|rendered\s+as|maps?\s+to|mapped\s+to)"
# A wiki/portal TARGET idiom (the rendered form). Deliberately NOT generic words like "image",
# "heading", or "badge", which are source-side or neutral and which a clean publish step uses safely.
IDIOM = r"(?:panels?|lozenges?|expand\s+macros?|layout\s+macros?|toc\s+macros?|info\s+panels?|note\s+panels?)"
# The mapping construction: connective immediately (within ~3 words) followed by a target idiom.
MAPPING = re.compile(r"\b" + CONNECTIVE + r"\s+(?:\w+\s+){0,3}" + IDIOM + r"\b", re.IGNORECASE)


def strip_code_fences(text: str) -> str:
    out, in_fence = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append("")  # keep the slot so reported line numbers stay exact (the fence line itself is blanked)
            continue
        out.append("" if in_fence else line)  # keep line numbers stable; blank out fenced lines
    return "\n".join(out)


def scan_skill(md_path: Path):
    """Return a list of (lineno, matched_text) for mapping constructions in one SKILL.md."""
    findings = []
    raw = md_path.read_text(encoding="utf-8", errors="ignore")
    for i, line in enumerate(strip_code_fences(raw).splitlines(), start=1):
        m = MAPPING.search(line)
        if m:
            findings.append((i, m.group(0).strip()))
    return findings


def main():
    ap = argparse.ArgumentParser(description="Suite lint: render-contract restatement guard (WARN-only).")
    here = Path(__file__).resolve().parent
    ap.add_argument("skills_dir", nargs="?", default=str(here / "skills"),
                    help="Path to the skills/ directory (default: ./skills next to this script).")
    ap.add_argument("--strict", action="store_true",
                    help="Exit 1 on any finding (suite-hardening only; default is WARN/exit 0).")
    args = ap.parse_args()

    skills_dir = Path(args.skills_dir)
    if not skills_dir.is_dir():
        print(f"lint-render-restatement: skills dir not found: {skills_dir}")
        return 0  # absence of the tree is not this lint's failure to report

    total = 0
    for md in sorted(skills_dir.glob("*/SKILL.md")):
        name = md.parent.name
        if name in SKIP_SKILLS:
            continue
        for lineno, text in scan_skill(md):
            total += 1
            print(f"   warn  {name}/SKILL.md:{lineno}  render-contract restatement: {text!r} "
                  f"— state only the reader-facing consequence and point to render-contract.md; "
                  f"the per-element mapping lives there, not in the skill")

    if total:
        print(f"--- render-restatement lint: {total} warning(s) "
              f"(WARN-only; the conversion's one home is shared/render-contract.md) ---")
    else:
        print("--- render-restatement lint: clean (no mapping construction restated in any skill) ---")
    return 1 if (args.strict and total) else 0


if __name__ == "__main__":
    sys.exit(main())
