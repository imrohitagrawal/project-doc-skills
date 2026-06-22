#!/usr/bin/env python3
"""
usage_guide_generator.py — build a simple, friendly, illustrated usage guide as one HTML file.

This is the usage-guide counterpart of the FAQ's generator: a *different layout* (a calm, linear,
grade-1 how-to page — big numbered steps and pictures, no tabs), but the SAME three guarantees baked
in BY CONSTRUCTION, so an author cannot ship an HTML usage guide that silently drops them:

  1. the © licence footer   (render-contract.md P14; licensing-and-credits.md Section 2)
  2. an About & credits block (licensing-and-credits.md Section 4 — the first-class `credits` block)
  3. an ISO last-reviewed stamp (render-contract.md P2 — `<meta name="last-reviewed">` + a visible line)

Why a second generator and not a shared emitter both pages call: the FAQ is a tabbed sidebar app and
the usage guide is a linear page — forcing both through one emitter is over-engineering (the suite
declined exactly that). What is single-sourced is what matters: the *values* come from the profile
(licensing-and-credits.md `{{key}}` keys — never hard-code a name), and the *rules* live once in
render-contract.md (P2/P14) + licensing-and-credits.md. Each generator only *renders* them, and
`verify.py` is the deterministic backstop for all of it (a public page or internal set with no © FAILs;
a stale stamp WARNs). So this file restates no policy — it applies it.

Import it and call build_usage_guide(guide_dict, "out.html"), or run this file directly to emit a
small grade-1 demo (so you can confirm it renders, and passes `verify.py --skill usage-guide`, before
wiring real content).

The HTML it produces has: a single h1, a `lang` attribute, an "On this page" jump list, a contentinfo
footer carrying the ©, alt text required on every picture, ✓+word success cues (never colour alone),
WCAG-AA contrast, a skip link, and an optional non-overlapping watermark. No build dependencies.

Content model (a plain dict):

guide = {
  "title": str, "subtitle": str, "lang": "en",
  "intro": str,                     # optional: one short, friendly line under the title (inline HTML ok)
  "last_reviewed": "YYYY-MM-DD",    # optional but recommended: the day you last checked the STEPS still
                                    #   work. Emits a machine-readable <meta name="last-reviewed"> plus a
                                    #   visible stamp (render-contract.md P2). verify.py WARNs once it is
                                    #   older than the staleness threshold; omit and the page is undated
                                    #   (INFO, never a failure).
  "footer": str,                    # REQUIRED for the licensing gate: the licence line carrying the © (the
                                    #   PUBLIC variant for a usage guide, since scope_usage_guide is public;
                                    #   the internal variant if a project sets it internal). Inline HTML
                                    #   allowed (link the licence + the About & credits page). Rendered as a
                                    #   contentinfo <footer>. The watermark below does NOT replace it.
                                    #   Alias accepted: "licence_footer".
  "watermark": str | "",            # optional DECORATIVE credit line (profile `watermark`); never a
  "watermark_opacity": 0.22,        #   substitute for the © footer (licensing-and-credits.md Section 2).
  "sections": [                     # the guide, in order — keep to the usage-guide structure:
    {"id": str, "title": str, "blocks": [ <block>, ... ]},   #   What this is / What you need / Quickstart /
  ],                                #   each task / If something goes wrong / Words we used / About & credits
}

Blocks (each a dict with a "type"):
  {"type":"p","html":...}                            a short, plain paragraph (inline HTML allowed)
  {"type":"steps","items":[...]}                     a NUMBERED list — say exactly what to click/type/tap
  {"type":"bullets","items":[...]}                   a short checklist (e.g. "What you need")
  {"type":"h3","text":...}                           a small sub-heading inside a section (a task name)
  {"type":"goal","html":...}                         a one-line "Goal:" for a task
  {"type":"see","html":...}                          the "What you will see" box (green, ✓ + words)
  {"type":"note","label":"Tip","html":...}           a calm aside (Tip / Note / Careful)
  {"type":"trouble","items":[(if_html, then_html),]} "If you see X -> do Y" rows (calm, plain)
  {"type":"picture","src":...,"alt":...,             a picture for a task. `alt` is REQUIRED (a short
            "caption":...}                           sentence of what it shows); a missing/empty alt raises.
  {"type":"glossary","items":[(term, defn_html),]}   "Words we used", each defined in kid words
  {"type":"code","lang":"bash","text":...}           a command to type (text is escaped)
  {"type":"credits","heading":...,"intro":html,      the About & credits block (licensing-and-credits.md
            "items":[(label, value_html), ...]}      Section 4). Keep it PLAIN (grade-1) and SHORT: a
                                                     who-made-it line, the licence line, and a link to the
                                                     full About & credits page / LICENSE — the formal
                                                     attribution_line and the full "AS IS" disclaimer live
                                                     there, off this page. It does NOT replace the © footer
                                                     (set `footer` too).
"""
from __future__ import annotations
import datetime
import html
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- block render

