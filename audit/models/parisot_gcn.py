"""Controlled adapter for the immutable Parisot population-GCN source."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import eigsh
from scipy.spatial import distance
from sklearn.feature_selection import RFE
from sklearn.linear_model import RidgeClassifier


@dataclass(frozen=True)
class ParisotGraph:
    subject_ids: tuple[str, ...]
    phenotype_affinity: np.ndarray
    imaging_affinity: np.ndarray
    adjacency: np.ndarray

    def hash(self) -> str:
        digest = hashlib.sha256()
        digest.update("\n".join(self.subject_ids).encode("utf-8"))
        digest.update(np.ascontiguousarray(self.adjacency).tobytes())
        return digest.hexdigest()


class ParisotFeatureSelector:
    """Released Ridge-RFE preprocessing with an explicit F-only fit API."""

    def __init__(self, n_features: int = 2000, step: int = 100) -> None:
        self.n_features = n_features
        self.step = step
        self._selector: RFE | None = None
        self.fit_subject_ids: tuple[str, ...] = ()

    def fit(self, features: np.ndarray, labels: np.ndarray, fit_subject_ids: tuple[str, ...]) -> None:
        if len(features) != len(labels) or len(labels) != len(fit_subject_ids):
            raise ValueError("F-only feature-selection inputs have inconsistent lengths")
        if len(set(fit_subject_ids)) != len(fit_subject_ids):
            raise ValueError("duplicate F subject IDs")
        count = min(self.n_features, features.shape[1])
        self._selector = RFE(RidgeClassifier(), n_features_to_select=count, step=self.step)
        self._selector.fit(features, labels)
        self.fit_subject_ids = fit_subject_ids

    def transform(self, features: np.ndarray) -> np.ndarray:
        if self._selector is None:
            raise RuntimeError("feature selector has not been fit on F")
        return np.asarray(self._selector.transform(features), dtype=np.float32)


def build_parisot_graph(
    subject_ids: tuple[str, ...],
    features: np.ndarray,
    sites: np.ndarray,
    sexes: np.ndarray,
) -> ParisotGraph:
    """Match released SEX+SITE affinity multiplied by imaging similarity."""
    n = len(subject_ids)
    if len(set(subject_ids)) != n:
        raise ValueError("duplicate subject IDs")
    if features.shape[0] != n or len(sites) != n or len(sexes) != n:
        raise ValueError("graph inputs have inconsistent subject dimensions")
    phenotype = (sites[:, None] == sites[None, :]).astype(np.float64)
    phenotype += (sexes[:, None] == sexes[None, :]).astype(np.float64)
    np.fill_diagonal(phenotype, 0.0)
    distances = distance.squareform(distance.pdist(features, metric="correlation"))
    sigma = float(np.mean(distances))
    if not np.isfinite(sigma) or sigma <= 0:
        raise ValueError("invalid imaging-distance scale")
    imaging = np.exp(-(distances**2) / (2.0 * sigma**2))
    adjacency = phenotype * imaging
    if not np.all(np.isfinite(adjacency)):
        raise ValueError("non-finite Parisot adjacency")
    return ParisotGraph(subject_ids, phenotype, imaging, adjacency)


def normalized_adjacency(adjacency: np.ndarray) -> sparse.coo_matrix:
    """Kipf-style symmetric normalization after adding self-loops."""
    matrix = sparse.coo_matrix(adjacency) + sparse.eye(adjacency.shape[0])
    rowsum = np.asarray(matrix.sum(1)).ravel()
    inverse_sqrt = np.power(rowsum, -0.5, where=rowsum != 0)
    inverse_sqrt[rowsum == 0] = 0.0
    degree = sparse.diags(inverse_sqrt)
    return (degree @ matrix @ degree).tocoo()


def chebyshev_supports(adjacency: np.ndarray, degree: int = 3) -> tuple[sparse.coo_matrix, ...]:
    """Generate the supports used by the released `gcn_cheby` configuration."""
    if degree < 0:
        raise ValueError("Chebyshev degree must be non-negative")
    adj_norm = normalized_adjacency(adjacency)
    laplacian = sparse.eye(adjacency.shape[0]) - adj_norm
    largest = float(eigsh(laplacian, 1, which="LM", return_eigenvectors=False)[0])
    scaled = ((2.0 / largest) * laplacian - sparse.eye(adjacency.shape[0])).tocsr()
    supports = [sparse.eye(adjacency.shape[0], format="csr")]
    if degree >= 1:
        supports.append(scaled)
    for _ in range(2, degree + 1):
        supports.append(2 * scaled @ supports[-1] - supports[-2])
    return tuple(item.tocoo() for item in supports)

