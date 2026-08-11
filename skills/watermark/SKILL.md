---
name: watermark
description: Apply the suite's credit furniture — the decorative watermark and the thin inset border — to EXPORTED artifacts, and enforce that HTML pages carrying a watermark also carry the © footer. A post-processing step that runs AFTER an authoring skill has produced and verified its exports; it never authors or edits content. Use this whenever diagrams, images, OG cards or finished HTML pages are about to be published, shared, or mirrored, and need the credit line the render contract specifies. It reads every value from project-profile.md, refuses a diagram source passed instead of an export, refuses an opacity outside the specified range, refuses an HTML page that has no © footer, and fails when it finds nothing to process. NOT for writing documentation (use the authoring skills) and NOT for publishing (use publish-mirror).
---

# Watermark & Credit Furniture

Version: 1.0.0 · see `CHANGELOG.md`.

The credit furniture was **specified in this suite from the start and never applied.** The values
sit in `assets/project-profile.md`, the placement rule in `references/render-contract.md`, and the
"never substitutes for the footer" rule in `references/licensing-and-credits.md` — and every skill
referenced them while none executed them. **A contract with no executor is a passenger.** This
skill is the executor.

Read these two first, every time:

- `references/render-contract.md` — where the furniture goes. The one line that governs this
  skill: it goes on the **exported** image, *never* on the diagram source.
- `references/licensing-and-credits.md` — the watermark is **decorative and does not satisfy the
  footer requirement**. It says this three times. So does this skill.

---

## The one idea, and why it is not obvious

**A watermark is the signature on a painting. The © footer is the receipt.**

The signature travels with the picture when it leaves the gallery. The receipt proves ownership
but stays with the paperwork. Screenshot a diagram into a slide deck and the receipt is gone —
only the signature survives.

That is why the suite insists they are different things, and why this skill will **refuse** to
put a watermark on an HTML page that has no footer. A page with a mark and no footer *looks*
credited and is not, which is worse than a page with neither: it stops anyone from noticing the
gap.

---

## What it does

| | |
|---|---|
| **Input** | An exported image or HTML file, or a directory of them, plus `assets/project-profile.md` for every value |
| **Images** | Watermark text at the configured opacity in the outer margin band, plus the thin inset slate border. The band is sized from the image, so it scales instead of being a fixed pixel guess — that is how *"never overlap content"* is enforced structurally rather than by cleverness |
| **HTML** | The same mark, **only if a © footer is already present**. Idempotent: re-running never double-marks |
| **Portable** | Reads the profile. Hard-codes no name, no URL, no opacity, no path. Reusable on every project under the umbrella |

## What it refuses, and why each refusal exists

- **A diagram source** (`.svg`, `.drawio`, `.excalidraw`, `.mmd`, `.puml`). The render contract is
  explicit that furniture belongs on exports. Marking a source poisons every future export from it.
- **An opacity outside 0.18–0.30.** It refuses rather than clamping, because a silently corrected
  value is one nobody notices is wrong.
- **HTML with no © footer.** See above — this is the contract, not a preference.
- **Finding nothing.** A run that matched zero artifacts exits **non-zero**. A watermarker that
  silently finds nothing would report success while every artifact ships uncredited, which is the
  "check that counts nothing" pattern. Zero is a failure.

## What it must never do

- Substitute for the licence footer.
- Touch a diagram source.
- Silently skip a file it could not process — every skip is reported as a refusal with its reason.

---

## Running it

```bash
# One export
python3 scripts/apply_watermark.py docs/exports/architecture.png

# A directory, writing alongside rather than over the originals
python3 scripts/apply_watermark.py docs/exports/ --out docs/exports/watermarked

# Overwrite the exports in place, once you trust it
python3 scripts/apply_watermark.py docs/exports/ --in-place

# Prove it bites before you rely on it
python3 scripts/apply_watermark.py --self-test
```

`--profile` defaults to `assets/project-profile.md`, the copy the build stages into every skill.

## Prove it bites

`AGENTS.md`: *a gate that has never failed has proven nothing.* The self-test plants each failure
shape and asserts the refusal, including the two that matter most — an HTML page with no footer,
and a run that finds nothing:

```
ok   opacity 0.9 outside 0.18-0.30 is refused, not clamped
ok   HTML without a © footer is refused — watermark never substitutes for it
ok   HTML with a © footer receives the mark
ok   re-running does not double-mark
ok   zero artifacts found exits non-zero — a run that matched nothing is not a pass
ok   a .svg source is refused while the .png export is marked
ok   the exported image is genuinely modified
```

That last one exists because a watermarker that reports success while changing no pixels is
precisely the failure this skill was written to end. The `.svg` assertion caught a real bug during
development: sources were not being collected at all, so they fell through silently instead of
being refused.

---

## Where it fits

Runs **after** an authoring skill has produced and verified its exports, and **before**
`publish-mirror` sends them anywhere. The order matters: `publish-mirror`'s inputs are described
as *"diagrams exported to PNG/SVG (watermarked, framed)"* — this is the step that makes that
sentence true.

## Scope decision on record

Approved 2026-08-12 (RCA-001) covering **images and HTML pages both**. On the site that prompted
it, the scope was then narrowed by measurement rather than assumption: only two files actually
leave that site — the OG share card and the favicon — so the OG card is the whole real case. The
in-page figures are inline `<svg>` markup inside the HTML, which cannot travel on its own and
already sits inside a page carrying the footer. **Watermark what leaves. Measure what leaves
before deciding.**
