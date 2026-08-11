# Changelog — watermark

## 1.0.0 — 2026-08-12

First release. The executor for credit furniture the suite has specified since its
first version and never applied (RCA-001, approved 2026-08-12).

- Applies the watermark and the thin inset border to **exported** images.
- Applies the watermark to HTML **only when a © footer is already present**, per
  `licensing-and-credits.md`, which states three times that the watermark is decorative
  and does not satisfy the footer requirement.
- Refuses a diagram source passed instead of an export; refuses an opacity outside the
  specified 0.18–0.30 rather than clamping it; exits non-zero when it finds nothing.
- Reads every value from `project-profile.md`. Hard-codes no name, URL, opacity or path,
  so it is reusable on any project under the umbrella.
- `--self-test` plants each failure shape and asserts the refusal. It caught a real bug
  during development: sources were not being collected at all, so a `.svg` fell through
  silently instead of being refused, and a directory of sources reported "found 0" —
  which reads like an empty directory rather than like a directory of drawings.
