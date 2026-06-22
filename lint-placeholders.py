#!/usr/bin/env python3
"""
lint-placeholders.py — suite-level placeholder-resolution guard.

The placeholder convention (project-profile.md): every `{{key}}` is a slot a tool/agent fills from
the matching key in `project-profile.md` or `publish-targets.yaml`. The recurring defect this guards
(CROSS-SKILL-FINDINGS.md F5) is a `{{...}}` token that backs to NOTHING — e.g. `{{today}}`, which is
not a profile key — so an agent filling the template cannot resolve it. This lint makes the
convention machine-true: every `{{...}}` in the suite must resolve, or it is reported with file:line.

What counts as resolved (the closed set):
  - a key in project-profile.md (parsed from its embedded ```yaml blocks),
  - a fill-slot the manifest itself declares (a token that appears in publish-targets.yaml — that file
    IS the template that declares those slots: "Replace each {{...}} with the real value"),
  - a documented RUNTIME token, declared once in project-profile.md "Runtime tokens": {{today}} (build
    date), {{canonical_url}} (wired at publish),
  - the convention's own illustration token {{key}} (literally the word "key", used in the docs that
    teach the convention), and any token whose inner text is not a valid identifier (e.g. {{...}},
    {{…}}, {{double curly braces}}) — those are illustrations, never real slots.

Scope: skills/** and shared/** (what ships in a bundle, plus the canonical sources). Root scaffolding
(README, CHANGELOG, the prompts) is not scanned — it describes the work and names tokens illustratively.

Usage:
    python3 lint-placeholders.py [root] [--strict]
    (root defaults to the directory this file sits in)

WARN by default (exit 0); --strict exits 1 on any unresolved token (the build uses --strict). Mirrors
lint-render-restatement.py's contract so the release gate composes the two the same way.
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
    _HAVE_YAML = True
except Exception:
    _HAVE_YAML = False

TOKEN = re.compile(r"\{\{\s*([^}]*?)\s*\}\}")
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")        # a real profile/manifest key looks like this
_RUNTIME_TOKENS = {"today", "canonical_url"}       # documented in project-profile.md "Runtime tokens"
_ILLUSTRATION = {"key"}                            # the convention's own self-name, in convention docs
_SCAN_EXTS = {".md", ".yaml", ".yml", ".py", ".html", ".htm", ".txt"}


def _merge_yaml_blocks(md_text: str) -> dict:
    if not _HAVE_YAML:
        return {}
    merged: dict = {}
    for block in re.findall(r"```ya?ml\s*\n(.*?)```", md_text, flags=re.S | re.I):
        try:
            data = yaml.safe_load(block)
        except Exception:
            continue
        if isinstance(data, dict):
            merged.update(data)
    return merged


def profile_keys(profile_path: Path) -> set[str]:
    if not profile_path.exists():
        return set()
    return set(_merge_yaml_blocks(profile_path.read_text(encoding="utf-8", errors="ignore")).keys())


def manifest_slots(manifest_path: Path) -> set[str]:
    """The fill-slots the manifest declares — every {{X}} token that appears in publish-targets.yaml."""
    if not manifest_path.exists():
        return set()
    text = manifest_path.read_text(encoding="utf-8", errors="ignore")
    return {m.group(1).strip() for m in TOKEN.finditer(text)}


def known_keys(root: Path) -> set[str]:
    keys = set()
    keys |= profile_keys(root / "shared" / "project-profile.md")
    keys |= manifest_slots(root / "shared" / "publish-targets.yaml")
    keys |= _RUNTIME_TOKENS
    keys |= _ILLUSTRATION
    return keys


def scan_text(text: str, known: set[str]):
    """Return [(lineno, token)] for unresolved {{...}} tokens. An import-friendly core (golden tests
    call this directly)."""
    findings = []
    for m in TOKEN.finditer(text):
        inner = m.group(1).strip()
        if not _IDENT.match(inner):          # {{...}}, {{…}}, {{double curly braces}} — illustrations
            continue
        if inner in known:
            continue
        lineno = text[: m.start()].count("\n") + 1
        findings.append((lineno, inner))
    return findings


def scan_tree(root: Path):
    known = known_keys(root)
    out = []  # (relpath, lineno, token)
    for sub in ("skills", "shared"):
        base = root / sub
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in _SCAN_EXTS:
                continue
            for lineno, tok in scan_text(p.read_text(encoding="utf-8", errors="ignore"), known):
                out.append((p.relative_to(root).as_posix(), lineno, tok))
    return out, known


def main():
    ap = argparse.ArgumentParser(description="Suite lint: every {{...}} placeholder must resolve.")
    here = Path(__file__).resolve().parent
    ap.add_argument("root", nargs="?", default=str(here),
                    help="Suite root (default: the directory this script sits in).")
    ap.add_argument("--strict", action="store_true",
                    help="Exit 1 on any unresolved token (the build uses --strict; default WARN/exit 0).")
    args = ap.parse_args()

    root = Path(args.root)
    if not _HAVE_YAML:
        print("lint-placeholders: PyYAML not installed — cannot read the profile keys; skipping.")
        return 0

    findings, known = scan_tree(root)
    for rel, lineno, tok in findings:
        print(f"   warn  {rel}:{lineno}  unresolved placeholder {{{{{tok}}}}} — it backs to no key in "
              f"project-profile.md / publish-targets.yaml and is not a documented runtime token "
              f"(today, canonical_url). Add the key, use a runtime token, or reword to a literal.")
    if findings:
        print(f"--- placeholder lint: {len(findings)} unresolved token(s) "
              f"({len(known)} known keys/slots/runtime tokens) ---")
    else:
        print(f"--- placeholder lint: clean (every {{{{...}}}} resolves; "
              f"{len(known)} known keys/slots/runtime tokens) ---")
    return 1 if (args.strict and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
