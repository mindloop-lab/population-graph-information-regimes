#!/usr/bin/env python3
"""Aggregate EV-GCN per-cell jsons into the standard order-controlled registry
(train-seed averaged per subject), reusing statistics_bootstrap_lim / render.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell-dir", type=Path, required=True)
    ap.add_argument("--glob", default="ev_*_*_*.json")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    acc = defaultdict(lambda: {"p1": [], "p2": []})
    meta = {}
    for f in sorted(glob.glob(str(args.cell_dir / args.glob))):
        d = json.loads(Path(f).read_text())
        for r in d.get("rows", []):
            key = (str(r["split_seed"]), r["subject_id"])
            acc[key]["p1"].append(float(r["p_r1"])); acc[key]["p2"].append(float(r["p_r2"]))
            meta[r["subject_id"]] = (r["site"], int(r["label"]))
    rows = []
    for (ss, sid), v in sorted(acc.items()):
        p1 = float(np.mean(v["p1"])); p2 = float(np.mean(v["p2"]))
        site, label = meta[sid]
        rows.append({"model": "evgcn", "split_seed": ss, "subject_id": sid, "site": site, "label": label,
                     "p_r1": round(p1, 8), "p_r2": round(p2, 8), "abs_shift": round(abs(p1 - p2), 8)})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"wrote {args.out}  rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
