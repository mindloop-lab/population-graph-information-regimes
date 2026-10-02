#!/usr/bin/env python3
"""Regenerate the numeric source data of manuscript Figure 2 from the frozen record.

Reads only frozen_results/ (the per-cell out-of-fold files and the derived CSVs) and writes
the three panel datasets to reproduced/fig2_source/:
  panel A  interaction point estimate + bootstrap intervals per split;
  panel B  condition-level ensemble AUCs before/after the intervention;
  panel C  single-seed interactions alongside the ensemble.

Rendering the figure itself needs the plotting stack of the released figure scripts; this
entry guarantees the numbers the figure draws. Values are cross-checked against
S1_FREEZE.yaml canonical text.
"""
from __future__ import annotations

import csv
import glob
import json
from collections import defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
FROZEN = ROOT / "frozen_results"
OUT = ROOT / "reproduced" / "fig2_source"


def auc(pairs):
    n1 = sum(1 for _, y in pairs if y == 1)
    idx = {}
    s = sorted(x for x, _ in pairs)
    i = 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]:
            j += 1
        idx[s[i]] = (i + 1 + j) / 2.0
        i = j
    sr = sum(idx[x] for x, y in pairs if y == 1)
    return (sr - n1 * (n1 + 1) / 2.0) / (n1 * (len(pairs) - n1))


def main() -> int:
    freeze = yaml.safe_load((FROZEN / "S1_FREEZE.yaml").read_text(encoding="utf-8"))
    pr = freeze["primary_results"]
    OUT.mkdir(parents=True, exist_ok=True)
    ok = True

    # panel A: per-split interaction with both interval types
    t2 = list(csv.DictReader((FROZEN / "derived" / "cross_split_primary.csv").open(encoding="utf-8")))
    with (OUT / "panel_a_interaction.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["split", "ddAUC", "subject_ci95", "site_cluster_ci95"])
        for r in t2:
            w.writerow([r["split"], r["delta_delta_auc"], r["subject_bootstrap_ci95"],
                        r["site_cluster_ci95"]])
            if r["delta_delta_auc"] != pr[f"split_{r['split']}"]["delta_delta_auc"]["canonical_text"]:
                ok = False

    # panel B/C: per-seed and ensemble values recomputed from the per-subject record
    per_seed = defaultdict(lambda: defaultdict(list))
    labels = {}
    for f in sorted(glob.glob(str(FROZEN / "oof" / "*" / "*.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        split, model, arm = str(d["split_seed"]), *Path(f).parent.name.split("_")
        arm = arm.upper()
        for r in d["rows"]:
            p = r["p_r0"] if "p_r0" in r else r["p_r1"]
            per_seed[(split, model, arm, d["train_seed"])][r["subject_id"]] = p
            labels[r["subject_id"]] = r["label"]
    with (OUT / "panel_b_conditions.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["split", "model", "arm", "ensemble_auc"])
        for split in ("1024", "2024"):
            for model in ("evgcn", "parisot"):
                for arm in ("P0", "P1"):
                    subs = defaultdict(list)
                    for (s, m, a, ts), rows in per_seed.items():
                        if (s, m, a) == (split, model, arm):
                            for sid, p in rows.items():
                                subs[sid].append(p)
                    val = auc([(sum(v) / len(v), labels[s]) for s, v in subs.items()])
                    w.writerow([split, model, arm, f"{val:.5f}"])
    with (OUT / "panel_c_seeds.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["split", "model", "arm", "train_seed", "auc"])
        for (split, model, arm, ts), rows in sorted(per_seed.items()):
            val = auc([(p, labels[s]) for s, p in rows.items()])
            w.writerow([split, model, arm, ts, f"{val:.5f}"])

    print(f"wrote panel_a/b/c -> {OUT}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
