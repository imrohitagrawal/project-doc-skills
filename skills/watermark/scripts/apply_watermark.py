#!/usr/bin/env python3
"""Apply the suite's credit furniture to EXPORTED artifacts.

WHY THIS EXISTS. The watermark is specified across three shared files and nothing
applies it:

    shared/project-profile.md   watermark: "<name> - <url>", watermark_opacity
    shared/render-contract.md   "go on the EXPORTED image, never on the diagram
                                 source", "in whitespace, never overlapping content",
                                 "a thin inset slate border"
    shared/licensing-and-credits.md  "decorative only and does not satisfy the
                                      footer requirement"

Every skill referenced the spec; none executed it.

THE MARK GOES IN AN ADDED MARGIN BAND, NOT OVER THE ARTWORK. This is the whole
design, and it is a correction. The first version drew the text into the
bottom-right corner of the image and claimed "never overlap content" was
"enforced structurally". It was not - it was a guess that the corner is empty,
and on a real export it ran straight across the content. A band added BELOW the
artwork cannot overlap it, because it is not drawn on it. Geometry, not hope.

THE INK IS READ OFF THE IMAGE, NOT HARDCODED. The first version hardcoded white.
On a light export - which is what a diagram is - white on near-white changed
ZERO pixels while the tool printed "watermarked N of N". Slate was the contract's
answer, but it fails the mirror case: it goes faint on a dark export. A skill
that runs on artifacts nobody has generated yet cannot bet on the background, so
the band's ink is derived from the image's own bottom edge: dark ink on a light
edge, light ink on a dark one. Slate survives as the hairline rule, which is what
the contract's "thin inset slate border" was protecting.

THE FOOTER CHECK PARSES HTML, IT DOES NOT GREP IT. A watermark is the signature
on a painting; the (c) footer is the receipt. The signature travels when the
picture leaves the gallery; the receipt stays with the paperwork. So an HTML page
with no footer is REFUSED - a page with a mark and no footer looks credited and
is not, which is worse than a page with neither. Grepping the raw bytes for a (c)
got this wrong in both directions: it accepted a page whose only copyright sign
sat in a code sample, and refused a real footer written &#xA9;.

DENOMINATOR RULE. "Processed 0 of 0" is a failure, not a success. A watermarker
that silently matches nothing would report green while every artifact ships
uncredited.

PROVE IT BITES:  python3 apply_watermark.py --self-test
"""

from __future__ import annotations

import argparse
import html as htmlmod
import os
import re
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
HTML_EXT = {".html", ".htm"}

# A source is not an export. render-contract.md is explicit that the furniture
# goes on the exported image, never the drawing it came from: marking a source
# poisons every future export made from it.
SOURCE_EXT = {".svg", ".drawio", ".excalidraw", ".mmd", ".puml"}

# The spec's bounds. Outside these the mark either cannot be read or fights the
# content, so this refuses rather than clamping - a silently corrected value is
# a value nobody notices is wrong.
OPACITY_MIN, OPACITY_MAX = 0.18, 0.30

SLATE = (100, 116, 139)          # #64748B, the contract's rule colour
INK_ON_LIGHT = (30, 41, 59)      # slate-900
INK_ON_DARK = (226, 232, 240)    # slate-200
# The floor for a DECORATIVE mark, not WCAG AA. AA (4.5:1) is arithmetically
# unreachable here and demanding it would be a claim the code cannot keep:
# compositing ink at alpha a moves the pixel only a fraction a of the way from
# the background, so at the contract's own 0.18-0.30 the best possible ratio on
# a plain band is about 1.4:1. WCAG exempts purely decorative text, and
# licensing-and-credits.md calls this mark decorative in as many words. 1.35:1 is
# set just under that ceiling: high enough that an invisible mark fails, low
# enough to be achievable at the minimum opacity the contract allows.
CONTRAST_FLOOR = 1.35

MARKER = "data-credit-watermark"


class Refusal(Exception):
    """A deliberate stop. Distinct from a crash so the caller can tell them apart."""


# --------------------------------------------------------------------------- #
# Profile
# --------------------------------------------------------------------------- #

def read_profile(path: Path) -> dict:
    """Pull the values from project-profile.md. Nothing is hardcoded: the skill
    is portable across every project, so name, URL and opacity all come from
    the profile."""
    if not path.is_file():
        raise Refusal(f"no profile at {path} - the values live there, not in this script")
    text = path.read_text(encoding="utf-8")
    out: dict = {}
    m = re.search(r'^watermark:[^\S\n]*"([^"]*)"', text, re.M)
    if m:
        out["watermark"] = m.group(1).strip()
    else:
        # Absent and blank are different states and must not look alike: a typo in
        # the key silently disabled the whole run in the first version.
        out["watermark_missing"] = True
    m = re.search(r"^watermark_opacity:[^\S\n]*([0-9]*\.?[0-9]+)[^\S\n]*(?:#.*)?$", text, re.M)
    if m:
        out["opacity"] = float(m.group(1))          # anchored: "0.22junk" no longer reads as 0.22
    return out