def _esc(s: str) -> str:
    return html.escape(str(s), quote=False)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-") or "section"


def _render_block(b: dict) -> str:
    t = b.get("type")
    if t == "p":
        return f"<p>{b['html']}</p>"
    if t == "h3":
        return f"<h3>{_esc(b['text'])}</h3>"
    if t == "goal":
        return f'<p class="goal"><span class="goal-tag">Goal</span> {b["html"]}</p>'
    if t == "steps":
        items = "".join(f"<li>{it}</li>" for it in b["items"])
        return f"<ol class=\"steps\">{items}</ol>"
    if t == "bullets":
        items = "".join(f"<li>{it}</li>" for it in b["items"])
        return f"<ul class=\"need\">{items}</ul>"
    if t == "see":
        # "What you will see" — success cue is ✓ + the word, never colour alone (house-style.md S7).
        return (f'<div class="box box-see"><span class="box-label">✓ What you will see</span>'
                f'<div class="box-body">{b["html"]}</div></div>')
    if t == "note":
        label = _esc(b.get("label", "Tip"))
        return (f'<div class="box box-note"><span class="box-label">{label}</span>'
                f'<div class="box-body">{b["html"]}</div></div>')
    if t == "trouble":
        rows = "".join(
            f'<div class="trouble-row"><span class="t-if">If {iff}</span>'
            f'<span class="t-arrow" aria-hidden="true">\u2192</span>'
            f'<span class="t-then">do this: {then}</span></div>'
            for iff, then in b["items"])
        return f'<div class="trouble">{rows}</div>'
    if t == "picture":
        # Alt text is required (house-style.md S7 / render-contract.md P7). Refuse to emit a picture
        # with no alt rather than ship an inaccessible image — fail loud at build, not silent on the page.
        alt = str(b.get("alt", "")).strip()
        if not alt:
            raise ValueError(
                "picture block is missing required 'alt' text — every picture needs a short sentence "
                "saying what it shows (house-style.md Section 7). Add alt=... to the block.")
        cap = f'<figcaption>{_esc(b["caption"])}</figcaption>' if b.get("caption") else ""
        return (f'<figure class="pic"><img src="{_esc(b["src"])}" alt="{_esc(alt)}">{cap}</figure>')
    if t == "glossary":
        items = "".join(f"<dt>{_esc(term)}</dt><dd>{defn}</dd>" for term, defn in b["items"])
        return f'<dl class="glossary">{items}</dl>'
    if t == "code":
        lang = _esc(b.get("lang", ""))
        return f'<pre class="code" data-lang="{lang}"><code>{_esc(b["text"])}</code></pre>'
    if t == "credits":
        head = _esc(b.get("heading", "About & credits"))
        intro = f'<div class="box-body">{b["intro"]}</div>' if b.get("intro") else ""
        rows = "".join(f"<dt>{_esc(lbl)}</dt><dd>{val}</dd>" for lbl, val in b.get("items", []))
        dl = f'<dl class="credits-list">{rows}</dl>' if rows else ""
        return (f'<div class="box box-credits"><span class="box-label">{head}</span>'
                f'{intro}{dl}</div>')
    return ""


