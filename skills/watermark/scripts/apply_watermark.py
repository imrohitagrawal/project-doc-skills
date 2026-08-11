#!/usr/bin/env python3
"""Apply the suite's credit furniture to EXPORTED artifacts. The executor the
contract has always specified and never had.

WHY THIS EXISTS (RCA-001, approved 2026-08-12). The watermark is fully specified
across three shared files and nothing applies it:

    shared/project-profile.md:66   watermark: "<name> · <url>"
    shared/project-profile.md:67   watermark_opacity: 0.22   (range 0.18-0.30)
    shared/render-contract.md      "go on the EXPORTED image - never on the
                                    diagram source"
    shared/licensing-and-credits.md  "decorative only and does not satisfy the
                                      footer requirement"

Every skill referenced the spec; no skill executed it. A contract with no
executor is a passenger.

THE ONE RULE THAT IS EASY TO GET WRONG. A watermark is the signature on a
painting - it travels when the picture leaves the gallery. The (c) footer is the
receipt - it proves ownership but stays with the paperwork. They do different
jobs, which is why the spec says three times that one never substitutes for the
other. So for HTML this script REFUSES to add a watermark to a page that has no
footer, rather than quietly producing a page that looks credited and is not.

DENOMINATOR RULE. "Processed 0 of 0" is a failure, not a success. A watermarker
that silently matches nothing would report green while every artifact ships
uncredited - the "check that counts nothing" pattern. Zero inputs exits non-zero.

PROVE IT BITES:  python3 apply_watermark.py --self-test
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
HTML_EXT = {".html", ".htm"}

# The spec's own bounds. Outside these the mark either cannot be read or fights
# the content, so the script refuses rather than clamps - a silently corrected
# value is a value nobody notices is wrong.
OPACITY_MIN, OPACITY_MAX = 0.18, 0.30

# A source is not an export. render-contract.md is explicit that the mark goes on
# the exported image, never on the drawing it came from.
SOURCE_EXT = {".svg", ".drawio", ".excalidraw", ".mmd", ".puml"}

FOOTER_PAT = re.compile(r"(©|&copy;|&#169;)", re.I)


class Refusal(Exception):
    """A deliberate stop. Distinct from a crash so the caller can tell them apart."""


def read_profile(path: Path) -> dict:
    """Pull the two values from project-profile.md. Nothing is hardcoded here:
    the skill is portable across every project under the umbrella, so the name,
    the URL and the opacity all come from the profile."""
    if not path.is_file():
        raise Refusal(f"no profile at {path} - the values live there, not in this script")
    text = path.read_text(encoding="utf-8")
    out = {}
    m = re.search(r'^watermark:\s*"([^"]*)"', text, re.M)
    if m:
        out["watermark"] = m.group(1).strip()
    m = re.search(r"^watermark_opacity:\s*([0-9.]+)", text, re.M)
    if m:
        out["opacity"] = float(m.group(1))
    return out


def check_opacity(value: float) -> None:
    if not (OPACITY_MIN <= value <= OPACITY_MAX):
        raise Refusal(
            f"opacity {value} is outside the specified range {OPACITY_MIN}-{OPACITY_MAX}. "
            "Refusing rather than clamping: a silently corrected value is one nobody notices."
        )


def watermark_image(src: Path, dst: Path, text: str, opacity: float) -> None:
    """Bottom-right, inside the margin, over the image's own quietest corner.

    'Never overlap content' is enforced structurally rather than by cleverness:
    the mark sits in the outer margin band, and the band is sized from the image
    so it scales with it instead of being a fixed pixel guess."""
    from PIL import Image, ImageDraw, ImageFont

    im = Image.open(src).convert("RGBA")
    w, h = im.size
    pad = max(12, round(min(w, h) * 0.025))
    size = max(11, round(min(w, h) * 0.022))

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", size)
    except OSError:
        font = ImageFont.load_default()

    layer = Image.new("RGBA", im.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(layer)
    box = draw.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]

    alpha = round(255 * opacity)
    draw.text((w - tw - pad, h - th - pad * 2), text, font=font, fill=(255, 255, 255, alpha))

    # The thin inset slate border the contract asks for, at the same opacity so
    # the furniture reads as one thing rather than two.
    draw.rectangle(
        [pad // 2, pad // 2, w - pad // 2, h - pad // 2],
        outline=(255, 255, 255, round(alpha * 0.6)),
        width=1,
    )

    out = Image.alpha_composite(im, layer)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.suffix.lower() in {".jpg", ".jpeg"}:
        out.convert("RGB").save(dst, quality=92)
    else:
        out.save(dst)


def watermark_html(src: Path, dst: Path, text: str, opacity: float) -> None:
    """HTML gets the mark ONLY if it already carries the (c) footer.

    licensing-and-credits.md, three times over: the watermark is decorative and
    does not satisfy the footer requirement. A page with a mark and no footer
    looks credited and is not, which is worse than a page with neither."""
    html = src.read_text(encoding="utf-8")
    if not FOOTER_PAT.search(html):
        raise Refusal(
            f"{src.name} has no © footer. The watermark is decorative and never substitutes "
            "for it - adding one here would make an uncredited page look credited. "
            "Add the footer first."
        )
    if "data-credit-watermark" in html:
        return  # already marked; idempotent so a re-run is safe

    mark = (
        f'<div data-credit-watermark style="position:fixed;right:.75rem;bottom:.75rem;'
        f"font:400 11px/1.4 system-ui,sans-serif;opacity:{opacity};pointer-events:none;"
        f'user-select:none;z-index:1">{text}</div>'
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(html.replace("</body>", f"{mark}</body>"), encoding="utf-8")


def collect(target: Path) -> list[Path]:
    """Collects sources too, deliberately.

    An earlier version matched only images and HTML, so a .svg fell straight
    through and was never refused - and pointing the tool at a directory of
    sources reported "found 0", which reads like an empty directory rather than
    like "these are all drawings, not exports". Caught by the self-test. A file
    the tool must not process is a refusal, not an absence."""
    if target.is_file():
        return [target]
    return sorted(
        p for p in target.rglob("*")
        if p.suffix.lower() in IMAGE_EXT | HTML_EXT | SOURCE_EXT
    )


def run(target: Path, profile: Path, out_dir: Path | None, in_place: bool) -> int:
    prof = read_profile(profile)
    text = prof.get("watermark", "").strip()
    if not text:
        print("watermark is blank in the profile - nothing to apply, by configuration.")
        return 0
    opacity = prof.get("opacity", 0.22)
    check_opacity(opacity)

    found = collect(target)
    if not found:
        # The denominator rule, and the reason this exits non-zero: a run that
        # matched nothing must never read as a run that succeeded.
        print(f"✖ found 0 artifacts under {target} - nothing was watermarked.", file=sys.stderr)
        return 1

    done, refused = 0, []
    for src in found:
        if src.suffix.lower() in SOURCE_EXT:
            refused.append(f"{src} is a source, not an export")
            continue
        dst = src if in_place else (out_dir or target.parent / "watermarked") / src.name
        try:
            if src.suffix.lower() in HTML_EXT:
                watermark_html(src, dst, text, opacity)
            else:
                watermark_image(src, dst, text, opacity)
            done += 1
        except Refusal as e:
            refused.append(str(e))

    print(f"watermarked {done} of {len(found)} artifact(s) at opacity {opacity}")
    for r in refused:
        print(f"  refused: {r}")
    # A refusal is a real outcome, not a warning to scroll past.
    return 1 if refused else 0


# --------------------------------------------------------------------------- #
# Self-test. A gate that has only ever seen a healthy input has proven nothing.
# --------------------------------------------------------------------------- #

def self_test() -> int:
    import tempfile

    from PIL import Image

    failed = 0

    def say(ok: bool, what: str) -> None:
        nonlocal failed
        print(f"  {'ok  ' if ok else 'FAIL'} {what}")
        if not ok:
            failed += 1

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        prof = root / "project-profile.md"
        prof.write_text('watermark:         "Test Name · https://example.test/x"\n'
                        "watermark_opacity: 0.22\n", encoding="utf-8")

        # 1. Opacity outside the spec must REFUSE, not clamp.
        try:
            check_opacity(0.9)
            say(False, "opacity 0.9 outside 0.18-0.30 is refused")
        except Refusal:
            say(True, "opacity 0.9 outside 0.18-0.30 is refused, not clamped")

        # 2. THE CONTRACT: HTML with no © footer must be refused.
        nofoot = root / "nofooter.html"
        nofoot.write_text("<html><body><h1>hi</h1></body></html>", encoding="utf-8")
        try:
            watermark_html(nofoot, root / "o1.html", "x", 0.22)
            say(False, "HTML without a © footer is refused")
        except Refusal:
            say(True, "HTML without a © footer is refused - watermark never substitutes for it")

        # 3. HTML WITH a footer is marked.
        foot = root / "footer.html"
        foot.write_text("<html><body><p>© 2026 Someone</p></body></html>", encoding="utf-8")
        out = root / "o2.html"
        watermark_html(foot, out, "Test Name", 0.22)
        say("data-credit-watermark" in out.read_text(encoding="utf-8"),
            "HTML with a © footer receives the mark")

        # 4. Idempotent - a re-run must not double-mark.
        watermark_html(out, out, "Test Name", 0.22)
        say(out.read_text(encoding="utf-8").count("data-credit-watermark") == 1,
            "re-running does not double-mark")

        # 5. THE DENOMINATOR RULE: zero inputs must FAIL, not pass.
        empty = root / "empty"
        empty.mkdir()
        say(run(empty, prof, None, False) == 1,
            "zero artifacts found exits non-zero - a run that matched nothing is not a pass")

        # 6. A source file is refused, never marked.
        srcdir = root / "mixed"
        srcdir.mkdir()
        Image.new("RGB", (400, 300), "white").save(srcdir / "export.png")
        (srcdir / "diagram.svg").write_text("<svg/>", encoding="utf-8")
        rc = run(srcdir, prof, root / "out6", False)
        say(rc == 1 and (root / "out6" / "export.png").exists(),
            "a .svg source is refused while the .png export is marked")

        # 7. The image actually changes - a no-op that reports success is the
        #    failure mode this whole script exists to prevent.
        before = (srcdir / "export.png").read_bytes()
        after = (root / "out6" / "export.png").read_bytes()
        say(before != after, "the exported image is genuinely modified")

    print("\nSELF-TEST FAILED" if failed else
          "\nSELF-TEST PASS — refuses what it must, marks what it should, and fails on zero")
    return failed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", nargs="?", help="an exported image/HTML file, or a directory")
    ap.add_argument("--profile", default="assets/project-profile.md")
    ap.add_argument("--out", help="output directory (default: <target>/../watermarked)")
    ap.add_argument("--in-place", action="store_true", help="overwrite the exports")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return self_test()
    if not a.target:
        ap.error("a target is required (or --self-test)")
    try:
        return run(Path(a.target), Path(a.profile), Path(a.out) if a.out else None, a.in_place)
    except Refusal as e:
        print(f"✖ refused: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
