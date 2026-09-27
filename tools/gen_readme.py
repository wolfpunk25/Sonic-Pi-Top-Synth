#!/usr/bin/env python3
"""Rebuild the sketch guide in README.md from the sketches' own header comments.

    python3 tools/gen_readme.py

Everything between <!-- sketches:start --> and <!-- sketches:end --> is
replaced. Each sketch's first comment line is "# Title - one-line summary";
the comment lines after it (other than category/keys/gain) are the
description. Lines indented after the "#" become a bulleted list.
"""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from pitop_weather import sonicpi  # noqa: E402

START, END = "<!-- sketches:start -->", "<!-- sketches:end -->"

INTROS = {
    "Keys": "Playable instruments: every note you play sounds straight away. The Grooves use whichever of these "
            "you played last.",
    "Sequencers": "They play by themselves, and your notes steer them: change the key, rewrite the pattern, "
                  "teach them a phrase.",
    "Grooves": "Backing tracks to play over. Most add **your last Keys sound** on top, so pick an instrument "
               "under Keys first (Pluck until you do).",
    "Ambient": "Slow, evolving soundscapes that need no keys at all; playing adds something gentle. Some follow "
               "the real weather.",
}


def describe(path):
    lines = open(path, encoding="utf-8").read().split("\n")
    head = []
    for l in lines:
        if not l.startswith("#"):
            break
        head.append(l)
    title_line = head[0].lstrip("# ").strip() if head else os.path.basename(path)
    parts = re.split(r"\s+[-–—]\s+", title_line, maxsplit=1)
    summary = parts[1] if len(parts) > 1 else ""
    body, bullets, indent = [], [], None
    for l in head[1:]:
        if re.match(r"#\s*(category|keys|gain)\s*:", l, re.I):
            continue
        text = l[1:]
        lead = len(text) - len(text.lstrip())
        if lead >= 3 and text.strip():
            if bullets and indent is not None and lead > indent:
                bullets[-1] += " " + text.strip()          # a wrapped bullet
            else:
                bullets.append(text.strip())
                indent = lead
        elif text.strip():
            if bullets:                                  # text after a list continues its last item
                bullets[-1] += " " + text.strip()
            else:
                body.append(text.strip())
    # "below middle C   - changes the key" -> "**below middle C**: changes the key"
    bullets = [re.sub(r"^(.+?)\s{2,}-\s+", lambda m: "**%s**: " % m.group(1), b) for b in bullets]
    return summary, " ".join(body), bullets


def section():
    sketches = sonicpi.load_sketches(os.path.join(REPO, "sketches"))
    out = [START, "", "## The sketches", ""]
    cats = sonicpi.categories(sketches)
    out.append(" · ".join("[%s (%d)](#%s)" % (c, len(g), c.lower()) for c, g in cats))
    out.append("")
    for cat, group in cats:
        out += ["### %s" % cat, "", INTROS.get(cat, ""), ""]
        for s in group:
            summary, body, bullets = describe(s.path)
            out.append("#### %s" % s.title)
            meta = "`%s`" % os.path.basename(s.path)
            if s.keys == "last":
                meta += " · plays your last Keys sound"
            out.append("*%s*: %s" % (meta, summary[0].upper() + summary[1:] + ("" if summary.endswith(".") else ".")
                                      if summary else ""))
            out.append("")
            if body:
                out += [body, ""]
            if bullets:
                out += ["- " + b for b in bullets] + [""]
    out.append(END)
    return "\n".join(out)


def main():
    path = os.path.join(REPO, "README.md")
    text = open(path, encoding="utf-8").read()
    new = section()
    if START in text and END in text:
        text = text[:text.index(START)] + new + text[text.index(END) + len(END):]
    else:
        text = text.rstrip("\n") + "\n\n" + new + "\n"
    open(path, "w", encoding="utf-8").write(text)
    print("README: %d sketches" % len(sonicpi.load_sketches(os.path.join(REPO, "sketches"))))


if __name__ == "__main__":
    main()
