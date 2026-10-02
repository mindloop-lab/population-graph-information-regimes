"""Fail-closed checkpoint selection using query-isolated validation only."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from sklearn.metrics import roc_auc_score

from audit.protocols.firewall import CheckpointEvidence, LabelFirewall


@dataclass(frozen=True)
class ValidationPrediction:
    subject_id: str
    label: int
    probability: float
    context_ids: tuple[str, ...]


@dataclass(frozen=True)
class EpochValidation:
    epoch: int
    checkpoint_hash: str
    predictions: tuple[ValidationPrediction, ...]


def validate_query_isolated_epoch(
    result: EpochValidation,
    *,
    fit_ids: frozenset[str],
    validation_ids: frozenset[str],
    query_ids: frozenset[str],
    label_firewall: LabelFirewall,
) -> None:
    """Require one F+v context per V subject and no Q membership."""
    if result.epoch < 1:
        raise ValueError("epoch numbering must start at one")
    if not result.checkpoint_hash:
        raise ValueError("checkpoint hash is empty")
    observed_ids = [item.subject_id for item in result.predictions]
    if len(observed_ids) != len(set(observed_ids)):
        raise ValueError("duplicate validation predictions")
    if frozenset(observed_ids) != validation_ids:
        missing = sorted(validation_ids - set(observed_ids))
        extra = sorted(set(observed_ids) - validation_ids)
        raise ValueError(f"validation coverage mismatch: missing={missing[:5]}, extra={extra[:5]}")
    for item in result.predictions:
        expected = fit_ids | {item.subject_id}
        context = frozenset(item.context_ids)
        if len(context) != len(item.context_ids):
            raise ValueError(f"duplicate context IDs for {item.subject_id}")
        if context != expected:
            raise PermissionError(f"validation context is not F+v for {item.subject_id}")
        if context & query_ids:
            raise PermissionError(f"query subject visible during validation for {item.subject_id}")
        if item.label != label_firewall.get(item.subject_id):
            raise ValueError(f"label mismatch for validation subject {item.subject_id}")
        if not 0.0 <= item.probability <= 1.0 or not isfinite(item.probability):
            raise ValueError(f"invalid probability for {item.subject_id}")


def select_checkpoint(
    epochs: tuple[EpochValidation, ...],
    *,
    fit_ids: frozenset[str],
    validation_ids: frozenset[str],
    query_ids: frozenset[str],
    label_firewall: LabelFirewall,
) -> tuple[CheckpointEvidence, str, float]:
    """Select maximum validation AUC, resolving ties toward the earliest epoch."""
    if not epochs:
        raise ValueError("no checkpoint candidates")
    scored: list[tuple[float, int, str]] = []
    seen_epochs: set[int] = set()
    for result in epochs:
        if result.epoch in seen_epochs:
            raise ValueError(f"duplicate epoch candidate: {result.epoch}")
        seen_epochs.add(result.epoch)
        validate_query_isolated_epoch(
            result,
            fit_ids=fit_ids,
            validation_ids=validation_ids,
            query_ids=query_ids,
            label_firewall=label_firewall,
        )
        labels = [item.label for item in result.predictions]
        if len(set(labels)) != 2:
            raise ValueError("validation AUC requires both classes")
        probabilities = [item.probability for item in result.predictions]
        scored.append((float(roc_auc_score(labels, probabilities)), result.epoch, result.checkpoint_hash))
    score, best_epoch, checkpoint_hash = max(scored, key=lambda row: (row[0], -row[1]))
    evidence = CheckpointEvidence(
        best_epoch=best_epoch,
        selection_metric="query_isolated_validation_auc",
        selection_subject_ids=validation_ids,
    )
    evidence.validate(validation_ids)
    return evidence, checkpoint_hash, score

