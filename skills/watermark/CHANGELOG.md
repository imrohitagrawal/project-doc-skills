# Changelog — watermark

All notable changes to this skill are recorded here (Keep a Changelog format).

## [1.0.0] — the executor the contract always specified and never had

### Added
- **The skill.** The credit furniture was specified across `project-profile.md` (the text and the
  opacity), `render-contract.md` (placement, and *"never on the diagram source"*) and
  `licensing-and-credits.md` (*"does not satisfy the footer requirement"*), and nothing applied it.
  Every skill referenced the spec; none executed it.
- **Standalone by design.** It does not require an authoring skill to have run first. An image or a
  page produced by hand is exactly as valid an input as one a skill generated — which is most of the
  point of packaging it separately.
- **Margin-band placement.** The mark goes in a band added below the artwork, so the contract's
  *"in whitespace, never overlapping content"* holds by geometry rather than by assuming the corner
  is empty.
- **Ink derived from the artifact.** The band's background is read from the image's own bottom edge
  and the ink flips with it, so the same command works on a light diagram and a dark screenshot.
  Slate remains the hairline rule between band and artwork.
- **An HTML footer check that parses.** `©` inside a comment, a `<script>` string, a `<pre><code>`
  sample, a CSS `content` property or an `alt` attribute is not a footer; `&#xA9;`, `&#x00A9;` and
  the word *Copyright* are.
- **Atomic writes.** `--in-place` writes to a temp file in the destination directory and renames, so
  an interrupted run cannot leave a truncated original.
- **15-assertion self-test**, mutation-tested in both directions.

### Design decisions on record
- **The ink is not a fixed colour, and that is deliberate** even though the contract names slate.
  A fixed colour is a bet on a background the skill never sees: white changes **zero pixels** on a
  light export while reporting success, and slate goes faint on a dark one. Deriving the ink keeps
  slate's intent — a quiet credit line that never competes — without a class of inputs it silently
  ruins.
- **Zero artifacts is a failure, not a success.** A watermarker that matches nothing would report
  green while every artifact ships uncredited.
- **A missing `watermark:` key is refused, a blank one is honoured.** Absent and empty are different
  states; treating them alike let a mistyped key disable every run and still exit 0.

### Corrections carried from the first attempt
Recorded rather than quietly dropped, because the same mistakes are easy to make again.
- **The mark was hardcoded white**, against a contract that says slate. On a light export it changed
  zero pixels while the tool printed `watermarked N of N`.
- **The self-test compared bytes, not pixels**, and was named in `SKILL.md` as the guard against
  exactly that failure. A PNG re-encode changes bytes, so a mutant that drew nothing passed. The
  first repair — measuring contrast across the whole band — passed the same mutant again, on the
  strength of the slate rule alone. It now measures the rows the text occupies.
- **The footer check was a raw-bytes search**, wrong in both directions: it accepted five pages whose
  only `©` sat in markup, and refused `&#xA9;`, `&#x00A9;` and the word *Copyright*.
- **`--in-place` truncated originals** when interrupted, and one corrupt file aborted a whole
  directory mid-write with a traceback and no summary.
- **Nested directories were flattened** onto the base filename, so two exports named alike
  overwrote each other while the run reported both as done.
- **The profile value was interpolated into HTML unescaped**, so a hostile value wrote a live
  `<script>` tag into the published page.
- **`SKILL.md` cited an `AGENTS.md` and an `RCA-001` that do not exist in this repository**, and
  claimed a rule was stated three times in a file that states it once. All removed.
