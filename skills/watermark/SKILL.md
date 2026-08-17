---
name: watermark
description: Stamp the decorative credit watermark and a thin inset slate border onto an exported raster image (a diagram export, an OG/social-preview card) per render-contract.md's credit-furniture rule — placement is measured against the actual image (lowest-variance corner), never a fixed guess, and the script refuses rather than overlapping content it cannot confirm is empty. Use when an image LEAVES the project as a standalone file; never on the diagram source, and never as a substitute for the © licence footer, which HTML generators (project-faq, usage-guide) already render and shared/verify.py already hard-gates independent of this skill.
---

# Watermark

Version: 0.1.0 · see `CHANGELOG.md`.

The executor for the image half of the credit-furniture contract
(`references/render-contract.md:151-153`, `references/project-profile.md`'s `watermark`/
`watermark_opacity` fields). RCA-001 found the contract fully specified and nothing applying
it — that was true for exported images and had already been fixed for HTML by the time this
shipped: `project-faq`'s and `usage-guide`'s generators already render the `{{watermark}}`
decorative line, and `references/verify.py` already hard-fails a public page missing the ©
footer, independent of whether a watermark is present. **This skill closes the remaining gap:
an exported image carries nothing once it leaves the page it was embedded in.**

## Before you start

- **Only for EXPORTS.** Never watermark a diagram's source file (`.excalidraw`, `.drawio`,
  the SVG a page inlines) — only the raster image once it is saved as a standalone artifact
  that will travel independently (a download, an OG card, an attached export).
- **Decorative, not a substitute.** A watermarked image never satisfies the licensing gate's
  © footer requirement (`licensing-and-credits.md` Section 2) — that requirement is checked
  on the HTML page, separately, by `verify.py`, and stays checked whether or not the page
  also embeds a watermarked image.
- **The watermark text is the profile's `watermark` field**, verbatim — do not invent
  different credit text per image.

## Run it

```
python3 assets/apply_watermark.py IN.png OUT.png --text "Name · link" [--opacity 0.22]
```

Or import `apply_watermark(in_path, out_path, text, opacity)` from `assets/apply_watermark.py`.

**Opacity** is read from the profile's `watermark_opacity` (default 0.22); the script rejects
anything outside 0.18–0.30 (`project-profile.md`'s own recommended range) rather than silently
clamping it.

**Placement is measured, not assumed.** The script samples pixel-colour variance in each
corner of the image and places the mark in the lowest-variance (flattest, most likely empty)
one, inside a thin inset slate border. If every corner exceeds the variance floor — the image
has content everywhere, e.g. a dense diagram with no margin — **it refuses and exits non-zero**
rather than guessing and risking an overlap. This was found the hard way: a first version
picked a fixed bottom-right corner and it overlapped a real button on the first real image
tested (a 28,710-variance corner vs. a genuinely empty one measuring 0). Don't reintroduce a
fixed corner; the measured approach is the fix, not an enhancement.

**If it refuses**, the image itself has no safe margin — the fix is upstream (leave whitespace
in the export), not in this script. Do not loosen `CORNER_VARIANCE_LIMIT` to force a pass; that
reopens the exact overlap this skill exists to prevent.

## What it must not do (RCA-001, verbatim)

- Not substitute for the licence footer — this script never touches HTML.
- Not watermark diagram sources — only the exported raster image.
- Not silently skip an image it could not process — every failure path raises or exits
  non-zero with the specific cause (Pillow missing, file missing, opacity out of range, no
  safe corner). There is no bare `except: pass` anywhere in `apply_watermark.py`.

## Dependency

`Pillow` — this skill's own, isolated, documented dependency. Every other script in this
suite is stdlib-only so the core verifier runs anywhere; compositing translucent text onto a
raster image with alpha blending has no reasonable stdlib path. The import is guarded: if
Pillow is missing, the script prints the install command and exits 2 — never a silent no-op.

```
pip install Pillow
```

## File-size discipline

An unquantized RGBA save loses a palette-mode source's efficiency — measured against a real
72KB indexed PNG, a naive save more than doubled it (189KB). The script quantizes the final
composite back to an adaptive 256-colour palette; measured within 3% of the source's own size
on the same real image. If you change the save path, re-measure before/after on a real image,
not a synthetic one — the size cost only shows up against real colour distributions.
