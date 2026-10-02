"""Controlled EV-GCN adapter: faithful reimplementation of the immutable upstream
`third_party/EV_GCN` model under the modern stack (torch2.x).

The upstream model cannot be loaded unchanged here because torch_geometric 2.8
reparameterised `ChebConv` (per-K `lins.k.weight` instead of a single
`weight (K, in, out)`). This module reimplements pyg-1.4.3 `ChebConv` (the exact
operator the native env uses) with plain torch index_add, plus the upstream
EV_GCN forward (ReLU + JK-concat + cls head + PAE edge network), so the native
state_dict loads directly and logits can be parity-checked.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import torch
from torch import nn


def load_upstream_pae(upstream: Path) -> type:
    """Import the immutable upstream PAE class without editing third_party."""
    utils_prev = sys.modules.get("PAE")
    spec = importlib.util.spec_from_file_location("ev_upstream_pae", upstream / "PAE.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {upstream/'PAE.py'}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ev_upstream_pae"] = module
    spec.loader.exec_module(module)
    if utils_prev is None:
        sys.modules.pop("PAE", None)
    return module.PAE


class ChebConv143(nn.Module):
    """pyg-1.4.3 ChebConv (normalization='sym', lambda_max=2, bias off).

    Effective operator: L_hat = -D^{-1/2} A D^{-1/2} (the identity from
    get_laplacian is cancelled by the fill_value=-1 self loops), applied on the
    edge list exactly as given (single direction), messages col -> row.
    """

    def __init__(self, in_channels: int, out_channels: int, k: int, bias: bool = False) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.empty(k, in_channels, out_channels))
        nn.init.xavier_uniform_(self.weight.reshape(k, in_channels, out_channels))
        if bias:
            self.bias = nn.Parameter(torch.zeros(out_channels))
        else:
            self.register_parameter("bias", None)

    @staticmethod
    def _operator(edge_index: torch.Tensor, edge_weight: torch.Tensor, num_nodes: int):
        # ChebConv.norm: remove_self_loops -> get_laplacian(sym) -> /lambda_max -> add_self_loops(-1)
        # pyg flow='source_to_target': messages from edge_index[0] (source) to edge_index[1] (target).
        keep = edge_index[0] != edge_index[1]
        src, dst = edge_index[0][keep], edge_index[1][keep]
        ew = edge_weight[keep]
        deg = torch.zeros(num_nodes, dtype=ew.dtype, device=ew.device).index_add_(0, src, ew)
        dinv = deg.pow(-0.5)
        dinv[deg == 0] = 0.0
        off = -dinv[src] * ew * dinv[dst]      # -A_norm off-diagonal (identity nets to 0)
        return src, dst, off

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor, edge_weight: torch.Tensor) -> torch.Tensor:
        n = x.size(0)
        src, dst, off = self._operator(edge_index, edge_weight, n)
        k = self.weight.size(0)

        def prop(z: torch.Tensor) -> torch.Tensor:
            msg = off.unsqueeze(1) * z[src]
            return torch.zeros_like(z).index_add_(0, dst, msg)

        tx0 = x
        out = tx0 @ self.weight[0]
        if k > 1:
            tx1 = prop(x)
            out = out + tx1 @ self.weight[1]
            for j in range(2, k):
                tx2 = 2.0 * prop(tx1) - tx0
                out = out + tx2 @ self.weight[j]
                tx0, tx1 = tx1, tx2
        if self.bias is not None:
            out = out + self.bias
        return out


class ControlledEVGCN(nn.Module):
    """Mirror of upstream EV_GCN (EV_GCN.py) with ChebConv143. Same state_dict keys."""

    def __init__(self, upstream: Path, input_dim: int, num_classes: int, dropout: float,
                 edgenet_input_dim: int, edge_dropout: float, hgc: int, lg: int) -> None:
        super().__init__()
        self.dropout = dropout
        self.edge_dropout = edge_dropout
        self.lg = lg
        self.relu = nn.ReLU(inplace=True)
        self.gconv = nn.ModuleList()
        for i in range(lg):
            in_ch = input_dim if i == 0 else hgc
            self.gconv.append(ChebConv143(in_ch, hgc, 3, bias=False))
        self.cls = nn.Sequential(
            nn.Linear(hgc * lg, 256), nn.ReLU(inplace=True), nn.BatchNorm1d(256), nn.Linear(256, num_classes))
        pae = load_upstream_pae(upstream)
        self.edge_net = pae(input_dim=edgenet_input_dim // 2, dropout=dropout)

    def forward(self, features: torch.Tensor, edge_index: torch.Tensor, edgenet_input: torch.Tensor):
        if self.edge_dropout > 0 and self.training:
            raise RuntimeError("edge dropout not supported in the controlled adapter")
        edge_weight = torch.squeeze(self.edge_net(edgenet_input))
        h = self.relu(self.gconv[0](features, edge_index, edge_weight))
        h0 = h
        jk = h
        for i in range(1, self.lg):
            h = self.relu(self.gconv[i](h, edge_index, edge_weight))
            jk = torch.cat((h0, h), dim=1)
            h0 = jk
        return self.cls(jk), edge_weight
