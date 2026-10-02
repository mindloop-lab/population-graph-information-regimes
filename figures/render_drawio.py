#!/usr/bin/env python3
"""Render the ChatGPT .drawio concept drafts to inclusion-ready vector art.

Why this exists: LaTeX cannot include a .drawio file, and no draw.io CLI is installed on this
host. Rather than re-drawing the author's design by hand (which would silently change it), this
converts the drafts directly, preserving their geometry, colours and text.

Scope, stated honestly: this is NOT a general draw.io renderer. It implements the subset of
mxGraph used by these two files -- plain/rounded rectangles, ellipses, lines, left/centre text,
orthogonal edges with a block or no arrowhead, and the inline tags <b>, <sub>, <br>. Anything
outside that subset is reported and skipped rather than guessed at.

Output is deterministic: same input, same bytes.
"""
from __future__ import annotations

import argparse
import html
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _frozen_inputs import pin_output_dates  # noqa: E402

pin_output_dates()

BASE = pathlib.Path(__file__).resolve().parents[1]
PKG = BASE / "PaperA_Figure_Design_Package"
FIGDIR = BASE / "figures"

PX_PER_IN = 96.0


# --------------------------------------------------------------------------- style parsing
def parse_style(style: str) -> dict:
    out: dict[str, str] = {}
    for part in (style or "").split(";"):
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
        else:
            out[part.strip()] = "1"
    return out


# The received design drafts are kept byte-identical as the record of what was delivered. Where a
# draft's notation disagrees with the manuscript's generated macro, the alignment is applied here,
# at render time, and counted: a silent rewrite inside the artwork would be indistinguishable from
# the draughtsman having written it that way.
NOTATION_ALIGNMENT = {
    "EV,": "EVGCN,",          # draft: AUC_{EV,P0}; manuscript macro: \mathrm{AUC}_{\mathrm{EVGCN},P0}
}
NOTATION_HITS: dict[str, int] = {}


def align_notation(text: str) -> str:
    for wrong, right in NOTATION_ALIGNMENT.items():
        if wrong in text:
            NOTATION_HITS[wrong] = NOTATION_HITS.get(wrong, 0) + text.count(wrong)
            text = text.replace(wrong, right)
    return text


def inline_runs(value: str) -> list[list[tuple[str, bool, bool]]]:
    """Split an mxCell label into lines of (text, bold, subscript) runs."""
    text = align_notation(html.unescape(value or ""))
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.I)
    lines: list[list[tuple[str, bool, bool]]] = [[]]
    bold = sub = False
    i = 0
    while i < len(text):
        m = re.match(r"<\s*(/)?\s*(b|strong|sub|sup|i|em|u|font)\b[^>]*>", text[i:], flags=re.I)
        if m:
            closing = bool(m.group(1))
            tag = m.group(2).lower()
            if tag in ("b", "strong"):
                bold = not closing
            elif tag in ("sub", "sup"):
                sub = not closing
            i += m.end()
            continue
        nxt = text.find("<", i)
        chunk = text[i:] if nxt == -1 else text[i:nxt]
        for j, seg in enumerate(chunk.split("\n")):
            if j:
                lines.append([])
            if seg:
                lines[-1].append((seg, bold, sub))
        i = len(text) if nxt == -1 else nxt
    if not any(lines):
        lines = [[("", False, False)]]
    return [ln or [("", False, False)] for ln in lines]


# One estimator, used by the wrapper and by any audit of the result: two different estimates
# of the same quantity is how "fits in the box" and "overflows the box" get reported for the
# same label at the same time.
CHAR_EM = {"regular": 0.56, "bold": 0.60, "sub": 0.75}


def estimate_width(text: str, fs: float, bold: bool = False, sub: bool = False) -> float:
    em = CHAR_EM["bold"] if bold else CHAR_EM["regular"]
    return len(text) * fs * em * (CHAR_EM["sub"] if sub else 1.0)


def run_width(text: str, fs: float, bold: bool, sub: bool) -> float:
    return estimate_width(text, fs, bold, sub)


