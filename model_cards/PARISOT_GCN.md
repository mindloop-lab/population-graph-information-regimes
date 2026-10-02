# Parisot-GCN — Static population graph

- Upstream: `third_party/population-gcn` at the locked commit.
- License: GPL-3.0.
- Framework: legacy TensorFlow plus the authors' fork of Kipf GCN.
- Population graph: phenotypic affinity from SEX and SITE_ID, multiplied by an
  imaging-feature similarity kernel.
- Released feature selection: supervised selection uses training indices.
- Released-code validation risk: outer test indices are passed as validation
  indices, including an explicit `val = test` path.
- Released graph visibility: all subjects are present when the population
  graph and imaging kernel are constructed.
- Track N: characterize released behavior without using it for inference.
- Track A: disjoint F/V/Q, F-only supervised preprocessing, validation-only
  checkpoint/threshold selection, centralized R0/R1/R2 context construction.
- Fidelity requirement: adjacency, Chebyshev supports, parameter count, and
  fixed-weight logits must match the legacy implementation within a declared
  numerical tolerance.