def _render_section(sec: dict, is_first: bool) -> str:
    sid = _esc(sec.get("id") or _slug(sec.get("title", "section")))
    head_tag = "h1" if is_first else "h2"
    body = "\n".join(_render_block(b) for b in sec.get("blocks", []))
    return (f'<section class="card" id="{sid}">\n'
            f'<{head_tag} class="sec-title">{_esc(sec["title"])}</{head_tag}>\n{body}\n</section>')


def _has_block(guide: dict, block_type: str) -> bool:
    return any(b.get("type") == block_type
              for sec in guide.get("sections", []) for b in sec.get("blocks", []))

# ---------------------------------------------------------------------- styles
# Friendly, distinctive, and readable for non-technical / young readers: a rounded display face
# (Baloo 2) + a humanist body face (Nunito) + a mono for commands — deliberately NOT the
# Inter/Roboto/Arial defaults, and indigo is an ACCENT on a warm light page, never purple body text
# on white. Palette is the profile/house-style palette (indigo / green / slate). Contrast meets AA.

_CSS = """
:root{
  --bg:#FBF8F2; --card:#FFFFFF; --ink:#16201d; --muted:#475467;
  --line:#e7e2d6; --indigo:#4338CA; --indigo-dk:#3730A3; --indigo-bg:#eef0fb;
  --green:#15803D; --green-bg:#e9f6ee; --green-bd:#bfe3cb;
  --amber:#9a5b00; --amber-bg:#fbf2df; --amber-bd:#ecd9ad; --code:#23201a;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"Nunito","Segoe UI",system-ui,sans-serif;font-size:20px;line-height:1.7}
a{color:var(--indigo);text-decoration:underline;text-underline-offset:3px}
.wrap{max-width:760px;margin:0 auto;padding:40px clamp(18px,5vw,40px) 64px}
.head{margin:0 0 6px}
h1.sec-title,h2.sec-title{font-family:"Baloo 2","Nunito",sans-serif;line-height:1.15;color:#0F172A}
.title{font-family:"Baloo 2","Nunito",sans-serif;font-weight:700;font-size:40px;line-height:1.1;
  color:#0F172A;margin:0}
.subtitle{color:var(--muted);font-size:19px;margin:6px 0 0}
.intro{font-size:21px;margin:14px 0 4px}
.reviewed{display:inline-block;font-size:13px;color:var(--muted);margin-top:10px;
  font-family:"JetBrains Mono",ui-monospace,monospace}
nav.toc{background:var(--indigo-bg);border:1px solid #c7cdf3;border-radius:14px;
  padding:14px 18px;margin:20px 0 8px}
nav.toc b{font-family:"Baloo 2",sans-serif;display:block;margin-bottom:4px;font-size:16px}
nav.toc ol{margin:0;padding-left:22px}
nav.toc a{color:var(--indigo-dk)}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;
  padding:22px clamp(16px,4vw,28px);margin:22px 0;box-shadow:0 1px 0 rgba(20,20,20,.03)}
h1.sec-title{font-weight:700;font-size:30px;margin:0 0 12px}
h2.sec-title{font-weight:700;font-size:26px;margin:0 0 12px}
h3{font-family:"Baloo 2",sans-serif;font-weight:600;font-size:21px;margin:20px 0 8px;color:#0F172A}
p{margin:0 0 14px}
.goal{font-size:19px}
.goal-tag{display:inline-block;background:var(--indigo);color:#fff;font-family:"Baloo 2",sans-serif;
  font-size:13px;font-weight:600;padding:2px 10px;border-radius:999px;margin-right:8px}
ol.steps{counter-reset:step;list-style:none;margin:6px 0 16px;padding:0}
ol.steps>li{counter-increment:step;position:relative;padding:6px 0 6px 46px;margin:0 0 4px;
  font-size:20px}
ol.steps>li::before{content:counter(step);position:absolute;left:0;top:4px;width:32px;height:32px;
  background:var(--indigo);color:#fff;border-radius:50%;display:grid;place-items:center;
  font-family:"Baloo 2",sans-serif;font-weight:700;font-size:16px}
ul.need{list-style:none;margin:6px 0 14px;padding:0}
ul.need>li{position:relative;padding:4px 0 4px 30px}
ul.need>li::before{content:"\u2713";position:absolute;left:0;top:4px;color:var(--green);font-weight:800}
.box{border-radius:14px;padding:14px 16px;margin:14px 0;border:1px solid}
.box-label{display:inline-block;font-family:"Baloo 2",sans-serif;font-weight:600;font-size:14px;
  margin-bottom:6px;padding:2px 10px;border-radius:999px}
.box-body p:last-child{margin-bottom:0}
.box-see{background:var(--green-bg);border-color:var(--green-bd)}
.box-see .box-label{background:var(--green);color:#fff}
.box-note{background:var(--amber-bg);border-color:var(--amber-bd)}
.box-note .box-label{background:var(--amber);color:#fff}
.box-credits{background:#f3f1ea;border-color:var(--line)}
.box-credits .box-label{background:#0F172A;color:var(--bg)}
.trouble{margin:10px 0 14px;display:grid;gap:8px}
.trouble-row{display:grid;grid-template-columns:1fr auto 1fr;gap:8px;align-items:center;
  background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px 12px}
.t-if{font-weight:700}
.t-arrow{color:var(--indigo);font-weight:800;font-size:20px}
@media(max-width:560px){.trouble-row{grid-template-columns:1fr;text-align:left}
  .t-arrow{display:none}}
figure.pic{margin:14px 0;text-align:center}
figure.pic img{max-width:100%;height:auto;border:1px solid var(--line);border-radius:12px}
figure.pic figcaption{color:var(--muted);font-size:15px;margin-top:6px}
pre.code{background:var(--code);color:#f6f0e4;border-radius:12px;padding:14px 16px;overflow:auto;
  font-family:"JetBrains Mono",ui-monospace,monospace;font-size:15px;line-height:1.5}
code{font-family:"JetBrains Mono",ui-monospace,monospace}
p code,li code{background:#efe9db;padding:1px 6px;border-radius:6px;font-size:.9em}
dl.glossary dt{font-family:"Baloo 2",sans-serif;font-weight:600;margin-top:12px}
dl.glossary dd{margin:2px 0 0;color:var(--muted)}
dl.credits-list{margin:8px 0 0;display:grid;grid-template-columns:max-content 1fr;gap:4px 14px}
dl.credits-list dt{font-family:"Baloo 2",sans-serif;font-weight:600}
dl.credits-list dd{margin:0;color:var(--muted)}
footer.licence{border-top:1px solid var(--line);color:var(--muted);font-size:14px;line-height:1.55;
  margin-top:28px;padding-top:18px}
footer.licence a{color:var(--indigo)}
.watermark{position:fixed;right:14px;bottom:10px;font-size:12px;color:var(--muted);
  pointer-events:none;font-family:"JetBrains Mono",monospace}
.skip{position:absolute;left:-999px}.skip:focus{left:8px;top:8px;background:#fff;padding:8px;z-index:9}
"""

_FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
          '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
          '<link href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700&'
          'family=Nunito:wght@400;600;700&family=JetBrains+Mono:wght@400&display=swap" '
          'rel="stylesheet">')

# ----------------------------------------------------------------------- build

def build_usage_guide(guide: dict, out_path: str | Path) -> Path:
    lang = _esc(guide.get("lang", "en"))
    title = _esc(guide["title"])
    subtitle = _esc(guide.get("subtitle", ""))

    # Last-reviewed stamp (render-contract.md P2): a machine-readable <meta> verify.py reads for the
    # staleness check, plus a visible line. Omit `last_reviewed` and both are dropped (page undated; INFO).
    last_reviewed = _esc(guide.get("last_reviewed", "")).strip()
    meta_reviewed = f'<meta name="last-reviewed" content="{last_reviewed}">' if last_reviewed else ""
    reviewed_line = f'<span class="reviewed">Last reviewed: {last_reviewed}</span>' if last_reviewed else ""

    sections = guide.get("sections", [])
    if not sections:
        raise ValueError("a usage guide needs at least one section (start with 'What this is').")

    # "On this page" jump list (render-contract.md P3) — only when there is more than one section.
    toc = ""
    if len(sections) > 1:
        links = "".join(
            f'<li><a href="#{_esc(s.get("id") or _slug(s.get("title", "section")))}">'
            f'{_esc(s["title"])}</a></li>' for s in sections)
        toc = f'<nav class="toc" aria-label="On this page"><b>On this page</b><ol>{links}</ol></nav>'

    body = "\n".join(_render_section(s, i == 0) for i, s in enumerate(sections))

    intro = f'<p class="intro">{guide["intro"]}</p>' if guide.get("intro") else ""
    head = (f'<div class="head"><p class="title">{title}</p>'
            + (f'<p class="subtitle">{subtitle}</p>' if subtitle else "")
            + reviewed_line + "</div>")

    wm = ""
    if guide.get("watermark"):
        op = guide.get("watermark_opacity", 0.22)
        wm = f'<div class="watermark" style="opacity:{op}">{_esc(guide["watermark"])}</div>'

    # Licence footer (carries the ©). Required by the licensing gate; the watermark above does not
    # replace it (licensing-and-credits.md Section 2). Inline HTML allowed (link the licence + the
    # About & credits page). Rendered as a contentinfo landmark; verify.py excludes this <footer> from
    # the reading-grade so the required legal line can never trip the grade-1 gate.
    footer_text = guide.get("footer") or guide.get("licence_footer") or ""
    footer_html = (f'<footer class="licence" role="contentinfo">{footer_text}</footer>'
                   if footer_text else "")

    doc = f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{meta_reviewed}
