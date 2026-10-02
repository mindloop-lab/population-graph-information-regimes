#!/usr/bin/env python3
"""Rasterise/convert the concept-figure SVGs to PDF and PNG.

The SVG is the primary artifact (deterministic text, editable, what draw.io and Inkscape read).
This produces the PDF that LaTeX \\includegraphics consumes plus a PNG preview.

cairosvg writes a creation date into PDF metadata, so without pinning, the same input produced a
different PDF on every run and the hash recorded in the registry could never be re-verified. The
date is pinned through the reproducible-builds convention, same as the matplotlib figures.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _frozen_inputs import pin_output_dates  # noqa: E402

pin_output_dates()

import cairosvg  # noqa: E402

FIG = pathlib.Path(__file__).resolve().parents[1] / "figures"
TARGETS = ["Fig1_information_regimes", "Fig1_information_regimes_stacked",
           "FigS1_evidence_reporting_chain", "FigS1_evidence_reporting_chain_stacked"]

for name in TARGETS:
    svg = FIG / f"{name}.svg"
    if not svg.exists():
        print(f"{name}: no SVG, skipped")
        continue
    cairosvg.svg2pdf(url=str(svg), write_to=str(FIG / f"{name}.pdf"))
    cairosvg.svg2png(url=str(svg), write_to=str(FIG / f"{name}.png"), scale=2)
    print(f"{name}: pdf + png written")
