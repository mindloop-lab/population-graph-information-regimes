#!/usr/bin/env python3
"""Layout gate for the concept figures: does every label fit, and is anything drawn twice?

The vision pass cannot be trusted for this (it has reported overstruck text that does not
exist and misread values), so the layout is measured instead: each label's estimated extent is
compared with the box that hosts it, and identical strings on the same baseline are flagged as
duplication. The width estimator is imported from the renderer so the two cannot disagree.

Rotated labels are measured along the canvas y-axis, since that is the direction their text
runs after the -90 degree transform.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from render_drawio import estimate_width  # noqa: E402

FIG = pathlib.Path(__file__).resolve().parents[1] / "figures"
NS = "{http://www.w3.org/2000/svg}"
# The *_stacked variants are the print variants included in the manuscript; the others are the
# faithful render of the received design, kept for reference and documented as not printable at
# this text width (3.6 pt body text). The rendered-output overprint check therefore applies to
# the print variants; the reference renders are checked for the source-level invariants only,
# and the reason is printed rather than silently skipped.
TARGETS = ["Fig1_information_regimes", "Fig1_information_regimes_stacked",
           "FigS1_evidence_reporting_chain", "FigS1_evidence_reporting_chain_stacked"]
REFERENCE_ONLY = {"Fig1_information_regimes", "FigS1_evidence_reporting_chain"}

problems = 0
for name in TARGETS:
    p = FIG / f"{name}.svg"
    if not p.exists():
        print(f"{name}: MISSING")
        problems += 1
        continue
    root = ET.fromstring(p.read_text(encoding="utf-8"))
    boxes = []
    for el in root.iter(f"{NS}rect"):
        try:
            boxes.append((float(el.get("x")), float(el.get("y")),
                          float(el.get("width")), float(el.get("height"))))
        except (TypeError, ValueError):
            pass

    def rotated(el) -> bool:
        for parent in root.iter():
            if el in list(parent):
                t = parent.get("transform", "")
                if "rotate(-90)" in t:
                    return True
                if parent is not root:
                    return rotated(parent) or "rotate(-90)" in t
        return False

    texts = []
    for el in root.iter(f"{NS}text"):
        content = "".join(el.itertext())
        if not content.strip():
            continue
        fs = float(el.get("font-size", 12))
        texts.append({"t": content, "x": float(el.get("x", 0)), "y": float(el.get("y", 0)),
                      "fs": fs, "anchor": el.get("text-anchor", "start"),
                      "w": estimate_width(content, fs), "rot": rotated(el)})

    # Structural invariant: no tspan anywhere. Every tspan formulation this renderer used
    # produced overlapping glyphs in one renderer or another, and the markup looked clean while
    # the rendering was broken, so the absence of tspans is asserted rather than trusted.
    n_tspan = p.read_text(encoding="utf-8").count("<tspan")

    # Rendered-output invariant: no two words may share a baseline while overlapping
    # horizontally. This reads the converted PDF, not the markup.
    pdf = p.with_suffix(".pdf")
    rendered = []
    check_render = name not in REFERENCE_ONLY
    if pdf.exists() and check_render:
        import subprocess
        xml = subprocess.run(["pdftotext", "-bbox-layout", str(pdf), "-"],
                             capture_output=True, text=True).stdout
        words = []
        for m in re.finditer(
                r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>',
                xml):
            x0, y0, x1, y1, w = (float(m.group(1)), float(m.group(2)), float(m.group(3)),
                                 float(m.group(4)), m.group(5))
            if x1 - x0 >= 8.0:
                words.append((x0, y0, x1, y1, w))
        for i, a in enumerate(words):
            for b in words[i + 1:]:
                if abs(a[1] - b[1]) > 1.5 or abs(a[3] - b[3]) > 1.5:
                    continue
                ix = min(a[2], b[2]) - max(a[0], b[0])
                if ix > 0 and ix / min(a[2] - a[0], b[2] - b[0]) > 0.5:
                    rendered.append((a[4], b[4], round(a[1], 1)))

    dupes = [(a["t"], b["t"]) for i, a in enumerate(texts) for b in texts[i + 1:]
             if a["t"] == b["t"] and abs(a["y"] - b["y"]) < 3 and abs(a["x"] - b["x"]) < 40]

    overflow = []
    for t in texts:
        if t["rot"]:
            host = [b for b in boxes if b[0] <= t["x"] <= b[0] + b[2] + 1
                    and b[1] - 1 <= t["y"] <= b[1] + b[3] + 1]
            # after rotation the label runs along y; the box it must fit is the rotated cell
            if host and t["w"] > max(b[3] for b in host) + 2:
                overflow.append((t["t"][:40], "rotated label longer than its box height"))
            continue
        x0 = t["x"] - (t["w"] / 2 if t["anchor"] == "middle" else (t["w"] if t["anchor"] == "end" else 0))
        x1 = x0 + t["w"]
        host = [b for b in boxes if b[0] - 1 <= x0 and x1 <= b[0] + b[2] + 1
                and b[1] <= t["y"] <= b[1] + b[3]]
        if not host:
            overflow.append((t["t"][:40], f"no box contains x {x0:.0f}..{x1:.0f} at y {t['y']:.0f}"))

    scope = "reference render (source invariants only)" if not check_render else "print variant"
    print(f"{name} [{scope}]: {len(texts)} text elements, {len(boxes)} boxes, {n_tspan} tspans, "
          f"{len(dupes)} duplicated, {len(overflow)} not fitting, "
          f"{len(rendered)} overprinted in the rendered PDF")
    for d in dupes[:4]:
        print("    DUPLICATE:", d[0][:60])
    for o in overflow[:4]:
        print("    OVERFLOW: ", o[0], "-", o[1])
    for r in rendered[:4]:
        print("    OVERPRINT:", r)
    problems += len(dupes) + len(overflow) + len(rendered) + (1 if n_tspan else 0)

print()
if problems:
    print(f"LAYOUT: {problems} problem(s)")
    sys.exit(1)
print("LAYOUT: every label fits its box and nothing is drawn twice")
