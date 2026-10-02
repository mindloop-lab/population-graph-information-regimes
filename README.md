# population-graph-information-regimes

This repository accompanies **"Information regimes in population-graph neuroimaging: cohort
context and implementation-dependent evaluation sensitivity"** (submission version RC4,
2026-09-30).

It reproduces the controlled **P0/P1 evaluation-regime experiments** for two
population-graph implementations (EV-GCN, learned/adaptive graph; Parisot-GCN, static
weighted graph) on ABIDE-I (871 subjects, 20 sites). Within each implementation, subjects,
features, split partitions, training and selection rules are held fixed; the controlled
intervention changes training-time cohort visibility.

**Data are not redistributed.** Users must obtain ABIDE through the authorized source
(see `docs/DATA_PREPARATION.md`). No raw imagery, no phenotypic tables and no checkpoints
are included.

## Reproduce the paper's primary results without retraining

```bash
python3 scripts/validate_environment.py
python3 scripts/reproduce_primary_results.py --from-frozen   # ΔΔAUC per split, vs the frozen record
python3 scripts/reproduce_tables.py                          # Table 2 / S1 / S2 as CSV
python3 scripts/reproduce_fig2.py                            # Figure 2 panel source data
```

Each entry reads only `frozen_results/` (integrity-checked against its SHA256SUMS),
recomputes the values from the per-subject out-of-fold record and compares them with the
canonical text in `S1_FREEZE.yaml`; any mismatch fails the run. Split 666 predates the
extension runs and carries no per-subject record; its interaction is carried by the frozen
record and is cross-checked, not recomputed. Full campaign reruns are available through
the controlled runner scripts documented below.

## Layout

| path | content |
|---|---|
| `audit/` | the controlled-evaluation library: regime protocols (P0/P1), graph construction, preprocessing scope, training and checkpoint-selection rules |
| `scripts/` | named entry points: split generation, controlled runners, aggregation, bootstrap inference, table/figure generation |
| `configs/` | the locked campaign definition (`configs/study/locked_campaign_v1.yaml`) |
| `frozen_results/` | the frozen record the paper reports from: `S1_FREEZE.yaml`, the per-subject out-of-fold files (`oof/`), the derived table sources (`derived/`), per-cell results, checksums |
| `tests/` | protocol and adapter tests, including the parity checks against upstream implementations |
| `docs/` | regime definitions, data preparation, reproducibility, the reporting checklist |
| `THIRD_PARTY_NOTICES.md` | upstream licenses and pinned commits |

## Regimes in one paragraph

P0 (`test nodes present in the training graph`) and P1 (`train-only graph, cohort-visible
inference`) differ only in whether query subjects appear as unlabeled nodes in the training
graph; labels, fit sets, validation-based selection and training rules are identical. The
primary estimand is the implementation-by-training-context interaction (ΔΔAUC), reported per
preselected split, never pooled. See `docs/REGIME_DEFINITIONS.md`.

## License

Code: GPL-3.0 (the controlled implementations wrap GPL-3.0 upstreams; see
`THIRD_PARTY_NOTICES.md`). Upstreams are fetched by pinned commit and are not vendored here.

## Citation

Repository: <https://github.com/mindloop-lab/population-graph-information-regimes>

Software archive (v1.0.0): DOI `10.5281/zenodo.23104123` — see `CITATION.cff`. Cite both the
software record and the paper.

