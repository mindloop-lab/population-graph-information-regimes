#!/usr/bin/env python3
"""Paper A — supplemental LOSO sensitivity plot (prompt FS2).

One horizontal range per preselected split: the stored leave-one-site-out interaction
range, with the split's main ΔΔAUC point overlaid for reference. It is a sensitivity range,
not a confidence interval, and it is not combined across splits in any way.

Numeric authority: S1_FREEZE.yaml -> H3 derived CSVs, verified on every run through
figures/_frozen_inputs.py. Rendered labels are frozen canonical texts, never typed values.
"""
from __future__ import annotations

import platform
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from PIL import Image  # noqa: E402
import yaml  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _frozen_inputs import pin_output_dates  # noqa: E402
pin_output_dates()

from _frozen_inputs import FrozenInputError, FrozenInputs, sha  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
FIGDIR = BASE / "figures"
FORBIDDEN = ("mean", "pooled", "meta", "average across splits", "confidence interval")
STAGE_LABEL = {"666": "666 (prior audit)", "1024": "1024 (M4.5-S1)", "2024": "2024 (M4.5-S1)"}

try:
    F = FrozenInputs(BASE)
except FrozenInputError as exc:
    print(f"ABORT: {exc}")
    sys.exit(1)

fails: list[str] = []
n_checks = 0


def check(ok: bool, label: str, detail: str = "") -> None:
    global n_checks
    n_checks += 1
    print(f"[{n_checks:2d}] [{'PASS' if ok else 'FAIL'}] {label}" + (f": {detail}" if detail else ""))
    if not ok:
        fails.append(label)


prim = {r["split"]: r for r in F.primary}
sens = {r["split"]: r for r in F.sensitivity}

check(len(sens) == 3, "exactly three LOSO ranges", f"{len(sens)} rows: {sorted(sens)}")
check(all(s in sens for s in ("666", "1024", "2024")),
      "the three preselected splits are present", ", ".join(sorted(sens)))

parsed: dict[str, tuple[float, float]] = {}
for split, r in sens.items():
    m = re.fullmatch(r"\s*([0-9.]+)[–-]([0-9.]+)\s*", r["leave_one_site_out_range"])
    if not m:
        check(False, f"split {split}: LOSO range parses", r["leave_one_site_out_range"])
        continue
    parsed[split] = (float(m.group(1)), float(m.group(2)))
check(len(parsed) == 3, "every LOSO range parses as a low–high pair",
      ", ".join(f"{k}: {v[0]}–{v[1]}" for k, v in sorted(parsed.items())))
check(all(lo < hi for lo, hi in parsed.values()), "every range has low < high")

inside = []
for split, (lo, hi) in parsed.items():
    pt = float(prim[split]["delta_delta_auc"])
    inside.append(lo <= pt <= hi)
check(all(inside), "each split's main ΔΔAUC point lies inside its LOSO range",
      ", ".join(f"{s}: {prim[s]['delta_delta_auc']} in [{parsed[s][0]}, {parsed[s][1]}]"
                for s in sorted(parsed)))

# the sensitivity record must agree with the primary record about the same range
agree = all(sens[s]["leave_one_site_out_range"].strip()
            in prim[s]["leave_one_site_out_range"].strip()
            or prim[s]["leave_one_site_out_range"].strip()
            in sens[s]["leave_one_site_out_range"].strip() for s in parsed)
check(agree, "the two frozen records carry the same LOSO range per split")

# stage wording: 666 comes from the prior audit, 1024/2024 from M4.5-S1
check(prim["666"]["evidence_stage"] == "frozen_prior_audit_M4.4R"
      and prim["1024"]["evidence_stage"] == prim["2024"]["evidence_stage"] == "M4.5-S1",
      "stage labels match the frozen records",
      ", ".join(f"{s}: {prim[s]['evidence_stage']}" for s in ("666", "1024", "2024")))

if fails:
    print("ABORT: " + "; ".join(fails))
    sys.exit(1)

# ---------------------------------------------------------------- draw
CB = {"blue": "#0072B2", "orange": "#D55E00", "green": "#009E73", "grey": "#4D4D4D"}
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8, "axes.labelsize": 8.5,
    "axes.titlesize": 8.5, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
    "legend.fontsize": 7.5, "axes.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
})

fig = plt.figure(figsize=(5.06, 2.30))
ax = fig.add_subplot(111)
ys = {"666": 2.0, "1024": 1.0, "2024": 0.0}
for split in ("666", "1024", "2024"):
    lo, hi = parsed[split]
    y = ys[split]
    ax.plot([lo, hi], [y, y], color=CB["green"], lw=2.0, solid_capstyle="butt", zorder=3)
    ax.plot([lo, hi], [y, y], color=CB["green"], lw=0, marker="|", ms=5, zorder=4)
    pt = float(prim[split]["delta_delta_auc"])
    ax.plot([pt], [y], marker="D", ms=5.2, color="black", zorder=5)
    # the range is printed as the frozen string itself, so the reader sees the stored value
    ax.annotate(sens[split]["leave_one_site_out_range"].strip(), (hi, y),
                textcoords="offset points", xytext=(6, 0), ha="left", va="center",
                fontsize=6.5, color=CB["grey"])
ax.axvline(0, color="0.25", lw=1.0, zorder=1)
ax.set_yticks([ys[s] for s in ("666", "1024", "2024")],
              [STAGE_LABEL[s] for s in ("666", "1024", "2024")])
