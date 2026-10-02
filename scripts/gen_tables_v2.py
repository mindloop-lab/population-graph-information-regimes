#!/usr/bin/env python3
"""Generate every Paper A v1 table from the frozen numeric sources.

Number gate: nothing is typed by hand. Inputs
  results/registry_v2.csv
  results/analysis_v2/analysis_v2.json
  results/rf/rf_matrix_summary.json
Outputs (tables/)
  table1_protocols.tex|csv    information contract of the audited regimes
  table2_main.tex|csv         cross-paradigm results per model x regime
  table3_contrasts.tex|csv    pre-registered paired contrasts (Holm)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "tables"

MODEL_LABEL = {
    "rf": "RF (no graph, negative control)",
    "ev_gcn": "EV-GCN (learned/adaptive graph)",
    "parisot_gcn": "Parisot-GCN (static weighted graph)",
    "lim": "Lim-IPGNN (inductive)",
}

PROTOCOLS = [
    ("P0 / R0-T", "transductive", "yes", "yes", "cohort-conditioned"),
    ("P1 / R1-C", "cohort-visible inference", "no", "yes", "cohort-conditioned"),
    ("P2", "batch / context-dose (k swept)", "no", "k of N", "budgeted"),
    ("P3 / R2-Q", "strict single-query", "no", "no", "prospective"),
    ("P4", "size-matched target-site context", "no", "site-matched", "mechanism probe"),
    ("P5 / LOSO", "leave-one-site-out", "no", "held-out site", "site generalisation"),
]


def f(x, nd=4):
    return "—" if x is None else f"{x:.{nd}f}"


def ci(pair, nd=4):
    return "—" if pair is None else f"[{pair[0]:.{nd}f}, {pair[1]:.{nd}f}]"


def table1() -> tuple[str, list[dict]]:
    rows = [{"regime": a, "definition": b, "test_nodes_at_training": c,
             "other_test_subjects_at_inference": d, "deployment_question": e}
            for a, b, c, d, e in PROTOCOLS]
    lines = [
        r"\begin{tabular}{lllll}", r"\toprule",
        r"Regime & Definition & Test nodes at training & Other test subjects at inference & Deployment question \\",
        r"\midrule",
    ]
    for r in rows:
        lines.append(" & ".join([r["regime"], r["definition"], r["test_nodes_at_training"],
                                 r["other_test_subjects_at_inference"], r["deployment_question"]]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n", rows


def table2(report: dict, rf: dict) -> tuple[str, list[dict]]:
    rows = []
    for model, label in MODEL_LABEL.items():
        if model == "rf":
            aucs = [c["query_auc"] for c in rf["cells"]]
            mean = sum(aucs) / len(aucs)
            var = sum((a - mean) ** 2 for a in aucs) / (len(aucs) - 1)
            rows.append({
                "model": model, "label": label,
                "r1c_auc": "—", "r2q_auc": "—",
                "cis": "0.0000 (exact)", "cis_ci": "[0, 0]",
                "cve": "0.0000 (exact)", "cve_ci": "[0, 0]",
                "n_split_seeds": 3, "regime_invariance": rf["regime_invariance"]["status"],
                "subject_only_auc": f"{mean:.4f} $\\pm$ {var ** 0.5:.4f}"})
            continue
        s = report["split_summary"][model]
        v = report["split_variance"][model]
        n = s["n_split_seeds"]
        auc1 = (f"{s['auc_r1_mean']:.4f}" if n == 1
                else f"{s['auc_r1_mean']:.4f} $\\pm$ {s['auc_r1_sd']:.4f}")
        auc2 = (f"{s['auc_r2_mean']:.4f}" if n == 1
                else f"{s['auc_r2_mean']:.4f} $\\pm$ {s['auc_r2_sd']:.4f}")
        rows.append({
            "model": model, "label": label, "subject_only_auc": "—",
            "r1c_auc": auc1, "r2q_auc": auc2,
            "cis": f"{s['cis_mean']:.4f}", "cis_ci": f"[{s['cis_range'][0]:.4f}, {s['cis_range'][1]:.4f}]",
            "cve": f"{s['cve_mean']:.4f}", "cve_ci": f"[{s['cve_range'][0]:.4f}, {s['cve_range'][1]:.4f}]",
            "n_split_seeds": n,
            "regime_invariance": f"sd(CIS) across splits {f(v['cis_sd_over_splits'], 4)}"})
    lines = [
        r"\begin{tabular}{lrrrrr}", r"\toprule",
        r"Model (paradigm) & AUC(P1/R1-C) & AUC(P3/R2-Q) & CIS & CIS range & CVE \\",
        r"\midrule",
    ]
    for r in rows:
        lines.append(" & ".join([r["label"], r["r1c_auc"], r["r2q_auc"], r["cis"], r["cis_ci"], r["cve"]]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n", rows


def table3(report: dict) -> tuple[str, list[dict]]:
    seeds = sorted(report["interaction_paired"])
    rows = []
    lines = [
        r"\begin{tabular}{llrrrr}", r"\toprule",
        r"Split seed & Contrast & $\Delta$ & 95\% CI & $p_{\mathrm{raw}}$ & $p_{\mathrm{Holm}}$ \\",
        r"\midrule",
    ]
    for si, ss in enumerate(seeds):
        contrasts = report["interaction_paired"][ss]["contrasts"]
        lines.append(r"\multicolumn{6}{l}{\emph{Performance shift "
                     r"(CVE$_{\mathrm{AUC}}$), split seed " + ss + r"}} \\")
        for c in contrasts:
            name = (c["contrast"].replace("CVE[", "").replace("]", "")
                    .replace(" - ", " $-$ ").replace("_", r"\_"))
            rows.append({"split_seed": ss, "estimand": "CVE", "contrast": c["contrast"],
                         "estimate": f"{c['estimate']:.4f}", "ci95": ci(c["ci"]),
                         "p_raw": f"{c['p_raw']:.3f}", "p_holm": f"{c['p_holm']:.3f}",
                         "significant": c["significant_holm_0.05"]})
            lines.append(" & ".join([ss, name, f"{c['estimate']:.4f}", ci(c["ci"]),
                                     f"{c['p_raw']:.3f}", f"{c['p_holm']:.3f}"]) + r" \\")
        lines.append(r"\multicolumn{6}{l}{\emph{Regime sensitivity (CIS)}, split seed "
                     + ss + r"} \\")
        for c in contrasts:
            name = (c["cis_contrast"].replace("CIS[", "").replace("]", "")
                    .replace(" - ", " $-$ ").replace("_", r"\_"))
            rows.append({"split_seed": ss, "estimand": "CIS", "contrast": c["cis_contrast"],
                         "estimate": f"{c['cis_estimate']:.4f}", "ci95": ci(c["cis_ci"]),
                         "p_raw": f"{c['cis_p_raw']:.4f}", "p_holm": f"{c['cis_p_holm']:.4f}",
                         "significant": c["cis_significant_holm_0.05"]})
            lines.append(" & ".join([ss, name, f"{c['cis_estimate']:.4f}", ci(c["cis_ci"]),
                                     f"{c['cis_p_raw']:.4f}", f"{c['cis_p_holm']:.4f}"]) + r" \\")
        if si < len(seeds) - 1:
            lines.append(r"\midrule")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n", rows


def numbers_tex(report: dict, rf: dict) -> str:
    """LaTeX macros for every number quoted in prose (number gate: no literals)."""
    def m(name, val, nd=4):
        return f"\\newcommand{{\\{name}}}{{{val:.{nd}f}}}"

    lines = [r"% AUTO-GENERATED by scripts/gen_tables_v2.py -- do not edit by hand"]
    ss = report["split_summary"]
    for key, tag in (("rf", "Rf"), ("ev_gcn", "Ev"), ("parisot_gcn", "Par"), ("lim", "Lim")):
        if key == "rf":
            aucs = [c["query_auc"] for c in rf["cells"]]
            mean = sum(aucs) / len(aucs)
            sd = (sum((a - mean) ** 2 for a in aucs) / (len(aucs) - 1)) ** 0.5
            lines += [m(f"rfAuc", mean), m(f"rfAucSd", sd), m(f"rfCells", len(aucs), 0)]
            lines += [f"\\newcommand{{\\rfInvariant}}{{{rf['regime_invariance']['status']}}}",
                      f"\\newcommand{{\\rfMaxDiff}}{{{rf['regime_invariance']['max_abs_difference_all_cells']:.1f}}}"]
            continue
        s = ss[key]
        lines += [m(f"{tag}Cis", s["cis_mean"]), m(f"{tag}CisLo", s["cis_range"][0]),
                  m(f"{tag}CisHi", s["cis_range"][1]),
                  m(f"{tag}Cve", s["cve_mean"]), m(f"{tag}CveLo", s["cve_range"][0]),
                  m(f"{tag}CveHi", s["cve_range"][1]),
                  m(f"{tag}AucRone", s["auc_r1_mean"]), m(f"{tag}AucRtwo", s["auc_r2_mean"])]
        if s["auc_r1_sd"] is not None:
            lines += [m(f"{tag}AucRoneSd", s["auc_r1_sd"]), m(f"{tag}AucRtwoSd", s["auc_r2_sd"])]
        v = report["split_variance"][key]
        if v["cis_sd_over_splits"] is not None:
            lines += [m(f"{tag}CisSplitSd", v["cis_sd_over_splits"]),
                      m(f"{tag}CveSplitSd", v["cve_sd_over_splits"])]
    cons = report["interaction_paired"]["1024"]["contrasts"]
    by_cve = {c["contrast"]: c for c in cons}
    by_cis = {c["cis_contrast"]: c for c in cons}

    def emit(tag: str, est: float, lo: float, hi: float, p: float) -> None:
        lines.extend([m(f"{tag}Est", est), m(f"{tag}Lo", lo), m(f"{tag}Hi", hi)])
        lines.append(f"\\newcommand{{\\{tag}PHolm}}{{{p:.4f}}}")

    # replication across split seeds for the two headline contrast families
    seeds = sorted(report["interaction_paired"])
    cis_sig = {"CisLimEv": 0, "CisEvPar": 0, "CisLimPar": 0}
    cve_sig = {"CveLimEv": 0, "CveLimPar": 0, "CveEvPar": 0}
    for ss in seeds:
        for c in report["interaction_paired"][ss]["contrasts"]:
            if c["cis_contrast"] == "CIS[lim] - CIS[ev_gcn]" and c["cis_significant_holm_0.05"]:
                cis_sig["CisLimEv"] += 1
            if c["cis_contrast"] == "CIS[ev_gcn] - CIS[parisot_gcn]" and c["cis_significant_holm_0.05"]:
                cis_sig["CisEvPar"] += 1
            if c["cis_contrast"] == "CIS[lim] - CIS[parisot_gcn]" and c["cis_significant_holm_0.05"]:
                cis_sig["CisLimPar"] += 1
            if c["contrast"] == "CVE[lim] - CVE[ev_gcn]" and c["significant_holm_0.05"]:
                cve_sig["CveLimEv"] += 1
            if c["contrast"] == "CVE[lim] - CVE[parisot_gcn]" and c["significant_holm_0.05"]:
                cve_sig["CveLimPar"] += 1
            if c["contrast"] == "CVE[ev_gcn] - CVE[parisot_gcn]" and c["significant_holm_0.05"]:
                cve_sig["CveEvPar"] += 1
    lines.append(f"\\newcommand{{\\nSplitSeeds}}{{{len(seeds)}}}")
    for k, v in list(cis_sig.items()) + list(cve_sig.items()):
        lines.append(f"\\newcommand{{\\{k}SigSeeds}}{{{v}}}")
    for tag, key in (("CveLimEv", "CVE[lim] - CVE[ev_gcn]"),
                     ("CveLimPar", "CVE[lim] - CVE[parisot_gcn]"),
                     ("CveEvPar", "CVE[ev_gcn] - CVE[parisot_gcn]")):
        c = by_cve.get(key)
        if c:
            emit(tag, c["estimate"], c["ci"][0], c["ci"][1], c["p_holm"])
    for tag, key in (("CisLimEv", "CIS[lim] - CIS[ev_gcn]"),
                     ("CisLimPar", "CIS[lim] - CIS[parisot_gcn]"),
                     ("CisEvPar", "CIS[ev_gcn] - CIS[parisot_gcn]")):
        c = by_cis.get(key)
        if c:
            emit(tag, c["cis_estimate"], c["cis_ci"][0], c["cis_ci"][1], c["cis_p_holm"])
    lines += [f"\\newcommand{{\\sesoi}}{{0.01}}",
              f"\\newcommand{{\\nBoot}}{{5000}}"]
    return "\n".join(lines) + "\n"


def hand_maintained_tex() -> str:
    """Constants quoted from source documents, kept as macros so that the
    manuscript body contains no literals. Each entry names its source."""
    items = [
        ("EvFidelity", r"1.19\times10^{-6}",
         "docs/RESULTS_A4_EV_adapter_fidelity_2026-09-09.md"),
        ("ParFidelity", r"4.0\times10^{-7}",
         "docs/RESULTS_A5_parisot_fidelity_2026-09-09.md"),
        ("LimFidelity", r"7.15\times10^{-7}",
         "model_cards/LIM_IPGNN.md (adapter gate)"),
        ("PermSorted", "0.4722",
         "docs/FINDING_order_sensitivity_2026-09-09.md / RESULTS_cross_paradigm"),
        ("PermLast", "0.3888",
         "docs/FINDING_order_sensitivity_2026-09-09.md"),
        ("NSubjectsCohort", "871", "manifests/DATA_LOCK.tsv"),
        ("NEdgesCc", "19,900", "configs/data/abide1_legacy_matched.yaml"),
        ("NFolds", "5", "splits/mixed_site_dx_5fold_v2.csv"),
        ("NSitesLosoCov", "19", "docs/LOSO_SDSU_fidelity_tie_2026-09-09.md"),
        ("NSitesTotal", "20", "manifests/DATA_LOCK.tsv"),
    ]
    lines = [r"% Quoted constants (source in comment) -- body must use the macros"]
    for name, value, src in items:
        lines.append(f"\\newcommand{{\\{name}}}{{{value}}}  % {src}")
    return "\n".join(lines) + "\n"


def fonly_tex() -> str:
    """Macros for the F-only graph-scaling sensitivity analysis (B12#1)."""
    f = REPO / "results/parisot_fonly/fonly_summary.json"
    if not f.is_file():
        return ""
    d = json.loads(f.read_text())
    lines = [r"% F-only scaling-scope sensitivity (Parisot-GCN, B12#1)"]
    splits = sorted(d["per_split"])
    lines.append(f"\\newcommand{{\\FoNSplits}}{{{len(splits)}}}")
    cis = [d["per_split"][ss]["cis"] for ss in splits]
    cve = [d["per_split"][ss]["cve"] for ss in splits]
    lines += [
        f"\\newcommand{{\\FoCisMin}}{{{min(cis):.4f}}}",
        f"\\newcommand{{\\FoCisMax}}{{{max(cis):.4f}}}",
        f"\\newcommand{{\\FoCveMin}}{{{min(cve):+.4f}}}",
        f"\\newcommand{{\\FoCveMax}}{{{max(cve):+.4f}}}",
    ]
    dc = [d["per_split"][ss]["cis"] - d["primary_scope"]["per_split"][ss]["cis"] for ss in splits]
    dv = [d["per_split"][ss]["cve"] - d["primary_scope"]["per_split"][ss]["cve"] for ss in splits]
    lines += [
        f"\\newcommand{{\\FoDCisMax}}{{{max(abs(x) for x in dc):.4f}}}",
        f"\\newcommand{{\\FoDCveMax}}{{{max(abs(x) for x in dv):.4f}}}",
    ]
    return "\n".join(lines) + "\n"


def matched_site_tex() -> str:
    """Macros for the matched-site (target-site mechanism) contrasts."""
    lines = []
    for prefix, tag in (("lim", "MatLim"), ("parisot", "MatPar")):
        f = REPO / f"results/matchsite/{prefix}_matchsite_all_summary.json"
        if not f.is_file():
            continue
        d = json.loads(f.read_text())
        p, c = d["pooled"], d["diff_D_same_minus_cross"]
        lines += [
            f"\\newcommand{{\\{tag}N}}{{{p['n']}}}",
            f"\\newcommand{{\\{tag}AucNone}}{{{p['auc_none']:.4f}}}",
            f"\\newcommand{{\\{tag}AucSame}}{{{p['auc_same']:.4f}}}",
            f"\\newcommand{{\\{tag}AucCross}}{{{p['auc_cross']:.4f}}}",
            f"\\newcommand{{\\{tag}DSame}}{{{p['D_same_none']:.4f}}}",
            f"\\newcommand{{\\{tag}DCross}}{{{p['D_cross_none']:.4f}}}",
            f"\\newcommand{{\\{tag}Diff}}{{{c['obs']:.4f}}}",
            f"\\newcommand{{\\{tag}DiffLo}}{{{c['ci95'][0]:.4f}}}",
            f"\\newcommand{{\\{tag}DiffHi}}{{{c['ci95'][1]:.4f}}}",
            f"\\newcommand{{\\{tag}DiffNonzero}}{{{'yes' if c['nonzero'] else 'no'}}}",
            f"\\newcommand{{\\{tag}AucSameMinusNone}}{{{p['auc_same_minus_none']:+.4f}}}",
            f"\\newcommand{{\\{tag}AucCrossMinusNone}}{{{p['auc_cross_minus_none']:+.4f}}}",
            f"\\newcommand{{\\{tag}NSplits}}{{{len(d['split_seeds_present'])}}}",
        ]
    return "\n".join(lines) + "\n" if lines else ""


def write(name: str, tex: str, rows: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.tex").write_text(tex)
    if rows:
        with (OUT / f"{name}.csv").open("w", newline="", encoding="utf-8") as h:
            w = csv.DictWriter(h, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"wrote {OUT / name}.tex ({len(rows)} rows)")


def main() -> int:
    report = json.loads((REPO / "results/analysis_v2/analysis_v2.json").read_text())
    rf = json.loads((REPO / "results/rf/rf_matrix_summary.json").read_text())
    write("table1_protocols", *table1())
    write("table2_main", *table2(report, rf))
    write("table3_contrasts", *table3(report))
    # manuscript/ copies for the LaTeX build
    man = REPO / "manuscript"
    man.mkdir(parents=True, exist_ok=True)
    for name in ("table1_protocols", "table2_main", "table3_contrasts"):
        (man / f"{name}.tex").write_text((OUT / f"{name}.tex").read_text())
    numbers = numbers_tex(report, rf) + matched_site_tex() + hand_maintained_tex() + fonly_tex()
    (man / "numbers.tex").write_text(numbers)
    print(f"copied tables into manuscript/ and wrote manuscript/numbers.tex "
          f"({numbers.count('newcommand')} macros)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
