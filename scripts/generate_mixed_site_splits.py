#!/usr/bin/env python3
"""Generate deterministic site-by-diagnosis balanced F/V/Q registries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


def stable_seed(*parts: object) -> int:
    digest = hashlib.sha256("::".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big")


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def canonical_label(raw: str) -> int:
    return {"1": 1, "2": 0}[raw]


def assign_outer_folds(rows: list[dict[str, str]], folds: int, seed: int) -> dict[int, list[int]]:
    strata: dict[tuple[str, int], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        strata[(row["SITE_ID"].strip(), canonical_label(row["DX_GROUP"].strip()))].append(index)
    assigned: dict[int, list[int]] = defaultdict(list)
    for key in sorted(strata):
        indices = strata[key]
        rng = random.Random(stable_seed(seed, "outer", *key))
        rng.shuffle(indices)
        offset = rng.randrange(folds)
        for position, index in enumerate(indices):
            assigned[(offset + position) % folds].append(index)
    return assigned


def select_validation(
    rows: list[dict[str, str]], fit_val_indices: list[int], fraction: float, seed: int, fold: int
) -> set[int]:
    strata: dict[tuple[str, int], list[int]] = defaultdict(list)
    for index in fit_val_indices:
        row = rows[index]
        strata[(row["SITE_ID"].strip(), canonical_label(row["DX_GROUP"].strip()))].append(index)
    selected: set[int] = set()
    for key in sorted(strata):
        indices = strata[key]
        rng = random.Random(stable_seed(seed, fold, "validation", *key))
        rng.shuffle(indices)
        count = 0 if len(indices) == 1 else max(1, round(len(indices) * fraction))
        count = min(count, len(indices) - 1)
        selected.update(indices[:count])
    return selected


def validate(records: list[dict[str, object]], subject_ids: set[str], folds: int) -> None:
    by_split: dict[tuple[int, int], list[dict[str, object]]] = defaultdict(list)
    for row in records:
        by_split[(int(row["split_seed"]), int(row["outer_fold"]))].append(row)
    for key, group in by_split.items():
        roles: dict[str, set[str]] = defaultdict(set)
        for row in group:
            roles[str(row["role"])].add(str(row["subject_id"]))
        if set(roles) != {"fit", "validation", "query"}:
            raise ValueError(f"missing role in {key}")
        if roles["fit"] & roles["validation"] or roles["fit"] & roles["query"] or roles["validation"] & roles["query"]:
            raise ValueError(f"overlapping role in {key}")
        if set().union(*roles.values()) != subject_ids:
            raise ValueError(f"incomplete cohort in {key}")
    for seed in sorted({int(row["split_seed"]) for row in records}):
        counts = Counter(
            str(row["subject_id"])
            for row in records
            if int(row["split_seed"]) == seed and row["role"] == "query"
        )
        if set(counts) != subject_ids or set(counts.values()) != {1}:
            raise ValueError(f"query coverage failure for seed {seed}")
        if len({int(row["outer_fold"]) for row in records if int(row["split_seed"]) == seed}) != folds:
            raise ValueError(f"fold count failure for seed {seed}")


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
    all_indices = set(range(len(rows)))
    records: list[dict[str, object]] = []
    diagnostics: dict[str, object] = {
        "status": "PASS",
        "algorithm": "within-site-within-diagnosis shuffled round-robin",
        "validation_algorithm": "within-site-within-diagnosis proportional sample",
        "seeds": {},
    }
    for seed in args.seeds:
        query_folds = assign_outer_folds(rows, args.folds, seed)
        fold_diagnostics = []
        for fold in range(args.folds):
            query = set(query_folds[fold])
            fit_val = sorted(all_indices - query)
            validation = select_validation(rows, fit_val, args.validation_fraction, seed, fold)
            fit = set(fit_val) - validation
            for role, indices in {"fit": fit, "validation": validation, "query": query}.items():
                for index in sorted(indices, key=lambda item: int(rows[item]["SUB_ID"])):
                    row = rows[index]
                    records.append(
                        {
                            "subject_id": row["SUB_ID"].strip(),
                            "site_id": row["SITE_ID"].strip(),
                            "label": canonical_label(row["DX_GROUP"].strip()),
                            "split_seed": seed,
                            "outer_fold": fold,
                            "role": role,
                        }
                    )
            query_strata = Counter(
                (rows[index]["SITE_ID"].strip(), canonical_label(rows[index]["DX_GROUP"].strip()))
                for index in query
            )
            fold_diagnostics.append(
                {
                    "fold": fold,
                    "n_fit": len(fit),
                    "n_validation": len(validation),
                    "n_query": len(query),
                    "query_label_counts": dict(sorted(Counter(canonical_label(rows[index]["DX_GROUP"].strip()) for index in query).items())),
                    "query_site_counts": dict(sorted(Counter(rows[index]["SITE_ID"].strip() for index in query).items())),
                    "query_strata": {f"{site}::{label}": count for (site, label), count in sorted(query_strata.items())},
                }
            )
        diagnostics["seeds"][str(seed)] = fold_diagnostics

    subject_ids = {row["SUB_ID"].strip() for row in rows}
    validate(records, subject_ids, args.folds)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = ["subject_id", "site_id", "label", "split_seed", "outer_fold", "role"]
    with args.out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    diagnostics["manifest"] = str(args.manifest.resolve())
    diagnostics["manifest_sha256"] = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    diagnostics["registry_sha256"] = hashlib.sha256(args.out_csv.read_bytes()).hexdigest()
    diagnostics["n_records"] = len(records)
    args.out_json.write_text(json.dumps(diagnostics, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "records": len(records), "sha256": diagnostics["registry_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
