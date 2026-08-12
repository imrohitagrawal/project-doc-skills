#!/usr/bin/env bash
# release-gate.sh — the one composed gate a suite release must pass (root scaffolding; never bundled).
#
# It COMPOSES the existing and new gates in dependency order rather than re-implementing any of them.
# A release ships only if every step below passes:
#
#   1. ./build-skills.sh        — validate each skill against the platform upload rules, package it
#                                 deterministically, AND run the three now-active suite checks
#                                 (render-restatement & placeholder lints --strict; the
#                                 skill-enumeration check --check). Emits dist/MANIFEST.sha256 on a
#                                 clean full build.
#   2. tests/run-golden.py      — the gates that guard the gates: every produced golden-good doc passes
#                                 verify.py with 0 FAIL, every golden-bad doc is caught by the right
#                                 gate, and the staleness + readability pins hold.
#   3. ./build-skills.sh --check — reproducibility: every committed dist/<name>.skill must be
#                                 byte-identical to a fresh rebuild (DRIFT fails).
#   4. manifest presence         — dist/MANIFEST.sha256 exists and is non-empty (the integrity record a
#                                 consumer verifies before install).
#   6. tests/mutation-runner.py  — every declared mutation reddens its own fixture, and a thinned
#                                  mutation list is refused rather than reported as 0/0 green
#   7. watermark --self-test      — the credit-furniture executor refuses what it must and proves
#                                  the mark in PIXELS, not in file bytes
#   5. check-version.py          — VERSION is SemVer, the root CHANGELOG names it, every skill is
#                                 versioned.
#
# The render-restatement lint is NOT added here a second time — it already runs inside step 1 with
# --strict, which is exactly the "compose, don't re-add" rule. Distinct from the per-skill
# shared/ci/verify-docs.yml, which ships INSIDE each .skill to verify a CONSUMER's produced docs; this
# script gates a release of the SUITE itself.
#
# Usage: ./release-gate.sh         # exit 0 only if all steps pass; first failure stops the gate.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

step=0
run() {   # run "<label>" <command...>; on failure print where the gate stopped and exit 1.
  step=$((step+1))
  local label="$1"; shift
  echo ""
  echo "================ release-gate step $step: $label ================"
  if ! "$@"; then
    echo ""
    echo "XXXX release gate FAILED at step $step ($label). Fix the above and re-run. XXXX"
    exit 1
  fi
}

run "build (validate + deterministic package + render-restatement & placeholder lints + skill-enumeration check + manifest)" \
    ./build-skills.sh

run "golden fixtures (golden-good 0 FAIL, every golden-bad caught, staleness/readability pins)" \
    python3 tests/run-golden.py

run "reproducibility (--check: every committed .skill is byte-identical to a fresh rebuild)" \
    ./build-skills.sh --check

check_manifest() {
  local m="$ROOT/dist/MANIFEST.sha256"
  if [[ -s "$m" ]] && grep -qE '^[0-9a-f]{64}  ' "$m"; then
    echo "manifest present: $(grep -cE '^[0-9a-f]{64}  ' "$m") entries in dist/MANIFEST.sha256"
    return 0
  fi
  echo "manifest missing or empty: $m"
  return 1
}
run "integrity manifest present (dist/MANIFEST.sha256, non-empty)" check_manifest

run "version & changelog bump (SemVer VERSION, root CHANGELOG heading, every skill versioned)" \
    python3 check-version.py

# Steps 6 and 7 were advisory until 2026-08-12, which meant CI could go green
# without either ever running. gate-reviews/0024 and 0026 both recorded that as a
# residual and stated what would make them blocking: exactly this. A gate nothing
# invokes is a gate that has never refused anything.
run "mutation harness (every declared mutation reddens its own fixture; a thinned list is refused)" \
    python3 tests/mutation-runner.py

run "watermark executor self-test (refusals bite; the mark is proved in pixels, not bytes)" \
    python3 skills/watermark/scripts/apply_watermark.py --self-test

echo ""
echo "================================================================"
echo "release gate PASSED — all $step steps green. Suite is releasable."
echo "================================================================"
