import pytest

from audit.inference import RunCard


def test_run_card_rejects_unknown_status() -> None:
    with pytest.raises(ValueError, match="invalid run status"):
        RunCard(
            run_id="x",
            model="rf",
            track="A",
            regime="R2-Q",
            upstream_sha="none",
            data_hash="data",
            split_hash="split",
            feature_hash="feature",
            checkpoint_hash="checkpoint",
            graph_hash="graph",
            command="cmd",
            device="cpu",
            environment="test",
            status="UNKNOWN",
        )