def wrap_lines(lines, max_w: float, fs: float):
    """Greedy word wrap that keeps each word's bold/subscript flags."""
    out = []
    for line in lines:
        cur: list[tuple[str, bool, bool]] = []
        width = 0.0
        for text, bold, sub in line:
            for chunk in re.split(r"(\s+)", text):
                if not chunk:
                    continue
                cw = run_width(chunk, fs, bold, sub)
                if chunk.strip() and cur and width + cw > max_w:
                    out.append(cur)
                    cur, width = [], 0.0
                cur.append((chunk, bold, sub))
                width += cw
        out.append(cur or [("", False, False)])
    return out


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def text_esc(s: str) -> str:
    """Escape for SVG text and protect spaces.

    SVG collapses whitespace by default, so a tspan holding only a space renders as nothing and
    the words on either side lose their advance (they then run together and their reported boxes
    overlap). xml:space="preserve" is not honoured by every renderer; a non-breaking space is
    never collapsed by any of them.
    """
    return esc(s).replace(" ", "\u00a0")


# --------------------------------------------------------------------------- geometry
class Shape:
    def __init__(self, cid, g, style, value, kind):
        self.id, self.style, self.value, self.kind = cid, style, value, kind
        self.x, self.y = float(g.get("x", 0)), float(g.get("y", 0))
        self.w, self.h = float(g.get("width", 0)), float(g.get("height", 0))

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def boundary_point(self, tx: float, ty: float) -> tuple[float, float]:
        """Where the line from the centre towards (tx, ty) leaves this shape."""
        dx, dy = tx - self.cx, ty - self.cy
        if dx == 0 and dy == 0:
            return self.cx, self.cy
        if self.style.get("ellipse"):
            a, b = self.w / 2, self.h / 2
            import math
            t = 1.0 / math.sqrt((dx / a) ** 2 + (dy / b) ** 2)
            return self.cx + dx * t, self.cy + dy * t
        hw, hh = self.w / 2, self.h / 2
        sx = hw / abs(dx) if dx else float("inf")
        sy = hh / abs(dy) if dy else float("inf")
        t = min(sx, sy)
        return self.cx + dx * t, self.cy + dy * t


def load(path: pathlib.Path):
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    shapes: dict[str, Shape] = {}
    edges: list[tuple[Shape, dict, str, str, str]] = []
    skipped: list[str] = []
    for cell in root.iter("mxCell"):
        cid = cell.get("id")
        if cid in ("0", "1"):
            continue
        geo = cell.find("mxGeometry")
        if geo is None:
            skipped.append(f"{cid}: no geometry")
            continue
        style = parse_style(cell.get("style", ""))
        value = cell.get("value", "")
        if cell.get("edge"):
            edges.append((Shape(cid, geo, style, value, "edge"), style,
                          cell.get("source", ""), cell.get("target", ""), value))
            continue
        known = ("ellipse" in style or "shape" in style or "rounded" in style
                 or "text" in style or "whiteSpace" in style)
        if not known:
            skipped.append(f"{cid}: unrecognised style {cell.get('style','')[:60]}")
        shapes[cid] = Shape(cid, geo, style, value, "vertex")
    return shapes, edges, skipped


