#!/usr/bin/env python3
"""Controlled Parisot Deep_GCN cheby run for one cell (modern stack).

F-only feature selection + row normalisation; population affinity = phenotype
(SEX/SITE_ID matches) * imaging (exp(-corr^2/2 sigma^2)) over the cohort, fixed
once; chebyshev supports rebuilt per context with a single global lambda_max
(document deviation: upstream recomputes eigsh per graph). Train on F (labels),
select checkpoint on V (F+single_v context), order-controlled R2/R1 inference.
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
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import eigsh
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.metrics import roc_auc_score, roc_curve

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from audit.models.parisot_adapter import ParisotDeepGCN  # noqa: E402


def vec(root, sid, atlas="cc200"):
    m = np.asarray(loadmat(root / "subjects" / sid / f"{sid}_{atlas}_correlation.mat")["correlation"], dtype=np.float32)
    return m[np.triu_indices(m.shape[0], k=1)]


def roles(split, ss, fold):
    by = defaultdict(list); lab = {}
    for r in csv.DictReader(split.open(newline="", encoding="utf-8")):
        if int(r["split_seed"]) == ss and int(r["outer_fold"]) == fold:
            by[r["role"]].append(r["subject_id"]); lab[r["subject_id"]] = int(r["label"])
    return {k: sorted(v) for k, v in by.items()}, lab


def normalize_adj(a):
    deg = a.sum(1); dinv = np.where(deg > 0, deg ** -0.5, 0.0)
    return (a * dinv[:, None]) * dinv[None, :]


def threshold_youden(y, p):
    fpr, tpr, thr = roc_curve(y, p)
    cand = [(float(t - f), -abs(float(x) - 0.5), -float(x)) for f, t, x in zip(fpr, tpr, thr) if np.isfinite(x)]
    return -max(cand)[2] if cand else 0.5


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--split-registry", type=Path, required=True)
    ap.add_argument("--split-seed", type=int, required=True)
    ap.add_argument("--fold", type=int, required=True)
    ap.add_argument("--train-seed", type=int, required=True)
    ap.add_argument("--device", default="cuda:1")
    ap.add_argument("--features", type=int, default=2000)
    ap.add_argument("--max-epochs", type=int, default=200)
    ap.add_argument("--val-every", type=int, default=10)
    ap.add_argument("--patience", type=int, default=12)
    ap.add_argument("--lr", type=float, default=0.005)
    ap.add_argument("--weight-decay", type=float, default=5e-4)
    ap.add_argument("--hidden", type=int, default=16)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--max-degree", type=int, default=3)
    ap.add_argument("--scaling-scope", choices=["cohort", "f-only"], default="cohort",
                    help="Scope used to derive the graph-scaling constants (sigma, "
                         "lambda_max). 'cohort' reproduces the frozen v1 behaviour; "
                         "'f-only' derives both from the fit partition only.")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    args = ap.parse_args()

    t0 = time.time()
    dev = torch.device(args.device if torch.cuda.is_available() else "cpu")
    by, lab = roles(args.split_registry, args.split_seed, args.fold)
    F, V, Q = by["fit"], by["validation"], by["query"]
    all_ids = sorted(set(F) | set(V) | set(Q)); idx = {s: i for i, s in enumerate(all_ids)}
    man = {r["SUB_ID"]: r for r in csv.DictReader((args.data_root / "metadata/cohort_manifest.csv").open(newline="", encoding="utf-8-sig"))}
    sc = {s: i for i, s in enumerate(sorted({r["SITE_ID"] for r in man.values()}))}

    X = np.stack([vec(args.data_root, s) for s in all_ids]).astype(np.float64)
    y = np.array([lab[s] for s in all_ids])
    fi = [idx[s] for s in F]
    sel = SelectKBest(f_classif, k=min(args.features, X.shape[1])).fit(X[fi], y[fi])
    Xs = sel.transform(X); rsum = Xs.sum(1); Xn = Xs * np.where(np.isfinite(1.0 / rsum), 1.0 / rsum, 0.0)[:, None]

    site = np.array([sc[man[s]["SITE_ID"].strip()] for s in all_ids]); sex = np.array([int(float(man[s]["SEX"])) for s in all_ids])
    pd_aff = (sex[:, None] == sex[None, :]).astype(np.float64) * 1.0 + (site[:, None] == site[None, :]).astype(np.float64)
    Xc = Xn - Xn.mean(1, keepdims=True); Xcn = Xc / np.linalg.norm(Xc, axis=1, keepdims=True)
    D = np.clip(1.0 - Xcn @ Xcn.T, 0.0, 2.0)
    if args.scaling_scope == "f-only":
        # B12#1 fix: both graph-scaling constants are derived from the fit
        # partition only, so no outer-test information enters preprocessing.
        d_f = D[np.ix_(fi, fi)]
        sigma = float(np.mean(d_f))
        adj_scale = pd_aff[np.ix_(fi, fi)] * np.exp(-(d_f ** 2) / (2 * sigma ** 2))
    else:
        sigma = float(np.mean(D))
        adj_scale = pd_aff * np.exp(-(D ** 2) / (2 * sigma ** 2))

    adj_full = pd_aff * np.exp(-(D ** 2) / (2 * sigma ** 2))
    an = normalize_adj(adj_scale)          # chebyshev uses normalize_adj(adj)
    lap = np.eye(an.shape[0]) - an
    lmax = float(eigsh(csr_matrix(lap), 1, which="LM")[0][0])

    def supports(nodes):
        a = normalize_adj(adj_full[np.ix_(nodes, nodes)])
        n = a.shape[0]
        s = (2.0 / lmax) * (np.eye(n) - a) - np.eye(n)
        t = [np.eye(n), s]
        for _ in range(2, args.max_degree + 1):
            t.append(2.0 * (s @ t[-1]) - t[-2])
        return [torch.as_tensor(x, dtype=torch.float32, device=dev) for x in t]

    torch.manual_seed(args.train_seed); np.random.seed(args.train_seed)
    nsup = args.max_degree + 1
    model = ParisotDeepGCN(Xn.shape[1], args.hidden, 2, args.depth, nsup).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    sup_F = supports(fi); xF = torch.as_tensor(Xn[fi], dtype=torch.float32, device=dev)
    yF = torch.as_tensor(y[fi], dtype=torch.long, device=dev)

    def forward(nodes):
        sup = supports(nodes)
        x = torch.as_tensor(Xn[nodes], dtype=torch.float32, device=dev)
        return model(x, sup)

    best_auc, best_state, stale, epochs = -np.inf, None, 0, 0
    for ep in range(1, args.max_epochs + 1):
        model.train(); opt.zero_grad(set_to_none=True)
        logits = model(xF, sup_F)
        loss = torch.nn.functional.cross_entropy(logits, yF)
        loss.backward(); opt.step(); epochs = ep
        if ep == 1 or ep % args.val_every == 0 or ep == args.max_epochs:
            model.eval(); vp = []
            with torch.no_grad():
                for v in V:
                    logits = forward(fi + [idx[v]])
                    vp.append(float(logits[-1].softmax(-1)[1].cpu()))
            auc = roc_auc_score(y[[idx[s] for s in V]], vp)
            if auc > best_auc + 1e-9:
                best_auc = auc; best_state = {k: t.detach().cpu().clone() for k, t in model.state_dict().items()}; stale = 0
            else:
                stale += 1
            if stale >= args.patience:
                break
    model.load_state_dict(best_state); model.eval()
    with torch.no_grad():
        vp = [float(forward(fi + [idx[v]])[-1].softmax(-1)[1].cpu()) for v in V]
    thr = threshold_youden(list(y[[idx[s] for s in V]]), vp)

    rows = []
    with torch.no_grad():
        for q in Q:
            others = [idx[x] for x in sorted(set(Q) - {q})]
            p_r2 = float(forward(fi + [idx[q]])[-1].softmax(-1)[1].cpu())
            p_r1 = float(forward(fi + others + [idx[q]])[-1].softmax(-1)[1].cpu())
            rows.append({"model": "parisot", "split_seed": args.split_seed, "subject_id": q,
                         "site": man[q]["SITE_ID"].strip(), "label": lab[q],
                         "p_r1": round(p_r1, 8), "p_r2": round(p_r2, 8), "abs_shift": round(abs(p_r1 - p_r2), 8)})

    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    sd = {k: t.detach().cpu() for k, t in model.state_dict().items()}
    h = hashlib.sha256()
    for k in sorted(sd):
        h.update(k.encode()); h.update(sd[k].numpy().astype(np.float32).tobytes())
    torch.save({"model_state_dict": sd, "checkpoint_hash": h.hexdigest(), "threshold": thr}, str(args.checkpoint))
    report = {"status": "PASS", "split_seed": args.split_seed, "fold": args.fold, "train_seed": args.train_seed,
              "n_fit": len(F), "n_validation": len(V), "n_query": len(Q), "epochs": epochs,
              "best_val_auc": float(best_auc), "threshold": thr, "lambda_max": lmax,
              "scaling_scope": args.scaling_scope, "sigma": sigma,
              "cis_mean": float(np.mean([r["abs_shift"] for r in rows])),
              "cis_max": float(np.max([r["abs_shift"] for r in rows])), "elapsed_seconds": round(time.time() - t0, 1),
              "rows": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: report[k] for k in ["split_seed", "fold", "train_seed", "epochs", "best_val_auc",
                                             "cis_mean", "cis_max", "elapsed_seconds"]}, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
