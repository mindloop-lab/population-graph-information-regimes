"""Controlled Parisot Deep_GCN (gcn_cheby) adapter, reimplemented in modern torch.

Reproduces the immutable forked `gcn` (third_party/parisots_gcn) forward:
per GraphConvolution layer  h = act( sum_i S_i @ (h @ W_i) )  with ReLU on all
layers but the identity on the last, where S_i are the Chebyshev supports
(precomputed by gcn.utils.chebyshev_polynomials on the normalised adjacency) and
the node features are row-normalised (gcn.utils.preprocess_features).
"""
from __future__ import annotations

import numpy as np
import torch


def parisot_forward(features: np.ndarray, supports: list[np.ndarray],
                    layer_weights: list[list[np.ndarray]]) -> torch.Tensor:
    h = torch.as_tensor(np.asarray(features), dtype=torch.float32)
    sup = [torch.as_tensor(s, dtype=torch.float32) for s in supports]
    last = len(layer_weights) - 1
    for l, ws in enumerate(layer_weights):
        total = None
        for s, w in zip(sup, ws, strict=True):
            term = s @ (h @ torch.as_tensor(np.asarray(w), dtype=torch.float32))
            total = term if total is None else total + term
        h = total if l == last else torch.relu(total)
    return h


def parisot_predict(features, supports, layer_weights) -> torch.Tensor:
    return torch.softmax(parisot_forward(features, supports, layer_weights), dim=-1)


class ParisotDeepGCN(torch.nn.Module):
    """Trainable Deep_GCN(cheby) mirroring upstream: depth+2 GraphConvolution layers,
    each summing over the same chebyshev supports."""

    def __init__(self, in_dim: int, hidden: int, out_dim: int, depth: int, n_support: int) -> None:
        super().__init__()
        dims = [in_dim] + [hidden] * (depth + 1) + [out_dim]
        self.n_support = n_support
        self.weights = torch.nn.ParameterList(
            [torch.nn.Parameter(torch.empty(dims[i], dims[i + 1])) for i in range(len(dims) - 1)
             for _ in range(n_support)]
        )
        self._n_layers = len(dims) - 1
        for p in self.weights:
            torch.nn.init.xavier_uniform_(p)

    def forward(self, x: torch.Tensor, supports: list[torch.Tensor]) -> torch.Tensor:
        h = x
        for l in range(self._n_layers):
            total = None
            for i, s in enumerate(supports):
                w = self.weights[l * self.n_support + i]
                term = s @ (h @ w)
                total = term if total is None else total + term
            h = total if l == self._n_layers - 1 else torch.relu(total)
        return h
