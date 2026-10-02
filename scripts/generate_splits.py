#!/usr/bin/env python3
"""Generate deterministic mixed-site F/V/Q split registries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedKFold, train_test_split


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def canonical_label(raw: str) -> int:
    if raw == "1":
        return 1
    if raw == "2":
        return 0
    raise ValueError(f"unexpected DX_GROUP: {raw}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_registry(records: list[dict[str, object]], subject_ids: set[str], folds: int) -> None:
    grouped: dict[tuple[int, int], list[dict[str, object]]] = defaultdict(list)
    for record in records:
        grouped[(int(record["split_seed"]), int(record["outer_fold"]))].append(record)
    for key, group in grouped.items():
        by_role: dict[str, set[str]] = defaultdict(set)
        for row in group:
            by_role[str(row["role"])].add(str(row["subject_id"]))
        if set(by_role) != {"fit", "validation", "query"}:
            raise ValueError(f"missing role in split {key}: {set(by_role)}")
        if by_role["fit"] & by_role["validation"] or by_role["fit"] & by_role["query"] or by_role["validation"] & by_role["query"]:
            raise ValueError(f"overlapping roles in split {key}")
        if set().union(*by_role.values()) != subject_ids:
            raise ValueError(f"split {key} does not cover the complete cohort")
    for seed in {int(row["split_seed"]) for row in records}:
        query_counts = Counter(
            str(row["subject_id"])
            for row in records
            if int(row["split_seed"]) == seed and row["role"] == "query"
        )
        if set(query_counts) != subject_ids or set(query_counts.values()) != {1}:
            raise ValueError(f"subjects do not appear exactly once as query for seed {seed}")
        if len({int(row["outer_fold"]) for row in records if int(row["split_seed"]) == seed}) != folds:
            raise ValueError(f"wrong fold count for seed {seed}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--validation-fraction", type=float, default=0.125)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1024, 2024, 2025])
    args = parser.parse_args()

    rows = read_manifest(args.manifest)
    subject_ids = np.array([row["SUB_ID"].strip() for row in rows])
    sites = np.array([row["SITE_ID"].strip() for row in rows])
    labels = np.array([canonical_label(row["DX_GROUP"].strip()) for row in rows])
    strata = np.array([f"{site}::{label}" for site, label in zip(sites, labels, strict=True)])

    # Rare site/label strata cannot support five folds. Falling back to the
    # diagnosis label preserves valid folds; site balance is audited below.
    counts = Counter(strata)
    outer_strata = strata if min(counts.values()) >= args.folds else labels.astype(str)
    records: list[dict[str, object]] = []
    diagnostics: dict[str, object] = {"seeds": {}, "outer_stratification": "site_label" if outer_strata is strata else "label"}

    for seed in args.seeds:
        skf = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=seed)
        seed_diag: list[dict[str, object]] = []
        for fold, (fit_val_idx, query_idx) in enumerate(skf.split(subject_ids, outer_strata)):
            inner_strata = strata[fit_val_idx]
            inner_counts = Counter(inner_strata)
            if min(inner_counts.values()) < 2:
                inner_strata = labels[fit_val_idx].astype(str)
            fit_idx, validation_idx = train_test_split(
                fit_val_idx,
                test_size=args.validation_fraction,
                random_state=seed + fold,
                stratify=inner_strata,
            )
            roles = {
                "fit": fit_idx,
                "validation": validation_idx,
                "query": query_idx,
            }
            for role, indices in roles.items():
                for idx in sorted(indices, key=lambda value: subject_ids[value]):
                    records.append(
                        {
                            "subject_id": subject_ids[idx],
                            "site_id": sites[idx],
                            "label": int(labels[idx]),
                            "split_seed": seed,
                            "outer_fold": fold,
                            "role": role,
                        }
                    )
            seed_diag.append(
                {
                    "fold": fold,
                    "n_fit": len(fit_idx),
                    "n_validation": len(validation_idx),
                    "n_query": len(query_idx),
                    "query_label_counts": dict(sorted(Counter(labels[query_idx].tolist()).items())),
                    "query_site_counts": dict(sorted(Counter(sites[query_idx].tolist()).items())),
                }
            )
        diagnostics["seeds"][str(seed)] = seed_diag

    validate_registry(records, set(subject_ids.tolist()), args.folds)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = ["subject_id", "site_id", "label", "split_seed", "outer_fold", "role"]
    with args.out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    diagnostics["status"] = "PASS"
    diagnostics["manifest"] = str(args.manifest.resolve())
    diagnostics["manifest_sha256"] = sha256(args.manifest)
    diagnostics["registry_sha256"] = sha256(args.out_csv)
    diagnostics["n_records"] = len(records)
    args.out_json.write_text(json.dumps(diagnostics, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "records": len(records), "sha256": diagnostics["registry_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
