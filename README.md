# population-graph-information-regimes

This repository accompanies **"Information regimes in population-graph neuroimaging: cohort
context and implementation-dependent evaluation sensitivity"**.

Manuscript versions and dates: the first public release (tag `v1.0.0`, commit `b83ad83`)
accompanied manuscript **RC4 (2026-09-30)**. Manuscript **RC5.18 (2026-10-21)** is released as
**v1.0.1 (2026-10-22)**, and the revision candidate **`revision-1022-v8` (2026-10-22)** as
**v1.1.0**. The manuscript was submitted to bioRxiv on
**2 October 2026** and first posted on **8 October 2026** (DOI
`10.64898/2026.10.02.756253`, CC-BY 4.0).

| manuscript | date | this repository |
|---|---|---|
| RC4 | 2026-09-30 | tag `v1.0.0`, commit `b83ad83` |
| RC5.18 | 2026-10-21 | release `v1.0.1` (2026-10-22) |
| revision-1022-v8 | 2026-10-22 | release `v1.1.0` (candidate branch `release/v1.1.0`) |

The software result layer is unchanged between `v1.0.0` and `v1.0.1`: no model, split,
training rule or frozen value has changed. What `v1.0.1` adds is the frozen split
registry, the Table 1 source and generator, and documentation. `v1.1.0` is an increment on
top of it: the negative-control study (scripts, the 60 per-cell records and both aggregate
outputs), Reporting Checklist v2, and the regenerated Figure 1 and Figure 2 used by the
revision candidate. No primary result, split or frozen value is altered by the increment.

Version history: `v1.0.0` is archived at the version DOI `10.5281/zenodo.23104123` and `v1.0.1`
at `10.5281/zenodo.23554740`; the concept DOI `10.5281/zenodo.23104122` resolves to the latest
version. `v1.1.0` is archived at the version DOI `10.5281/zenodo.23609463`.

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

The figure generators (`figures/Fig2_primary_interaction.py`,
`figures/FS2_loso_sensitivity.py`) read the same frozen inputs and also run from a public
checkout: when the private control plane is absent they verify against `frozen_results/SHA256SUMS`
instead. Running them rewrites the figure PDF/SVG/PNG in place and prints a validation
summary. `figures/verify_concept_figures.py` additionally needs the manuscript sources and
skips itself in a public checkout.

## Re-run the negative control

`control_analysis/` ships the negative-control study behind the revision: four scripts, the
60 per-cell records (P0/P1 × splits 1024/2024 × 5 folds × 3 training seeds) and both
aggregates. The strict aggregate is a gate; it fails on missing or extra cells, duplicate
keys, a query set that differs from the split registry, non-finite predictions, metadata
disagreement, a feature-matrix hash that differs between regimes, or identical training
node sets.

```bash
python3 control_analysis/scripts/nc_aggregate_v2.py \
    --cells control_analysis/cells \
    --split-registry splits/mixed_site_dx_5fold_v2.csv \
    --out control_analysis/invariance_deterministic_v2.json --expect-dropout 0.0
```

Regenerating the cells needs the ABIDE data root and a GPU; see
`control_analysis/ENVIRONMENT.md` and `control_analysis/scripts/nc_run_matrix.py`.

## Layout

| path | content |
|---|---|
| `audit/` | the controlled-evaluation library: regime protocols (P0/P1), graph construction, preprocessing scope, training and checkpoint-selection rules |
| `scripts/` | named entry points: split generation, controlled runners, aggregation, bootstrap inference, table/figure generation |
| `control_analysis/` | the negative-control study added in `v1.1.0`: scripts, 60 per-cell records, strict and diagnostic aggregates, environment note |
| `checklist/` | Reporting Checklist v2 (source Markdown and generated LaTeX) shipped with the revision |
| `configs/` | the historical campaign configuration (`configs/study/locked_campaign_v1.yaml`). It describes an earlier campaign (R1-C vs R2-Q, split seeds 1024/2024/2025), **not** the P0/P1 contrast reported in the manuscript; see `docs/CONFIG_MAPPING.md` |
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

Paper preprint: <https://doi.org/10.64898/2026.10.02.756253> (bioRxiv; submitted 2 October 2026,
first posted 8 October 2026, CC-BY 4.0).

Software archive: `v1.1.0` carries the negative-control study, Checklist v2 and the regenerated
figures; its version DOI is minted at publication (see `CHANGELOG.md` and `CITATION.cff`).
`v1.0.1` is archived at DOI `10.5281/zenodo.23554740` and the earlier `v1.0.0` at
`10.5281/zenodo.23104123`; the concept DOI `10.5281/zenodo.23104122` resolves to the latest
version. Cite both the software record and the paper.

