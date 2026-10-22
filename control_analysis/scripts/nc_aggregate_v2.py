#!/usr/bin/env python3
"""Strict aggregation gate for the negative-control matrix (v2).

Every check below must pass for a cell set to produce PASS. Nothing is skipped silently: a
missing file, an extra file, a duplicate key, a query-set mismatch, non-finite values or a
metadata mismatch each fail the run.

Usage:
    nc_aggregate_v2.py --cells cells --out invariance_deterministic_v2.json --expect-dropout 0.0
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
SPLIT = None  # set from --split-registry
SPLITS = (1024, 2024)
FOLDS = tuple(range(5))
SEEDS = (11, 22, 33)
NAME_RE = re.compile(r"^(P0|P1)_s(1024|2024)_f([0-4])_t(11|22|33)\.json$")
TOL = 1e-6


def registry(split_file: Path):
    roles = {}
    with split_file.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            key = (int(r["split_seed"]), int(r["outer_fold"]))
            roles.setdefault(key, {"fit": set(), "validation": set(), "query": set(),
                                   "label": {}})
            roles[key][r["role"]].add(r["subject_id"])
            roles[key]["label"][r["subject_id"]] = int(r["label"])
    return roles


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", type=Path, required=True)
    ap.add_argument("--split-registry", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--expect-dropout", type=float, required=True)
    args = ap.parse_args()
    global SPLIT
    SPLIT = args.split_registry

    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})
        return ok

    files = sorted(args.cells.glob("*.json"))
    named = {p.name: p for p in files if NAME_RE.match(p.name)}
    extras = [p.name for p in files if not NAME_RE.match(p.name)]
    check("only canonical cell filenames present", not extras, f"extras: {extras}")
    check("cell file count is 60", len(named) == 60, f"found {len(named)}")

    data = {}
    dupes = []
    for name, p in named.items():
        m = NAME_RE.match(name)
        key = (int(m.group(2)), int(m.group(3)), int(m.group(4)))
        regime = m.group(1)
        if key in data and regime in data[key]:
            dupes.append(name)
        data.setdefault(key, {})[regime] = json.loads(p.read_text())
    check("no duplicate (split, fold, seed, regime) keys", not dupes, f"duplicates: {dupes}")

    expected = {(s, f, t) for s in SPLITS for f in FOLDS for t in SEEDS}
    check("expected 30 (split, fold, seed) keys present",
          set(data) == expected,
          f"missing {sorted(expected - set(data))}, extra {sorted(set(data) - expected)}")
    check("every key has both regimes",
          all(set(v) == {"P0", "P1"} for v in data.values()),
          f"incomplete: {[k for k, v in data.items() if set(v) != {'P0', 'P1'}]}")

    roles = registry(SPLIT)
    rows = []
    problems = []

    for key in sorted(data):
        ss, fold, ts = key
        a, b = data[key]["P0"], data[key]["P1"]
        tag = f"{ss}/{fold}/{ts}"

        for d, regime in ((a, "P0"), (b, "P1")):
            if d.get("split_seed") != ss or d.get("fold") != fold or d.get("train_seed") != ts:
                problems.append(f"{tag}/{regime}: metadata does not match filename")
            if d.get("regime") != regime:
                problems.append(f"{tag}/{regime}: regime field {d.get('regime')}")
            if abs(float(d.get("dropout", -1)) - args.expect_dropout) > 1e-12:
                problems.append(f"{tag}/{regime}: dropout {d.get('dropout')} != {args.expect_dropout}")
            if d.get("features") != 2000:
                problems.append(f"{tag}/{regime}: features {d.get('features')}")
            if not (1 <= int(d.get("epochs", 0)) <= 300):
                problems.append(f"{tag}/{regime}: epochs {d.get('epochs')}")

        # query membership must equal the registry, and both regimes must agree
        q = set(a["predictions"])
        if q != roles[(ss, fold)]["query"]:
            problems.append(f"{tag}: P0 query set differs from registry")
        if q != set(b["predictions"]):
            problems.append(f"{tag}: P0/P1 query sets differ")
        if a.get("n_query") != len(q) or b.get("n_query") != len(q):
            problems.append(f"{tag}: n_query does not equal the prediction count")

        vals = np.array([a["predictions"][k] for k in sorted(q)])
        vals_b = np.array([b["predictions"][k] for k in sorted(q)])
        if not (np.isfinite(vals).all() and np.isfinite(vals_b).all()):
            problems.append(f"{tag}: non-finite prediction")
        if vals.min() < 0 or vals.max() > 1 or vals_b.min() < 0 or vals_b.max() > 1:
            problems.append(f"{tag}: prediction outside [0,1]")

        if a["xn_sha256"] != b["xn_sha256"]:
            problems.append(f"{tag}: feature-matrix hash differs between regimes")
        if a["train_nodes_sha256"] == b["train_nodes_sha256"]:
            problems.append(f"{tag}: training node sets identical (regime not applied)")

        y = np.array([roles[(ss, fold)]["label"][k] for k in sorted(q)])
        auc0 = float(roc_auc_score(y, vals))
        auc1 = float(roc_auc_score(y, vals_b))
        dp = np.abs(vals - vals_b)
        rows.append({"split": ss, "fold": fold, "seed": ts, "n_query": len(q),
                     "max_dp": float(dp.max()), "mean_dp": float(dp.mean()),
                     "auc_p0": auc0, "auc_p1": auc1, "d_auc": auc0 - auc1,
                     "n_train_p0": a["n_train_nodes"], "n_train_p1": b["n_train_nodes"],
                     "val_auc_p0": a["best_val_auc"], "val_auc_p1": b["best_val_auc"],
                     "epochs_p0": a["epochs"], "epochs_p1": b["epochs"]})

    check("per-cell metadata, query membership, finiteness and identity consistent",
          not problems, "; ".join(problems[:6]))

    # identity across the whole set: one feature hash per split
    # The feature matrix is fold-specific (feature selection is fitted on the fit fold), so the
    # identity requirement is: one hash per (split, fold), shared by both regimes and all seeds.
    hashes = {}
    for key in sorted(data):
        h = data[key]["P0"]["xn_sha256"]
        hashes.setdefault((key[0], key[1]), set()).add(h)
    check("one feature-matrix hash per (split, fold), shared by both regimes and all seeds",
          all(len(v) == 1 for v in hashes.values()),
          json.dumps({f"{k[0]}/{k[1]}": len(v) for k, v in hashes.items()}))

    max_dp = max(r["max_dp"] for r in rows) if rows else float("nan")
    max_dauc = max(abs(r["d_auc"]) for r in rows) if rows else float("nan")
    max_mean = float(np.mean([r["mean_dp"] for r in rows])) if rows else float("nan")
    check("max |dp| within the registered tolerance", max_dp <= TOL, f"{max_dp:.3e} vs {TOL:g}")
    check("query AUC difference is exactly zero in every pair", max_dauc == 0.0, f"{max_dauc:.3e}")

    verdict = "PASS" if all(c["pass"] for c in checks) else "FAIL"
    summary = {
        "cells": len(rows), "files": len(named), "dropout": args.expect_dropout,
        "tolerance": TOL, "max_dp": max_dp, "mean_dp": max_mean,
        "max_abs_d_auc": max_dauc,
        "median_query_auc": float(np.median([r["auc_p0"] for r in rows])) if rows else None,
        "n_train_min": min(min(r["n_train_p0"], r["n_train_p1"]) for r in rows) if rows else None,
        "n_train_max": max(max(r["n_train_p0"], r["n_train_p1"]) for r in rows) if rows else None,
        "feature_hash_by_split_fold": {f"{k[0]}/{k[1]}": sorted(v) for k, v in hashes.items()},
        "verdict": verdict,
        "checks": checks,
        "failures": [c["check"] for c in checks if not c["pass"]],
    }
    args.out.write_text(json.dumps({"summary": summary, "cells": rows}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("verdict", "cells", "max_dp", "mean_dp",
                                              "max_abs_d_auc", "median_query_auc",
                                              "failures")}, indent=2))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