def text_block(s: Shape, font_scale: float, line_h: float = 1.25) -> str:
    """SVG for a vertex's label, honouring align and the vertical text case."""
    st = s.style
    fs = float(st.get("fontSize", 12)) * font_scale
    bold_all = st.get("fontStyle") == "1"
    align = st.get("align", "center")
    valign = st.get("verticalAlign", "middle")
    rot = st.get("rotation") == "270"
    pad = float(st.get("spacingLeft", 0)) * font_scale
    lines = inline_runs(s.value)
    avail = (s.h - 2 * pad) if rot else (s.w - 2 * pad - 4)
    if avail > 0:
        lines = wrap_lines(lines, avail, fs)
    parts = []
    lh = fs * line_h
    total = lh * len(lines)
    if valign == "middle":
        y0 = s.cy - total / 2 + lh * 0.78
    elif valign == "top":
        y0 = s.y + lh * 0.78
    else:
        y0 = s.y + s.h - total + lh * 0.78
    if rot:
        cx, cy = s.cx, s.cy
        parts.append(f'<g transform="translate({cx:.1f},{cy:.1f}) rotate(-90)">')
        # after rotation the lines advance along the rotated x-axis
        start = -total / 2 + lh * 0.78
        for i, line in enumerate(lines):
            txt = "".join(t for t, _, _ in line)
            y = start + i * lh
            parts.append(f'<text x="0" y="{y:.1f}" font-size="{fs:.1f}" '
                         f'font-weight="700" text-anchor="middle" xml:space="preserve" '
                         f'dominant-baseline="middle">{text_esc(txt)}</text>')
        parts.append("</g>")
        return "".join(parts)
    for i, line in enumerate(lines):
        y = y0 + i * lh
        if align == "left":
            x = s.x + pad + 2
            anchor = "start"
        elif align == "right":
            x = s.x + s.w - pad
            anchor = "end"
        else:
            x = s.cx
            anchor = "middle"
        # No <tspan> anywhere: every tspan formulation this renderer used produced overlapping
        # glyphs in one renderer or another (a space-only tspan loses its advance; a line mixing
        # plain text with tspans is mis-positioned). Instead:
        #   * a line with no subscript is ONE text node, its weight set for the whole line;
        #   * a line that needs subscripts is drawn as separately positioned text runs, with x
        #     accumulated from the same width estimator the wrapper uses.
        weight = "700" if (bold_all or any(b for _, b, _ in line)) else "400"
        if not any(sub for _, _, sub in line):
            txt = "".join(t for t, _, _ in line)
            parts.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{fs:.1f}" '
                         f'font-weight="{weight}" text-anchor="{anchor}">'
                         f"{text_esc(txt)}</text>")
            continue
        runs = [(rt, rb, rs) for rt, rb, rs in line if rt]
        widths = [estimate_width(rt, fs * (0.75 if rs else 1.0), bold_all or rb)
                  for rt, rb, rs in runs]
        total = sum(widths)
        if anchor == "middle":
            cursor = x - total / 2
        elif anchor == "end":
            cursor = x - total
        else:
            cursor = x
        for (rt, rb, rs), wdt in zip(runs, widths):
            sfs = fs * (0.75 if rs else 1.0)
            dy = 2.0 if rs else 0.0
            parts.append(f'<text x="{cursor:.1f}" y="{y + dy:.1f}" font-size="{sfs:.1f}" '
                         f'font-weight="{"700" if (bold_all or rb) else "400"}">'
                         f"{text_esc(rt)}</text>")
            cursor += wdt
    return "".join(parts)


def render(shapes, edges, font_scale: float, panel_shift=None) -> tuple[str, float, float]:
    xs = [s.x for s in shapes.values()] + [s.x + s.w for s in shapes.values()]
    ys = [s.y for s in shapes.values()] + [s.y + s.h for s in shapes.values()]
    pad = 16.0
    x0, y0 = min(xs) - pad, min(ys) - pad
    w, h = max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad
    out = []
    # edges first so vertices sit on top
    for e, st, src, tgt, value in edges:
        if src not in shapes or tgt not in shapes:
            continue
        a, b = shapes[src], shapes[tgt]
        x1, y1 = a.boundary_point(b.cx, b.cy)
        x2, y2 = b.boundary_point(a.cx, a.cy)
        cc = st.get("strokeColor", "#000000")
        sw = float(st.get("strokeWidth", 1)) * font_scale
        marker = ""
        if st.get("endArrow", "classic") != "none":
            marker = ' marker-end="url(#arrow)"'
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                   f'stroke="{cc}" stroke-width="{sw:.1f}"{marker}/>')
        if value.strip():
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            fs = float(st.get("fontSize", 10)) * font_scale
            txt = html.unescape(re.sub(r"<[^>]+>", "", value))
            tw = len(txt) * fs * 0.58 + 8
            out.append(f'<rect x="{mx - tw / 2:.1f}" y="{my - fs * 0.85:.1f}" '
                       f'width="{tw:.1f}" height="{fs * 1.5:.1f}" fill="#ffffff"/>')
            out.append(f'<text x="{mx:.1f}" y="{my + fs * 0.36:.1f}" font-size="{fs:.1f}" '
                       f'text-anchor="middle" xml:space="preserve">{text_esc(txt)}</text>')
    for s in shapes.values():
        st = s.style
        fill = st.get("fillColor")
        stroke = st.get("strokeColor")
        sw = float(st.get("strokeWidth", 1)) * font_scale
        dash = ' stroke-dasharray="6 4"' if st.get("dashed") == "1" else ""
        if "shape" in st and st.get("shape") == "line":
            out.append(f'<line x1="{s.x:.1f}" y1="{s.cy:.1f}" x2="{s.x + s.w:.1f}" '
                       f'y2="{s.cy:.1f}" stroke="{stroke}" stroke-width="{sw:.1f}"{dash}/>')
            continue
        if "text" in st and "fillColor" not in st:
            out.append(text_block(s, font_scale))
            continue
        if st.get("ellipse"):
            out.append(f'<ellipse cx="{s.cx:.1f}" cy="{s.cy:.1f}" rx="{s.w / 2:.1f}" '
                       f'ry="{s.h / 2:.1f}" fill="{fill}" stroke="{stroke}" '
                       f'stroke-width="{sw:.1f}"{dash}/>')
        else:
            rx = 8 if st.get("rounded") == "1" else 0
            out.append(f'<rect x="{s.x:.1f}" y="{s.y:.1f}" width="{s.w:.1f}" height="{s.h:.1f}" '
                       f'rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw:.1f}"{dash}/>')
        out.append(text_block(s, font_scale))
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
        f'viewBox="{x0:.1f} {y0:.1f} {w:.1f} {h:.1f}" '
        f'font-family="DejaVu Sans, Liberation Sans, Arial, sans-serif">\n'
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke"/></marker></defs>\n'
        '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#ffffff"/>\n' % (x0, y0, w, h)
        + "\n".join(out) + "\n</svg>\n")
    return svg, w, h


