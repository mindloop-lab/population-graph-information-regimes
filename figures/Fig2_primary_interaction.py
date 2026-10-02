#!/usr/bin/env python3
"""Paper A — Figure 2: primary interaction.

Prompt F2. Numeric authority is the frozen chain only:
    S1_FREEZE.yaml  ->  H3 derived CSVs (deterministically generated from it)
Nothing is read from manuscript prose and no result value is typed by hand: every number
that reaches the figure is a `canonical_text` string carried from the freeze through the
H3 CSV, and the annotations render those strings verbatim.

Aborts (writes nothing) if any recorded SHA-256 disagrees with the file on disk.
"""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from PIL import Image  # noqa: E402
import yaml  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _frozen_inputs import FrozenInputError, FrozenInputs, pin_output_dates  # noqa: E402

pin_output_dates()

BASE = Path(__file__).resolve().parents[1]
CP = BASE / "paperA-control"
DER = CP / "derived"
FIGDIR = BASE / "figures"

FORBIDDEN = ("mean", "pooled", "meta", "average across splits")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def die(msg: str) -> "None":
    print(f"ABORT: {msg}")
    sys.exit(1)


# ---------------------------------------------------------------- input verification
# One shared reader for the frozen chain; it aborts on any recorded-hash mismatch. This script
# used to carry its own copy of this logic, which is exactly how two readers drift apart.
try:
    FROZEN = FrozenInputs(BASE)
except FrozenInputError as exc:
    die(str(exc))

freeze, CANON, SELECTED = FROZEN.freeze, FROZEN.canonical, FROZEN.selected
inputs, recorded, csv_paths, rows = (FROZEN.inputs, FROZEN.recorded, FROZEN.csv_paths, FROZEN.rows)


def _walk_values(node, key, acc=None):
    """Every value stored under `key` anywhere in the freeze."""
    acc = [] if acc is None else acc
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                acc.append(v)
            else:
                _walk_values(v, key, acc)
    elif isinstance(node, list):
        for v in node:
            _walk_values(v, key, acc)
    return acc


def canonical_texts(node, acc=None):
    """Every canonical_text value anywhere in the freeze."""
    acc = [] if acc is None else acc
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "canonical_text" and isinstance(v, str):
                acc.append(v)
            else:
                canonical_texts(v, acc)
    elif isinstance(node, list):
        for v in node:
            canonical_texts(v, acc)
    return acc


primary = rows("cross_split_primary.csv")
seeds = rows("seed_level_interactions.csv")
cond = rows("condition_level_auc.csv")
sens = rows("sensitivity_summary.csv")

# ---- validation battery, before anything is drawn -------------------------------
fails: list[str] = []
n_checks = 0


def check(ok: bool, label: str, detail: str = "") -> None:
    global n_checks
    n_checks += 1
    print(f"[{n_checks:2d}] [{'PASS' if ok else 'FAIL'}] {label}"
          + (f": {detail}" if detail else ""))
    if not ok:
        fails.append(label)


check(len(primary) == 3, "exactly three split-level ΔΔAUC points", f"{len(primary)} rows")
check([r["split"] for r in primary] == ["666", "1024", "2024"],
      "the three preselected splits, in order", ", ".join(r["split"] for r in primary))

traj = {}
for r in cond:
    if r["availability"] == "present":
        traj.setdefault((r["split"], r["model"]), {})[r["regime"]] = r
present_traj = sorted(k for k, v in traj.items() if set(v) == {"P0", "P1"})
unsupported = [r for r in cond if r["availability"] != "present"]
check(len(present_traj) == 4,
      "four condition-level paired trajectories present (2 architectures x 2 splits)",
      ", ".join(f"{s}/{m}" for s, m in present_traj))
check(len([r for r in cond if r["availability"] == "present"]) == 8,
      "eight condition-level points drawn (no 666 value invented)",
      f"{len([r for r in cond if r['availability'] == 'present'])} points")
check(len(unsupported) == 4 and {r["split"] for r in unsupported} == {"666"},
      "split 666 condition-level rows stay NOT_PRESENT_IN_FROZEN_SOURCE",
      f"{len(unsupported)} rows, all split 666")

