"""Adapters for immutable upstream model implementations."""

try:
    from .lim_ipgnn import CanonicalABIDE, LimIPGNNAdapter
except ImportError:  # the public release tree ships without the Lim track
    pass
from .parisot_gcn import ParisotFeatureSelector, ParisotGraph, build_parisot_graph, chebyshev_supports

__all__ = [
    "CanonicalABIDE",
    "LimIPGNNAdapter",
    "ParisotFeatureSelector",
    "ParisotGraph",
    "build_parisot_graph",
    "chebyshev_supports",
]