def check_opacity(value: float) -> None:
    if not (OPACITY_MIN <= value <= OPACITY_MAX):
        raise Refusal(
            f"opacity {value} is outside the specified range {OPACITY_MIN}-{OPACITY_MAX}. "
            "Refusing rather than clamping: a silently corrected value is one nobody notices."
        )


# --------------------------------------------------------------------------- #
# HTML footer detection - a parser, not a grep
# --------------------------------------------------------------------------- #

class _FooterFinder(HTMLParser):
    """Finds a copyright notice in TEXT the reader actually sees.

    Ignores <script>, <style>, <code>, <pre> and <template> content, ignores
    attribute values, and ignores comments - every one of which defeated the
    raw-bytes grep this replaces. Entities are resolved by the parser, so
    &#xA9; and &#x00A9; count exactly as much as a literal (c) sign.
    """

    # Not visible to a reader of the page: executable/markup content, the document
    # head, editable field defaults, and vector accessible names.
    SKIP = {"script", "style", "code", "pre", "template", "noscript",
            "head", "title", "textarea", "svg", "select", "option"}
    # A notice, not the word in prose. "Copyright law is complex" is an essay, not
    # a footer, so a bare `copyright` no longer counts - it needs a mark or a year.
    SIGN = re.compile(r"(©|Ⓒ|（c）|\(c\)|copr\.|copyright)\s*\(?\s*(?:©|\d{4})", re.I)

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_stack: list[str] = []
        self.hidden = 0
        self.found = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            # A STACK of tag names, not a counter. A counter never came back down
            # through an unclosed <pre>, so a real footer after one was skipped
            # and the page refused.
            self.skip_stack.append(tag)
            return
        style = dict(attrs).get("style") or ""
        if "display:none" in style.replace(" ", "") or dict(attrs).get("hidden") is not None:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in self.skip_stack:
            while self.skip_stack and self.skip_stack.pop() != tag:
                pass
        elif self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.skip_stack and not self.hidden and self.SIGN.search(data):
            self.found = True


def has_copyright_footer(html: str) -> bool:
    p = _FooterFinder()
    try:
        p.feed(html)
        p.close()
    except Exception:
        return False
    return p.found


# --------------------------------------------------------------------------- #
# Images
# --------------------------------------------------------------------------- #

