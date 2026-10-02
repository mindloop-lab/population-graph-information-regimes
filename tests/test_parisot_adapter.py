import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import numpy as np

from audit.models.parisot_gcn import build_parisot_graph, chebyshev_supports


def load_native_parser(path: Path) -> ModuleType:
    nilearn = ModuleType("nilearn")
    connectome = ModuleType("connectome")
    nilearn.connectome = connectome
    previous = sys.modules.get("nilearn")
    sys.modules["nilearn"] = nilearn
    spec = importlib.util.spec_from_file_location("parisot_native_parser", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    old_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old_bytecode
        if previous is None:
            sys.modules.pop("nilearn", None)
        else:
            sys.modules["nilearn"] = previous
    return module


def test_phenotype_adjacency_matches_immutable_upstream() -> None:
    ids = ("a", "b", "c", "d")
    sites = np.asarray(["X", "X", "Y", "Y"])
    sexes = np.asarray([1, 2, 1, 2])
    features = np.asarray([[1, 2, 4], [2, 1, 3], [4, 2, 1], [3, 4, 2]], dtype=float)
    native = load_native_parser(
        Path(__file__).parents[1] / "third_party" / "population-gcn" / "ABIDEParser.py"
    )
    values = {"SITE_ID": dict(zip(ids, sites)), "SEX": dict(zip(ids, sexes))}
    native.get_subject_score = lambda subject_ids, score: {
        subject_id: values[score][subject_id] for subject_id in subject_ids
    }
    expected = native.create_affinity_graph_from_scores(["SEX", "SITE_ID"], ids)
    actual = build_parisot_graph(ids, features, sites, sexes)
    np.testing.assert_array_equal(actual.phenotype_affinity, expected)
    np.testing.assert_allclose(actual.adjacency, expected * actual.imaging_affinity, atol=0, rtol=0)


def test_chebyshev_support_count_and_symmetry() -> None:
    adjacency = np.asarray([[0.0, 1.0, 0.2], [1.0, 0.0, 0.5], [0.2, 0.5, 0.0]])
    supports = chebyshev_supports(adjacency, degree=3)
    assert len(supports) == 4
    for support in supports:
        np.testing.assert_allclose(support.toarray(), support.toarray().T, atol=1e-12)

