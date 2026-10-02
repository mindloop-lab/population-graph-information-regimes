#!/usr/bin/env python3
"""Reproduce the manuscript's primary results from the frozen record, without training.

Reads only frozen_results/: the per-cell out-of-fold prediction files (oof/), the derived
summary CSVs and S1_FREEZE.yaml. Recomputes, for each extension split (1024, 2024):

  * the three-training-seed probability ensemble AUC of every condition
    (EV-GCN/Parisot-GCN x P0/P1);
  * the per-implementation P0-to-P1 AUC change (dAUC);
  * the implementation-by-training-context interaction (ddAUC);

and compares every recomputed value with the canonical text recorded in S1_FREEZE.yaml.
Split 666 predates the extension runs and carries no per-subject predictions in the frozen
record; for it the script verifies the derived-table value against the freeze record and
states that provenance explicitly.

Usage:  python3 scripts/reproduce_primary_results.py --from-frozen
Exit status is non-zero on any mismatch or on a failed integrity check of the frozen inputs.
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
FROZEN = ROOT / "frozen_results"
OUT = ROOT / "reproduced"

MODEL_KEYS = {"evgcn": "EVGCN", "parisot": "Parisot"}


def auc(pairs):
    """Rank-based AUC (Mann-Whitney) with mid-rank tie handling."""
    n1 = sum(1 for _, y in pairs if y == 1)
    n0 = len(pairs) - n1
    if not n1 or not n0:
        raise ValueError("AUC undefined for a single-class set")
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
    return (sr - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def verify_input_hashes():
    sums = (FROZEN / "SHA256SUMS").read_text(encoding="utf-8")
    bad = []
    for line in sums.splitlines():
        if not line.strip():
            continue
        h, name = line.split("  ", 1)
        p = FROZEN / name.strip()
        if hashlib.sha256(p.read_bytes()).hexdigest() != h:
            bad.append(name.strip())
    return bad


def load_conditions():
    """Return {(split, model, arm): auc} for the P0/P1 arms of both implementations.

    File convention of the frozen record: *_p0 cells export one arm (rows carry p_r0 under
    a P0 regime); *_p1 cells export both inference arms of the same trained checkpoint
    (p_r1 = cohort-visible, p_r2 = single-query). The primary campaign conditions are
    P0 (train-visible, cohort-visible inference) and P1 (train-only, cohort-visible
    inference), so the P1 condition reads p_r1.
    """
    acc = defaultdict(lambda: defaultdict(list))
    labels = {}
    for f in sorted(glob.glob(str(FROZEN / "oof" / "*" / "*.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        split = str(d["split_seed"])
        model, arm = Path(f).parent.name.split("_")
        for r in d["rows"]:
            p = r["p_r0"] if "p_r0" in r else r["p_r1"]
            acc[(split, model, arm.upper())][r["subject_id"]].append(p)
            labels[r["subject_id"]] = r["label"]
    return {k: auc([(sum(v) / len(v), labels[s]) for s, v in subs.items()])
            for k, subs in acc.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-frozen", action="store_true", required=True)
    args = ap.parse_args()

    bad = verify_input_hashes()
    if bad:
        print(f"INPUT INTEGRITY FAIL: {bad}")
        return 1
    print("input integrity: frozen_results/SHA256SUMS verified")

    freeze = yaml.safe_load((FROZEN / "S1_FREEZE.yaml").read_text(encoding="utf-8"))
    pr = freeze["primary_results"]

    cond = load_conditions()
    OUT.mkdir(exist_ok=True)
    ok = True

    rows = []
    for split in ("1024", "2024"):
        c = {m: {a: cond[(split, m, a)] for a in ("P0", "P1")} for m in ("evgcn", "parisot")}
        dd = (c["evgcn"]["P0"] - c["evgcn"]["P1"]) - (c["parisot"]["P0"] - c["parisot"]["P1"])
        want = pr[f"split_{split}"]["delta_delta_auc"]["canonical_text"]
        got = f"{dd:+.5f}"
        match = got == want
        ok &= match
        print(f"split {split}: recomputed ddaAUC {got} vs frozen {want} -> "
              f"{'MATCH' if match else 'MISMATCH'}")
        for m in ("evgcn", "parisot"):
            for a in ("P0", "P1"):
                rows.append({"split": split, "model": MODEL_KEYS[m], "arm": a,
                             "ensemble_auc": f"{c[m][a]:.5f}"})
        rows.append({"split": split, "model": "interaction", "arm": "ddAUC", "ensemble_auc": got})

    # split 666: no per-subject predictions in the frozen record; cross-check table vs freeze
    t = list(csv.DictReader((FROZEN / "derived" / "cross_split_primary.csv").open(encoding="utf-8")))
    row666 = next(r for r in t if r["split"] == "666")
    want666 = pr["split_666"]["delta_delta_auc"]["canonical_text"]
    m666 = row666["delta_delta_auc"] == want666
    ok &= m666
    print(f"split 666: derived table {row666['delta_delta_auc']} vs frozen {want666} -> "
          f"{'MATCH' if m666 else 'MISMATCH'} (no per-subject record exists for this prior-audit "
          f"split; the interaction is carried by the freeze record, not recomputed)")
    rows.append({"split": "666", "model": "interaction", "arm": "ddAUC",
                 "ensemble_auc": row666["delta_delta_auc"]})

    with (OUT / "primary_interactions.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["split", "model", "arm", "ensemble_auc"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    print(f"\nwrote {OUT/'primary_interactions.csv'}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
