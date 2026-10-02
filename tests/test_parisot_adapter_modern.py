"""Clean-room test for the controlled Parisot adapter (no legacy env needed)."""
from __future__ import annotations

import numpy as np

from audit.models.parisot_adapter import parisot_forward, parisot_predict


def test_identity_support_equals_linear() -> None:
    rng = np.random.default_rng(0)
    x = rng.standard_normal((6, 4)).astype(np.float32)
    w = rng.standard_normal((4, 3)).astype(np.float32)
    out = parisot_forward(x, [np.eye(6, dtype=np.float32)], [[w]])
    assert np.allclose(out.numpy(), x @ w, atol=1e-5)


def test_two_supports_sum_and_relu() -> None:
    rng = np.random.default_rng(1)
    x = rng.standard_normal((5, 3)).astype(np.float32)
    s1 = rng.standard_normal((5, 5)).astype(np.float32)
    s2 = rng.standard_normal((5, 5)).astype(np.float32)
    w1 = rng.standard_normal((3, 2)).astype(np.float32)
    w2 = rng.standard_normal((3, 2)).astype(np.float32)
    out = parisot_forward(x, [s1, s2], [[w1, w2]])
    ref = s1 @ (x @ w1) + s2 @ (x @ w2)   # single layer == last layer -> identity
    assert np.allclose(out.numpy(), ref, atol=1e-5)


def test_relu_applied_on_non_final_layer() -> None:
    rng = np.random.default_rng(3)
    x = rng.standard_normal((4, 3)).astype(np.float32)
    w1 = rng.standard_normal((3, 3)).astype(np.float32)
    w2 = rng.standard_normal((3, 2)).astype(np.float32)
    out = parisot_forward(x, [np.eye(4, dtype=np.float32)], [[w1], [w2]])
    ref = np.maximum(x @ w1, 0) @ w2
    assert np.allclose(out.numpy(), ref, atol=1e-5)


def test_predict_is_softmax() -> None:
    rng = np.random.default_rng(2)
    x = rng.standard_normal((4, 5)).astype(np.float32)
    w = rng.standard_normal((5, 2)).astype(np.float32)
    p = parisot_predict(x, [np.eye(4, dtype=np.float32)], [[w]])
    assert p.shape == (4, 2)
    assert np.allclose(p.sum(1).numpy(), 1.0, atol=1e-5)
