"""Clean-room correctness tests for the controlled EV-GCN adapter.

These do NOT require the legacy (py3.7/torch1.4) environment: the Chebyshev
operator is validated against an explicit dense-matrix formulation of the exact
pyg-1.4.3 semantics (L_hat = -D^{-1/2} A D^{-1/2}, messages src=edge_index[0]
-> dst=edge_index[1]), and the full model is checked to be trainable on the
modern stack.
"""
from __future__ import annotations

from pathlib import Path

import torch

from audit.models.ev_gcn_adapter import ChebConv143, ControlledEVGCN

UPSTREAM = Path(__file__).resolve().parent.parent / "third_party" / "EV_GCN"


def _dense_operator(edge_index: torch.Tensor, edge_weight: torch.Tensor, n: int) -> torch.Tensor:
    src, dst = edge_index[0], edge_index[1]
    deg = torch.zeros(n, dtype=edge_weight.dtype)
    deg.index_add_(0, src, edge_weight)
    dinv = deg.pow(-0.5)
    dinv[deg == 0] = 0.0
    off = -dinv[src] * edge_weight * dinv[dst]
    m = torch.zeros(n, n)
    m.index_put_((dst, src), off, accumulate=True)   # m[dst, src] += off
    return m


def test_chebconv143_matches_dense_recurrence() -> None:
    torch.manual_seed(0)
    n, cin, cout, k = 15, 4, 3, 3
    conv = ChebConv143(cin, cout, k, bias=False)
    x = torch.randn(n, cin)
    edge_index = torch.stack([torch.arange(n - 1), torch.arange(1, n)])
    edge_weight = torch.rand(edge_index.size(1))

    out = conv(x, edge_index, edge_weight)

    m = _dense_operator(edge_index, edge_weight, n)
    tx0, tx1 = x, m @ x
    ref = tx0 @ conv.weight[0] + tx1 @ conv.weight[1]
    for j in range(2, k):
        tx2 = 2.0 * (m @ tx1) - tx0
        ref = ref + tx2 @ conv.weight[j]
        tx0, tx1 = tx1, tx2
    assert torch.allclose(out, ref, atol=1e-5), (out - ref).abs().max()


def test_chebconv143_symmetric_graph_matches_dense() -> None:
    torch.manual_seed(1)
    n, cin, cout, k = 12, 3, 2, 3
    conv = ChebConv143(cin, cout, k, bias=False)
    x = torch.randn(n, cin)
    src = torch.arange(n)
    dst = (torch.arange(n) + 2) % n
    edge_index = torch.stack([torch.cat([src, dst]), torch.cat([dst, src])])
    edge_weight = torch.rand(edge_index.size(1))
    out = conv(x, edge_index, edge_weight)
    m = _dense_operator(edge_index, edge_weight, n)
    tx0, tx1 = x, m @ x
    ref = tx0 @ conv.weight[0] + tx1 @ conv.weight[1] + (2.0 * (m @ tx1) - tx0) @ conv.weight[2]
    assert torch.allclose(out, ref, atol=1e-5)


def test_controlled_evgcn_trainable() -> None:
    torch.manual_seed(0)
    model = ControlledEVGCN(UPSTREAM, input_dim=8, num_classes=2, dropout=0.0,
                            edgenet_input_dim=6, edge_dropout=0.0, hgc=16, lg=4)
    n = 20
    features = torch.randn(n, 8, requires_grad=False)
    edge_index = torch.stack([torch.arange(n - 1), torch.arange(1, n)])
    edgenet_input = torch.randn(edge_index.size(1), 6)
    labels = torch.randint(0, 2, (n,))
    logits, _ = model(features, edge_index, edgenet_input)
    loss = torch.nn.functional.cross_entropy(logits, labels)
    loss.backward()
    grads = [p.grad.abs().sum().item() for p in model.parameters() if p.grad is not None]
    assert grads and any(g > 0 for g in grads)
    assert logits.shape == (n, 2)
