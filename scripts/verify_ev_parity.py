#!/usr/bin/env python3
"""Clean-room EV-GCN parity: load the native state_dict into the controlled
adapter (audit/models/ev_gcn_adapter.py) under the modern stack and compare
logits/edge weights to the native reference.

Fails closed unless both agree within atol.
"""
from __future__ import annotations

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from audit.models.ev_gcn_adapter import ControlledEVGCN  # noqa: E402

UPSTREAM = Path(sys.argv[1]).resolve()
REF = Path(sys.argv[2]).resolve()
ATOL = 1e-4

ref = torch.load(REF, map_location="cpu", weights_only=False)
cfg = ref["config"]
model = ControlledEVGCN(UPSTREAM, cfg["input_dim"], 2, dropout=0.0,
                        edgenet_input_dim=cfg["edgenet_input_dim"], edge_dropout=0.0,
                        hgc=cfg["hgc"], lg=cfg["lg"])
missing, unexpected = model.load_state_dict(ref["state_dict"], strict=False)
print("missing:", list(missing), "unexpected:", list(unexpected))
model.eval()
with torch.no_grad():
    logits, edge_weight = model(ref["features"], ref["edge_index"], ref["edgenet_input"])

err = float((logits - ref["logits"]).abs().max())
ew_err = float((edge_weight - ref["edge_weight"]).abs().max())
print("native torch", ref["torch"], "-> modern torch", torch.__version__)
print(f"logit max abs err      = {err:.3e}")
print(f"edge_weight max abs err= {ew_err:.3e}")
ok = err <= ATOL and not missing and not unexpected
print("PARITY:", "PASS" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
