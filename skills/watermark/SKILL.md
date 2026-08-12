---
name: watermark
description: Apply the suite's credit furniture — a decorative watermark line in an added margin band, and the thin slate rule — to EXPORTED images, and enforce that HTML pages carrying a watermark also carry a visible © footer. A post-processing step that runs AFTER an authoring skill has produced and verified its exports, or on any image or page you produced by hand; it never authors or rewrites content. Use it whenever diagrams, screenshots, OG cards or finished HTML pages are about to be published, shared or mirrored and need the credit line the render contract specifies. It reads every value from project-profile.md, derives the ink from the artifact so it works on light and dark exports alike, refuses a diagram source passed instead of an export, refuses an opacity outside the specified range, refuses an HTML page with no visible footer, and fails when it finds nothing to process. NOT for writing documentation (use the authoring skills) and NOT for publishing (use publish-mirror).
---

# Watermark & Credit Furniture

Version: 1.0.0 · see `CHANGELOG.md`.

The credit furniture was specified in this suite from the start and never applied. The values sit
in `assets/project-profile.md`, the placement rule in `references/render-contract.md`, and the
"never substitutes for the footer" rule in `references/licensing-and-credits.md` — and every skill
referenced them while none executed them. This skill is the executor.

## Before you start: what this needs, when to run it, where it fits

**Needs:** an exported image or HTML file (or a directory of them), and `assets/project-profile.md`
for the credit text and opacity. Pillow for images. Nothing else.

**When to run it:** after an export exists and has been checked, and before it is published or
shared. It is deliberately usable **on its own** — you do not have to have used any authoring skill
to reach it. If you drew an architecture diagram by hand and want it credited, this is the step.

**Where it fits:** after the review gate, before `publish-mirror`, whose inputs are described as
*"diagrams exported to PNG/SVG (watermarked, framed)"* — this is the step that makes that true.

Read these two before changing anything here:

- `references/render-contract.md` — where the furniture goes. The governing line: it goes on the
  **exported** image, *never* on the diagram source.
- `references/licensing-and-credits.md` — the watermark is **decorative and does not satisfy the
  footer requirement**.

## The one idea, and why it is not obvious

**A watermark is the signature on a painting. The © footer is the receipt.**

The signature travels with the picture when it leaves the gallery. The receipt proves ownership but
stays with the paperwork. Screenshot a diagram into a slide deck and the receipt is gone — only the
signature survives.

That is why the suite insists they are different things, and why this skill **refuses** to put a
watermark on an HTML page with no footer. A page with a mark and no footer *looks* credited and is
not, which is worse than a page with neither: it stops anyone noticing the gap.

## Workflow

```bash
# One export
python3 scripts/apply_watermark.py docs/exports/architecture.png

# A directory, writing alongside rather than over the originals
python3 scripts/apply_watermark.py docs/exports/ --out docs/exports/watermarked

# Overwrite in place. Writes are atomic, so an interrupted run cannot truncate an original.
python3 scripts/apply_watermark.py docs/exports/ --in-place

# Prove it bites before relying on it
python3 scripts/apply_watermark.py --self-test
```

`--profile` defaults to `assets/project-profile.md`, the copy the build stages into every skill.

## How the mark is placed, and why not in the corner

**The mark goes in a margin band added below the artwork, not over it.** The render contract says
*"in whitespace, never overlapping content"*. Drawing into the bottom-right corner and calling that
whitespace is a guess about the artifact, and on a real export it ran straight across the content.
A band added beneath the image cannot overlap it, because there is nothing underneath the mark.
Geometry, not hope.

**The ink is read off the artifact, not hardcoded.** A fixed colour is a bet on a background this
skill never gets to see:

| Fixed choice | Fails on |
|---|---|
| White | any light export — on near-white it changes **zero pixels** while reporting success |
| Slate | any dark export — it goes faint and unreadable |

So the band's background comes from the image's own bottom edge and the ink flips with it: dark ink
on a light edge, light ink on a dark one. Slate survives as the hairline rule between band and
artwork, which is what the contract's *"thin inset slate border"* was protecting.

## What it refuses, and why each refusal exists

- **A diagram source** (`.svg`, `.drawio`, `.excalidraw`, `.mmd`, `.puml`). Marking a source poisons
  every future export made from it.
- **An opacity outside 0.18–0.30.** It refuses rather than clamping: a silently corrected value is
  one nobody notices is wrong.
- **An HTML page with no visible © footer.** The footer is detected by **parsing** the page, not by
  searching the bytes — a `©` inside a comment, a `<script>` string, a code sample, a CSS `content`
  property or an `alt` attribute is not a footer, and `&#xA9;`, `&#x00A9;` and the word *Copyright*
  all are.
- **An HTML fragment with no `</body>`.** Writing it back unchanged would report success while
  marking nothing.
- **A profile with no `watermark:` key.** Absent is not the same as blank; a mistyped key would
  otherwise disable every run and still exit 0.
- **An unreadable or corrupt image** — reported as a refusal, so the rest of the directory still
  processes.
- **Finding nothing.** A run that matched zero artifacts exits **non-zero**. Zero is a failure.

## What it must never do

- Substitute for the licence footer.
- Touch a diagram source.
- Silently skip a file it could not process — every skip is reported as a refusal with its reason.
- Overwrite one export with another. Nested directories keep their shape.

## Quality bar (self-check before presenting)

- [ ] `--self-test` passes, 15 of 15.
- [ ] The output was **looked at**, on a light artifact and a dark one. A build that succeeds is not
      a mark you can read.
- [ ] The artwork above the band is pixel-identical to the input.
- [ ] Any HTML you marked still carries its own visible footer — the mark did not become the credit.
- [ ] Nothing was written outside the target directory.

## Prove it bites

The self-test plants each failure shape and asserts the refusal — 15 assertions, including the two
that matter most: an HTML page with no footer, and a run that finds nothing.

Two of them exist because an earlier version of this skill got them wrong:

- **The pixel assertions.** The first version compared file **bytes** and was described as the check
  against "reports success while changing no pixels". A PNG re-encode changes bytes, so a mutant
  that drew nothing at all still passed. The suite now measures **ink inside the band**, on a light
  and a dark surface, skipping the rows the slate rule occupies — because measuring the whole band
  passed that same mutant a second time on the strength of the rule alone.
- **The footer decoys.** Five pages whose only `©` sits in markup are asserted **refused**, and five
  real footers spelled five different ways are asserted **accepted**. Reverting to the old
  raw-bytes search fails both assertions at once.

Every assertion has been mutation-tested: clamping instead of refusing, dropping the footer check,
reverting the parser to a grep, returning 0 on zero inputs, flattening nested directories, and
removing the HTML escaping each turn the suite red.

## References

- `references/render-contract.md` — placement, opacity band, the slate rule.
- `references/licensing-and-credits.md` — why the watermark never substitutes for the footer.
- `assets/project-profile.md` — the credit text and opacity for this project.