def text_block_height(s: "Shape", font_scale: float, line_h: float = 1.25) -> float:
    """Height the wrapped label will actually occupy inside its box."""
    st = s.style
    fs = float(st.get("fontSize", 12)) * font_scale
    pad = float(st.get("spacingLeft", 0)) * font_scale
    avail = (s.h - 2 * pad) if st.get("rotation") == "270" else (s.w - 2 * pad - 4)
    lines = inline_runs(s.value)
    if avail > 0:
        lines = wrap_lines(lines, avail, fs)
    return fs * line_h * len(lines)


def autofit_boxes(shapes, font_scale: float, margin: float = 8.0) -> int:
    """Let a box grow to hold its text, pushing down whatever sits below it.

    The drafts were laid out for 11 px type; rendering them larger (so the labels survive being
    placed on a 137 mm page) makes some labels taller than their original boxes. Rather than
    shrink the type back down, the boxes grow and their neighbours move.
    """
    grown = 0
    boxes = [s for s in shapes.values() if s.style.get("fillColor") and not s.style.get("ellipse")]
    for _ in range(6):
        moved = False
        for s in boxes:
            if not s.value.strip():
                continue
            need = text_block_height(s, font_scale) + 6
            if need > s.h + 0.5:
                delta = need - s.h
                s.h = need
                grown += 1
                for o in boxes:
                    if o is s or o.value.strip() == "":
                        continue
                    overlap = min(s.x + s.w, o.x + o.w) - max(s.x, o.x)
                    if o.y > s.y + 1 and overlap > 0.4 * min(s.w, o.w):
                        o.y += delta
                        moved = True
        if not moved:
            break
    # containers (no label of their own) grow to cover what they hold
    for s in shapes.values():
        if s.value.strip() or not s.style.get("fillColor") or s.style.get("ellipse"):
            continue
        inside = [o for o in shapes.values() if o is not s and not o.style.get("shape")
                  and s.x <= o.x and o.x + o.w <= s.x + s.w
                  and s.y <= o.y and o.y + o.h <= s.y + s.h + 400]
        if inside and not any(o.value.strip() for o in inside):
            continue
        kids = [o for o in inside if o.value.strip()]
        if kids:
            bottom = max(o.y + o.h for o in kids) + 12
            if bottom > s.y + s.h:
                s.h = bottom - s.y
    return grown


def drop_embedded_titles(shapes) -> int:
    """Remove a figure's own title cell in the print variants.

    These drafts carry their title inside the artwork, but a submitted figure gets its caption
    from LaTeX: the embedded title is redundant *and* it is a full-width cell, which is what kept
    the re-flowed canvas as wide as the original and the type unreadably small.
    """
    drop = [cid for cid, s in shapes.items()
            if "text" in s.style and float(s.style.get("fontSize", 0)) >= 18]
    for cid in drop:
        del shapes[cid]
    return len(drop)


def stack_panels(shapes, bands):
    """Re-flow side-by-side panels into rows, for print at a narrow text width.

    A cell that spans more than one band (the figure title) belongs to no single panel: it is
    kept as a full-width header row. Funnelling it into one panel is what made an earlier
    version of this reflow come out as wide as the original.
    """
    span = max(x.x + x.w for x in shapes.values()) - min(x.x for x in shapes.values())
    header, panels = [], [[] for _ in bands]
    for s in shapes.values():
        if s.w > 0.55 * span:
            header.append(s)
            continue
        for i, (lo, hi) in enumerate(bands):
            if lo <= s.cx < hi:
                panels[i].append(s)
                break
    offset = 0.0
    if header:
        top = min(x.y for x in header)
        for s in header:
            s.x -= min(x.x for x in header) - 20
            s.y -= top - 10
        offset = max(x.y + x.h for x in header) + 30
    for g in panels:
        if not g:
            continue
        top = min(x.y for x in g)
        xs0 = min(x.x for x in g)
        h = max(x.y + x.h for x in g) - top
        for s in g:
            s.x = s.x - xs0 + 20
            s.y = s.y - top + offset + 10
        offset += h + 30
    return shapes


