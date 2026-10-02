"""Typed, immutable definitions for the controlled audit protocols."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class Protocol(StrEnum):
    R0_T = "R0-T"
    R1_C = "R1-C"
    R2_Q = "R2-Q"


@dataclass(frozen=True)
class SplitRecord:
    subject_id: str
    site_id: str
    label: int
    split_seed: int
    outer_fold: int
    role: str

    def __post_init__(self) -> None:
        if self.role not in {"fit", "validation", "query"}:
            raise ValueError(f"invalid split role: {self.role}")
        if self.label not in {0, 1}:
            raise ValueError(f"invalid binary label: {self.label}")


@dataclass(frozen=True)
class ProtocolSpec:
    protocol: Protocol
    fit_ids: tuple[str, ...]
    validation_ids: tuple[str, ...]
    query_ids: tuple[str, ...]
    inference_context_ids: tuple[str, ...]

    @classmethod
    def create(
        cls,
        protocol: Protocol,
        fit_ids: Iterable[str],
        validation_ids: Iterable[str],
        query_ids: Iterable[str],
        inference_context_ids: Iterable[str],
    ) -> "ProtocolSpec":
        obj = cls(
            protocol=protocol,
            fit_ids=tuple(fit_ids),
            validation_ids=tuple(validation_ids),
            query_ids=tuple(query_ids),
            inference_context_ids=tuple(inference_context_ids),
        )
        obj.validate()
        return obj

    def validate(self) -> None:
        fit = set(self.fit_ids)
        validation = set(self.validation_ids)
        query = set(self.query_ids)
        context = set(self.inference_context_ids)
        if len(fit) != len(self.fit_ids):
            raise ValueError("duplicate fit subject IDs")
        if len(validation) != len(self.validation_ids):
            raise ValueError("duplicate validation subject IDs")
        if len(query) != len(self.query_ids):
            raise ValueError("duplicate query subject IDs")
        if fit & validation or fit & query or validation & query:
            raise ValueError("fit, validation, and query sets must be disjoint")
        if not context <= query:
            raise ValueError("inference context must be a subset of query IDs")
        if self.protocol is Protocol.R2_Q and len(context) != 1:
            raise ValueError("R2-Q must contain exactly one query in context")
        if self.protocol in {Protocol.R0_T, Protocol.R1_C} and context != query:
            raise ValueError(f"{self.protocol} requires the complete query cohort")
