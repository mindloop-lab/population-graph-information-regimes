#!/usr/bin/env python3
"""Validate the locked 871-subject ABIDE-I dataset and emit an audit report."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.io import loadmat


EXPECTED = {
    "subjects": 871,
    "labels": {"1": 403, "2": 468},
    "sites": 20,
    "shapes": {"aal": (116, 116), "cc200": (200, 200), "ho": (111, 111)},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def validate_matrix(path: Path, shape: tuple[int, int]) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing matrix: {path}"]
    payload = loadmat(path)
    matrix = payload.get("correlation")
    if matrix is None:
        return [f"missing 'correlation' key: {path}"]
    if matrix.shape != shape:
        errors.append(f"wrong shape {matrix.shape}, expected {shape}: {path}")
    if not np.isfinite(matrix).all():
        errors.append(f"non-finite values: {path}")
    if not np.allclose(matrix, matrix.T, atol=1e-6, rtol=0):
        errors.append(f"non-symmetric matrix: {path}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--atlas", choices=["aal", "cc200", "ho", "all"], default="all")
    args = parser.parse_args()

    metadata = args.root / "metadata"
    manifest_path = metadata / "cohort_manifest.csv"
    ids_path = metadata / "subject_IDs.txt"
    mapping_path = metadata / "subject_id_mapping.csv"
    rows = read_csv(manifest_path)
    mappings = read_csv(mapping_path)
    ids = [line.strip() for line in ids_path.read_text().splitlines() if line.strip()]

    errors: list[str] = []
    subject_ids = [row["SUB_ID"].strip() for row in rows]
    label_counts = Counter(row["DX_GROUP"].strip() for row in rows)
    site_counts = Counter(row["SITE_ID"].strip() for row in rows)
    mapping_ids = [row["legacy_subject_id"].strip() for row in mappings]

    if len(rows) != EXPECTED["subjects"]:
        errors.append(f"manifest rows={len(rows)}, expected 871")
    if len(set(subject_ids)) != len(subject_ids):
        errors.append("duplicate SUB_ID values in cohort manifest")
    if len(ids) != len(set(ids)):
        errors.append("duplicate IDs in subject_IDs.txt")
    if subject_ids != ids:
        errors.append("cohort manifest order differs from subject_IDs.txt")
    if subject_ids != mapping_ids:
        errors.append("cohort manifest order differs from subject_id_mapping.csv")
    if dict(label_counts) != EXPECTED["labels"]:
        errors.append(f"label counts={dict(label_counts)}, expected {EXPECTED['labels']}")
    if len(site_counts) != EXPECTED["sites"]:
        errors.append(f"site count={len(site_counts)}, expected 20")

    atlases = list(EXPECTED["shapes"]) if args.atlas == "all" else [args.atlas]
    matrix_count = 0
    for subject_id in subject_ids:
        for atlas in atlases:
            matrix_path = args.root / "subjects" / subject_id / f"{subject_id}_{atlas}_correlation.mat"
            errors.extend(validate_matrix(matrix_path, EXPECTED["shapes"][atlas]))
            matrix_count += 1

    report = {
        "status": "PASS" if not errors else "FAIL",
        "root": str(args.root.resolve()),
        "n_subjects": len(rows),
        "label_counts_raw": dict(sorted(label_counts.items())),
        "n_sites": len(site_counts),
        "site_counts": dict(sorted(site_counts.items())),
        "atlases_checked": atlases,
        "matrices_checked": matrix_count,
        "hashes": {
            "cohort_manifest.csv": sha256(manifest_path),
            "subject_IDs.txt": sha256(ids_path),
            "subject_id_mapping.csv": sha256(mapping_path),
        },
        "errors": errors,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "n_subjects", "n_sites", "matrices_checked")}))
    if errors:
        for error in errors[:20]:
            print(f"ERROR: {error}")
        if len(errors) > 20:
            print(f"ERROR: {len(errors) - 20} additional errors omitted")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
