# Third-party notices

This repository's code wraps or interoperates with third-party model implementations.
Each upstream is **fetched at a pinned commit** by the user (see
`docs/DATA_PREPARATION.md`) and is not vendored here. The table is reproduced from
`manifests/THIRD_PARTY_LOCK.tsv` (source verification: `results/source_lock_verification_cleanroom.json`).

| upstream | role in the audit | license | pinned commit | redistribution decision |
|---|---|---|---|---|
| population-gcn (Parisot et al.) | core-static population-graph implementation (Parisot-GCN wrapper) | GPL-3.0 | `185e2f5d9745484b8c7994f80254740b9cbb7b75` | not vendored; user fetches at pinned commit. Because the controlled wrappers interoperate with (and are derived from) GPL-3.0 upstream code, this repository is distributed under GPL-3.0 |
| EV_GCN (Huang & Chung) | core-adaptive population-graph implementation (EV-GCN wrapper) | GPL-3.0 | `57363b85c56ee9d093976bda203ef62c237c985f` | not vendored; user fetches at pinned commit; covered by this repository's GPL-3.0 |
| single_subject_popgnn | core-inductive reference (Track N characterisation only) | **NO-LICENSE-FILE** | `3522c83cf2ac19a8488baeb444dadf57a62fc35a` | **no content redistributed** (all rights reserved by default); user may fetch for private study |
| FC-HGNN_Pytorch | engineering-gated extension (excluded from the paper's reported matrix) | MIT | `e887e1b9e39287d5f3a52701437235df4249f0fa` | not used in the primary campaign; not vendored |
| BrainGNN_Pytorch | optional individual-graph control (excluded) | **NO-LICENSE-FILE** | `1e337e7a13af5e4374343fda81ce11b62c5ce566` | **no content redistributed** |
| fMRI-site-adaptation | optional site-shift control (excluded) | GPL-3.0 | `0a70cf827192244fc8fadd818d5d7cf946d32096` | not used in the primary campaign; not vendored |
| LGMF-GNN | not in the primary matrix | MIT | `98cf56c322404e4d1aa80ba24bef7568c8df4bbf` | not vendored |
| abide (Preprocessed Connectomes Project) | data provenance reference only | **NO-LICENSE-FILE** | `fda1ec5d3f53eb97d94352e779f37c3ce46caee1` | **no content redistributed**; ABIDE data obtained from the official source only |

## Why GPL-3.0

The two primary implementations (Parisot-GCN, EV-GCN wrappers) are controlled variants of
GPL-3.0 upstream code. Distributing them together with this repository's glue code under
GPL-3.0 keeps every contribution compliant without case-by-case legal judgment. If a future
contributor establishes that a component is independent of GPL upstream code, that
component may be relicensed then; the default remains GPL-3.0.

## What is ours

Everything under `audit/`, `scripts/` (the controlled runners, aggregation, bootstrap
inference and figure/table generation), `tests/`, `configs/`, `frozen_results/` and the
documentation is part of this repository's contribution and is licensed GPL-3.0 (or, for
the frozen result records, released as data alongside the code under the same terms).
