#!/usr/bin/env python3
"""
pkgtools.py — deterministic packaging + integrity manifest for the suite (root scaffolding; never
bundled into a .skill).

Two reasons a plain `zip` is not enough for a released artifact:
  1. Reproducibility. A zip stores each entry's mtime and the entry ORDER. With wall-clock mtimes and
     filesystem ordering, two builds of identical source produce DIFFERENT bytes — so you cannot prove
     that what a consumer installs is what was reviewed. This packer pins every entry's timestamp to
     the zip epoch (1980-01-01) and writes entries in sorted arcname order, with a fixed compression
     level, so identical source -> byte-identical .skill (within one toolchain; see the honesty note).
  2. Integrity. `manifest` emits a SHA-256 over each built .skill AND each shared/ source file, plus
     the suite version. A consumer verifies the bundle before install; tampering or drift shows up as a
     hash mismatch. (No build-time commit field: it recorded the build HEAD, which is always the PARENT
     of the commit that carries the manifest, so it flipped on every commit and produced spurious diffs
     on content-free changes. The SHA-256 rows are the integrity guarantee — see write_manifest.)

Honesty note (built-vs-designed applies to tooling): byte-identity holds for rebuilds on the same
zlib/Python toolchain (DEFLATE output is deterministic for fixed input + level on a given zlib). The
SHA-256 manifest is the cross-environment guarantee — it pins the exact bytes that were reviewed.

Commands:
    python3 pkgtools.py zip <src_dir> <out.skill>
        Package src_dir deterministically into out.skill.
    python3 pkgtools.py manifest <dist_dir> <shared_dir> <out_manifest> [--version V] [--root R]
        Write a SHA-256 manifest of every <dist_dir>/*.skill and every file under <shared_dir>.
"""
from __future__ import annotations
import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

_EPOCH = (1980, 1, 1, 0, 0, 0)   # the zip format's minimum timestamp — fixed, so mtimes never vary
_FILE_ATTR = (0o644 & 0xFFFF) << 16   # rw-r--r-- as external attributes, fixed across machines


def _is_cruft(path: Path) -> bool:
    """Build cruft that must never enter a packaged artifact OR the integrity manifest: bytecode caches
    (environment-specific and non-deterministic) and OS junk. The build strips these from staged
    packages; doing it here too keeps pkgtools correct when used directly and keeps the manifest from
    hashing a `.pyc` that differs per machine."""
    if "__pycache__" in path.parts:
        return True
    return path.name == ".DS_Store" or path.suffix in (".pyc", ".pyo")


def collect_files(src_dir: Path):
    """All regular files under src_dir, as (arcname, path), sorted by arcname. Files only — no dir
    entries (unzip recreates directories), so ordering is fully determined by the file set. Build
    cruft (__pycache__/*.pyc, .DS_Store) is excluded."""
    files = [(p.relative_to(src_dir.parent).as_posix(), p)
             for p in src_dir.rglob("*") if p.is_file() and not _is_cruft(p)]
    return sorted(files, key=lambda t: t[0])


def zip_deterministic(src_dir: Path, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for arcname, path in collect_files(src_dir):
            zi = zipfile.ZipInfo(filename=arcname, date_time=_EPOCH)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = _FILE_ATTR
            zi.create_system = 3   # Unix, fixed (default varies by OS)
            zf.writestr(zi, path.read_bytes())
    return out_path


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_manifest(dist_dir: Path, shared_dir: Path, out_path: Path,
                   version: str, root: Path) -> Path:
    # All paths are written relative to the repo root, so a single `cd <repo-root> && sha256sum -c
    # dist/MANIFEST.sha256` resolves every line (the .skill files under dist/ and the shared sources
    # under shared/). Mixing per-directory roots would leave no single cwd where all lines resolve.
    def rel(p: Path) -> str:
        try:
            return p.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return p.name  # outside the root (unexpected) — fall back to the bare name

    lines = []
    lines.append("# MANIFEST.sha256 — integrity manifest for the project-doc-skills suite")
    lines.append(f"# suite-version: {version}")
    # Deliberately NO build-commit line: it recorded the build HEAD, always the PARENT of the commit
    # carrying the manifest, so it flipped on every build and produced spurious diffs on content-free
    # changes. The SHA-256 rows below are the integrity guarantee; identical hashed content now yields a
    # byte-identical manifest. (The commit that adds a manifest is its own provenance, via git.)
    lines.append("# Verify before install:  cd <repo-root> && sha256sum -c dist/MANIFEST.sha256")
    lines.append("# Paths are relative to the repo root. Each line: <sha256>  <path>")
    lines.append("#")
    rows = []
    for sk in sorted(dist_dir.glob("*.skill")):
        rows.append((_sha256(sk.read_bytes()), rel(sk)))
    for f in sorted(p for p in shared_dir.rglob("*") if p.is_file() and not _is_cruft(p)):
        rows.append((_sha256(f.read_bytes()), rel(f)))
    for digest, name in rows:
        lines.append(f"{digest}  {name}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="Deterministic packaging + integrity manifest.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pz = sub.add_parser("zip", help="Deterministically package a staged skill directory.")
    pz.add_argument("src_dir")
    pz.add_argument("out_path")

    pm = sub.add_parser("manifest", help="Emit a SHA-256 manifest of the dist/ and shared/ trees.")
    pm.add_argument("dist_dir")
    pm.add_argument("shared_dir")
    pm.add_argument("out_path")
    pm.add_argument("--version", default="0.0.0")
    pm.add_argument("--root", default=".")

    args = ap.parse_args()
    if args.cmd == "zip":
        p = zip_deterministic(Path(args.src_dir), Path(args.out_path))
        print(f"packaged {p}")
    elif args.cmd == "manifest":
        p = write_manifest(Path(args.dist_dir), Path(args.shared_dir), Path(args.out_path),
                           args.version, Path(args.root))
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
