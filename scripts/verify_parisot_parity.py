#!/usr/bin/env python3
"""Parity: controlled Parisot adapter (modern torch) vs native TF1 reference."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from audit.models.parisot_adapter import parisot_predict  # noqa: E402

ref = np.load(Path(sys.argv[1]).resolve())
n, dim, K, depth, n_sup, n_layers = [int(x) for x in ref["meta"]]
supports = [ref[f"support_{i}"] for i in range(n_sup)]
layer_weights = [[ref[f"layer{l}_w{i}"] for i in range(n_sup)] for l in range(n_layers)]
pred = parisot_predict(ref["features"], supports, layer_weights).numpy()
err = float(np.abs(pred - ref["logits"]).max())
print(f"n={n} dim={dim} supports={n_sup} layers={n_layers}")
print(f"softmax max abs err = {err:.3e}   (native sum {ref['logits'].sum():.6f}, modern {pred.sum():.6f})")
print("PARITY:", "PASS" if err <= 1e-5 else "FAIL")
raise SystemExit(0 if err <= 1e-5 else 1)
