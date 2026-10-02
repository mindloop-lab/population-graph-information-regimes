#!/usr/bin/env python3
"""Controlled EV-GCN run for one cell (split_seed, fold, train_seed).

Mirrors the audit protocol (fit=F labels, selection=V labels, query=Q isolated)
under the modern stack:
  - feature selection (f_classif top-k) and row-normalisation fitted on F only;
  - population graph = imaging affinity (correlation) * phenotype affinity
    (SEX/SITE_ID matches) > thr, edges i<j (single direction, as upstream);
  - PAE edge inputs = standardised concat of [SITE_ID, SEX, AGE_AT_SCAN];
  - model = audit.models.ev_gcn_adapter.ControlledEVGCN (native-parity 1.19e-6);
  - checkpoint selected by V AUC (query never used);
  - order-controlled R2-Q (F+query) vs R1-C (F+others+query), query last.

Writes per-cell json + appends rows to results/evgcn/ev_oc_registry.csv.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from scipy.io import loadmat
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.metrics import roc_auc_score, roc_curve

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from audit.models.ev_gcn_adapter import ControlledEVGCN  # noqa: E402

PHENO = ["SITE_ID", "SEX", "AGE_AT_SCAN"]


def load_cohort(root: Path, atlas: str = "cc200"):
    with (root / "metadata" / "cohort_manifest.csv").open(newline="", encoding="utf-8-sig") as h:
        rows = {r["SUB_ID"].strip(): r for r in csv.DictReader(h)}
    sites = sorted({r["SITE_ID"].strip() for r in rows.values()})
    site_code = {s: i for i, s in enumerate(sites)}
    return rows, site_code


def vector(root: Path, sid: str, atlas: str = "cc200") -> np.ndarray:
    m = np.asarray(loadmat(root / "subjects" / sid / f"{sid}_{atlas}_correlation.mat")["correlation"], dtype=np.float32)
    return m[np.triu_indices(m.shape[0], k=1)]


def roles(split: Path, ss: int, fold: int):
    by = defaultdict(list)
    lab = {}
    with split.open(newline="", encoding="utf-8") as h:
        for r in csv.DictReader(h):
            if int(r["split_seed"]) == ss and int(r["outer_fold"]) == fold:
                by[r["role"]].append(r["subject_id"]); lab[r["subject_id"]] = int(r["label"])
    return {k: sorted(v) for k, v in by.items()}, lab


def threshold_youden(labels, probs):
    fpr, tpr, thr = roc_curve(labels, probs)
    cand = [(float(t - f), -abs(float(x) - 0.5), -float(x)) for f, t, x in zip(fpr, tpr, thr) if np.isfinite(x)]
    return -max(cand)[2] if cand else 0.5


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--split-registry", type=Path, required=True)
    ap.add_argument("--upstream", type=Path, required=True)
    ap.add_argument("--split-seed", type=int, required=True)
    ap.add_argument("--fold", type=int, required=True)
    ap.add_argument("--train-seed", type=int, required=True)
    ap.add_argument("--device", default="cuda:1")
    ap.add_argument("--atlas", default="cc200")
    ap.add_argument("--features", type=int, default=2000)
    ap.add_argument("--max-epochs", type=int, default=300)
    ap.add_argument("--val-every", type=int, default=5)
    ap.add_argument("--patience", type=int, default=20)
    ap.add_argument("--lr", type=float, default=0.01)
    ap.add_argument("--weight-decay", type=float, default=5e-5)
    ap.add_argument("--dropout", type=float, default=0.2)
    ap.add_argument("--hidden", type=int, default=16)
    ap.add_argument("--layers", type=int, default=4)
    ap.add_argument("--thr", type=float, default=1.1)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--registry", type=Path, required=True)
    args = ap.parse_args()

    t0 = time.time()
    dev = torch.device(args.device if torch.cuda.is_available() else "cpu")
    by, lab = roles(args.split_registry, args.split_seed, args.fold)
    F, V, Q = by["fit"], by["validation"], by["query"]
    all_ids = sorted(set(F) | set(V) | set(Q))
    man, site_code = load_cohort(args.data_root, args.atlas)

    # node features
    vecs = {s: vector(args.data_root, s, args.atlas) for s in all_ids}
    X = np.stack([vecs[s] for s in all_ids]).astype(np.float64)
    idx = {s: i for i, s in enumerate(all_ids)}
    fit_idx = [idx[s] for s in F]; val_idx = [idx[s] for s in V]; qry_idx = [idx[s] for s in Q]
    y_all = np.array([lab[s] for s in all_ids])

    # F-only selection + row-normalisation (upstream preprocess_features)
    sel = SelectKBest(f_classif, k=min(args.features, X.shape[1])).fit(X[fit_idx], y_all[fit_idx])
    Xs = sel.transform(X)
    rsum = Xs.sum(1); rinv = np.where(np.isfinite(1.0 / rsum), 1.0 / rsum, 0.0)
    Xn = (Xs * rinv[:, None]).astype(np.float64)

    # phenotype
    sites = np.array([site_code[man[s]["SITE_ID"].strip()] for s in all_ids])
    sexes = np.array([int(float(man[s]["SEX"])) for s in all_ids])
    ages = np.array([float(man[s]["AGE_AT_SCAN"]) for s in all_ids])
    nonimg = np.column_stack([sites, sexes, ages]).astype(np.float64)   # 3 pheno

    # cohort-wide correlation distance on row-normalised selected features
    Xc = Xn - Xn.mean(1, keepdims=True)
    Xcn = Xc / np.linalg.norm(Xc, axis=1, keepdims=True)
    Dfull = np.clip(1.0 - Xcn @ Xcn.T, 0.0, 2.0)
    ui_cache: dict[int, tuple] = {}

    def graph(sel_nodes):
        d = Dfull[np.ix_(sel_nodes, sel_nodes)]; n = len(sel_nodes)
        sigma = float(np.mean(d))
        if n not in ui_cache:
            ui_cache[n] = np.triu_indices(n, k=1)
        ui, uj = ui_cache[n]
        ni = nonimg[sel_nodes]
        phen = (ni[ui, 1] == ni[uj, 1]).astype(np.int8) + (ni[ui, 0] == ni[uj, 0]).astype(np.int8)  # SEX + SITE
        imaging = np.exp(-(d[ui, uj] ** 2) / (2 * sigma ** 2))
        keep = (imaging * phen) > args.thr
        ei, ej = ui[keep], uj[keep]
        # Symmetrise the edge list: upstream emits single-direction i<j edges, but
        # ChebConv normalises degree over edge_index[0] (source), so the highest-index
        # node would have zero degree and receive nothing. Symmetrisation gives a
        # well-defined, permutation-invariant operator (controlled deviation).
        e_idx = np.vstack([np.concatenate([ei, ej]), np.concatenate([ej, ei])])
        e_in = np.concatenate([np.concatenate([ni[ei], ni[ej]], axis=1),
                               np.concatenate([ni[ej], ni[ei]], axis=1)], axis=0).astype(np.float32)
        e_in = (e_in - e_in.mean(0)) / (e_in.std(0) + 1e-12)
        return torch.as_tensor(e_idx, dtype=torch.long, device=dev), torch.as_tensor(e_in, device=dev)

    torch.manual_seed(args.train_seed)
    np.random.seed(args.train_seed)
    model = ControlledEVGCN(args.upstream, input_dim=Xn.shape[1], num_classes=2, dropout=args.dropout,
                            edgenet_input_dim=2 * len(PHENO), edge_dropout=0.0, hgc=args.hidden, lg=args.layers).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    ftr = torch.as_tensor(Xn[fit_idx], dtype=torch.float32, device=dev)
    flat = torch.as_tensor(y_all[fit_idx], dtype=torch.long, device=dev)
    fei, fein = graph(fit_idx)

    def val_probs():
        model.eval(); out = []
        with torch.no_grad():
            for v in val_idx:
                nodes = fit_idx + [v]
                ei, ein = graph(nodes)
                feats = torch.as_tensor(Xn[nodes], dtype=torch.float32, device=dev)
                logits, _ = model(feats, ei, ein)
                out.append(float(logits[-1].softmax(-1)[1].cpu()))
        return out

    best_auc, best_state, stale, epochs_done = -np.inf, None, 0, 0
    for epoch in range(1, args.max_epochs + 1):
        model.train(); opt.zero_grad(set_to_none=True)
        ftr = ftr.detach()
        feats = ftr.clone().requires_grad_(False)
        logits, _ = model(feats, fei, fein)
        loss = torch.nn.functional.cross_entropy(logits, flat)
        loss.backward(); opt.step()
        epochs_done = epoch
        if epoch == 1 or epoch % args.val_every == 0 or epoch == args.max_epochs:
            vp = val_probs()
            auc = roc_auc_score(y_all[val_idx], vp)
            if auc > best_auc + 1e-9:
                best_auc = auc
                best_state = {k: t.detach().cpu().clone() for k, t in model.state_dict().items()}
                stale = 0
            else:
                stale += 1
            if stale >= args.patience:
                break
    model.load_state_dict(best_state)
    model.eval()
    vp = val_probs()
    thr = threshold_youden(list(y_all[val_idx]), vp)

    # order-controlled inference: R2 (F+query) and R1 (F+others+query), query last
    def predict(nodes):
        ei, ein = graph(nodes)
        feats = torch.as_tensor(Xn[nodes], dtype=torch.float32, device=dev)
        with torch.no_grad():
            logits, _ = model(feats, ei, ein)
        return float(logits[-1].softmax(-1)[1].cpu())

    rows = []
    for q in Q:
        others = [idx[x] for x in sorted(set(Q) - {q})]
        p_r2 = predict(fit_idx + [idx[q]])
        p_r1 = predict(fit_idx + others + [idx[q]])
        rows.append({"model": "evgcn", "split_seed": args.split_seed, "subject_id": q,
                     "site": man[q]["SITE_ID"].strip(), "label": lab[q],
                     "p_r1": round(p_r1, 8), "p_r2": round(p_r2, 8), "abs_shift": round(abs(p_r1 - p_r2), 8)})

    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    sd = {k: t.detach().cpu() for k, t in model.state_dict().items()}
    h = hashlib.sha256()
    for k in sorted(sd):
        h.update(k.encode()); h.update(sd[k].numpy().astype(np.float32).tobytes())
    torch.save({"model_state_dict": sd, "checkpoint_hash": h.hexdigest(), "threshold": thr,
                "config": vars(args) | {"data_root": str(args.data_root), "split_registry": str(args.split_registry),
                                        "upstream": str(args.upstream), "out": str(args.out),
                                        "checkpoint": str(args.checkpoint), "registry": str(args.registry)}},
               str(args.checkpoint))
    report = {"status": "PASS", "split_seed": args.split_seed, "fold": args.fold, "train_seed": args.train_seed,
              "n_fit": len(F), "n_validation": len(V), "n_query": len(Q), "epochs": epochs_done,
              "best_val_auc": float(best_auc), "threshold": thr, "checkpoint_hash": h.hexdigest(),
              "n_features": int(Xn.shape[1]), "edgenet_input_dim": 2 * len(PHENO),
              "cis_mean": float(np.mean([r["abs_shift"] for r in rows])),
              "cis_max": float(np.max([r["abs_shift"] for r in rows])),
              "elapsed_seconds": round(time.time() - t0, 1),
              "rows": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: report[k] for k in ["split_seed", "fold", "train_seed", "epochs", "best_val_auc",
                                             "cis_mean", "cis_max", "elapsed_seconds"]}, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
