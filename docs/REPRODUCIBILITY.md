# Reproducibility

This repository releases the evaluation code, the frozen results and the deterministic
reproduction path for the primary campaign of the paper. Three levels, cheapest first.

## 1. Recompute every reported table and figure from the frozen record (no training)

```bash
python scripts/reproduce_primary_results.py --from-frozen
```

Reads only `frozen_results/` (the per-subject out-of-fold registry, the per-cell result
JSONs, `S1_FREEZE.yaml`) and re-derives:

- the cross-split interaction table: per-split ΔΔAUC point estimates with paired
  subject-bootstrap and site-cluster-bootstrap intervals (splits are replication units and
  are never pooled);
- the condition-level and single-seed supplement tables (Table S1/S2);
- the Figure 2 source data.

Every recomputed value is compared against `frozen_results/SHA256SUMS` / `S1_FREEZE.yaml`;
the script exits non-zero on any mismatch. No network access, no training.

## 2. Re-run the controlled evaluation on the frozen cohort

After obtaining ABIDE-I derivatives yourself (`docs/DATA_PREPARATION.md`) and building the
connectivity matrices, the controlled runners reproduce the per-cell results:

```bash
python scripts/generate_mixed_site_splits.py --config configs/study/locked_campaign_v1.yaml
python scripts/run_evgcn_matrix.py  --regimes p0,p1 --splits 666,1024,2024
python scripts/run_parisot_matrix_v2.py --regimes p0,p1 --splits 666,1024,2024
python scripts/aggregate_evgcn.py && python scripts/aggregate_parisot_regimes.py
python scripts/analysis_v2.py
```

3 split seeds × 5 outer folds × 3 training seeds per implementation/regime cell; ensemble
and per-seed interactions are reported separately (the ensemble is not the arithmetic mean
of seed-specific values).

## 3. Verification independent of training

- `scripts/validate_data.py` — cohort/derivative consistency (871 subjects / 20 sites).
- `scripts/verify_ev_parity.py`, `scripts/verify_parisot_parity.py` — each controlled
  implementation against its upstream counterpart on fixed inputs.
- `tests/` — protocol firewalls (checkpoint-selection scope, label authorization, adapter
  behaviour), runnable with `pytest -q`.

## Environment

`pyproject.toml` + `uv.lock` pin the full environment (`uv sync`). Upstream model code is
**not vendored**: fetch each repository at the exact commit recorded in
`THIRD_PARTY_NOTICES.md` / `manifests/THIRD_PARTY_LOCK.tsv`.

## Provenance discipline

Every number in the paper is generated from `frozen_results/S1_FREEZE.yaml`, whose entries
carry the exact text form and the source line of the stored evidence; no primary number is
typed by hand. The per-subject registry carries subject/site/outer-fold/seed identifiers so
that aggregate claims can be recomputed independently.

`frozen_results/` is byte-identical to the internal frozen record except that
site-specific absolute path prefixes and one host identifier are mechanically masked
(`<site-root>`, `<host>`); every substitution is itemised in `EXPORT_MANIFEST.json`
(`redactions`), and no value-bearing line is touched.