def _rel_luma(rgb) -> float:
    """WCAG relative luminance."""
    def ch(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b) -> float:
    la, lb = _rel_luma(a), _rel_luma(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _composite(ink, bg, alpha: float):
    """The colour text of `ink` at `alpha` actually lands as, over `bg`."""
    return tuple(round(ink[i] * alpha + bg[i] * (1 - alpha)) for i in range(3))


def _edge_ink(im, opacity: float):
    """Band background and ink, derived from the image's own bottom edge.

    Two things this must get right, both learned by measurement:

    1. THE OPACITY IS REAL. Drawing text with an alpha in `fill` on an RGB canvas
       silently drops it - measured identical output at alpha 10 and alpha 255 -
       so the mark shipped at 100% against a contract that specifies 18-30%. The
       mark is now composited through an RGBA layer, and this function accounts
       for the alpha when it picks colours.

    2. LEGIBILITY IS GUARANTEED, NOT ASSUMED. A binary light/dark split left the
       mid-tones at 2.76:1 - a mid-grey screenshot got an unreadable mark while
       every check passed. The band is OUR pixels, so the one variable we own is
       moved: the background is pushed away from the ink until the COMPOSITED
       text clears CONTRAST_FLOOR at the requested opacity.

    Returns (band_bg, ink).
    """
    from PIL import ImageStat

    w, h = im.size
    edge = im.convert("RGB").crop((0, max(0, h - 8), w, h))
    r, g, b = (int(v) for v in ImageStat.Stat(edge).mean[:3])
    bg = (r, g, b)
    ink = INK_ON_LIGHT if _rel_luma(bg) > _rel_luma((128, 128, 128)) else INK_ON_DARK
    toward = 255 if ink == INK_ON_LIGHT else 0
    for _ in range(64):
        if contrast_ratio(_composite(ink, bg, opacity), bg) >= CONTRAST_FLOOR:
            break
        bg = tuple(round(c + (toward - c) * 0.08) for c in bg)
    return bg, ink


def watermark_image(src: Path, dst: Path, text: str, opacity: float) -> None:
    """Extend the canvas by a margin band and put the credit line in it.

    'Never overlap content' is true by construction: the band is new pixels
    below the artwork, so there is no content under the mark to overlap."""
    from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

    try:
        im = Image.open(src)
        im.load()
    except (UnidentifiedImageError, OSError) as e:
        # A file PIL cannot read is a refusal, not a traceback. In the first
        # version this aborted a whole directory run mid-write, leaving some
        # originals overwritten and the rest untouched, with no summary printed.
        raise Refusal(f"{src.name} is not a readable image ({type(e).__name__})") from None

    if im.info.get(MARKER) or (im.text.get(MARKER) if hasattr(im, "text") else None):
        # Idempotent. Without this, a second --in-place run read the FIRST band as
        # the bottom edge and stacked another: measured 328 -> 356 -> 384 px, and
        # on a dark export the ink flipped between runs.
        raise Refusal(f"{src.name} already carries the credit band - refusing to stack a second")

    im = im.convert("RGB")
    w, h = im.size
    size = max(11, round(min(w, h) * 0.020))
    band_h = int(size * 2.6)
    bg, ink = _edge_ink(im, opacity)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", size)
    except OSError:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", size)
        except OSError:
            font = ImageFont.load_default()

    out = Image.new("RGB", (w, h + band_h), bg)
    out.paste(im, (0, 0))

    # Composited through an RGBA layer so the opacity is genuinely applied.
    # Drawing straight onto the RGB canvas with an alpha in `fill` discards it.
    layer = Image.new("RGBA", out.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    box = d.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    d.text((max(size, w - tw - size), h + (band_h - th) // 2 - 2),
           text, font=font, fill=ink + (round(255 * opacity),))
    d.line([0, h, w, h], fill=SLATE + (round(255 * opacity),), width=1)
    out = Image.alpha_composite(out.convert("RGBA"), layer).convert("RGB")

    _atomic_save(out, dst)


def _atomic_save(im, dst: Path) -> None:
    """Write to a temp file in the destination directory, then rename.

    --in-place used to truncate the original and leave it unreadable if the run
    was interrupted: a 64MB image was measured at 18MB and corrupt after a kill.
    os.replace is atomic on the same filesystem, so the original survives until
    a complete file exists."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    suffix = dst.suffix.lower()
    # The temp name must be one collect() SKIPS. mkstemp's default "tmpXXXX.png"
    # matched the glob, so a killed run left a partial file that every later run
    # collected and refused - permanently reddening the directory until someone
    # deleted it by hand.
    fd, tmp = tempfile.mkstemp(dir=str(dst.parent), prefix=".wm-", suffix=suffix + ".part")
    os.close(fd)
    try:
        if suffix in {".jpg", ".jpeg"}:
            im.save(tmp, format="JPEG", quality=92)
        elif suffix == ".webp":
            im.save(tmp, format="WEBP", quality=92)
        else:
            from PIL import PngImagePlugin
            meta = PngImagePlugin.PngInfo()
            meta.add_text(MARKER, "1")      # so a second run can refuse instead of stacking
            im.save(tmp, format="PNG", pnginfo=meta)
        os.replace(tmp, dst)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def watermark_html(src: Path, dst: Path, text: str, opacity: float) -> None:
    """HTML gets the mark ONLY if it already carries a (c) footer.

    licensing-and-credits.md: the watermark is decorative and does not satisfy
    the footer requirement. A page with a mark and no footer looks credited and
    is not, which is worse than a page with neither."""
    raw = src.read_text(encoding="utf-8", errors="replace")
    if not has_copyright_footer(raw):
        raise Refusal(
            f"{src.name} has no visible © footer. The watermark is decorative and never "
            "substitutes for it - adding one here would make an uncredited page look "
            "credited. Add the footer first."
        )
    if MARKER in raw:
        # Idempotent, and it still WRITES: returning early without producing dst
        # made a publish step read an empty output directory and report success.
        _atomic_write_text(raw, dst)
        return

    mark = (
        f'<div {MARKER} aria-hidden="true" style="position:fixed;right:.75rem;bottom:.75rem;'
        f"font:400 11px/1.4 system-ui,sans-serif;opacity:{opacity};pointer-events:none;"
        f'user-select:none;z-index:1">{htmlmod.escape(text, quote=True)}</div>'
    )
    lower = raw.lower()
    idx = lower.rfind("</body>")
    if idx == -1:
        raise Refusal(
            f"{src.name} has no </body> - it looks like a fragment, not a page. Writing it "
            "unchanged would report success while marking nothing."
        )
    # rfind + slice: the first version used str.replace, which marked EVERY
    # </body> including ones inside <pre>, double-marking in a single run.
    _atomic_write_text(raw[:idx] + mark + raw[idx:], dst)


def _atomic_write_text(text: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dst.parent), suffix=dst.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, dst)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


# --------------------------------------------------------------------------- #
# Walking the target
# --------------------------------------------------------------------------- #

def collect(target: Path) -> list[Path]:
    """Collects sources too, deliberately: a file the tool must not process is a
    REFUSAL, not an absence. Pointing it at a directory of drawings used to
    report "found 0", which reads like an empty directory."""
    if target.is_file():
        return [target]
    if not target.is_dir():
        raise Refusal(f"{target} is neither a file nor a directory")
    keep = IMAGE_EXT | HTML_EXT | SOURCE_EXT
    root = target.resolve()
    # NOTE: a sweep of ".wm-*.part" used to run here. REMOVED 2026-08-12 — it
    # deleted any file matching that glob anywhere under the target, with no
    # ownership, age or content check, on a run that is otherwise non-destructive.
    # It was also dead: ".part" is not in the keep-set, so the rename alone
    # already stops litter being collected, and mutating the sweep to `pass` left
    # the whole suite green. A tool that destroys data it did not create, in
    # service of a problem that was already solved, is strictly worse than the
    # litter it was cleaning up.
    out = []
    for p in sorted(target.rglob("*")):
        if p.suffix.lower() not in keep or not p.is_file():
            continue
        # A symlink pointing outside the target used to rewrite a file elsewhere
        # on disk, silently, on an --in-place run.
        try:
            if not p.resolve().is_relative_to(root):
                continue
        except (OSError, ValueError):
            continue
        out.append(p)
    return out


def _destination(src: Path, target: Path, out_dir: Path | None, in_place: bool) -> Path:
    if in_place:
        return src
    base = out_dir or (target.parent if target.is_file() else target.parent / "watermarked")
    if target.is_file():
        return base / src.name
    # Preserve the tree. Flattening onto src.name made a/chart.png and b/chart.png
    # overwrite each other while the run reported both as done.
    return base / src.relative_to(target)


def run(target: Path, profile: Path, out_dir: Path | None, in_place: bool) -> int:
    prof = read_profile(profile)
    if prof.get("watermark_missing"):
        raise Refusal(
            f"{profile} has no 'watermark:' key. Absent is not the same as blank - a renamed "
            "or mistyped key would otherwise disable every run and still exit 0."
        )
    text = prof.get("watermark", "").strip()
    opacity = prof.get("opacity", 0.22)
    check_opacity(opacity)

    found = collect(target)
    if not found:
        print(f"x found 0 artifacts under {target} - nothing was watermarked.", file=sys.stderr)
        return 1
    if not text:
        # Blank is a real configuration, but it must still report the denominator
        # so "nothing to do" can never be mistaken for "everything done".
        print(f"watermark is blank in the profile - {len(found)} artifact(s) left unmarked, "
              "by configuration.")
        return 0

    done, refused = 0, []
    for src in found:
        if src.suffix.lower() in SOURCE_EXT:
            refused.append(f"{src} is a source, not an export")
            continue
        dst = _destination(src, target, out_dir, in_place)
        try:
            if src.suffix.lower() in HTML_EXT:
                watermark_html(src, dst, text, opacity)
            else:
                watermark_image(src, dst, text, opacity)
            done += 1
        except Refusal as e:
            refused.append(str(e))
        except OSError as e:
            refused.append(f"{src}: {type(e).__name__}: {e}")

    print(f"watermarked {done} of {len(found)} artifact(s) at opacity {opacity}")
    for r in refused:
        print(f"  refused: {r}")
    return 1 if refused else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply the suite's credit furniture to exports.")
    ap.add_argument("target", nargs="?", help="an exported image/HTML file, or a directory")
    ap.add_argument("--profile", default="assets/project-profile.md")
    ap.add_argument("--out", help="output directory (default: <target>/../watermarked)")
    ap.add_argument("--in-place", action="store_true", help="overwrite the exports")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        from selftest import self_test          # noqa: PLC0415  (kept out of production runs)
        return self_test()
    if not a.target:
        ap.error("a target is required (or --self-test)")
    try:
        return run(Path(a.target), Path(a.profile), Path(a.out) if a.out else None, a.in_place)
    except Refusal as e:
        print(f"x refused: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