def column_reflow(shapes):
    """Lay a left-to-right chain out as a single column (narrower canvas -> larger print type)."""
    span_x = max(x.x + x.w for x in shapes.values()) - min(x.x for x in shapes.values())
    wide = [s for s in shapes.values() if s.w > 0.55 * span_x or not x_is_box(s)]
    boxes = [s for s in shapes.values() if s not in wide]
    boxes.sort(key=lambda s: (s.x, s.y))
    offset = 0.0
    if wide:
        top = min(s.y for s in wide)
        for s in wide:
            s.x -= min(x.x for x in wide) - 20
            s.y -= top - 10
        offset = max(s.y + s.h for s in wide) + 30
    for s in boxes:
        s.x = 20
        s.y = offset
        offset += s.h + 26
    return shapes


def x_is_box(s: "Shape") -> bool:
    return bool(s.style.get("fillColor"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    jobs = [("Fig1_information_regimes.drawio", "Fig1_information_regimes",
             [(-1e9, 405.0), (405.0, 790.0), (790.0, 1e9)]),
            ("FigS1_evidence_reporting_chain.drawio", "FigS1_evidence_reporting_chain", None)]
    # Print variants: the drafts' 11 px body text lands near 3.6 pt if the native 12.4 in canvas
    # is placed on a 137 mm page, so each concept figure is emitted re-flowed. The scale is 1.0 —
    # design size — because the re-flow already narrows the canvas, and scaling the type up on top
    # of that made Figure 1 taller than a page (LaTeX then refuses to place the float at all).
    PRINT_SCALE = 1.0
    probe = pathlib.Path.cwd()
    global NOTATION_HITS
    for drawio, out_name, bands in jobs:
        if args.only and args.only not in out_name:
            continue
        src = PKG / drawio if (PKG / drawio).exists() else probe / drawio
        shapes, edges, skipped = load(src)
        print(f"--- {drawio}: {len(shapes)} shapes, {len(edges)} edges"
              + (f", skipped {skipped}" if skipped else ""))
        svg, w, h = render(shapes, edges, 1.0)
        (FIGDIR / f"{out_name}.svg").write_text(svg, encoding="utf-8")
        print(f"    native    {w:.0f} x {h:.0f} px  -> {out_name}.svg")
        if bands:
            shapes2, edges2, _ = load(src)
            n_titles = drop_embedded_titles(shapes2)
            grown = autofit_boxes(shapes2, PRINT_SCALE)
            stack_panels(shapes2, bands)
            grown += autofit_boxes(shapes2, PRINT_SCALE)
            svg2, w2, h2 = render(shapes2, edges2, PRINT_SCALE)
            (FIGDIR / f"{out_name}_stacked.svg").write_text(svg2, encoding="utf-8")
            print(f"    stacked   {w2:.0f} x {h2:.0f} px (font x{PRINT_SCALE}, "
                  f"{n_titles} title(s) dropped, {grown} box(es) grown to fit) "
                  f"-> {out_name}_stacked.svg")
        if not bands:
            shapes3, edges3, _ = load(src)
            n_titles3 = drop_embedded_titles(shapes3)
            autofit_boxes(shapes3, PRINT_SCALE)
            column_reflow(shapes3)
            autofit_boxes(shapes3, PRINT_SCALE)
            svg3, w3, h3 = render(shapes3, edges3, PRINT_SCALE)
            (FIGDIR / f"{out_name}_stacked.svg").write_text(svg3, encoding="utf-8")
            print(f"    stacked   {w3:.0f} x {h3:.0f} px (font x{PRINT_SCALE}, "
                  f"{n_titles3} embedded title(s) dropped) -> {out_name}_stacked.svg")
    if NOTATION_HITS:
        print("    notation aligned at render time (the received draft is unchanged): "
              + ", ".join(f"{k!r}->{NOTATION_ALIGNMENT[k]!r} x{n}"
                          for k, n in sorted(NOTATION_HITS.items())))
    else:
        print("    no notation alignment was needed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
