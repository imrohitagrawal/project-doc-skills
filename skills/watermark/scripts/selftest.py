#!/usr/bin/env python3
"""Self-test for apply_watermark.py. Run: python3 apply_watermark.py --self-test

A gate that has only ever seen a healthy input has proven nothing, so every
assertion here plants a failure shape and asserts the refusal.

WHY THIS FILE EXISTS SEPARATELY. The first version's assertion 7 compared
file BYTES and was singled out in SKILL.md as the one guarding against "reports
success while changing no pixels". It did the opposite: a PNG re-encode changes
bytes, so replacing the compositing step with `out = im` - the watermarker
drawing literally nothing - still passed. The suite now compares PIXELS, on both
a light and a dark surface, because the failure it missed was colour-dependent.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from apply_watermark import (
    CONTRAST_FLOOR, Refusal, check_opacity, contrast_ratio, has_copyright_footer, run,
    watermark_html, watermark_image,
)

PROFILE = 'watermark:         "Test Name · https://example.test/x"\nwatermark_opacity: 0.22\n'


def self_test() -> int:
    from PIL import Image, ImageChops

    failed = 0

    def say(ok: bool, what: str) -> None:
        nonlocal failed
        print(f"  {'ok  ' if ok else 'FAIL'} {what}")
        if not ok:
            failed += 1

    def pixels_changed(before: Path, after: Path) -> int:
        """The real question: did anything visible happen? Compares the artwork
        region only, so the added band cannot mask a no-op inside it."""
        a = Image.open(before).convert("RGB")
        b = Image.open(after).convert("RGB").crop((0, 0, a.size[0], a.size[1]))
        diff = ImageChops.difference(a, b)
        return max(ch.getextrema()[1] for ch in diff.split())

    def band_ink_differs(path: Path, artwork_h: int) -> int:
        """Did the TEXT actually get drawn into the band?

        Skips the first 3 rows of the band, which carry the slate rule. The first
        version of this assertion measured the whole band and passed a mutant that
        drew no text at all - the rule line alone gave it contrast 65. Measuring
        the region the text occupies is the only thing that separates 'marked'
        from 'ruled'."""
        im = Image.open(path).convert("RGB")
        band = im.crop((0, artwork_h + 3, im.size[0], im.size[1]))
        ex = [ch.getextrema() for ch in band.split()]
        return max(hi - lo for lo, hi in ex)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        prof = root / "project-profile.md"
        prof.write_text(PROFILE, encoding="utf-8")

        # 1. Opacity outside the spec REFUSES rather than clamping.
        try:
            check_opacity(0.9)
            say(False, "opacity 0.9 outside 0.18-0.30 is refused")
        except Refusal:
            say(True, "opacity 0.9 outside 0.18-0.30 is refused, not clamped")

        # 2. THE CONTRACT: HTML with no visible footer is refused.
        nofoot = root / "nofooter.html"
        nofoot.write_text("<html><body><h1>hi</h1></body></html>", encoding="utf-8")
        try:
            watermark_html(nofoot, root / "o1.html", "x", 0.22)
            say(False, "HTML without a © footer is refused")
        except Refusal:
            say(True, "HTML without a © footer is refused - a watermark never substitutes for it")

        # 3. The footer check reads TEXT, not raw bytes. These five defeated the grep.
        decoys = [
            ('<html><body><!-- add the &copy; footer later --><p>x</p></body></html>', "an HTML comment"),
            ('<html><body><script>var s="©";</script><p>x</p></body></html>', "a script string"),
            ('<html><body><pre><code>printf("©")</code></pre><p>x</p></body></html>', "a code sample"),
            ('<html><body><style>p:after{content:"©"}</style><p>x</p></body></html>', "a CSS property"),
            ('<html><body><img alt="the © symbol" src="x.png"><p>x</p></body></html>', "an alt attribute"),
        ]
        bad = [w for src, w in decoys if has_copyright_footer(src)]
        say(not bad, f"a © in markup is not a footer - all 5 decoys refused{'' if not bad else f' (accepted: {bad})'}")

        # 4. ...and a real footer is recognised however it is spelled.
        reals = [
            ("<html><body><footer>&#xA9; 2026 Someone</footer></body></html>", "&#xA9;"),
            ("<html><body><footer>&#x00A9; 2026 Someone</footer></body></html>", "&#x00A9;"),
            ("<html><body><footer>&copy; 2026 Someone</footer></body></html>", "&copy;"),
            ("<html><body><footer>Copyright 2026 Someone</footer></body></html>", "the word Copyright"),
            ("<html><body><footer>© 2026 Someone</footer></body></html>", "a literal ©"),
        ]
        missed = [w for src, w in reals if not has_copyright_footer(src)]
        say(not missed, f"a real footer is found however spelled - all 5 accepted{'' if not missed else f' (missed: {missed})'}")

        # 5. A page with a footer is marked, and the mark is escaped.
        foot = root / "footer.html"
        foot.write_text("<html><body><p>© 2026 Someone</p></body></html>", encoding="utf-8")
        out = root / "o2.html"
        watermark_html(foot, out, '</div><script>alert(1)</script>', 0.22)
        got = out.read_text(encoding="utf-8")
        say("data-credit-watermark" in got and "<script>alert(1)" not in got,
            "a footered page is marked, and a hostile profile value is escaped, not injected")

        # 6. Idempotent - and it still writes the destination.
        out2 = root / "o3.html"
        watermark_html(out, out2, "Test Name", 0.22)
        say(out2.exists() and out2.read_text(encoding="utf-8").count("data-credit-watermark") == 1,
            "re-running does not double-mark, and still produces the output file")

        # 7. A fragment with no </body> is refused, not written unchanged.
        frag = root / "frag.html"
        frag.write_text("<div><p>© 2026 Someone</p></div>", encoding="utf-8")
        try:
            watermark_html(frag, root / "o4.html", "x", 0.22)
            say(False, "a fragment with no </body> is refused")
        except Refusal:
            say(True, "a fragment with no </body> is refused - writing it unchanged would report a false success")

        # 8. THE ONE THAT MATTERED: the mark is present AND READABLE on every
        #    background, measured as a WCAG ratio rather than a raw pixel range.
        #    A raw range passed a mutant with hardcoded dark ink on a dark band at
        #    1.26:1 - invisible - because the band around it still had spread.
        #    Mid-grey is in the list because a binary light/dark split left the
        #    mid-tones at 2.76:1 while every check passed.
        surfaces = [("light", (248, 250, 252)), ("dark", (14, 19, 34)),
                    ("mid-grey", (139, 139, 139)), ("edge-of-split", (141, 141, 141))]
        for name, colour in surfaces:
            base = root / f"{name}.png"
            Image.new("RGB", (600, 300), colour).save(base)
            dst = root / f"{name}-marked.png"
            watermark_image(base, dst, "Test Name · https://example.test/x", 0.22)
            im = Image.open(dst).convert("RGB")
            band = im.crop((0, 303, im.size[0], im.size[1]))
            px = list(band.get_flattened_data()) if hasattr(band, "get_flattened_data") else list(band.getdata())
            bg = max(set(px), key=px.count)                       # the band's own field
            darkest = min(px, key=lambda p: sum(p)); lightest = max(px, key=lambda p: sum(p))
            worst = max(contrast_ratio(darkest, bg), contrast_ratio(lightest, bg))
            say(worst >= CONTRAST_FLOOR,
                f"the {name} export's mark clears the decorative floor {CONTRAST_FLOOR}:1 "
                f"against its band ({worst:.2f}:1)")

        # 8a. THE WORST LEGAL COMBINATION: the minimum opacity the contract allows,
        #     on a mid-tone where ink and background are closest. Without the
        #     background-adjustment loop this lands at ~1.32:1 and the mark is not
        #     perceptible; the surfaces above all pass at 0.22 whether the loop runs
        #     or not, so this is the assertion that actually guards it.
        worst_base = root / "worst.png"
        Image.new("RGB", (600, 300), (132, 132, 132)).save(worst_base)
        worst_dst = root / "worst-marked.png"
        watermark_image(worst_base, worst_dst, "Test Name · https://example.test/x", 0.18)
        wim = Image.open(worst_dst).convert("RGB")
        wb = wim.crop((0, 303, wim.size[0], wim.size[1]))
        wpx = list(wb.getdata()); wbg = max(set(wpx), key=wpx.count)
        wworst = max(contrast_ratio(min(wpx, key=sum), wbg), contrast_ratio(max(wpx, key=sum), wbg))
        say(wworst >= CONTRAST_FLOOR,
            f"mid-tone at the MINIMUM opacity 0.18 still clears the floor ({wworst:.2f}:1) - "
            f"the band-adjustment loop is what makes this reachable")

        # 8b. The ink derivation is guarded by its own assertion. Without this, a
        #     mutant that deletes the derivation and hardcodes dark ink stayed
        #     GREEN - the fix's guard did not protect the fix.
        def band_px(pth):
            im = Image.open(pth).convert("RGB")
            b = im.crop((0, 303, im.size[0], im.size[1]))
            return list(b.getdata())
        # DIRECTIONAL, not absolute: at 0.22 alpha a light ink over a dark band is
        # still dark in absolute terms, so an absolute threshold measures nothing.
        # What must hold is that the ink moves AWAY from the band, in opposite
        # directions on the two surfaces.
        dpx = band_px(root / "dark-marked.png"); dbg = max(set(dpx), key=dpx.count)
        lpx = band_px(root / "light-marked.png"); lbg = max(set(lpx), key=lpx.count)
        dark_goes_lighter = max(sum(p) for p in dpx) > sum(dbg)
        light_goes_darker = min(sum(p) for p in lpx) < sum(lbg)
        say(dark_goes_lighter and light_goes_darker,
            "the ink flips with the surface - lighter than a dark band, darker than a light one "
            "(a hardcoded ink fails one of the two)")

        # 8c. The opacity is genuinely applied. Drawing with an alpha in `fill` on
        #     an RGB canvas silently discards it: measured identical output at
        #     alpha 10 and alpha 255, so the mark shipped at 100% against a
        #     contract specifying 18-30%.
        faint, strong = root / "op-min.png", root / "op-max.png"
        for out_p, op in ((faint, 0.18), (strong, 0.30)):
            watermark_image(root / "light.png", out_p, "Test Name · https://example.test/x", op)
        d18 = min(sum(p) for p in Image.open(faint).convert("RGB").crop((0, 303, 600, 320)).getdata())
        d30 = min(sum(p) for p in Image.open(strong).convert("RGB").crop((0, 303, 600, 320)).getdata())
        say(d18 != d30, f"watermark_opacity actually changes the mark (0.18 -> {d18}, 0.30 -> {d30})")

        # 8d. A one-character mark is not a credit line. Without this, replacing
        #     the whole credit with "." stayed green.
        stub = root / "stub.png"
        watermark_image(root / "light.png", stub, ".", 0.22)
        full = root / "full.png"
        watermark_image(root / "light.png", full, "Test Name · https://example.test/x", 0.22)
        def inked(pth):
            im = Image.open(pth).convert("RGB")
            b = im.crop((0, 303, im.size[0], im.size[1]))
            px = list(b.getdata()); bg = max(set(px), key=px.count)
            return sum(1 for p in px if p != bg)     # anything that is not the band field
        say(inked(full) > inked(stub) * 5,
            f"the whole credit line is drawn, not a stub ({inked(full)} vs {inked(stub)} inked px)")

        # 9. ...and the ARTWORK itself is untouched, which is what "never overlap" means.
        untouched = pixels_changed(root / "light.png", root / "light-marked.png")
        say(untouched == 0, f"the artwork above the band is pixel-identical (max change {untouched})")

        # 10. THE DENOMINATOR RULE: zero inputs FAILS.
        empty = root / "empty"
        empty.mkdir()
        say(run(empty, prof, None, False) == 1,
            "zero artifacts found exits non-zero - a run that matched nothing is not a pass")

        # 11. A source file is refused while the export beside it is marked.
        mixed = root / "mixed"
        mixed.mkdir()
        Image.new("RGB", (400, 300), "white").save(mixed / "export.png")
        (mixed / "diagram.svg").write_text("<svg/>", encoding="utf-8")
        rc = run(mixed, prof, root / "out11", False)
        say(rc == 1 and (root / "out11" / "export.png").exists() and not (root / "out11" / "diagram.svg").exists(),
            "a .svg source is refused and never written, while the .png export is marked")

        # 12. Nested directories keep their shape instead of overwriting each other.
        nest = root / "nest"
        (nest / "a").mkdir(parents=True); (nest / "b").mkdir(parents=True)
        Image.new("RGB", (200, 120), "red").save(nest / "a" / "chart.png")
        Image.new("RGB", (200, 120), "blue").save(nest / "b" / "chart.png")
        run(nest, prof, root / "out12", False)
        say((root / "out12" / "a" / "chart.png").exists() and (root / "out12" / "b" / "chart.png").exists(),
            "same-named files in different directories both survive - the tree is preserved")

        # 13. An unreadable image is a refusal, not a traceback that aborts the run.
        broken = root / "broken"
        broken.mkdir()
        (broken / "corrupt.png").write_bytes(b"not a png")
        Image.new("RGB", (200, 120), "white").save(broken / "good.png")
        rc = run(broken, prof, root / "out13", False)
        say(rc == 1 and (root / "out13" / "good.png").exists(),
            "a corrupt image is refused and the rest of the directory still processes")

        # 14. A profile with no watermark key is refused, not silently treated as blank.
        noprof = root / "nokey.md"
        noprof.write_text("watermark_opacity: 0.22\n", encoding="utf-8")
        try:
            run(mixed, noprof, root / "out14", False)
            say(False, "a profile with no watermark key is refused")
        except Refusal:
            say(True, "a profile with no watermark: key is refused - absent is not blank")

        # 14b. Images are idempotent too. Without a marker, a second --in-place run
        #      read the FIRST band as the bottom edge and stacked another:
        #      measured 328 -> 356 -> 384 px, ink flipping on a dark export.
        idem = root / "idem"
        idem.mkdir()
        Image.new("RGB", (300, 200), "white").save(idem / "i.png")
        run(idem, prof, None, True)
        h1 = Image.open(idem / "i.png").size[1]
        rc2 = run(idem, prof, None, True)
        h2 = Image.open(idem / "i.png").size[1]
        say(h1 == h2 and rc2 == 1,
            f"a second --in-place run is refused, not stacked (height {h1} -> {h2})")

        # 14c. Litter from a killed run does not permanently redden the directory.
        lit = root / "litter"
        lit.mkdir()
        Image.new("RGB", (200, 120), "white").save(lit / "ok.png")
        (lit / ".wm-abc.png.part").write_bytes(b"partial")
        say(run(lit, prof, root / "out14c", False) == 0,
            "a partial file left by a killed run is swept, not collected and refused forever")

        # 15. --in-place is atomic: the original is never left truncated.
        atomic = root / "atomic"
        atomic.mkdir()
        p = atomic / "img.png"
        Image.new("RGB", (300, 200), "white").save(p)
        before = p.stat().st_size
        run(atomic, prof, None, True)
        ok = p.exists() and p.stat().st_size > 0
        try:
            Image.open(p).load()
        except Exception:
            ok = False
        say(ok and before > 0, "--in-place leaves a complete, readable file (atomic replace)")

    print("\nSELF-TEST FAILED" if failed else
          "\nSELF-TEST PASS - refuses what it must, marks what it should, and proves it in pixels")
    return failed


if __name__ == "__main__":
    sys.exit(self_test())
