"""Serializable records required for a reconstructable audit."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PredictionRecord:
    subject_id: str
    site: str
    label: int
    fold: str
    split_seed: int
    train_seed: int
    model: str
    track: str
    regime: str
    context_size: int
    context_draw: int
    probability: float
    threshold: float
    prediction: int
    checkpoint_hash: str
    graph_hash: str
    preprocess_hash: str
    context_ids_hash: str
    run_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextRecord:
    query_id: str
    split_seed: int
    fold: str
    regime: str
    context_size: int
    context_draw: int
    context_subject_id: str
    context_site: str
    context_ids_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunCard:
    run_id: str
    model: str
    track: str
    regime: str
    upstream_sha: str
    data_hash: str
    split_hash: str
    feature_hash: str
    checkpoint_hash: str
    graph_hash: str
    command: str
    device: str
    environment: str
    status: str

    def __post_init__(self) -> None:
        if self.status not in {"STARTED", "PASS", "FAIL", "PARTIAL"}:
            raise ValueError(f"invalid run status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