single = [r for r in seeds if r["training_seed"] in ("11", "22", "33")]
ens = [r for r in seeds if r["training_seed"] == "three_seed_ensemble"]
check(len(single) == 9, "exactly nine single-training-seed points", f"{len(single)} rows")
check(len(ens) == 3, "exactly three three-seed ensemble points", f"{len(ens)} rows")
check(len({r["split"] for r in single}) == 3, "seeds cover all three splits")

# every numeric string this script will render is a canonical_text of the freeze
render_numbers: list[tuple[str, str]] = []
for r in primary:
    render_numbers.append(("panel A point", r["delta_delta_auc"]))
    render_numbers.append(("panel A subject CI", r["subject_bootstrap_ci95"]))
    render_numbers.append(("panel A site CI", r["site_cluster_ci95"]))
for r in present_traj:
    for regime in ("P0", "P1"):
        render_numbers.append(("panel B AUC", traj[r][regime]["ensemble_auc"]))
for r in single + ens:
    render_numbers.append(("panel C interaction", r["interaction"]))
bad = [(w, s) for w, s in render_numbers if s not in CANON]
check(not bad, "every rendered numeric string is a canonical_text of the freeze",
      f"{len(render_numbers)} strings from {len(CANON)} canonical texts"
      + ("" if not bad else f" — not found: {bad}"))
check(SELECTED == ["666", "1024", "2024"],
      "selected_splits in the freeze are the expected three", ", ".join(SELECTED))
check(all(str(r["split"]) in SELECTED for r in primary),
      "every plotted split identifier is one of the freeze's selected splits", ", ".join(SELECTED))

# the primary point and the ensemble value must be the same frozen number
for r in primary:
    e = [x for x in ens if x["split"] == r["split"]]
    check(bool(e) and e[0]["interaction"] == r["delta_delta_auc"],
          f"split {r['split']}: ensemble value equals the primary point",
          e[0]["interaction"] if e else "missing")

if fails:
    die("validation failed before rendering: " + "; ".join(fails))

# ---------------------------------------------------------------- style
CB = {"blue": "#0072B2", "orange": "#D55E00", "green": "#009E73", "grey": "#4D4D4D"}
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8, "axes.labelsize": 8.5,
    "axes.titlesize": 9, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
    "legend.fontsize": 7.5, "axes.linewidth": 0.8, "xtick.major.width": 0.8,
    "ytick.major.width": 0.8, "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 120, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
})

STAGE_LABEL = {"666": "666 (prior audit)", "1024": "1024 (M4.5-S1)", "2024": "2024 (M4.5-S1)"}
ARCH_STYLE = {"EV-GCN": dict(color=CB["blue"], ls="-", marker="o", mfc="white", mew=1.1),
              "Parisot": dict(color=CB["orange"], ls="--", marker="s", mfc="white", mew=1.1)}

# Sized to the manuscript's own text width (elsarticle[preprint,12pt]: \textwidth = 390 pt
# = 5.42 in), so the figure is placed 1:1 and every label prints at its nominal point size.
TEXT_WIDTH_IN = 390.0 / 72.27
fig = plt.figure(figsize=(5.06, 7.30))
gs = fig.add_gridspec(3, 1, height_ratios=[1.0, 1.0, 1.05], hspace=1.02)

# ---------------------------------------------------------------- Panel A
axA = fig.add_subplot(gs[0])
ys = list(range(len(primary)))[::-1]
for y, r in zip(ys, primary):
    subj = json.loads(r["subject_bootstrap_ci95"])
    site = json.loads(r["site_cluster_ci95"])
    pt = float(r["delta_delta_auc"])
    axA.plot(subj, [y + 0.10] * 2, color=CB["blue"], lw=2.2, solid_capstyle="butt", zorder=3)
    axA.plot(site, [y - 0.10] * 2, color=CB["green"], lw=1.1, solid_capstyle="butt", zorder=3)
    axA.plot([pt], [y], marker="D", ms=5.2, color="black", zorder=4)
    # Interval bounds are deliberately not printed here: they are in the results table and
    # printing them would push the small type below the printable minimum on a 137 mm page.
    axA.text(pt, y + 0.22, "ΔΔAUC " + r["delta_delta_auc"], fontsize=7.0, ha="center",
             color="black")