ax.set_ylim(-0.6, 2.6)
ax.set_ylabel("Preselected outer split")
ax.set_xlabel("Leave-one-site-out interaction, ΔΔAUC")
ax.set_title("LOSO sensitivity range per preselected split", loc="left", pad=6)
ax.legend(handles=[
    Line2D([], [], color=CB["green"], lw=2.0, label="LOSO sensitivity range"),
    Line2D([], [], color="black", marker="D", ls="none", ms=5, label="main ΔΔAUC point"),
], loc="lower right", frameon=False, handlelength=1.8, borderaxespad=0.2)
ax.annotate("This is a sensitivity range, not a confidence interval. Each split is shown "
            "separately; the splits are not combined.",
            xy=(0, -0.34), xycoords="axes fraction", fontsize=7.0, color=CB["grey"],
            va="top", ha="left", annotation_clip=False)

texts = [t.get_text() for t in ax.texts] + [ax.get_title(), ax.get_xlabel(), ax.get_ylabel()]
texts += [t.get_text() for t in ax.get_xticklabels() + ax.get_yticklabels()]
texts += [t.get_text() for t in ax.get_legend().get_texts()]
NEG = re.compile(r"\b(not|no|never|neither|nor|without|rather than)\b[^.;]*$", re.I)
hits, negated = [], []
for t in texts:
    for w in FORBIDDEN:
        for m in re.finditer(re.escape(w), t, re.I):
            (negated if NEG.search(t[:m.start()]) else hits).append(t.strip())
check(not hits, "no annotation asserts " + " / ".join(FORBIDDEN),
      "; ".join(sorted(set(hits))) or f"clean; {len(negated)} inside an explicit denial")

for off, dpi in ((0, 120),):
    fig.savefig(FIGDIR / "FS2_loso_sensitivity.pdf")
    fig.savefig(FIGDIR / "FS2_loso_sensitivity.svg")
    fig.savefig(FIGDIR / "FS2_loso_sensitivity.png", dpi=600)
plt.close(fig)

# read the rendered page back: every number on it must be frozen or an axis tick
svg_strings = re.findall(r">([^<>]+)</text>",
                         (FIGDIR / "FS2_loso_sensitivity.svg").read_text(encoding="utf-8"))
joined = " | ".join(svg_strings)
onpage = {s.strip() for t in svg_strings for s in re.findall(r"[+-]?\d+\.\d{2,6}", t)}
ticks = {t.get_text().strip() for t in ax.get_xticklabels() + ax.get_yticklabels()}
unaccounted = sorted(n for n in onpage
                     if n not in F.canonical and n not in F.tokens() and n not in ticks)
check(not unaccounted, "every numeric string on the page is a frozen value or an axis tick",
      f"{len(onpage)} numbers, {len(ticks)} of them ticks"
      + ("" if not unaccounted else f" — unaccounted: {unaccounted}"))
check(all(STAGE_LABEL[s] in joined for s in ys), "all three stage labels are printed")
range_strings = [sens[s]["leave_one_site_out_range"].strip() for s in ys]
check(all(t in joined for t in range_strings),
      "every LOSO range is printed as its frozen canonical text",
      "; ".join(range_strings))

if fails:
    print("ABORT: " + "; ".join(fails))
    sys.exit(1)

with Image.open(FIGDIR / "FS2_loso_sensitivity.png") as im:
    natural = (round(im.size[0] / 600, 2), round(im.size[1] / 600, 2))
scale = 5.42 / natural[0]
manifest = {
    "figure": "FS2_loso_sensitivity",
    "prompt": "FS2 (supplemental LOSO sensitivity plot)",
    "generated": "2026-09-27",
    "numeric_authority": "S1_FREEZE.yaml -> H3 derived CSVs (sensitivity_summary.csv for the "
                         "ranges, cross_split_primary.csv for the reference points)",
    "inputs": F.inputs,
    "script": {"path": "figures/FS2_loso_sensitivity.py", "sha256": sha(Path(__file__).resolve())},
    "shared_module": {"path": "figures/_frozen_inputs.py",
                      "sha256": sha(Path(__file__).resolve().parent / "_frozen_inputs.py")},
    "command": "python3 figures/FS2_loso_sensitivity.py  (run from the repository root; pinned artifacts were rendered from this source)",
    "outputs": {o: sha(FIGDIR / o) for o in ("FS2_loso_sensitivity.pdf", "FS2_loso_sensitivity.svg",
                                             "FS2_loso_sensitivity.png")},
    "environment": {"python": platform.python_version(), "matplotlib": matplotlib.__version__,
                    "platform": platform.platform()},
    "validation": {"checks": f"{n_checks} PASS, {len(fails)} FAIL",
                   "ranges": {s: list(parsed[s]) for s in sorted(parsed)},
                   "reference_points": {s: prim[s]["delta_delta_auc"] for s in sorted(parsed)},
                   "pairing_rule": "each split shown separately; no pooling and no "
                                    "cross-split summary statistic is computed or drawn"},
    "placement": {"natural_size_in": list(natural), "manuscript_text_width_in": 5.42,
                  "resulting_scale": round(scale, 3),
                  "smallest_label_pt_on_page": round(7.0 * scale, 2)},
    "style": {"vector": ["pdf", "svg"], "preview": "png 600 dpi",
              "interval_encoding": "thick line with end caps for the range, black diamond for "
                                   "the reference point, 0 reference line drawn",
              "no_3d": True, "no_gradients": True},
}
(FIGDIR / "FS2_loso_sensitivity_manifest.yaml").write_text(
    yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")
print(f"\nwrote {FIGDIR}/FS2_loso_sensitivity.{{pdf,svg,png,_manifest.yaml}}")
print("VALIDATION: %d checks, %d PASS, %d FAIL" % (n_checks, n_checks - len(fails), len(fails)))
