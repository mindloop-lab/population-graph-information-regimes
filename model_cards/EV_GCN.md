# EV-GCN — Learned/adaptive population graph

- Upstream: `third_party/EV_GCN` at the locked commit.
- License: GPL-3.0.
- Framework: released requirements target Python 3.7, PyTorch 1.4, and an old
  torch-geometric release; use an isolated native environment.
- Node preprocessing: supervised feature selection receives train indices.
- Released graph visibility: edge candidates and phenotypic inputs are built
  over the complete cohort.
- Released normalization risk: edge inputs are standardized using complete
  cohort edge statistics.
- Released checkpoint risk: test accuracy is evaluated every epoch and used
  to save the selected checkpoint.
- Track N: describe released behavior and reproduction status.
- Track A: disjoint V, validation-only checkpoint selection, F-only fitted
  preprocessing, and centralized R0/R1/R2 graph contexts.
- Mechanism sensitivity: distinguish context-dependent graph construction from
  context-dependent edge normalization.
- Fidelity requirement: fixed graph, edge inputs, parameters, and evaluation
  mode must produce adapter logits matching the upstream implementation.
