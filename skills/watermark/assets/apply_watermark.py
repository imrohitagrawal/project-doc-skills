#!/usr/bin/env python3
"""
apply_watermark.py — stamp the decorative credit watermark and a thin inset
slate border onto an EXPORTED image (render-contract.md:151-153).

Import it and call apply_watermark(in_path, out_path, text, opacity), or run
this file directly:

    python3 apply_watermark.py IN.png OUT.png --text "Name · link" --opacity 0.22

WHY THIS EXISTS (RCA-001). The watermark is fully specified in
shared/project-profile.md (the `watermark`/`watermark_opacity` fields) and
shared/render-contract.md ("Exported images carry the credit furniture...
never on the diagram source"), and shared/licensing-and-credits.md is explicit
that a watermark is DECORATIVE ONLY and never substitutes for the © licence
footer. The HTML case is already handled — both project-faq/assets/
faq_generator.py and usage-guide/assets/usage_guide_generator.py already
render the {{watermark}} decorative line, and shared/verify.py already
hard-fails a public page missing the © footer independent of watermark
presence (verify.py:468-475). What had no executor was the IMAGE case: a
diagram or social-preview image, once exported, carries nothing. This script
is that executor. (RCA-001's original "no skill executes it" framing is
correct for images and was already stale for HTML by the time this shipped —
recorded, not silently carried forward.)

WHAT IT MUST NOT DO (RCA-001, verbatim):
  - Not substitute for the licence footer — this script never touches HTML.
  - Not watermark diagram SOURCES — only the exported raster image.
  - Not silently skip an image it could not process — every failure path
    below raises or exits non-zero with a specific message; there is no
    bare `except: pass`.

DEPENDENCY, DOCUMENTED AND DELIBERATE. Every other script in this suite is
stdlib-only (tests/run-golden.py: "No third-party deps") because a skill's
core verifier must run anywhere. Compositing translucent text onto a raster
image with alpha blending has no reasonable stdlib path. Pillow is this ONE
skill's own, isolated, checked dependency — never silently assumed: the
import is guarded and fails LOUD with the exact install command if missing,
never a silent no-op.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print(
        "apply_watermark.py: Pillow is required and is not installed.\n"
        "  pip install Pillow\n"
        "Per RCA-001, an image this skill cannot process must fail loud, "
        "never ship unwatermarked silently.",
        file=sys.stderr,
    )
    sys.exit(2)

# project-profile.md: "0.18-0.30 recommended; never overlap content".
MIN_OPACITY = 0.18
MAX_OPACITY = 0.30
DEFAULT_OPACITY = 0.22

# render-contract.md: "a thin inset slate border" on the exported image.
# Slate, not the brand palette — the border is credit furniture, not content.
SLATE = (100, 116, 139)  # #64748b
BORDER_WIDTH = 2
BORDER_INSET = 6

MARGIN = 14  # matches the HTML watermark's own right/bottom offset (14px, 10px)

# "Never overlap content" cannot be satisfied by a FIXED corner — proved
# wrong against the real og.png, whose bottom-right holds a live button.
# Measured: content-free corners read 0.0 pixel variance; the button/panel
# corners read 11,519 and 28,710. A flat threshold, not a guess, decides
# "empty enough" — the SPEC's own words, made checkable.
CORNER_VARIANCE_LIMIT = 50.0
CANDIDATE_CORNERS = ("bottom-right", "bottom-left", "top-right", "top-left")


def _load_font(size: int):
    # A specific installed font would make this script non-portable across
    # machines; Pillow's bundled default is guaranteed present everywhere
    # Pillow itself is. Bold text at small size on a translucent layer reads
    # fine without hinting a particular family.
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # Pillow <9.2 load_default() takes no size argument.
        return ImageFont.load_default()


def _corner_variance(rgb_image, box_w: int, box_h: int, corner: str):
    """Pixel-colour variance of the named corner region — a proxy for
    'empty': a flat background reads ~0, real content (a button, a panel
    edge) reads in the thousands (measured against the real og.png)."""
    w, h = rgb_image.size
    x0 = 0 if "left" in corner else w - box_w
    y0 = 0 if "top" in corner else h - box_h
    box = (x0, y0, x0 + box_w, y0 + box_h)
    pixels = list(rgb_image.crop(box).getdata())
    n = len(pixels)
    mean = tuple(sum(p[i] for p in pixels) / n for i in range(3))
    var = sum(sum((p[i] - mean[i]) ** 2 for i in range(3)) for p in pixels) / n
    return var, (x0 + MARGIN, y0 + MARGIN)


def _find_safe_corner(rgb_image, box_w: int, box_h: int):
    """The lowest-variance candidate corner, if any clears
    CORNER_VARIANCE_LIMIT; otherwise (None, None) — never a guess."""
    scored = [(c, *_corner_variance(rgb_image, box_w, box_h, c)) for c in CANDIDATE_CORNERS]
    scored.sort(key=lambda t: t[1])
    best_corner, best_var, best_xy = scored[0]
    if best_var > CORNER_VARIANCE_LIMIT:
        return None, (None, None)
    return best_corner, best_xy


def apply_watermark(
    in_path: str,
    out_path: str,
    text: str,
    opacity: float = DEFAULT_OPACITY,
) -> None:
    """Composite TEXT onto the image at IN_PATH, in the bottom-right margin,
    at OPACITY, plus a thin inset slate border; write the result to
    OUT_PATH. Raises on any failure — never returns having silently skipped."""
    if not text or not text.strip():
        raise ValueError("apply_watermark: empty watermark text — refusing to stamp nothing")
    if not (MIN_OPACITY <= opacity <= MAX_OPACITY):
        raise ValueError(
            f"apply_watermark: opacity {opacity} outside the specified "
            f"{MIN_OPACITY}-{MAX_OPACITY} range (project-profile.md)"
        )
    src = Path(in_path)
    if not src.is_file():
        raise FileNotFoundError(f"apply_watermark: no such file: {in_path}")

    base = Image.open(src).convert("RGBA")
    w, h = base.size

    # The slate border first — an inset rectangle, drawn directly (opaque,
    # it is furniture, not a translucent overlay).
    bordered = base.copy()
    draw = ImageDraw.Draw(bordered)
    draw.rectangle(
        [BORDER_INSET, BORDER_INSET, w - 1 - BORDER_INSET, h - 1 - BORDER_INSET],
        outline=SLATE + (255,),
        width=BORDER_WIDTH,
    )

    font_size = max(10, min(w, h) // 28)
    font = _load_font(font_size)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = probe.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    box_w, box_h = text_w + 2 * MARGIN, text_h + 2 * MARGIN

    rgb = base.convert("RGB")
    corner, (x, y) = _find_safe_corner(rgb, box_w, box_h)
    if corner is None:
        raise ValueError(
            f"apply_watermark: no corner of {w}x{h} is empty enough for "
            f"'{text}' (every candidate exceeds the variance floor "
            f"{CORNER_VARIANCE_LIMIT}) — refusing to overlap content by "
            "guessing a placement; pass an explicit safe region instead"
        )

    # The watermark text on its OWN transparent layer, composited at OPACITY
    # as a layer alpha — not a per-pixel font-color alpha — so the specified
    # opacity is exactly what a contrast/inspection tool would measure,
    # regardless of font rendering internals.
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    layer_draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    alpha = layer.getchannel("A").point(lambda a: int(a * opacity))
    layer.putalpha(alpha)

    out = Image.alpha_composite(bordered, layer)
    if src.suffix.lower() in (".jpg", ".jpeg"):
        out.convert("RGB").save(out_path, quality=90, optimize=True)
    else:
        # An un-quantized RGBA save against a palette-mode source (og.png
        # ships 8-bit indexed, per its own PNG optimizer) more than DOUBLED
        # the file size in testing (72KB -> 189KB) — `compress_level=9`
        # alone did not help (203KB): zlib compresses bytes, not colour
        # count, and the real cost is the color SPACE, not the compression
        # level. Alpha is dropped here deliberately — an OG/social-preview
        # image is always composited opaque by every consumer, so the
        # export can flatten and quantize like the source did. 256-colour
        # adaptive palette measured close to the source's own size while
        # keeping the translucent watermark blend free of banding (the
        # blending happens in RGBA above, quantization is the LAST step).
        flat = Image.new("RGB", out.size, (255, 255, 255))
        flat.paste(out, mask=out.getchannel("A"))
        flat.convert("P", palette=Image.ADAPTIVE, colors=256).save(
            out_path, optimize=True,
        )


def _main() -> int:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--text", required=True, help="the watermark credit line (profile `watermark`)")
    p.add_argument("--opacity", type=float, default=DEFAULT_OPACITY)
    args = p.parse_args()
    try:
        apply_watermark(args.input, args.output, args.text, args.opacity)
    except Exception as e:  # noqa: BLE001 — CLI boundary: report and fail loud, never swallow
        print(f"apply_watermark.py: FAILED — {e}", file=sys.stderr)
        return 1
    print(f"apply_watermark.py: wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
