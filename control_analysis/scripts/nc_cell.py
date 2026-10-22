#!/usr/bin/env python3
"""Negative control — one cell: feature-only MLP under one training regime.

The model never reads the graph, so P0 (query nodes present, unlabeled, in the training
batch) and P1 (absent) must give the same predictions if the controlled path carries no
context. Everything else — subject order, feature selection (fit-fold only), row
normalisation, initialisation, budget, early stopping, threshold rule — is identical
between regimes.

The deterministic settings are deliberate: dropout 0 and full-batch, so that any difference
between P0 and P1 cannot come from a different number of RNG draws. A stochastic variant
(--dropout 0.2) is available for a diagnostic, not for the invariance verdict.

Usage:
    python nc_cell.py --regime P0 --split-seed 1024 --fold 0 --train-seed 11 --out cell.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.metrics import roc_auc_score


def roles(split: Path, ss: int, fold: int):
    by = defaultdict(list)
    lab = {}
    for r in csv.DictReader(split.open(newline="", encoding="utf-8")):
        if int(r["split_seed"]) == ss and int(r["outer_fold"]) == fold:
            by[r["role"]].append(r["subject_id"])
            lab[r["subject_id"]] = int(r["label"])
    return {k: sorted(v) for k, v in by.items()}, lab


def make_model(dim: int, dropout: float):
    layers = [torch.nn.Linear(dim, 64), torch.nn.ReLU()]
    if dropout > 0:
        layers.append(torch.nn.Dropout(dropout))
    layers.append(torch.nn.Linear(64, 2))
    return torch.nn.Sequential(*layers).double()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features-dir", type=Path, required=True)
    ap.add_argument("--split-registry", type=Path, required=True)
    ap.add_argument("--split-seed", type=int, required=True)
    ap.add_argument("--fold", type=int, required=True)
    ap.add_argument("--train-seed", type=int, required=True)
    ap.add_argument("--regime", choices=["P0", "P1"], required=True)
    ap.add_argument("--dropout", type=float, default=0.0)
    ap.add_argument("--features", type=int, default=2000)
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--patience", type=int, default=20)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    t0 = time.time()
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)

    z = np.load(args.features_dir / "features.npz", allow_pickle=False)
    X, ids = z["X"].astype(np.float64), [str(s) for s in z["ids"]]
    idx = {s: i for i, s in enumerate(ids)}
    by, lab = roles(args.split_registry, args.split_seed, args.fold)
    F, V, Q = by["fit"], by["validation"], by["query"]
    fi = [idx[s] for s in F]
    vi = [idx[s] for s in V]
    qi = [idx[s] for s in Q]
    y = np.array([lab[s] for s in ids])

    # identical in both regimes: fit-fold-only selection + row-sum normalisation
    sel = SelectKBest(f_classif, k=min(args.features, X.shape[1])).fit(X[fi], y[fi])
    Xs = sel.transform(X)
    rsum = Xs.sum(1)
    Xn = Xs * np.where(np.isfinite(1.0 / rsum), 1.0 / rsum, 0.0)[:, None]
    xn_sha = hashlib.sha256(np.ascontiguousarray(Xn).tobytes()).hexdigest()

    train_nodes = fi + qi if args.regime == "P0" else fi
    tn_sha = hashlib.sha256(",".join(ids[i] for i in train_nodes).encode()).hexdigest()

    torch.manual_seed(args.train_seed)
    np.random.seed(args.train_seed)
    model = make_model(Xn.shape[1], args.dropout)
    opt = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=5e-5)

    xt = torch.as_tensor(Xn[train_nodes])
    yt = torch.as_tensor(y[train_nodes])
    pos = {n: i for i, n in enumerate(train_nodes)}
    ftrain = torch.as_tensor([pos[i] for i in fi])
    xall = torch.as_tensor(Xn)
    yv = y[vi]

    best, best_state, stale, ep_done = -np.inf, None, 0, 0
    for ep in range(1, args.epochs + 1):
        model.train()
        opt.zero_grad(set_to_none=True)
        logits = model(xt)
        loss = torch.nn.functional.cross_entropy(logits[ftrain], yt[ftrain])
        loss.backward()
        opt.step()
        ep_done = ep
        if ep == 1 or ep % 5 == 0 or ep == args.epochs:
            model.eval()
            with torch.no_grad():
                pv = model(xall)[vi].softmax(-1)[:, 1].numpy()
            auc = float(roc_auc_score(yv, pv))
            if auc > best + 1e-9:
                best, stale = auc, 0
                best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            else:
                stale += 1
                if stale >= args.patience:
                    break

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        pq = model(xall)[qi].softmax(-1)[:, 1].numpy()

    out = {
        "status": "PASS",
        "regime": args.regime,
        "split_seed": args.split_seed,
        "fold": args.fold,
        "train_seed": args.train_seed,
        "dropout": args.dropout,
        "n_fit": len(F), "n_validation": len(V), "n_query": len(Q),
        "n_train_nodes": len(train_nodes),
        "features": int(Xn.shape[1]),
        "best_val_auc": best,
        "epochs": ep_done,
        "xn_sha256": xn_sha,
        "train_nodes_sha256": tn_sha,
        "predictions": {s: float(p) for s, p in zip(Q, pq)},
        "elapsed_seconds": round(time.time() - t0, 2),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("regime", "split_seed", "fold", "train_seed",
                                         "best_val_auc", "epochs", "n_train_nodes",
                                         "elapsed_seconds")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
