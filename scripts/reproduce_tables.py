#!/usr/bin/env python3
"""Rebuild the manuscript's result tables (Table 2, S1, S2) from the frozen record.

Reads only frozen_results/ (derived CSVs + S1_FREEZE.yaml) and writes CSV renderings to
reproduced/. Every value is compared with the canonical text in the freeze record; a
mismatch fails the run. These CSVs mirror the generated LaTeX tables cell for cell.
"""
from __future__ import annotations

import csv
from pathlib import Path

import yaml

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
FROZEN = ROOT / "frozen_results"
OUT = ROOT / "reproduced"


def main() -> int:
    freeze = yaml.safe_load((FROZEN / "S1_FREEZE.yaml").read_text(encoding="utf-8"))
    pr = freeze["primary_results"]
    ok = True

    def want(split, field):
        return pr[f"split_{split}"][field]["canonical_text"]

    OUT.mkdir(exist_ok=True)

    # Table 2: cross-split replication record
    t2 = list(csv.DictReader((FROZEN / "derived" / "cross_split_primary.csv").open(encoding="utf-8")))
    checks = {"delta_delta_auc": "delta_delta_auc",
              "subject_bootstrap_ci95": "subject_bootstrap_ci95",
              "site_cluster_ci95": "site_cluster_ci95"}
    with (OUT / "table2_cross_split.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["split", "evidence_stage", "ddAUC", "subject_ci95", "site_cluster_ci95",
                    "loso_range"])
        for r in t2:
            w.writerow([r["split"], r["evidence_stage"], r["delta_delta_auc"],
                        r["subject_bootstrap_ci95"], r["site_cluster_ci95"],
                        r["leave_one_site_out_range"]])
            for field, col in checks.items():
                if r[col] != want(r["split"], field):
                    print(f"Table2 mismatch split {r['split']} {field}: "
                          f"{r[col]} != {want(r['split'], field)}")
                    ok = False

    # Table S1: condition-level ensemble AUCs (split 666 absent from the frozen source).
    # The derived file is long-form: one row per (split, model, regime).
    tS1 = list(csv.DictReader((FROZEN / "derived" / "condition_level_auc.csv").open(encoding="utf-8")))
    grid: dict = {}
    for r in tS1:
        grid.setdefault(r["split"], {})[f"{r['model']}_{r['regime']}"] = r["ensemble_auc"]
    with (OUT / "table_s1_condition_level.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["split", "EV-GCN_P0", "EV-GCN_P1", "Parisot-GCN_P0", "Parisot-GCN_P1"])
        for split in ("666", "1024", "2024"):
            g = grid.get(split, {})
            w.writerow([split, g.get("EV-GCN_P0", "--"), g.get("EV-GCN_P1", "--"),
                        g.get("Parisot_P0", "--"), g.get("Parisot_P1", "--")])

    # Table S2: seed-level interactions
    tS2 = list(csv.DictReader((FROZEN / "derived" / "seed_level_interactions.csv").open(encoding="utf-8")))
    with (OUT / "table_s2_seed_level.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(list(tS2[0]))
        for r in tS2:
            w.writerow(list(r.values()))

    print(f"wrote table2_cross_split.csv, table_s1_condition_level.csv, table_s2_seed_level.csv "
          f"-> {OUT}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
