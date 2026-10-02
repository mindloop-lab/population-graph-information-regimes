"""Label-blind, order-stable context interventions."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Iterable, Mapping


def stable_hash(values: Iterable[str]) -> str:
    canonical = "\n".join(sorted(str(value) for value in values)).encode()
    return hashlib.sha256(canonical).hexdigest()


def _stable_seed(*parts: object) -> int:
    digest = hashlib.sha256("::".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


@dataclass(frozen=True)
class ContextDraw:
    query_id: str
    context_ids: tuple[str, ...]
    draw: int
    kind: str

    @property
    def context_hash(self) -> str:
        return stable_hash(self.context_ids)

    def __post_init__(self) -> None:
        if self.query_id in self.context_ids:
            raise ValueError("query must not appear among additional context IDs")
        if len(set(self.context_ids)) != len(self.context_ids):
            raise ValueError("duplicate context IDs")


def random_context_draws(
    query_id: str,
    query_pool: Iterable[str],
    context_size: int,
    draws: int,
    seed: int,
) -> list[ContextDraw]:
    candidates = sorted(set(query_pool) - {query_id})
    if context_size < 0 or context_size > len(candidates):
        raise ValueError(f"context size {context_size} exceeds pool {len(candidates)}")
    output = []
    for draw in range(draws):
        rng = random.Random(_stable_seed(seed, query_id, context_size, draw, "random"))
        chosen = tuple(sorted(rng.sample(candidates, context_size)))
        output.append(ContextDraw(query_id, chosen, draw, "random"))
    return output


def site_matched_context_draws(
    query_id: str,
    query_pool: Iterable[str],
    sites: Mapping[str, str],
    cap: int,
    draws: int,
    seed: int,
) -> list[tuple[ContextDraw, ContextDraw]]:
    if query_id not in sites:
        raise KeyError(f"missing site for query {query_id}")
    candidates = sorted(set(query_pool) - {query_id})
    same = [subject_id for subject_id in candidates if sites[subject_id] == sites[query_id]]
    cross = [subject_id for subject_id in candidates if sites[subject_id] != sites[query_id]]
    size = min(cap, len(same), len(cross))
    if size == 0:
        return []
    output = []
    for draw in range(draws):
        rng = random.Random(_stable_seed(seed, query_id, size, draw, "site-matched"))
        same_ids = tuple(sorted(rng.sample(same, size)))
        cross_ids = tuple(sorted(rng.sample(cross, size)))
        output.append(
            (
                ContextDraw(query_id, same_ids, draw, "same-site"),
                ContextDraw(query_id, cross_ids, draw, "cross-site"),
            )
        )
    return output
