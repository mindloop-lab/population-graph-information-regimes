#!/usr/bin/env python3
"""Negative control — step 1: cache the raw subject-level feature matrix.

Rebuilds the exact vectors used by the controlled campaign (upper-triangular cc200
correlation, float32) and the manifest-derived phenotypes, then writes a single npz plus a
sha256 of the cache and of the source file list. No split, no model, no prediction here.

Usage:
    python nc_prepare_features.py --data-root <root> --out <dir>
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.io import loadmat


def vector(root: Path, sid: str, atlas: str = "cc200") -> np.ndarray:
    m = np.asarray(loadmat(root / "subjects" / sid / f"{sid}_{atlas}_correlation.mat")["correlation"],
                   dtype=np.float32)
    return m[np.triu_indices(m.shape[0], k=1)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    man = {r["SUB_ID"].strip(): r for r in
           csv.DictReader((args.data_root / "metadata" / "cohort_manifest.csv").open(newline="", encoding="utf-8-sig"))}
    ids = sorted(man)
    print(f"subjects: {len(ids)}")

    hashes = {}
    rows = []
    for i, sid in enumerate(ids):
        f = args.data_root / "subjects" / sid / f"{sid}_cc200_correlation.mat"
        hashes[f"{sid}_cc200_correlation.mat"] = hashlib.sha256(f.read_bytes()).hexdigest()
        rows.append(vector(args.data_root, sid))
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(ids)}", flush=True)

    X = np.stack(rows)
    sites = np.array([man[s]["SITE_ID"].strip() for s in ids])
    sex = np.array([int(float(man[s]["SEX"])) for s in ids], dtype=np.int64)
    age = np.array([float(man[s]["AGE_AT_SCAN"]) for s in ids], dtype=np.float64)

    args.out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out / "features.npz", X=X, ids=np.array(ids), sites=sites,
                        sex=sex, age=age)
    file_hash = hashlib.sha256((args.out / "features.npz").read_bytes()).hexdigest()
    src_hash = hashlib.sha256("".join(f"{k}:{v}\n" for k, v in sorted(hashes.items())).encode()).hexdigest()
    meta = {"n_subjects": len(ids), "n_features": int(X.shape[1]), "dtype": str(X.dtype),
            "features_npz_sha256": file_hash, "source_mat_manifest_sha256": src_hash,
            "n_source_files": len(hashes)}
    (args.out / "features_manifest.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
