#!/usr/bin/env python3
"""
check-version.py — version & changelog-bump check (root scaffolding; never bundled).

The release gate must refuse to ship a version that nobody recorded. This check is the deterministic
part of scope-item 3.3.6. It asserts, with no third-party deps and no flakiness:

  1. The suite VERSION file is valid SemVer.
  2. The root CHANGELOG.md carries a heading for that exact version  ('## [X.Y.Z]').
  3. Each skill is independently versioned — its CHANGELOG.md has at least one SemVer heading.
     (The suite/skill CHANGELOG split is the standing rule; skills do NOT share the suite number.)

The "advanced since the last release tag" comparison needs git history, which is not always present
(a delivered zip is not a git checkout). So that step is OPTIONAL and HONEST: it runs only when this is
a git repo with tags, and it never fails the build on the absence of history — it prints a skip note.
Built-vs-designed honesty applies to tooling: a check that cannot truly run says so rather than passing
green by doing nothing.

Exit 0 if the deterministic assertions hold (1-3), 1 otherwise. Usage:
    python3 check-version.py [root]      # root defaults to the dir holding this script
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
# A '## [X.Y.Z]' Keep-a-Changelog version heading (ignores '## [Unreleased]').
HEADING_VER = re.compile(r"^##\s*\[(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)\]", re.M)


def _is_git_repo(root: Path) -> bool:
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
                           capture_output=True, text=True, timeout=5)
        return r.returncode == 0 and r.stdout.strip() == "true"
    except Exception:
        return False


def _latest_tag(root: Path) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(root), "describe", "--tags", "--abbrev=0"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return None


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
    fails = 0

    def check(ok: bool, msg: str) -> None:
        nonlocal fails
        print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
        if not ok:
            fails += 1

    # 1. VERSION is valid SemVer.
    version_file = root / "VERSION"
    if not version_file.exists():
        check(False, "VERSION file present")
        print("--- check-version: 1 failure (no VERSION) ---")
        return 1
    version = version_file.read_text(encoding="utf-8").strip()
    check(bool(SEMVER.match(version)), f"suite VERSION '{version}' is valid SemVer")

    # 2. Root CHANGELOG.md has a heading for this version.
    root_cl = root / "CHANGELOG.md"
    if root_cl.exists():
        versions = set(HEADING_VER.findall(root_cl.read_text(encoding="utf-8")))
        check(version in versions,
              f"root CHANGELOG.md has a '## [{version}]' heading"
              + ("" if version in versions else f" (found: {sorted(versions) or 'none'})"))
    else:
        check(False, "root CHANGELOG.md present")

    # 3. Each skill is independently versioned.
    skills_dir = root / "skills"
    skill_dirs = sorted(p for p in skills_dir.glob("*/") if p.is_dir()) if skills_dir.is_dir() else []
    if not skill_dirs:
        check(False, "skills/ directory has skills")
    for sd in skill_dirs:
        cl = sd / "CHANGELOG.md"
        if not cl.exists():
            check(False, f"{sd.name}: CHANGELOG.md present")
            continue
        vers = HEADING_VER.findall(cl.read_text(encoding="utf-8"))
        check(bool(vers), f"{sd.name}: CHANGELOG.md has a SemVer entry"
              + (f" (latest [{vers[0]}])" if vers else ""))

    # Optional, honest: tag-bump comparison only when git history is available.
    if _is_git_repo(root):
        tag = _latest_tag(root)
        if tag is None:
            print("  [skip] no git tags yet — tag-bump comparison not applicable (this would be the "
                  "first tagged release)")
        else:
            tag_norm = tag.lstrip("vV")
            if tag_norm == version:
                print(f"  [note] VERSION {version} equals the latest tag {tag} — tag a new release "
                      f"only when shipping new bytes")
            else:
                print(f"  [note] VERSION {version} differs from latest tag {tag} — a new release is "
                      f"staged")
    else:
        print("  [skip] not a git checkout — tag-bump comparison skipped (deterministic checks 1-3 "
              "above are the gate; the manifest's source-commit field records provenance when built "
              "from git)")

    print(f"--- check-version: {fails} failure(s) ---")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