axA.axvline(0, color="0.25", lw=1.0, zorder=1)
axA.set_yticks(ys, [STAGE_LABEL[r["split"]] for r in primary])
axA.set_ylabel("Preselected outer split")
axA.set_ylim(-0.62, len(primary) + 0.62)
axA.set_xlim(-0.005, 0.196)
axA.set_xlabel("Architecture × training-context interaction, ΔΔAUC")
axA.set_title("A  Cross-split interaction (no pooled estimate)", loc="left", pad=6)
axA.legend(handles=[
    Line2D([], [], color=CB["blue"], lw=2.2, label="Subject-bootstrap 95% interval"),
    Line2D([], [], color=CB["green"], lw=1.1, label="Site-cluster 95% interval"),
    Line2D([], [], color="black", marker="D", ls="none", ms=5, label="ΔΔAUC point estimate"),
], loc="upper left", frameon=False, handlelength=1.8, borderaxespad=0.2)
axA.annotate("Positive values indicate a more negative P0→P1 AUC change for EV-GCN than for "
             "Parisot-GCN.\nSplits are replication units and are not pooled.",
             xy=(0, -0.30), xycoords="axes fraction", fontsize=7.0, color=CB["grey"],
             va="top", ha="left", annotation_clip=False)

# ---------------------------------------------------------------- Panel B
# A2 review: the earlier single panel encoded the split twice (colour and marker fill) and the
# implementation twice (marker shape and line style) — four redundant channels for four
# trajectories, which the reader had to decode. One facet per split removes the split encoding
# entirely: the facet *is* the split. Only the implementation remains a variable, carried by
# colour with line style and marker shape as redundant channels so the panel still works in
# grayscale. The two facets share one y-range, so the splits stay comparable by eye.
sub_b = gs[1].subgridspec(1, 2, wspace=0.32)
axBs = [fig.add_subplot(sub_b[0, i]) for i in range(2)]
xr = {"P0": 0.0, "P1": 1.0}
fit_splits = ["1024", "2024"]
arch_col = {"EV-GCN": CB["blue"], "Parisot": CB["orange"]}
# Panel C still colours by split, so the split palette stays defined here.
split_col = {"1024": CB["blue"], "2024": CB["orange"]}
markers = {"EV-GCN": "o", "Parisot": "s"}
linestyle = {"EV-GCN": "-", "Parisot": "--"}
b_vals = [float(traj[(s, a)][k]["ensemble_auc"]) for s in fit_splits
          for a in ("EV-GCN", "Parisot") for k in ("P0", "P1")]
b_pad = 0.18 * (max(b_vals) - min(b_vals))
ylim_b = (min(b_vals) - b_pad, max(b_vals) + b_pad)
for axB, split in zip(axBs, fit_splits):
    for arch in ("EV-GCN", "Parisot"):
        v = traj[(split, arch)]
        xs = [xr["P0"], xr["P1"]]
        fs = [float(v["P0"]["ensemble_auc"]), float(v["P1"]["ensemble_auc"])]
        axB.plot(xs, fs, ls=linestyle[arch], color=arch_col[arch], lw=1.4,
                 marker=markers[arch], ms=4.6, mew=1.1, mfc="white", zorder=3)
        for x, fv, key in zip(xs, fs, ("P0", "P1")):
            axB.annotate(v[key]["ensemble_auc"], (x, fv), textcoords="offset points",
                         xytext=(0, 9 if arch == "EV-GCN" else -15),
                         ha="center", fontsize=6.8, color=CB["grey"])
    axB.set_xticks([0.0, 1.0], ["P0\ntrain-time context", "P1\nquery-only context"])
    axB.set_xlim(-0.30, 1.30)
    axB.set_ylim(*ylim_b)
    # Titles must fit a half-width facet. The earlier descriptive title ("Condition-level AUC
    # response, split 1024") ran into the right facet's title — measured as a 13 pt overlap of
    # "1024" and "split" on one baseline. The description belongs to the caption, which already
    # states what panel B shows.
    axB.set_title(f"B  split {split}" if split == fit_splits[0] else f"split {split}",
                  loc="left", fontsize=8.0, pad=4)
axBs[0].set_ylabel("Ensemble AUC")
h = [Line2D([], [], color=arch_col[a], ls=linestyle[a], marker=markers[a], ms=4.6,
            mfc="white", lw=1.4, label=a) for a in ("EV-GCN", "Parisot")]
