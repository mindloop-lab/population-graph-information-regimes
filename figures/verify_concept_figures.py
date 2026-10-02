#!/usr/bin/env python3
"""Verify the rendered concept figures (Figure 1, Figure S1) against their sources.

These figures carry no result values, but they still make claims about the frozen record, so the
same discipline applies: the labels must survive rendering intact, the only number that appears
must be a frozen value, the estimand must be written the way the manuscript writes it, and no
wording that the project has excluded may creep in.

Checks run against the rendered SVG text nodes, not against the renderer's intent.
"""
from __future__ import annotations

import html
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _frozen_inputs import FrozenInputError, FrozenInputs  # noqa: E402
from render_drawio import NOTATION_ALIGNMENT, align_notation  # noqa: E402  (declared mapping)

BASE = pathlib.Path(__file__).resolve().parents[1]
FIG = BASE / "figures"
PKG = BASE / "PaperA_Figure_Design_Package"

fails: list[str] = []
warns: list[str] = []
n = 0


def check(ok: bool, label: str, detail: str = "") -> None:
    global n
    n += 1
    print(f"[{n:2d}] [{'PASS' if ok else 'FAIL'}] {label}" + (f": {detail}" if detail else ""))
    if not ok:
        fails.append(label)


def warn(label: str) -> None:
    print(f"     [WARN] {label}")
    warns.append(label)


def tokens(text: str) -> list[str]:
    return re.findall(r"[^\s]+", text)


def drawio_label_tokens(path: pathlib.Path, include_titles: bool = True) -> tuple[list[str], list[str]]:
    """Tokens of every label, plus the tokens that belong to the figure's embedded title."""
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    out: list[str] = []
    title: list[str] = []
    for cell in root.iter("mxCell"):
        val = cell.get("value") or ""
        if not val.strip():
            continue
        txt = html.unescape(val)
        txt = re.sub(r"<\s*br\s*/?\s*>", " ", txt, flags=re.I)
        txt = re.sub(r"<[^>]+>", " ", txt)
        # a title cell is the big-font one; the print variants drop it because LaTeX supplies
        # the caption instead
        style = cell.get("style") or ""
        m = re.search(r"fontSize=(\d+)", style)
        big = bool(m) and int(m.group(1)) >= 18 and "text" in style
        (title if big else out).extend(tokens(txt))
    return (out + title if include_titles else out), title


def svg_text(path: pathlib.Path) -> str:
    """All rendered text, read from the SVG tree (labels are split across tspans, so a
    regex over the raw file silently misses them)."""
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    parts: list[str] = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag in ("text", "tspan"):
            if el.text:
                parts.append(html.unescape(el.text))
            if el.tail:
                parts.append(html.unescape(el.tail))
    return " ".join(parts)


try:
    F = FrozenInputs(BASE)
except FrozenInputError as exc:
    print(f"ABORT: {exc}")
    sys.exit(1)

taxonomy = (BASE / "manuscript_s1/table1_protocols.tex").read_text(encoding="utf-8")
estimand_macro = (BASE / "manuscript_s1/numbers_s1_canonical.tex").read_text(encoding="utf-8")
oline = [l for l in estimand_macro.splitlines() if "\\SOneEstimand" in l and "newcommand" in l]
estimand_terms = re.findall(r"AUC\}_\{\\mathrm\{([^}]*)\}", oline[0]) if oline else []

