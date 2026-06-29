#!/usr/bin/env bash
# Assemble each .skill package from its bespoke files (skills/<name>/) plus the canonical
# shared files (shared/). Shared files are COPIED IN at build time — never hand-edit the copies
# inside a built .skill or inside skills/<name>/. Edit shared/ and rebuild.
#
# Each skill is VALIDATED against the platform upload rules (validate_skill.py) before it is
# packaged; an invalid skill (e.g. description over 1024 chars, or angle brackets in it) FAILS
# the build here instead of failing on upload. Packaging is DETERMINISTIC (pkgtools.py): identical
# source -> byte-identical .skill, so `--check` can prove an artifact matches its source.
#
# Usage: ./build-skills.sh            # build every skill into dist/ (+ emit dist/MANIFEST.sha256)
#        ./build-skills.sh faq        # build only skills whose name contains "faq"
#        ./build-skills.sh --check     # rebuild every .skill and assert it is BYTE-IDENTICAL to dist/
#        ./build-skills.sh --check faq # check only matching skills
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SHARED="$ROOT/shared"
DIST="$ROOT/dist"

CHECK=0
FILTER=""
for arg in "$@"; do
  case "$arg" in
    --check) CHECK=1 ;;
    *) FILTER="$arg" ;;
  esac
done

VERSION="$(cat "$ROOT/VERSION" 2>/dev/null | tr -d '[:space:]' || echo 0.0.0)"

mkdir -p "$DIST"
STAGE="$(mktemp -d)"
CHECKDIR="$(mktemp -d)"
trap 'rm -rf "$STAGE" "$CHECKDIR"' EXIT

# Stage one skill into $STAGE/$name (bespoke files + the copied shared layer). Echoes the validator msg.
stage_skill() {
  local skdir="$1" name="$2"
  local pkg="$STAGE/$name"
  rm -rf "$pkg"
  mkdir -p "$pkg/references" "$pkg/assets" "$pkg/scripts" "$pkg/ci"
  cp -r "$skdir"/. "$pkg"/                                   # bespoke files
  cp "$SHARED/house-style.md"            "$pkg/references/house-style.md"
  cp "$SHARED/licensing-and-credits.md" "$pkg/references/licensing-and-credits.md"
  cp "$SHARED/project-profile.md" "$pkg/assets/project-profile.md"
  cp "$SHARED/verify.py"          "$pkg/scripts/verify.py"
  cp "$SHARED/render-contract.md"       "$pkg/references/render-contract.md"
  cp "$SHARED/publish-targets.yaml"     "$pkg/assets/publish-targets.yaml"
  cp -r "$SHARED/ci/." "$pkg/ci/"
  # drop build artifacts that must never ship
  find "$pkg" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
  find "$pkg" \( -name '*.pyc' -o -name '.DS_Store' \) -delete 2>/dev/null || true
}

built=0; failed=0; checked=0; mismatched=0
for skdir in "$ROOT"/skills/*/; do
  name="$(basename "$skdir")"
  [[ -n "$FILTER" && "$name" != *"$FILTER"* ]] && continue

  if ! msg="$(stage_skill "$skdir" "$name" && python3 "$ROOT/validate_skill.py" "$STAGE/$name" 2>&1)"; then
    echo "FAIL  $name — $msg"; failed=$((failed+1)); continue
  fi

  if [[ "$CHECK" -eq 1 ]]; then
    # Rebuild into a scratch path and byte-compare to the committed dist/<name>.skill.
    ref="$DIST/$name.skill"
    if [[ ! -f "$ref" ]]; then
      echo "CHECK MISS  $name — no committed dist/$name.skill to compare against (run ./build-skills.sh first)"
      mismatched=$((mismatched+1)); continue
    fi
    fresh="$CHECKDIR/$name.skill"
    python3 "$ROOT/pkgtools.py" zip "$STAGE/$name" "$fresh" >/dev/null
    if cmp -s "$fresh" "$ref"; then
      echo "ok    $name — byte-identical ($(wc -c <"$ref") bytes, sha256 $(sha256sum "$ref" | cut -c1-12)…)"
      checked=$((checked+1))
    else
      echo "DRIFT $name — rebuilt .skill differs from dist/$name.skill (source changed or artifact tampered)"
      mismatched=$((mismatched+1))
    fi
  else
    out="$DIST/$name.skill"
    python3 "$ROOT/pkgtools.py" zip "$STAGE/$name" "$out" >/dev/null
    echo "built $out  [$msg]"
    built=$((built+1))
  fi
done

# Suite-level drift guard (ACTIVE GATE as of the 2026-06-20 suite-hardening pass). The Markdown/HTML
# -> publish-target conversion has ONE home, shared/render-contract.md; a skill must not restate the
# mapping. All seven skills were confirmed clean, so this runs with --strict and a finding FAILS the
# build (counted into $failed below). If a future per-skill session reintroduces a restatement, the
# build breaks here and names the file:line.
if ! python3 "$ROOT/lint-render-restatement.py" "$ROOT/skills" --strict; then
  echo "FAIL  render-restatement lint reported a restatement (see above)"
  failed=$((failed+1))
fi

# Suite-level placeholder-resolution guard (ACTIVE GATE, 2026-06-22 suite-hardening pass 2). Every
# {{...}} in skills/ + shared/ must resolve to a profile key, a manifest slot, or a documented runtime
# token. A leftover unresolved token FAILS the build (counted into $failed) and is named by file:line.
if ! python3 "$ROOT/lint-placeholders.py" "$ROOT" --strict; then
  echo "FAIL  placeholder lint reported an unresolved {{...}} token (see above)"
  failed=$((failed+1))
fi

# Suite-level skill-enumeration guard. README.md and per-skill-review-prompt.md are root scaffolding
# (never bundled), so they are invisible to validate_skill.py, the two lints above, and
# check-version.py — the blind spot that let the skill count/table/pick-list drift twice. This asserts
# both files enumerate exactly the skills in skills/. A drift FAILS the build (counted into $failed)
# and is named; run by hand it defaults to WARN.
if ! python3 "$ROOT/lint-skill-count.py" "$ROOT" --strict; then
  echo "FAIL  skill-count lint reported a skill-enumeration drift (see above)"
  failed=$((failed+1))
fi

if [[ "$CHECK" -eq 1 ]]; then
  echo "--- check: $checked byte-identical, $mismatched mismatched/missing, $failed validation/lint failure(s) ---"
  [[ "$mismatched" -gt 0 || "$failed" -gt 0 ]] && exit 1 || exit 0
fi

# Emit the integrity manifest over the freshly-built dist/ and the shared/ source (only on a full
# build with no failures and no name filter, so the manifest always covers all eight).
if [[ "$failed" -eq 0 && -z "$FILTER" ]]; then
  python3 "$ROOT/pkgtools.py" manifest "$DIST" "$SHARED" "$DIST/MANIFEST.sha256" \
    --version "$VERSION" --root "$ROOT" >/dev/null
  echo "manifest dist/MANIFEST.sha256  [suite $VERSION, $(grep -c '^[0-9a-f]\{64\}' "$DIST/MANIFEST.sha256") entries]"
fi

echo "--- $built built, $failed failed ---"
[[ "$failed" -gt 0 ]] && exit 1 || exit 0
