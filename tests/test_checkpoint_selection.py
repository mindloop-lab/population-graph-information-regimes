import pytest

from audit.protocols.firewall import LabelFirewall
from audit.training import EpochValidation, ValidationPrediction, select_checkpoint


FIT = frozenset({"f0", "f1"})
VALIDATION = frozenset({"v0", "v1"})
QUERY = frozenset({"q0", "q1"})
FIREWALL = LabelFirewall({"v0": 0, "v1": 1}, VALIDATION)


def epoch(number: int, p0: float, p1: float) -> EpochValidation:
    return EpochValidation(
        epoch=number,
        checkpoint_hash=f"hash-{number}",
        predictions=(
            ValidationPrediction("v0", 0, p0, ("f0", "f1", "v0")),
            ValidationPrediction("v1", 1, p1, ("f0", "f1", "v1")),
        ),
    )


def test_selects_auc_and_breaks_ties_toward_earlier_epoch() -> None:
    evidence, checkpoint_hash, score = select_checkpoint(
        (epoch(1, 0.2, 0.8), epoch(2, 0.1, 0.9)),
        fit_ids=FIT,
        validation_ids=VALIDATION,
        query_ids=QUERY,
        label_firewall=FIREWALL,
    )
    assert evidence.best_epoch == 1
    assert checkpoint_hash == "hash-1"
    assert score == 1.0


def test_rejects_cohort_visible_validation() -> None:
    invalid = EpochValidation(
        epoch=1,
        checkpoint_hash="hash",
        predictions=(
            ValidationPrediction("v0", 0, 0.2, ("f0", "f1", "v0", "v1")),
            ValidationPrediction("v1", 1, 0.8, ("f0", "f1", "v1")),
        ),
    )
    with pytest.raises(PermissionError, match="not F\\+v"):
        select_checkpoint(
            (invalid,),
            fit_ids=FIT,
            validation_ids=VALIDATION,
            query_ids=QUERY,
            label_firewall=FIREWALL,
        )


def test_rejects_query_visibility_and_incomplete_validation() -> None:
    invalid = EpochValidation(
        epoch=1,
        checkpoint_hash="hash",
        predictions=(ValidationPrediction("v0", 0, 0.2, ("f0", "f1", "v0", "q0")),),
    )
    with pytest.raises(ValueError, match="coverage mismatch"):
        select_checkpoint(
            (invalid,),
            fit_ids=FIT,
            validation_ids=VALIDATION,
            query_ids=QUERY,
            label_firewall=FIREWALL,
        )