axBs[0].legend(handles=h, loc="upper center", bbox_to_anchor=(1.06, -0.16), frameon=False,
               ncol=2, handlelength=1.9, columnspacing=2.0, labelspacing=0.55,
               borderaxespad=0.0)
axBs[0].annotate("Split 666: condition-level AUC unavailable in frozen source; interaction "
                 "retained in Panel A.",
                 xy=(0, -0.46), xycoords="axes fraction", fontsize=7.0, color=CB["grey"],
                 va="top", ha="left", annotation_clip=False)

# ---------------------------------------------------------------- Panel C
axC = fig.add_subplot(gs[2])
# Each split gets its own band: three seed rows, then the ensemble on a separate row above,
# so no marker ever sits on top of another.
yband = {"666": 2.0, "1024": 1.0, "2024": 0.0}
seed_row = {"11": -0.26, "22": 0.0, "33": 0.26}
ENS_DY = 0.52
for r in single:
    yv = yband[r["split"]] + seed_row[r["training_seed"]]
    xv = float(r["interaction"])
    axC.plot([xv], [yv], marker="o", ms=3.0, mfc="white", mew=1.0,
             color=split_col.get(r["split"], CB["green"]), ls="none", zorder=3)
    axC.annotate(r["interaction"], (xv, yv), textcoords="offset points", xytext=(4.5, 0),
                 ha="left", va="center", fontsize=6.5, color=CB["grey"])
for r in ens:
    yv = yband[r["split"]] + ENS_DY
    xv = float(r["interaction"])
    axC.plot([xv], [yv], marker="D", ms=6.0, color=split_col.get(r["split"], CB["green"]),
             ls="none", zorder=4)
    axC.annotate(r["interaction"], (xv, yv), textcoords="offset points", xytext=(0, 5.5),
                 ha="center", va="bottom", fontsize=6.8, color="black")
axC.axvline(0, color="0.25", lw=1.0, zorder=1)
axC.set_yticks([2, 1, 0], [STAGE_LABEL[s] for s in ("666", "1024", "2024")])
axC.set_ylabel("Preselected outer split")
axC.set_ylim(-0.62, 2.92)
axC.set_xlim(-0.012, 0.19)
axC.set_xlabel("Single-training-seed interaction, ΔΔAUC")
axC.set_title("C  Seed consistency (per-split; no averaging across splits)", loc="left", pad=6)
axC.legend(handles=[
    Line2D([], [], marker="o", ls="none", mfc="white", mew=1.0, ms=3.6, color="0.35",
           label="single seed (11 / 22 / 33)"),
    Line2D([], [], marker="D", ls="none", ms=6, color="0.35", label="three-seed ensemble"),
], loc="upper left", frameon=False, handlelength=1.6, borderaxespad=0.2)

# ---- forbidden vocabulary, checked on everything that ends up on the canvas --------
texts = []
for ax in (axA, *axBs, axC):
    texts += [t.get_text() for t in ax.texts]
    texts += [ax.get_title(), ax.get_xlabel(), ax.get_ylabel()]
    texts += [t.get_text() for t in ax.get_xticklabels() + ax.get_yticklabels()]
    lg = ax.get_legend()
    if lg:
        texts += [t.get_text() for t in lg.get_texts()]
# A banned term inside an explicit denial is not a banned claim: the caption the prompt
# mandates ("Splits are replication units and are not pooled.") must survive this check.
NEG = re.compile(r"\b(not|no|never|neither|nor|without|rather than)\b[^.;]*$", re.I)
hits, negated = [], []
for t in texts:
    for w in FORBIDDEN:
        for m in re.finditer(re.escape(w), t, re.I):
            (negated if NEG.search(t[:m.start()]) else hits).append(t.strip())
check(not hits, "no annotation asserts " + " / ".join(FORBIDDEN),
      "; ".join(sorted(set(hits))) or f"clean; {len(negated)} occurrence(s) inside an explicit denial")

fig.savefig(FIGDIR / "Fig2_primary_interaction.pdf")
fig.savefig(FIGDIR / "Fig2_primary_interaction.svg")
fig.savefig(FIGDIR / "Fig2_primary_interaction.png", dpi=600)
fig.savefig("/tmp/Fig2_single_column_check.png", dpi=200)
plt.close(fig)

