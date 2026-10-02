import pytest

from audit.protocols import Protocol, ProtocolSpec


def test_r1_accepts_complete_query_context() -> None:
    spec = ProtocolSpec.create(Protocol.R1_C, ["f1"], ["v1"], ["q1", "q2"], ["q1", "q2"])
    assert spec.protocol is Protocol.R1_C


def test_r2_requires_one_query() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        ProtocolSpec.create(Protocol.R2_Q, ["f1"], ["v1"], ["q1", "q2"], ["q1", "q2"])


def test_roles_must_be_disjoint() -> None:
    with pytest.raises(ValueError, match="disjoint"):
        ProtocolSpec.create(Protocol.R1_C, ["same"], ["v1"], ["same"], ["same"])


def test_context_cannot_escape_query_set() -> None:
    with pytest.raises(ValueError, match="subset"):
        ProtocolSpec.create(Protocol.R2_Q, ["f1"], ["v1"], ["q1"], ["other"])