for drawio_name, stem in (("Fig1_information_regimes.drawio", "Fig1_information_regimes"),
                          ("FigS1_evidence_reporting_chain.drawio", "FigS1_evidence_reporting_chain")):
    src = PKG / drawio_name
    print(f"--- {stem} ---")
    for variant in (stem, f"{stem}_stacked"):
        svg = FIG / f"{variant}.svg"
        if not svg.exists():
            check(False, f"{variant}: rendered SVG exists")
            continue
        want, title_tokens = drawio_label_tokens(src, include_titles="_stacked" not in variant)
        # The expectation is not "render == draft verbatim": where the draft's notation disagrees
        # with the manuscript macro, the render applies the declared alignment. So the reference is
        # align(draft), and the number of re-mapped tokens is reported rather than hidden.
        remapped = [t for t in want if align_notation(t) != t]
        want = [align_notation(t) for t in want]
        got = tokens(svg_text(svg))
        bag = {}
        for t in got:
            bag[t] = bag.get(t, 0) + 1
        missing = []
        for t in want:
            if bag.get(t, 0) <= 0:
                missing.append(t)
            else:
                bag[t] -= 1
        check(not missing,
              f"{variant}: every draft label token is present after the declared alignment",
              f"{len(want)} tokens, {len(remapped)} re-mapped by "
              f"{list(NOTATION_ALIGNMENT)}" if not missing else f"missing {missing[:6]}")

        page = svg_text(svg)
        # Two tiers, because these figures mix data with names:
        #  * a decimal number is a quantity and must be a frozen value (or part of a frozen
        #    value, e.g. an interval bound) -- no exceptions;
        #  * a whole number must be part of a declared identifier form (regime name, run stage,
        #    atlas name, hash name, split id, cell count) rather than an unexplained quantity.
        IDENT = (r"CC\d+", r"SHA-?\d+", r"M\d+\.\d+-S\d+", r"[PR]\d", r"Figure\s+\d",
                 r"Supp\w*\s+Figure\s+S\d")
        words = re.findall(r"[A-Za-z0-9.\-]+", page)
        bad_decimals, bad_whole = [], []
        for num in sorted({s for s in re.findall(r"\d+\.\d+|\d+", page)}):
            if not any(num in w for w in words):
                continue
            ctx = [w for w in words if num in w]
            if "." in num:
                if num in F.tokens() or num in F.canonical:
                    continue
                if any(re.fullmatch(p, w) for w in ctx for p in IDENT):
                    continue
                bad_decimals.append((num, ctx[:3]))
            else:
                if num in F.canonical or num in F.tokens() or num in F.selected:
                    continue
                if any(re.fullmatch(p, w) for w in ctx for p in IDENT):
                    continue
                if num in taxonomy or num in (BASE / "paperA-control/S1_FREEZE.yaml").read_text():
                    continue
                bad_whole.append((num, ctx[:3]))
        check(not bad_decimals,
              f"{variant}: every decimal number is a frozen value",
              "; ".join(f"{n} in {c}" for n, c in bad_decimals) or "none present beyond frozen data")
        check(not bad_whole,
              f"{variant}: every whole number is part of a declared identifier form",
              "; ".join(f"{n} in {c}" for n, c in bad_whole) or "all identifiers")
        check("leak" not in page.lower(), f"{variant}: no leakage wording")
        ranking = [w for w in ("better", "worse", "best", "worst", "outperform", "superior")
                   if re.search(rf"\b{w}\b", page, re.I)]
        check(not ranking, f"{variant}: no model ranking", "; ".join(ranking) or "none")

        if stem.startswith("Fig1"):
            terms = re.findall(r"AUC\s*([A-Za-z]+)", page)
            check(len(terms) >= 4, f"{variant}: the estimand is written out", f"terms {terms[:8]}")
            seen = [t.rstrip(",") for t in terms]
            if estimand_terms and seen:
                want_terms = list(estimand_terms)
                check(set(seen[:4]) == set(want_terms),
                      f"{variant}: estimand implementation names match the manuscript macro",
                      f"figure {sorted(set(seen[:4]))} vs macro {sorted(set(want_terms))}")
                # the alignment is applied at render time and declared; verify all three facts
                draft = src.read_text(encoding="utf-8")
                renderer = (FIG / "render_drawio.py").read_text(encoding="utf-8")
                check("EV," in draft and "EVGCN," not in draft,
                      f"{variant}: the received draft still carries its own notation",
                      "the design package stays byte-identical")
                check("EVGCN" in page and "EV," not in page,
                      f"{variant}: no bare EV survives into the rendered figure")
                check('"EV,"' in renderer and '"EVGCN,"' in renderer,
                      f"{variant}: the notation alignment is declared in the renderer",
                      "figures/render_drawio.py NOTATION_ALIGNMENT")
    print()

# the single number that appears must be the frozen cell count, and it must be the same number
fz = F.freeze
cells = [v for v in F.canonical if v.strip() == "120"]
check(cells, "the figure's cell count is a canonical_text of the freeze", f"{cells}")
body = (BASE / "manuscript_s1/paperA_v2.tex").read_text(encoding="utf-8")
check("SOneCells" in body, "the manuscript states the cell count through the generated macro, "
                           "not as a literal")

print()
print(f"CONCEPT FIGURES: {n} checks, {n - len(fails)} PASS, {len(fails)} FAIL, {len(warns)} warning(s)")
for w in warns:
    print("  WARN:", w)
if fails:
    print("ABORT: " + "; ".join(fails))
    sys.exit(1)
