"""Runtime firewalls that make forbidden label access fail loudly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class LabelFirewall:
    labels: Mapping[str, int]
    allowed_ids: frozenset[str]

    def get(self, subject_id: str) -> int:
        if subject_id not in self.allowed_ids:
            raise PermissionError(f"label access denied for subject {subject_id}")
        return self.labels[subject_id]

    def vector(self, subject_ids: list[str] | tuple[str, ...]) -> list[int]:
        return [self.get(subject_id) for subject_id in subject_ids]


@dataclass(frozen=True)
class CheckpointEvidence:
    best_epoch: int
    selection_metric: str
    selection_subject_ids: frozenset[str]

    def validate(self, validation_ids: frozenset[str]) -> None:
        if not self.selection_subject_ids:
            raise ValueError("checkpoint selection evidence is empty")
        if not self.selection_subject_ids <= validation_ids:
            forbidden = sorted(self.selection_subject_ids - validation_ids)
            raise PermissionError(f"checkpoint selection used non-validation IDs: {forbidden[:5]}")