<title>{title} — how to use it</title>
{_FONTS}
<style>{_CSS}</style>
</head>
<body>
<a class="skip" href="#start">Skip to content</a>
<main class="wrap" id="start">
{head}
{intro}
{toc}
{body}
{footer_html}
</main>
{wm}
</body>
</html>
"""
    out = Path(out_path)
    out.write_text(doc, encoding="utf-8")

    # Nudge on the two things the licensing gate cares about, so the right thing is the easy default.
    if "©" not in doc:
        sys.stderr.write(
            f"NOTE: {out} has no © licence footer — set guide['footer'] to the licence line "
            f"(public variant for a usage guide) from references/licensing-and-credits.md; "
            f"verify.py FAILS a public page or internal set with no ©.\n")
    if not _has_block(guide, "credits"):
        sys.stderr.write(
            f"NOTE: {out} has no About & credits block — add a final section with a 'credits' block "
            f"(licensing-and-credits.md Section 4): who made it, the licence, and a link to the full "
            f"About & credits page. Keep it plain and short.\n")
    return out


# --------------------------------------------------------------------- demo/cli

def _demo() -> dict:
    # Written in true grade-1 voice on purpose: short sentences, common words, one idea each — so the
    # demo page passes `verify.py --skill usage-guide` (grade target ~2), modelling the real bar.
    return {
        "title": "Example Tool",
        "subtitle": "How to use it",
        "lang": "en",
        # The day you last checked the steps still work. Here it is today's date so the demo never trips
        # the staleness WARN and models correct usage. In a real run, set it each time the steps change.
        "last_reviewed": datetime.date.today().isoformat(),
        "intro": "This guide shows you how to use the tool. The steps are small. You can do this.",
        # The licence line carrying the © (the PUBLIC variant; a usage guide is public). In a real run,
        # take this from the profile via references/licensing-and-credits.md — never hard-code a name.
        "footer": ('© 2026 Example Owner (Example Brand) · Licensed under '
                   '<a href="https://creativecommons.org/licenses/by-nc-nd/4.0/">CC BY-NC-ND 4.0</a> · '
                   '<a href="#about">About &amp; credits</a> · '
                   'Free to read and share, with credit, for non-commercial use. Provided "as is"; '
                   'see LICENSE.'),
        "watermark": "Your Name · your-link",
        "sections": [
            {"id": "what", "title": "What this is", "blocks": [
                {"type": "p", "html": "This tool helps you check your work. It does the hard parts "
                 "for you. You tell it what to check. It tells you what it found."},
            ]},
            {"id": "need", "title": "What you need first", "blocks": [
                {"type": "p", "html": "You need a few things first."},
                {"type": "bullets", "items": ["A computer.", "The app, set up.", "Your sign-in."]},
            ]},
            {"id": "start", "title": "Do this first", "blocks": [
                {"type": "p", "html": "This is the fast way to your first win."},
                {"type": "steps", "items": ["Open the app.",
                                            "Type the start word. Press Enter.",
                                            "Wait a moment."]},
                {"type": "code", "lang": "bash", "text": "example start"},
                {"type": "see", "html": "<p>You will see the word \u201cReady\u201d. Now you have done "
                 "it once. ✓ Done.</p>"},
            ]},
            {"id": "make-a-check", "title": "Make a new check", "blocks": [
                {"type": "goal", "html": "Make one new check."},
                {"type": "steps", "items": ["Click <strong>New</strong>.", "Type a name.",
                                            "Click <strong>Save</strong>."]},
                {"type": "see", "html": "<p>Your check shows up in the list. It has a green ✓.</p>"},
                {"type": "picture", "src": "img/new-check.png",
                 "alt": "The list with one new check and a green tick.",
                 "caption": "Your new check in the list."},
            ]},
            {"id": "trouble", "title": "If something goes wrong", "blocks": [
                {"type": "p", "html": "Here are the few common problems. Stay calm. Each one is easy "
                 "to fix."},
                {"type": "trouble", "items": [
                    ("you see \u201cNot signed in\u201d", "sign in again. Then try once more."),
                    ("you see a red mark", "check the name has no spaces. Then click Save again."),
                    ("nothing happens", "close the app. Open it again."),
                ]},
            ]},
            {"id": "words", "title": "Words we used", "blocks": [
                {"type": "glossary", "items": [
                    ("App", "a program you open."),
                    ("Command", "words you type to tell the app what to do."),
                    ("Save", "keep your work so it does not go away."),
                ]},
            ]},
            # About & credits — the first-class credits block (licensing-and-credits.md Section 4).
            # Kept PLAIN and SHORT for a grade-1 reader; the formal attribution line and the full "AS IS"
            # disclaimer live in the About & credits PAGE and LICENSE, not crammed onto this page. Built
            # from profile values in a real run; never hard-code a name.
            {"id": "about", "title": "About & credits", "blocks": [
                {"type": "credits",
                 "heading": "About & credits",
                 "intro": "<p>This guide is free to read and share, with credit. It is not for sale.</p>",
                 "items": [
                     ("Who made it", 'Example Owner (Example Brand) — '
                                     '<a href="https://github.com/example">links here</a>.'),
                     ("Licence", 'Free to read and share, for non-commercial use, with credit. '
                                 'See the LICENSE file.'),
                     ("Say where it came from",
                      'If you share it, say it is by Example Owner, from Example Tool.'),
                 ]},
            ]},
        ],
    }


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1].endswith(".json"):
        data = json.loads(Path(sys.argv[1]).read_text())
        p = build_usage_guide(data, sys.argv[2])
    else:
        out = sys.argv[1] if len(sys.argv) > 1 else "usage-guide-demo.html"
        p = build_usage_guide(_demo(), out)
    print(f"wrote {p}")