# ---- read the rendered vector output back and verify what is actually on the page ----
# The SVG is written with svg.fonttype="none", so every label is a real text node: this
# checks the artifact, not the script's intent, and it catches a wrong label that a
# variable-level check would miss.
svg_text = (FIGDIR / "Fig2_primary_interaction.svg").read_text(encoding="utf-8")
svg_strings = re.findall(r">([^<>]+)</text>", svg_text)
onpage_numbers = {s.strip() for t in svg_strings
                  for s in re.findall(r"[+-]?\d+\.\d{2,6}", t)}
# A rendered number is acceptable if it is a frozen canonical text, a token *inside* one
# (interval bounds are frozen as the composite "[a, b]"), or an axis tick mark. Ticks are
# not exempted by pattern: each unmatched number must be provably one of the ticks that
# this figure actually draws, which the axes themselves report.
frozen_tokens = set()
for c in CANON:
    frozen_tokens.update(re.findall(r"[+-]?\d+\.\d{2,6}", c))
tick_labels = set()
for _ax in (axA, *axBs, axC):
    tick_labels |= {t.get_text().strip() for t in _ax.get_xticklabels() + _ax.get_yticklabels()}
absent = sorted(n for n in onpage_numbers
                if n not in CANON and n not in frozen_tokens and n not in tick_labels)
check(not absent, "every numeric string rendered on the page is a frozen value or an axis tick",
      f"{len(onpage_numbers)} distinct numeric strings on the page, "
      f"{len(tick_labels)} of them axis ticks"
      + ("" if not absent else f" — unaccounted: {absent}"))
joined = " | ".join(svg_strings)
check(joined.count("EV-GCN") >= 2 and joined.count("Parisot") >= 2,
      "both architectures are named on the page in more than one place",
      f"EV-GCN x{joined.count('EV-GCN')}, Parisot x{joined.count('Parisot')}")
check(all(t in joined for t in ("666 (prior audit)", "1024 (M4.5-S1)", "2024 (M4.5-S1)")),
      "the three stage labels are printed on the page")
check(sum(joined.count(f"split {s}") for s in fit_splits) >= 2,
      "panel B names both splits it facets (one facet each)",
      ", ".join(f"split {s} x{joined.count('split ' + s)}" for s in fit_splits))
zero_lines = [ln for _ax in (axA, axC) for ln in _ax.get_lines()
              if list(ln.get_xdata()) == [0, 0]]
check(len(zero_lines) == 2, "a zero reference line is drawn in panels A and C",
      f"{len(zero_lines)} vertical lines at x=0")
# Same-baseline overlap in the *rendered* PDF. The concept-figure renderer taught this: a source
# check cannot certify the artifact, and a long title in a half-width facet ran into its neighbour
# (13 pt of "1024" over "split") while every check above passed. Only negative gaps are asserted:
# pdftotext gives every word box a fixed trailing space, so small positive gaps are its floor, not
# evidence of crowding.
_bbox = subprocess.run(["pdftotext", "-bbox-layout", str(FIGDIR / "Fig2_primary_interaction.pdf"), "-"],
                       capture_output=True, text=True).stdout
_rows: dict[float, list[tuple[float, float, str]]] = {}
for m in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>',
                     _bbox):
    _rows.setdefault(round(float(m.group(2)), 1), []).append(
        (float(m.group(1)), float(m.group(3)), m.group(5)))
_overlaps = []
for _y, _items in _rows.items():
    _items.sort()
    for (_a0, _a1, _at), (_b0, _b1, _bt) in zip(_items, _items[1:]):
        if _b0 - _a1 < 0:
            _overlaps.append((round(_b0 - _a1, 2), _y, _at, _bt))
check(not _overlaps, "no two words overlap on the rendered page",
      f"{len(_rows)} baselines checked" + ("" if not _overlaps else f" — {_overlaps[:3]}"))

unlabelled = [r["interaction"] for r in single + ens if r["interaction"] not in joined]
check(not unlabelled, "every seed and ensemble value is printed as a label on the page",
      f"{len(single) + len(ens)} labels expected"
      + ("" if not unlabelled else f" — missing: {unlabelled}"))

