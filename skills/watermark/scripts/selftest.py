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
    Refusal, check_opacity, has_copyright_footer, run, watermark_html, watermark_image,
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

        # 8. THE ONE THAT MATTERED: pixels change on BOTH a light and a dark export.
        #    White-on-white passed the old byte comparison while drawing nothing.
        for name, colour in [("light", (248, 250, 252)), ("dark", (14, 19, 34))]:
            base = root / f"{name}.png"
            Image.new("RGB", (600, 300), colour).save(base)
            dst = root / f"{name}-marked.png"
            watermark_image(base, dst, "Test Name · https://example.test/x", 0.22)
            ink = band_ink_differs(dst, 300)
            say(ink > 12, f"the {name} export's band carries visible ink (contrast {ink})")

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
