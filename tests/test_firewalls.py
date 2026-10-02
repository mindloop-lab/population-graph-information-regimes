import pytest

from audit.protocols.firewall import CheckpointEvidence, LabelFirewall


def test_label_firewall_denies_query_label() -> None:
    labels = LabelFirewall({"f": 0, "q": 1}, frozenset({"f"}))
    assert labels.get("f") == 0
    with pytest.raises(PermissionError, match="denied"):
        labels.get("q")


def test_checkpoint_evidence_allows_only_validation_ids() -> None:
    evidence = CheckpointEvidence(4, "balanced_accuracy", frozenset({"v"}))
    evidence.validate(frozenset({"v"}))
    with pytest.raises(PermissionError, match="non-validation"):
        CheckpointEvidence(4, "balanced_accuracy", frozenset({"q"})).validate(frozenset({"v"}))
