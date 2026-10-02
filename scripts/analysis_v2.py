#!/usr/bin/env python3
"""Paper A analysis layer v2 (WP1/WP2/WP3).

WP1  unified registry v2: model x split_seed x subject x regime (R1-C / R2-Q),
     plus intervention registries (matched-site / dose / LOSO) normalised into a
     single schema, plus the RF negative control cells.
WP2  architecture x regime interaction (pre-registered family
     `architecture_interactions` in configs/study/locked_campaign_v1.yaml):
     paired two-stage site->subject bootstrap difference-in-differences of
     CVE_AUC and CIS, with Holm correction over the pre-registered contrasts.
WP3  repeated-split statistical layer: split_seed level variance separated from
     subject-level sampling variance (EXPERIMENT_PLAN 7.6).

No new model, dataset, atlas or tuning. Reads only frozen artifacts.
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent

MODEL_REGIME_SOURCES = {
    "lim": "results/ordercontrolled/lim_oc_registry_avg.csv",
    "ev_gcn": "results/evgcn/ev_oc_registry_avg.csv",
    "parisot_gcn": "results/parisot/pa_oc_registry_avg.csv",
}
CELL_GLOBS = {
    "lim": "results/locked/lim_split*_fold*_seed*.json",
    "ev_gcn": "results/evgcn/ev_*_*_*.json",
    "parisot_gcn": "results/parisot/pa_*_*_*.json",
}
MATCHSITE_GLOB = "results/matchsite/*_matchsite_registry_*.csv"
LOSO_GLOB = "results/loso_oc/loso_registry_avg.csv"
DOSE_GLOB = "results/dose/*_dose_*.json"

REGISTRY_FIELDS = [
    "experiment_id", "model", "track", "regime", "subject_id", "site", "label",
    "prediction", "split_seed", "outer_fold", "train_seed", "context_size",
    "context_draw", "intervention", "source_commit", "environment_hash",
]
INTERVENTION_FIELDS = [
    "experiment_id", "model", "intervention", "subject_id", "site", "label",
    "p_reference", "p_treatment", "abs_shift", "context_size", "context_draw",
    "split_seed", "outer_fold", "source_commit", "environment_hash",
]


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    except Exception:
        return ""


def env_hash() -> str:
    f = REPO / "uv.lock"
    return hashlib.sha256(f.read_bytes()).hexdigest()[:16] if f.is_file() else ""


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def build_registry_v2(commit: str, ehash: str) -> tuple[list[dict], list[dict], dict]:
    rows: list[dict] = []
    for model, rel in MODEL_REGIME_SOURCES.items():
        f = REPO / rel
        if not f.is_file():
            print(f"WARN missing {rel}")
            continue
        for r in read_csv(f):
            base = {
                "experiment_id": f"{model}_regime", "model": model, "track": "A",
                "subject_id": r["subject_id"], "site": r["site"], "label": r["label"],
                "split_seed": r["split_seed"], "outer_fold": "", "train_seed": "",
                "context_size": "", "context_draw": "", "intervention": "none",
                "source_commit": commit, "environment_hash": ehash,
            }
            rows.append({**base, "regime": "R1-C", "prediction": r["p_r1"]})
            rows.append({**base, "regime": "R2-Q", "prediction": r["p_r2"]})

    # RF negative control (context-null runner). Emitted by scripts/run_rf_matrix.py.
    rf_glob = sorted(glob.glob(str(REPO / "results/rf/rf_registry_*.csv")))
    rf_cells = 0
    for f in rf_glob:
        for r in read_csv(Path(f)):
            rf_cells += 1
            base = {
                "experiment_id": "rf_negative_control", "model": "rf", "track": "A",
                "subject_id": r["subject_id"], "site": r["site"], "label": r["label"],
                "split_seed": r["split_seed"], "outer_fold": r.get("outer_fold", ""),
                "train_seed": r.get("train_seed", ""), "context_size": "",
                "context_draw": "", "intervention": "none",
                "source_commit": commit, "environment_hash": ehash,
            }
            rows.append({**base, "regime": "R1-C", "prediction": r["p_r1"]})
            rows.append({**base, "regime": "R2-Q", "prediction": r["p_r2"]})

    interventions: list[dict] = []
    # matched-site: p_none / p_same / p_cross
    for f in sorted(glob.glob(str(REPO / MATCHSITE_GLOB))):
        name = Path(f).name
        model = name.split("_")[0]
        for r in read_csv(Path(f)):
            for ref_key, treat_key, label in (("p_none", "p_same", "same_site"),
                                              ("p_none", "p_cross", "cross_site"),
                                              ("p_cross", "p_same", "same_vs_cross")):
                interventions.append({
                    "experiment_id": f"{model}_matched_site", "model": model,
                    "intervention": f"matched_site::{label}",
                    "subject_id": r["subject_id"], "site": r["site"], "label": r["label"],
                    "p_reference": r[ref_key], "p_treatment": r[treat_key],
                    "abs_shift": "", "context_size": "",
                    "context_draw": "", "split_seed": r["split_seed"],
                    "outer_fold": name.split("_")[-1].replace(".csv", ""),
                    "source_commit": commit, "environment_hash": ehash,
                })
    # LOSO
    for f in sorted(glob.glob(str(REPO / LOSO_GLOB))):
        for r in read_csv(Path(f)):
            interventions.append({
                "experiment_id": "lim_loso", "model": "lim", "intervention": "strict_loso",
                "subject_id": r["subject_id"], "site": r["site"], "label": r["label"],
                "p_reference": r["p_r2"], "p_treatment": r["p_r1"],
                "abs_shift": r.get("abs_shift", ""), "context_size": "all_same_site",
                "context_draw": "", "split_seed": r["split_seed"], "outer_fold": "",
                "source_commit": commit, "environment_hash": ehash,
            })
    # dose summaries (grid over context size, pre-registered E5)
    dose_summary = {}
    for f in sorted(glob.glob(str(REPO / DOSE_GLOB))):
        d = json.loads(Path(f).read_text())
        key = Path(f).stem
        dose_summary[key] = {k: v for k, v in d.items() if k not in {"fold"} or True}
        for grid_key, val in d.items():
            if not isinstance(val, dict):
                continue
            interventions.append({
                "experiment_id": "dose_grid", "model": key.split("_")[0],
                "intervention": f"context_dose::c={grid_key}",
                "subject_id": "", "site": "", "label": "",
                "p_reference": "", "p_treatment": "",
                "abs_shift": val.get("dose_mean_abs_shift", ""),
                "context_size": grid_key, "context_draw": val.get("n_draws_total", ""),
                "split_seed": d.get("split_seed", ""), "outer_fold": d.get("fold", ""),
                "source_commit": commit, "environment_hash": ehash,
            })

    meta = {"regime_rows": len(rows), "rf_cells": rf_cells,
            "intervention_rows": len(interventions), "dose_files": len(dose_summary)}
    return rows, interventions, meta


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


# --------------------------------------------------------------------------- #
# statistics
# --------------------------------------------------------------------------- #
def load_model_frame(model: str, split_seeds: list[int]) -> dict:
    """subject-level arrays for one model, keyed by split_seed."""
    src = REPO / MODEL_REGIME_SOURCES[model]
    acc: dict[int, dict[str, dict]] = defaultdict(dict)
    for r in read_csv(src):
        ss = int(r["split_seed"])
        if ss not in split_seeds:
            continue
        acc[ss][r["subject_id"]] = r
    out = {}
    for ss, subj in acc.items():
        ids = sorted(subj)
        out[ss] = {
            "subject_id": np.array(ids),
            "site": np.array([subj[s]["site"] for s in ids]),
            "label": np.array([int(subj[s]["label"]) for s in ids]),
            "p1": np.array([float(subj[s]["p_r1"]) for s in ids]),
            "p2": np.array([float(subj[s]["p_r2"]) for s in ids]),
        }
    return out


def auc(labels: np.ndarray, scores: np.ndarray) -> float:
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=np.float64)
    ranks[order] = np.arange(1, len(scores) + 1)
    # average ties
    sorted_scores = scores[order]
    i = 0
    while i < len(sorted_scores):
        j = i
        while j + 1 < len(sorted_scores) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    pos = labels == 1
    n_pos, n_neg = int(pos.sum()), int((~pos).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def stats_block(frame: dict, rng: np.random.Generator, n_boot: int) -> tuple[dict, np.ndarray, np.ndarray]:
    labels, p1, p2, sites = frame["label"], frame["p1"], frame["p2"], frame["site"]
    cis_point = float(np.mean(np.abs(p1 - p2)))
    cve_point = auc(labels, p1) - auc(labels, p2)
    unique_sites = np.unique(sites)
    site_index = {s: np.flatnonzero(sites == s) for s in unique_sites}
    boot_cis = np.empty(n_boot)
    boot_cve = np.empty(n_boot)
    for b in range(n_boot):
        drawn_sites = rng.choice(unique_sites, size=len(unique_sites), replace=True)
        idx = np.concatenate([rng.choice(site_index[s], size=len(site_index[s]), replace=True)
                              for s in drawn_sites])
        if labels[idx].sum() in (0, len(idx)):
            boot_cis[b] = np.nan
            boot_cve[b] = np.nan
            continue
        boot_cis[b] = np.mean(np.abs(p1[idx] - p2[idx]))
        boot_cve[b] = auc(labels[idx], p1[idx]) - auc(labels[idx], p2[idx])
    res = {"n_subjects": int(len(labels)), "n_sites": int(len(unique_sites)),
           "cis": cis_point, "cve": cve_point,
           "cis_ci": [float(np.nanpercentile(boot_cis, 2.5)), float(np.nanpercentile(boot_cis, 97.5))],
           "cve_ci": [float(np.nanpercentile(boot_cve, 2.5)), float(np.nanpercentile(boot_cve, 97.5))],
           "auc_r1": auc(labels, p1), "auc_r2": auc(labels, p2)}
    res["cis_lower_gt_sesoi"] = bool(res["cis_ci"][0] > 0.01)
    res["cve_excludes_zero"] = bool(res["cve_ci"][0] > 0 or res["cve_ci"][1] < 0)
    return res, boot_cis, boot_cve


def paired_interaction(frames_by_model: dict, rng: np.random.Generator,
                       n_boot: int) -> dict:
    """Strictly paired architecture x regime interaction.

    All models must share the same subject ordering (identical split seed), so
    the same site->subject resample is applied to every model: the
    difference-in-differences is then paired at the resample level.
    """
    models = list(frames_by_model)
    base = frames_by_model[models[0]]
    labels, sites = base["label"], base["site"]
    for m in models:
        if not np.array_equal(frames_by_model[m]["subject_id"], base["subject_id"]):
            raise ValueError(f"subject ordering mismatch for {m}")
    unique_sites = np.unique(sites)
    site_index = {s: np.flatnonzero(sites == s) for s in unique_sites}
    draws = {m: {"cve": [], "cis": []} for m in models}
    b = 0
    while b < n_boot:
        drawn_sites = rng.choice(unique_sites, size=len(unique_sites), replace=True)
        idx = np.concatenate([rng.choice(site_index[s], size=len(site_index[s]), replace=True)
                              for s in drawn_sites])
        if labels[idx].sum() in (0, len(idx)):
            continue
        for m in models:
            f = frames_by_model[m]
            draws[m]["cve"].append(auc(labels[idx], f["p1"][idx]) - auc(labels[idx], f["p2"][idx]))
            draws[m]["cis"].append(float(np.mean(np.abs(f["p1"][idx] - f["p2"][idx]))))
        b += 1
    out = {}
    for m in models:
        arr = np.asarray(draws[m]["cve"])
        out[m] = {"cve_boot": arr, "cis_boot": np.asarray(draws[m]["cis"])}
    contrasts = []
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            a, bb = models[i], models[j]
            d = out[a]["cve_boot"] - out[bb]["cve_boot"]
            dc = out[a]["cis_boot"] - out[bb]["cis_boot"]
            obs = float(np.mean(out[a]["cve_boot"]) - np.mean(out[bb]["cve_boot"]))
            contrasts.append({
                "contrast": f"CVE[{a}] - CVE[{bb}]", "family": "architecture_interactions",
                "paired": True, "estimate": obs,
                "ci": [float(np.nanpercentile(d, 2.5)), float(np.nanpercentile(d, 97.5))],
                "p_raw": boot_pvalue(d), "n_boot": int(len(d)),
                "cis_contrast": f"CIS[{a}] - CIS[{bb}]",
                "cis_estimate": float(np.mean(out[a]["cis_boot"]) - np.mean(out[bb]["cis_boot"])),
                "cis_ci": [float(np.nanpercentile(dc, 2.5)), float(np.nanpercentile(dc, 97.5))],
                "cis_p_raw": boot_pvalue(dc),
            })
    adj = holm([c["p_raw"] for c in contrasts])
    adj_cis = holm([c["cis_p_raw"] for c in contrasts])
    for c, p, pc in zip(contrasts, adj, adj_cis):
        c["p_holm"] = p
        c["significant_holm_0.05"] = bool(p < 0.05)
        c["cis_p_holm"] = pc
        c["cis_significant_holm_0.05"] = bool(pc < 0.05)
    return {"family": "architecture_interactions", "correction": "holm",
            "paired": True, "models": models, "contrasts": contrasts,
            "estimand_note": "CVE and CIS contrasts are Holm-corrected within their own "
                             "estimand set (same pre-registered family, different estimand)."}


def holm(pvals: list[float]) -> list[float]:
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        val = min(1.0, (m - rank) * pvals[i])
        running = max(running, val)
        adj[i] = running
    return adj


def boot_pvalue(diffs: np.ndarray) -> float:
    """two-sided bootstrap p-value from the centred null."""
    d = diffs[~np.isnan(diffs)]
    if len(d) == 0:
        return float("nan")
    obs = float(np.mean(d))
    centered = d - obs
    return float((np.sum(np.abs(centered) >= abs(obs)) + 1) / (len(d) + 1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-seeds", default="1024,2024,2025")
    ap.add_argument("--n-boot", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out-dir", type=Path, default=REPO / "results/analysis_v2")
    args = ap.parse_args()

    commit, ehash = git_head(), env_hash()
    rows, interventions, meta = build_registry_v2(commit, ehash)
    write_csv(REPO / "results/registry_v2.csv", REGISTRY_FIELDS, rows)
    write_csv(REPO / "results/registry_v2_interventions.csv", INTERVENTION_FIELDS, interventions)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    seeds = [int(s) for s in args.source_seeds.split(",") if s]
    report: dict = {"source_commit": commit, "environment_hash": ehash, "registry": meta,
                    "per_model_per_split": {}, "ensemble_sensitivity": {},
                    "split_summary": {}, "interaction": {}, "split_variance": {}}

    # ---- per model x split_seed, plus pooled ---------------------------------
    boot_store: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = {}
    for model in MODEL_REGIME_SOURCES:
        frames = load_model_frame(model, seeds)
        per_split = {}
        for ss, frame in sorted(frames.items()):
            rng = np.random.default_rng(args.seed + ss)
            res, bc, bv = stats_block(frame, rng, args.n_boot)
            per_split[str(ss)] = res
            boot_store[(model, str(ss))] = (bc, bv)
        report["per_model_per_split"][model] = per_split

        # NOTE (correctness): the pre-registered averaging rule covers training
        # seeds and context draws, NOT split seeds. Averaging predictions across
        # split seeds would evaluate an ensemble of three splits and inflate
        # AUC, so the cross-split numbers below are kept strictly as a
        # sensitivity analysis and the headline summary is the mean of the
        # per-split-seed estimates.
        seeds_sorted = sorted(frames)
        if not seeds_sorted:
            continue
        maps = {ss: {s: i for i, s in enumerate(frames[ss]["subject_id"].tolist())}
                for ss in seeds_sorted}
        common = sorted(set.intersection(*[set(maps[ss]) for ss in seeds_sorted]))
        base_ss = seeds_sorted[0]
        site = np.array([frames[base_ss]["site"][maps[base_ss][s]] for s in common])
        labels = np.array([int(frames[base_ss]["label"][maps[base_ss][s]]) for s in common])
        p1 = np.mean([[frames[ss]["p1"][maps[ss][s]] for ss in seeds_sorted] for s in common], axis=1)
        p2 = np.mean([[frames[ss]["p2"][maps[ss][s]] for ss in seeds_sorted] for s in common], axis=1)
        pooled_frame = {"subject_id": np.array(common), "site": site, "label": labels,
                        "p1": p1, "p2": p2}
        rng = np.random.default_rng(args.seed + 99)
        res, bc, bv = stats_block(pooled_frame, rng, args.n_boot)
        res["note"] = ("sensitivity analysis only: predictions averaged across split seeds "
                       "evaluate an ensemble of splits; not used for headline AUC claims")
        report["ensemble_sensitivity"][model] = res
        boot_store[(model, "pooled")] = (bc, bv)

    # ---- WP2: architecture x regime interaction ------------------------------
    # Headline interaction analysis: strictly paired within each split seed, so
    # that no cross-split ensemble is involved. The three-model basis exists at
    # split seed 1024; other seeds pair the two models with full coverage.
    models = [m for m in MODEL_REGIME_SOURCES if m in report["per_model_per_split"]]
    paired: dict = {}
    for ss in seeds:
        frames_by_model = {}
        for model in MODEL_REGIME_SOURCES:
            frames = load_model_frame(model, [ss])
            if ss in frames:
                frames_by_model[model] = frames[ss]
        if len(frames_by_model) >= 2:
            rng = np.random.default_rng(args.seed + 1234 + ss)
            try:
                paired[str(ss)] = paired_interaction(frames_by_model, rng, args.n_boot)
            except ValueError as exc:
                paired[str(ss)] = {"error": str(exc)}
    report["interaction_paired"] = paired
    report["interaction"] = {
        "family": "architecture_interactions",
        "correction": "holm",
        "note": "computed per split seed with a shared site->subject resample "
                "(paired difference-in-differences); no cross-split ensemble is used",
        "per_split": {ss: v.get("contrasts", []) for ss, v in paired.items()},
    }

    # ---- WP3: repeated-split layer -------------------------------------------
    for model in models:
        per_split = report["per_model_per_split"][model]
        cis_vals = np.array([v["cis"] for v in per_split.values()])
        cve_vals = np.array([v["cve"] for v in per_split.values()])
        auc1 = np.array([v["auc_r1"] for v in per_split.values()])
        auc2 = np.array([v["auc_r2"] for v in per_split.values()])
        report["split_variance"][model] = {
            "n_split_seeds": len(per_split),
            "split_seeds": sorted(per_split),
            "cis_per_split": cis_vals.tolist(), "cve_per_split": cve_vals.tolist(),
            "cis_mean_over_splits": float(cis_vals.mean()),
            "cis_sd_over_splits": float(cis_vals.std(ddof=1)) if len(cis_vals) > 1 else None,
            "cis_range_over_splits": [float(cis_vals.min()), float(cis_vals.max())],
            "cve_mean_over_splits": float(cve_vals.mean()),
            "cve_sd_over_splits": float(cve_vals.std(ddof=1)) if len(cve_vals) > 1 else None,
            "cve_range_over_splits": [float(cve_vals.min()), float(cve_vals.max())],
            "ensemble_sensitivity_cis": report["ensemble_sensitivity"][model]["cis"],
            "ensemble_sensitivity_cve": report["ensemble_sensitivity"][model]["cve"],
            "note": "split_seed spread is reported separately from subject-level "
                    "bootstrap width (EXPERIMENT_PLAN 7.6); seeds are not treated as subjects.",
        }
        report["split_summary"][model] = {
            "headline_convention": "mean across split-seed estimates (each split seed is one "
                                   "independent replication; predictions are never averaged "
                                   "across split seeds)",
            "n_split_seeds": len(per_split),
            "auc_r1_mean": float(auc1.mean()), "auc_r1_sd": float(auc1.std(ddof=1)) if len(auc1) > 1 else None,
            "auc_r2_mean": float(auc2.mean()), "auc_r2_sd": float(auc2.std(ddof=1)) if len(auc2) > 1 else None,
            "auc_r1_range": [float(auc1.min()), float(auc1.max())],
            "auc_r2_range": [float(auc2.min()), float(auc2.max())],
            "cis_mean": float(cis_vals.mean()),
            "cis_range": [float(cis_vals.min()), float(cis_vals.max())],
            "cis_sesoi_verdict_per_split": [bool(v["cis_lower_gt_sesoi"]) for v in per_split.values()],
            "cve_mean": float(cve_vals.mean()),
            "cve_range": [float(cve_vals.min()), float(cve_vals.max())],
            "cve_excludes_zero_per_split": [bool(v["cve_excludes_zero"]) for v in per_split.values()],
        }

    (args.out_dir / "analysis_v2.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"registry": meta,
                      "split_summary": {m: {"auc_r1_mean": report["split_summary"][m]["auc_r1_mean"],
                                            "auc_r2_mean": report["split_summary"][m]["auc_r2_mean"],
                                            "cis_mean": report["split_summary"][m]["cis_mean"],
                                            "cve_mean": report["split_summary"][m]["cve_mean"],
                                            "n_splits": report["split_summary"][m]["n_split_seeds"]}
                                        for m in models},
                      "interaction_paired": {
                          ss: [{"c": c["contrast"], "est": c["estimate"], "ci": c["ci"],
                                "p_holm": c["p_holm"], "sig": c["significant_holm_0.05"],
                                "cis_est": c["cis_estimate"], "cis_p_holm": c["cis_p_holm"],
                                "cis_sig": c["cis_significant_holm_0.05"]}
                               for c in v.get("contrasts", [])]
                          for ss, v in paired.items()},
                      "split_variance": {m: {"cis_sd": report["split_variance"][m]["cis_sd_over_splits"],
                                             "cve_sd": report["split_variance"][m]["cve_sd_over_splits"],
                                             "n": report["split_variance"][m]["n_split_seeds"]}
                                         for m in models}}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
