# Split registry (frozen membership tables)

Reproduced unmodified from the campaign that produced them; nothing here regenerates a split.

| File | Generation seeds | Data rows | SHA-256 |
|---|---|---|---|
| `mixed_site_dx_5fold_seed666.csv` | 666 | 4,355 | `fa689961a888b79b60141892149d61193828f3867652b9f88eb78feb8ee464b3` |
| `mixed_site_dx_5fold_v2.csv` | 1024, 2024 (reserve 2025 unused) | 13,065 | `d7d2a28cbc2fc97a90c7801dd5b8a2fcd084a1f694261b7a9a359583389af22d` |

Companion summaries: `*.summary.json` (fold diagnostics: fit/validation/query sizes, label and
site counts per fold).

## Fields

`subject_id, site_id, label, split_seed, outer_fold, role`

`role` ∈ {`fit`, `validation`, `query`}; within one (`split_seed`, `outer_fold`) the three
  roles are disjoint, and each subject is `query` in exactly one of the five folds.
- `outer_fold` runs from **0 to 4** (folds are labelled 1–5 in the text and figures).
- `label`: **1 = ASD, 0 = TD**.
- `split_seed` labels a partition. Training seeds 11/22/33 are drawn inside a partition and are
  not recorded here.

## Generation entry point

`scripts/generate_mixed_site_splits.py` with `configs/study/locked_campaign_v1.yaml`
(split seeds [1024, 2024, 2025], training seeds [11, 22, 33]); reserve 2025 was not run.
`scripts/generate_splits.py` is the earlier scikit-learn variant, kept for historical
reference. The archive does not document which script produced the seed-666 table, so it is
identified by its own hash and is not attributed to either entry point.