if fails:
    die("validation failed: " + "; ".join(fails))

# ---------------------------------------------------------------- manifest
outs = ["Fig2_primary_interaction.pdf", "Fig2_primary_interaction.svg",
        "Fig2_primary_interaction.png"]

with Image.open(FIGDIR / "Fig2_primary_interaction.png") as _im:
    natural_in = round(_im.size[0] / 600, 2), round(_im.size[1] / 600, 2)
scale = TEXT_WIDTH_IN / natural_in[0]
_placement = {
    "natural_size_in": list(natural_in),
    "manuscript_text_width_in": 5.42,
    "placement": "width=\\textwidth",
    "resulting_scale": round(scale, 3),
    "smallest_label_pt_on_page": round(6.5 * scale, 2),
    "measured_at": "figure rendered at 600 dpi; sizes derived from the PNG pixel dimensions",
    "note": "at a 90 mm half-width placement the smallest type would fall to "
            f"{round(6.5 * 3.543 / natural_in[0], 1)} pt, so this figure must be placed at full "
            "text width, or its panels separated, rather than set as a half-width float",
}
manifest = {
    "figure": "Fig2_primary_interaction",
    "prompt": "F2 (Paper A figure generation)",
    "generated": "2026-09-27",
    "numeric_authority": "S1_FREEZE.yaml -> H3 derived CSVs; no value read from prose, none typed by hand",
    "inputs": inputs,
    "recorded_by": {"PROJECT_STATE.yaml": {k: v[0] for k, v in recorded.items()},
                    "SOURCE_REGISTRY.yaml": {k: v[1] for k, v in recorded.items()}},
    "script": {"path": "figures/Fig2_primary_interaction.py",
               "sha256": sha(Path(__file__).resolve())},
    "command": "python3 figures/Fig2_primary_interaction.py  (run from the repository root; pinned artifacts were rendered from this source)",
    "outputs": {o: sha(FIGDIR / o) for o in outs},
    "environment": {"python": platform.python_version(), "matplotlib": matplotlib.__version__,
                    "platform": platform.platform()},
    "validation": {"checks": f"{n_checks} PASS, {len(fails)} FAIL",
                   "condition_level_trajectories": {
                       "present": 4, "points": 8, "unsupported": "split 666, NOT_PRESENT_IN_FROZEN_SOURCE",
                       "note": "the prompt text says 'exactly 6 condition-level paired trajectories' "
                               "and then describes four trajectories / 8 points; the frozen source "
                               "contains four present trajectories (2 architectures x 2 splits) and "
                               "four unsupported 666 rows, so four is drawn and six is the count of "
                               "trajectory slots that would exist if 666 carried condition-level values"},
                   "strings_rendered_as_numbers": len(render_numbers),
                   "canonical_texts_available": len(CANON)},
    "pairing_rule": "combination / group-mean, not one-to-one subject pairing",
    "labels": {
        "split_labels_in_figure": STAGE_LABEL,
        "labels_recorded_in_the_freeze": [v for v in _walk_values(freeze, "label")
                                          if isinstance(v, str)],
        "note": "the figure label '666 (prior audit)' renders the freeze's evidence stage "
                "(frozen_prior_audit_M4.4R) and its recorded note '(prior audit)'",
    },
    # Measured, not asserted: the natural size of the artwork and what happens to its
    # smallest type when it is placed at the manuscript's text width.
    "placement": _placement,
    "style": {"vector": ["pdf", "svg"], "preview": "png 600 dpi", "palette": "Okabe-Ito subset",
              "encoding_redundancy": "panel B is faceted by split (the facet carries the split, "
                                     "so nothing encodes it); within a facet the implementation is "
                                     "carried by colour, with line style and marker shape redundant "
                                     "for grayscale; subject vs site interval by weight and "
                                     "vertical offset",
              "no_3d": True, "no_gradients": True},
}
(FIGDIR / "Fig2_primary_interaction_manifest.yaml").write_text(
    yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")
print(f"\nwrote {FIGDIR}/Fig2_primary_interaction.{{pdf,svg,png,_manifest.yaml}}")
print("VALIDATION: %d checks, %d PASS, %d FAIL" % (n_checks, n_checks - len(fails), len(fails)))
