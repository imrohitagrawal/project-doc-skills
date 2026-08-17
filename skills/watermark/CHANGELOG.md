# Changelog — watermark skill

Skill-specific changes. Shared/suite changes live in the root `CHANGELOG.md`. Format follows Keep a
Changelog.

## [0.1.0] — 2026-08-17

Initial release. RCA-001, approved 2026-08-12.

### Added
- `assets/apply_watermark.py` — stamps the decorative credit watermark (`project-profile.md`'s
  `watermark`/`watermark_opacity`) and a thin inset slate border onto an exported raster image
  (`render-contract.md:151-153`). The HTML case (`{{watermark}}` decorative line) was already
  implemented in `project-faq`'s and `usage-guide`'s generators, and `shared/verify.py` already
  hard-fails a public page missing the © licence footer independent of watermark presence — this
  skill closes the one gap that remained: exported images carried nothing.
- **Placement is measured, not assumed.** "Never overlap content" is checked by sampling
  pixel-colour variance in each corner and picking the lowest — a flat background reads ~0, real
  UI content reads in the thousands (measured against a real consumer image: a candidate corner
  holding a button read 28,710). If no corner clears the variance floor, the script refuses and
  exits non-zero rather than guessing a placement. Found the hard way: a first version placed the
  mark in a fixed bottom-right corner and it overlapped a real button on first real-image test —
  fixed before shipping, not after.
- File-size discipline: an unquantized RGBA save against a palette-mode source more than doubled
  the file size in testing (72KB → 189KB) — a real regression for a social-preview image fetched
  on every share. The final composite quantizes back to an adaptive 256-colour palette, measured
  within 3% of the source's own size.
- Never silently skips an image it could not process (RCA-001's explicit requirement) — every
  failure path raises or exits non-zero with the specific cause: Pillow missing, file missing,
  opacity out of the 0.18–0.30 range, no safe corner found.
